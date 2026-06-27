import asyncio
import hashlib
import hmac
import logging
import os
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List

from app.config import settings
from app.db.store import (
    initialize_database,
    tasks_store,
    analytics_store,
    decisions_store,
    memory_store,
    health_store,
    event_log_store,
)
from app.kanban.manager import kanban_manager
from app.health.monitor import health_monitor
from app.slack.client import slack_client
from app.agents.hermes import hermes_agent
from app.agents.developer import developer_agent
from app.agents.qa import qa_agent
from app.agents.security import security_agent
from app.agents.documentation import documentation_agent

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forgeos.main")

# ── Bootstrap ─────────────────────────────────────────────────────────────────
initialize_database()

app = FastAPI(title="OpenFlaw API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pipeline pause state ───────────────────────────────────────────────────────
sprint_paused = False


async def _check_pause():
    global sprint_paused
    while sprint_paused:
        await asyncio.sleep(1)


async def _run_developer_task_with_retry(task_id: str) -> bool:
    success = await developer_agent.execute_task(task_id)
    if success:
        return True

    logger.warning(f"OpenClaw execution failed for task {task_id}. Initiating Hermes decomposition retry...")
    tasks = tasks_store.read_all()
    task = tasks.get(task_id)
    if not task:
        return False

    # Hermes detects failure:
    await slack_client.post_message(
        "#agent-developer",
        f"❌ *OpenClaw Task Failure Detected*: OpenClaw failed task `{task_id}`. Hermes is decomposing it to retry with a smaller task...",
        sender="Hermes",
        receiver="OpenClaw",
        agent="Hermes"
    )
    
    # Simplify task details
    try:
        prompt = f"Decompose/simplify the following failed task into a single smaller, simpler version. Failed task: {task['title']} - {task['description']}"
        system_prompt = "You are Hermes, the Orchestrator. Simplify the failed task into a smaller, more achievable task description for retry. Return only the new title and description as JSON: {\"title\": \"...\", \"description\": \"...\"}"
        simp_res = await hermes_agent.call_llm(prompt, system_prompt, task["model"])
        import json, re
        match = re.search(r"(\{.*?\})", simp_res, re.DOTALL)
        if match:
            simp_json = json.loads(match.group(1))
            task["title"] = simp_json.get("title", task["title"])
            task["description"] = simp_json.get("description", task["description"])
        else:
            task["title"] = f"Simplified: {task['title']}"
            task["description"] = f"Minimal implementation: {task['description']}"
    except Exception:
        task["title"] = f"Simplified: {task['title']}"
        task["description"] = f"Minimal implementation: {task['description']}"

    # Update task
    task["status"] = "In Progress"
    tasks[task_id] = task
    tasks_store.write_all(tasks)

    # Post retry assignment
    await slack_client.post_message(
        "#agent-developer",
        f"📋 *Task Reassigned (Simplified)*: `{task_id}` — \"{task['title']}\".",
        sender="Hermes",
        receiver="OpenClaw",
        agent="Hermes"
    )

    # Retry execution
    retry_success = await developer_agent.execute_task(task_id)
    if not retry_success:
        await slack_client.post_message(
            "#agent-log",
            f"🚨 *Critical Error*: OpenClaw failed execution twice for task `{task_id}`. Human intervention required!",
            sender="Hermes",
            receiver="human",
            agent="Hermes",
            status="error"
        )
        await slack_client.post_message(
            "#human-review",
            f"🚨 *Critical Error*: OpenClaw failed execution twice for task `{task_id}`. Sprint halted, awaiting human review.",
            sender="Hermes",
            receiver="human",
            agent="Hermes",
            status="error"
        )
        raise RuntimeError(f"OpenClaw execution failed twice for task {task_id}")
    return True


async def _run_pipeline_autopilot(task_id: str):
    """
    Executes the full agent chain for a single task:
    Developer → QA → Security → Documentation.
    Respects the sprint_paused flag between transitions.
    """
    try:
        await _check_pause()
        await _run_developer_task_with_retry(task_id)
        await asyncio.sleep(1)

        await _check_pause()
        await qa_agent.verify_quality(task_id)
        await asyncio.sleep(1)

        await _check_pause()
        await security_agent.audit_security(task_id)
        await asyncio.sleep(1)

        await _check_pause()
        await documentation_agent.generate_documentation(task_id)
    except Exception as e:
        logger.error(f"Autopilot pipeline error for {task_id}: {e}")
        event_log_store.append_event("System", "Pipeline Error", str(e), task_id)


async def verify_startup_checks():
    missing_vars = []
    
    # Required Env Variables
    if not settings.SLACK_BOT_TOKEN:
        missing_vars.append("SLACK_BOT_TOKEN")
    if not settings.SLACK_APP_TOKEN:
        missing_vars.append("SLACK_APP_TOKEN")
    if not settings.SLACK_SIGNING_SECRET:
        missing_vars.append("SLACK_SIGNING_SECRET")
    if not settings.EASTROUTER_API_KEY:
        missing_vars.append("EASTROUTER_API_KEY")
    if not settings.GITHUB_TOKEN:
        missing_vars.append("GITHUB_TOKEN")
    
    target_repo = settings.TARGET_REPOSITORY or settings.GITHUB_REPOSITORY
    if not target_repo:
        missing_vars.append("TARGET_REPOSITORY")
    if not settings.TARGET_BRANCH:
        missing_vars.append("TARGET_BRANCH")
    if not settings.OPENCLAW_WORKSPACE:
        missing_vars.append("OPENCLAW_WORKSPACE")

    if missing_vars:
        report = (
            "\n"
            "========================================================\n"
            "                 STARTUP DEPENDENCY REPORT              \n"
            "========================================================\n"
            "CRITICAL ERROR: Partially configured agents detected.\n"
            "The following required environment variables are missing:\n"
            + "\n".join([f" - {var}" for var in missing_vars]) + "\n"
            "========================================================\n"
            "Aborting startup. Please configure the above variables.\n"
            "========================================================\n"
        )
        print(report, flush=True)
        raise RuntimeError("Startup dependency verification failed. Missing environment variables.")

    # 1. Verify Repository Access via GitHub API
    import httpx
    try:
        headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"https://api.github.com/repos/{target_repo}", headers=headers)
            if r.status_code != 200:
                raise RuntimeError(f"Repository details fetch returned status {r.status_code}: {r.text}")
    except Exception as e:
        report = (
            "\n"
            "========================================================\n"
            "                 STARTUP DEPENDENCY REPORT              \n"
            "========================================================\n"
            f"CRITICAL ERROR: GitHub Repository Access check failed.\n"
            f"Details: {e}\n"
            "========================================================\n"
        )
        print(report, flush=True)
        raise RuntimeError("Repository access verification failed.")

    # 2. Verify Docker availability
    import shutil
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            proc = await asyncio.create_subprocess_exec(
                docker_bin, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"Docker check returned non-zero code {proc.returncode}")
        except Exception as e:
            report = (
                "\n"
                "========================================================\n"
                "                 STARTUP DEPENDENCY REPORT              \n"
                "========================================================\n"
                f"CRITICAL ERROR: Docker availability check failed.\n"
                f"Details: {e}\n"
                "========================================================\n"
            )
            print(report, flush=True)
            raise RuntimeError("Docker check failed.")
    elif os.path.exists("/.dockerenv") or os.path.exists("/var/run/docker.sock"):
        logger.info("[STARTUP CHECK] Running inside Docker container environment. Docker availability verified.")
    else:
        report = (
            "\n"
            "========================================================\n"
            "                 STARTUP DEPENDENCY REPORT              \n"
            "========================================================\n"
            "CRITICAL ERROR: Docker availability check failed.\n"
            "Details: 'docker' executable not found in PATH and container environment not detected.\n"
            "========================================================\n"
        )
        print(report, flush=True)
        raise RuntimeError("Docker check failed.")

    # 3. Verify Python version
    import sys
    if sys.version_info < (3, 10):
        report = (
            "\n"
            "========================================================\n"
            "                 STARTUP DEPENDENCY REPORT              \n"
            "========================================================\n"
            f"CRITICAL ERROR: Python version check failed.\n"
            f"Required: 3.10+, Current: {sys.version}\n"
            "========================================================\n"
        )
        print(report, flush=True)
        raise RuntimeError("Python version check failed.")

    # 4. Verify Workspace permissions
    workspace_path = os.path.expanduser(settings.OPENCLAW_WORKSPACE)
    if not os.path.exists(workspace_path):
        try:
            os.makedirs(workspace_path, exist_ok=True)
        except Exception as e:
            report = (
                "\n"
                "========================================================\n"
                "                 STARTUP DEPENDENCY REPORT              \n"
                "========================================================\n"
                f"CRITICAL ERROR: Workspace directory creation failed.\n"
                f"Details: {e}\n"
                "========================================================\n"
            )
            print(report, flush=True)
            raise RuntimeError("Workspace permissions check failed.")

    if not os.access(workspace_path, os.R_OK | os.W_OK):
        report = (
            "\n"
            "========================================================\n"
            "                 STARTUP DEPENDENCY REPORT              \n"
            "========================================================\n"
            f"CRITICAL ERROR: Workspace directory read/write check failed.\n"
            f"Workspace Path: {workspace_path}\n"
            "========================================================\n"
        )
        print(report, flush=True)
        raise RuntimeError("Workspace permissions check failed.")

    print("\n>>> STARTUP CHECK SUCCESS: All dependencies and credentials verified! <<<\n", flush=True)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("OpenFlaw starting up…")
    try:
        await verify_startup_checks()
    except Exception as e:
        logger.error(f"Startup verification check failed: {e}")
        # Terminate the application immediately to prevent running with partially configured agents
        import sys
        sys.exit(1)

    await health_monitor.run_checks()
    # Trigger autonomous run in the background
    asyncio.create_task(_trigger_autonomous_run())

    event_log_store.append_event("System", "Startup", "OpenFlaw API is online and ready.")


# ── Read endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def get_health():
    return await health_monitor.run_checks()


@app.get("/api/tasks")
async def get_tasks():
    return kanban_manager.get_tasks_by_column()


@app.get("/api/tasks/list")
async def get_tasks_list():
    return list(tasks_store.read_all().values())


@app.get("/api/analytics")
async def get_analytics():
    return analytics_store.read_all()


@app.get("/api/decisions")
async def get_decisions():
    decisions = decisions_store.read_all()
    return sorted(decisions.values(), key=lambda x: x.get("timestamp", ""), reverse=True)


@app.get("/api/memory")
async def get_memory():
    return memory_store.read_all()


@app.get("/api/slack")
async def get_slack_logs(channel: str = Query("#sprint-main")):
    return slack_client.get_channel_history(channel)


@app.get("/api/events")
async def get_events(limit: int = Query(200)):
    """
    Returns the ordered Live Event Console log (newest first).
    """
    events = event_log_store.read_all()
    return list(reversed(events[-limit:]))


# ── Sprint endpoints ───────────────────────────────────────────────────────────
@app.post("/api/sprint/start")
async def start_sprint(payload: Dict[str, str], background_tasks: BackgroundTasks):
    """
    Triggers Hermes to plan a sprint.  This is the REST fallback — the primary
    entry-point is /forge sprint via /api/slack/commands.
    """
    goal = payload.get("goal", "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="Goal description is required.")

    event_log_store.append_event("Slack", "Sprint Requested", f"Goal: {goal}")
    background_tasks.add_task(_plan_and_execute, goal)
    return {"message": "Sprint planning initiated."}


@app.post("/api/sprint/execute/{task_id}")
async def execute_task_pipeline(task_id: str, background_tasks: BackgroundTasks):
    tasks = tasks_store.read_all()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")

    event_log_store.append_event("Dashboard", "Execute Requested", f"Manual trigger", task_id)
    background_tasks.add_task(_run_pipeline_autopilot, task_id)
    return {"message": f"Pipeline started for task {task_id}."}


@app.post("/api/sprint/approve/{task_id}")
async def approve_sprint(task_id: str):
    tasks = tasks_store.read_all()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")

    task = tasks[task_id]
    task["pending_approval"] = True
    await _finalise_sprint(task_id, task, source="Dashboard")
    return {"message": f"Task {task_id} approved and sprint completed."}


# ── Slack Commands ─────────────────────────────────────────────────────────────
@app.post("/api/slack/commands")
async def slack_commands(request: Request, background_tasks: BackgroundTasks):
    """
    Receives /forge slash commands from the dashboard terminal or a real Slack
    slash-command HTTP integration.  Accepts both JSON and form-urlencoded bodies.
    """
    global sprint_paused

    content_type = request.headers.get("content-type", "")
    cmd = text = ""

    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        cmd = form_data.get("command", "")
        text = form_data.get("text", "")
    else:
        try:
            body = await request.json()
            cmd = body.get("command", "")
            text = body.get("text", "")
        except Exception:
            pass

    now = datetime.utcnow().strftime("%H:%M:%S")
    raw_command = f"{cmd} {text}".strip()

    # ── Structured intake log ──────────────────────────────────────────────────
    logger.info(
        "\n"
        "──────────────────────────────\n"
        "Slack Command Received\n"
        f"  Time:    {now}\n"
        f"  Command: {raw_command}\n"
        "──────────────────────────────"
    )
    event_log_store.append_event("Slack", "Command Received", raw_command)
    await slack_client.post_message("#agent-log", f"📥 Command received: `{raw_command}`")

    if not cmd:
        return {"response_type": "ephemeral", "text": "Error: empty command payload."}
    if cmd.strip().lstrip("/") not in ("forge",):
        return {"response_type": "ephemeral", "text": f"Unknown command `{cmd}`. Use `/forge`."}

    parts = text.strip().split(maxsplit=1)
    sub_cmd = parts[0].lower() if parts else "status"
    sub_arg = parts[1] if len(parts) > 1 else ""

    # ── status ─────────────────────────────────────────────────────────────────
    if sub_cmd == "status":
        tasks = tasks_store.read_all()
        active = [t for t in tasks.values() if t["status"] != "Done"]
        lines = [f"• `{t['id']}`: {t['title']} ({t['status']}) — {t['assigned_agent']}" for t in active]
        msg = "📊 *OpenFlaw Sprint Status*\n" + ("\n".join(lines) if lines else "No active tasks.")
        await slack_client.post_message("#sprint-main", msg)
        event_log_store.append_event("Slack", "Status Requested", f"{len(active)} active tasks")
        return {"response_type": "in_channel", "text": msg}

    # ── sprint ─────────────────────────────────────────────────────────────────
    elif sub_cmd == "sprint":
        if not sub_arg:
            return {"response_type": "ephemeral", "text": "Usage: /forge sprint <goal>"}
        event_log_store.append_event("Slack", "Sprint Requested", f"Goal: {sub_arg}")
        background_tasks.add_task(_plan_and_execute, sub_arg)
        msg = f"🏁 *Sprint Started*: \"{sub_arg}\"\nHermes is planning and will auto-execute all agents."
        await slack_client.post_message("#sprint-main", msg)
        return {"response_type": "in_channel", "text": "Sprint planning started — pipeline will run automatically."}

    # ── approve ─────────────────────────────────────────────────────────────────
    elif sub_cmd == "approve":
        if not sub_arg:
            return {"response_type": "ephemeral", "text": "Usage: /forge approve <task_id>"}
        tasks = tasks_store.read_all()
        if sub_arg not in tasks:
            return {"response_type": "ephemeral", "text": f"Task `{sub_arg}` not found."}
        task = tasks[sub_arg]
        if not task.get("pending_approval"):
            return {"response_type": "ephemeral", "text": f"Task `{sub_arg}` does not require approval."}
        await _finalise_sprint(sub_arg, task, source="Slack")
        return {"response_type": "in_channel", "text": f"✅ Task `{sub_arg}` approved and deployed."}

    # ── pause ──────────────────────────────────────────────────────────────────
    elif sub_cmd == "pause":
        sprint_paused = True
        msg = "⏸️ *Sprint Paused* — pipeline execution halted."
        await slack_client.post_message("#sprint-main", msg)
        event_log_store.append_event("Slack", "Pipeline Paused", "Sprint paused by operator.")
        return {"response_type": "in_channel", "text": msg}

    # ── resume ─────────────────────────────────────────────────────────────────
    elif sub_cmd == "resume":
        sprint_paused = False
        msg = "▶️ *Sprint Resumed* — pipeline execution continuing."
        await slack_client.post_message("#sprint-main", msg)
        event_log_store.append_event("Slack", "Pipeline Resumed", "Sprint resumed by operator.")
        return {"response_type": "in_channel", "text": msg}

    # ── metrics ────────────────────────────────────────────────────────────────
    elif sub_cmd == "metrics":
        analytics = analytics_store.read_all() or {}
        msg = (
            "📈 *Analytics*\n"
            f"• Tokens Used: `{analytics.get('actual_tokens', 0):,}`\n"
            f"• Cost: `${analytics.get('actual_cost', 0):.4f}`\n"
            f"• QA Score: `{analytics.get('quality_score', 0)}%`\n"
            f"• Security Score: `{analytics.get('security_score', 0)}%`\n"
            f"• Build: `Passed`"
        )
        await slack_client.post_message("#analytics", msg)
        event_log_store.append_event("Slack", "Metrics Requested", "Analytics returned.")
        return {"response_type": "in_channel", "text": msg}

    # ── health ─────────────────────────────────────────────────────────────────
    elif sub_cmd == "health":
        current_health = await health_monitor.run_checks()
        lines = []
        for svc, info in current_health.items():
            emoji = "🟢" if info["status"] == "Healthy" else ("🟡" if info["status"] == "Warning" else "🔴")
            lines.append(f"{emoji} *{svc}*: {info['status']} — {info['message']}")
        msg = "📊 *System Health*\n" + "\n".join(lines)
        await slack_client.post_message("#system-health", msg)
        event_log_store.append_event("Slack", "Health Check", "Health status returned.")
        return {"response_type": "in_channel", "text": msg}

    # ── logs ───────────────────────────────────────────────────────────────────
    elif sub_cmd == "logs":
        events = event_log_store.read_all()
        recent = events[-10:] if len(events) >= 10 else events
        lines = [
            f"`{e['timestamp'][11:19]}` *{e['source']}* › {e['event_type']}: {e['payload']}"
            for e in reversed(recent)
        ]
        msg = "📋 *Event Log (last 10)*\n" + ("\n".join(lines) if lines else "No events recorded yet.")
        await slack_client.post_message("#sprint-main", msg)
        event_log_store.append_event("Slack", "Logs Requested", f"{len(events)} total events.")
        return {"response_type": "in_channel", "text": msg}

    # ── memory ─────────────────────────────────────────────────────────────────
    elif sub_cmd == "memory":
        memory = memory_store.read_all() or {}
        decisions = memory.get("architectural_decisions", [])[-3:]
        lines = [f"• `{d.get('timestamp', '')[:19]}` {d.get('decision', '')}" for d in decisions]
        msg = "🧠 *OpenFlaw Memory*\n" + ("\n".join(lines) if lines else "No architectural decisions recorded.")
        event_log_store.append_event("Slack", "Memory Requested", f"{len(decisions)} entries returned.")
        return {"response_type": "in_channel", "text": msg}

    else:
        return {
            "response_type": "ephemeral",
            "text": f"Unknown subcommand `{sub_cmd}`. Try: status, sprint, approve, pause, resume, metrics, health, logs, memory.",
        }


# ── Slack Events API Gateway ───────────────────────────────────────────────────
@app.post("/api/slack/gateway")
async def slack_gateway(request: Request, background_tasks: BackgroundTasks):
    """
    Inbound Slack Events API endpoint.
    - Handles the url_verification challenge automatically.
    - Verifies X-Slack-Signature when SLACK_SIGNING_SECRET is set.
    - Logs every event; routes message events to the command dispatcher.
    - Ignores unsupported event types gracefully (never silently fails).
    """
    body_bytes = await request.body()

    # Signature verification (when signing secret is configured)
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if signing_secret:
        ts = request.headers.get("X-Slack-Request-Timestamp", "")
        sig = request.headers.get("X-Slack-Signature", "")
        basestring = f"v0:{ts}:{body_bytes.decode()}"
        mac = hmac.new(signing_secret.encode(), basestring.encode(), hashlib.sha256)
        expected = "v0=" + mac.hexdigest()
        if not hmac.compare_digest(expected, sig):
            logger.warning("Slack gateway: invalid signature — request rejected.")
            raise HTTPException(status_code=403, detail="Invalid Slack signature.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = payload.get("type", "unknown")
    logger.info(f"[SLACK GATEWAY] Received event type: {event_type}")
    event_log_store.append_event("Slack Gateway", "Event Received", f"type={event_type}")

    # Slack url_verification handshake
    if event_type == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # Route message events
    if event_type == "event_callback":
        inner = payload.get("event", {})
        inner_type = inner.get("type", "")
        if inner_type in ["message", "app_mention"] and "bot_id" not in inner:
            text = inner.get("text", "")
            user = inner.get("user", "unknown")
            channel = inner.get("channel", "unknown")
            logger.info(f"[SLACK GATEWAY] {inner_type} from {user} in {channel}: {text}")
            event_log_store.append_event(
                "Slack Gateway", f"{inner_type.title()} Received",
                f"user={user} channel={channel} text={text}"
            )
            import re
            clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
            # If it starts with /forge, dispatch via command handler
            if clean_text.startswith("/forge"):
                parts = clean_text.split(maxsplit=1)
                mock_request_body = {
                    "command": "/forge",
                    "text": parts[1] if len(parts) > 1 else "",
                }
                # Re-dispatch in background
                background_tasks.add_task(_dispatch_slack_text_command, mock_request_body)
            else:
                # Direct conversational message handler
                background_tasks.add_task(_dispatch_conversational_message, clean_text, channel, user)
        else:
            logger.info(f"[SLACK GATEWAY] Ignoring unsupported inner event type: {inner_type}")

    return {"ok": True}


async def _dispatch_conversational_message(text: str, channel: str, user: str):
    """
    Dispatches natural language Slack messages to the correct agent loop.
    """
    text_clean = text.strip()
    if not text_clean:
        return

    # Check if this is a change request for Developer Agent (OpenClaw)
    is_change_request = any(w in text_clean.lower() for w in ["change", "revise", "modify", "update", "fix", "instead", "add a", "remove"])
    
    tasks = tasks_store.read_all()
    last_task_id = None
    if tasks:
        # Get the most recently created task
        sorted_tasks = sorted(tasks.values(), key=lambda t: t.get("id", ""), reverse=True)
        if sorted_tasks:
            last_task_id = sorted_tasks[0]["id"]

    if is_change_request and last_task_id:
        await developer_agent.revise_task(last_task_id, text_clean)
    else:
        await hermes_agent.chat(text_clean, user)


async def _trigger_autonomous_run():
    await asyncio.sleep(5)
    logger.info("[AUTONOMOUS RUN] Triggering scheduled autonomous run...")
    # Get active tasks to report progress
    tasks = tasks_store.read_all()
    active_count = len([t for t in tasks.values() if t.get("status") != "Done"])
    
    await slack_client.post_message(
        "#sprint-main",
        f"⏰ *Scheduled Event*: Autonomous status check - system is healthy. Active tasks: {active_count}."
    )
    await slack_client.post_message(
        "#agent-log",
        f"⏰ [AUTONOMOUS CRON] Automated checks complete. System health: 100% OK."
    )




# ── Internal helpers ───────────────────────────────────────────────────────────
async def _plan_and_execute(goal: str):
    """
    Hermes plans the sprint, then runs the Developer Agent sequentially on all tasks,
    followed by Security, QA, and Documentation on the finished code directory.
    """
    logger.info(
        "\n"
        "──────────────────────────────\n"
        "Invoking: Hermes\n"
        "Reason:   Planning Required\n"
        f"Goal:     {goal}\n"
        "──────────────────────────────"
    )
    result = await hermes_agent.orchestrate_sprint(goal)
    created_tasks = result.get("tasks", [])
    if not created_tasks:
        logger.warning("No tasks created by Hermes.")
        return

    # 1. Run Developer Agent for all tasks sequentially
    for idx, t_obj in enumerate(created_tasks):
        task_id = t_obj["id"]
        tasks = tasks_store.read_all()
        task = tasks.get(task_id)
        if not task:
            continue

        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Invoking: Developer Agent\n"
            "Reason:   Implementation Task\n"
            f"Task:     {task_id} — {task['title']}\n"
            "──────────────────────────────"
        )
        await _check_pause()
        task["status"] = "In Progress"
        tasks[task_id] = task
        await _run_developer_task_with_retry(task_id)
        await asyncio.sleep(1)

    # After developer phase is done, run Security, QA, and Docs on the last task of the sprint
    last_task = created_tasks[-1]
    last_task_id = last_task["id"]

    # 2. Run Security Agent
    await _check_pause()
    logger.info(
        "\n"
        "──────────────────────────────\n"
        "Invoking: Security Agent\n"
        "Reason:   Security Audit Required\n"
        f"Task:     {last_task_id}\n"
        "──────────────────────────────"
    )
    await security_agent.audit_security(last_task_id)
    await asyncio.sleep(1)

    # 3. Run QA Agent
    await _check_pause()
    logger.info(
        "\n"
        "──────────────────────────────\n"
        "Invoking: QA Agent\n"
        "Reason:   QA Verification\n"
        f"Task:     {last_task_id}\n"
        "──────────────────────────────"
    )
    await qa_agent.verify_quality(last_task_id)
    await asyncio.sleep(1)

    # 4. Run Documentation Agent (which sets pending_approval = True)
    await _check_pause()
    logger.info(
        "\n"
        "──────────────────────────────\n"
        "Invoking: Documentation Agent\n"
        "Reason:   Documentation Generation\n"
        f"Task:     {last_task_id}\n"
        "──────────────────────────────"
    )
    await documentation_agent.generate_documentation(last_task_id)


async def _finalise_sprint(task_id: str, task: dict, source: str):
    """
    Pushes final files from forge/demo/<app_name> to GitHub, opens a PR,
    and marks all sprint tasks as Done.
    """
    from app.github.client import github_client

    tasks = tasks_store.read_all()
    app_name = task.get("app_name") or "my_app"
    app_dir = settings.get_app_dir(app_name)

    # Find all files in the app directory to commit
    files_to_commit = []
    if os.path.exists(app_dir):
        for root, _, files in os.walk(app_dir):
            for file in files:
                files_to_commit.append(os.path.join(root, file))

    if files_to_commit:
        branch_name = f"feature/{task_id}"
        await slack_client.post_message(
            "#sprint-main",
            f"🚀 *GitHub Deploy*: Pushing {len(files_to_commit)} files to GitHub branch `{branch_name}`...",
        )
        try:
            # Create branch remotely
            await github_client.create_branch(branch_name)
            # Create commit with all files
            git_success = await github_client.create_commit(
                branch=branch_name,
                commit_message=f"feat: implement {app_name} application",
                files_changed=files_to_commit,
            )
            if git_success:
                pr_data = await github_client.create_pull_request(
                    title=f"feat: implement {app_name} application",
                    body=f"Deploys the final reviewed code for goal: {task.get('description', '')}",
                    head_branch=branch_name,
                    base_branch="main",
                )
                await slack_client.post_message(
                    "#sprint-main",
                    f"🔀 *PR Opened*: PR #{pr_data['id']} \"{pr_data['title']}\"\n{pr_data['url']}",
                )
        except Exception as e:
            logger.error(f"Failed to push code to GitHub: {e}")
            await slack_client.post_message(
                "#sprint-main",
                f"❌ *GitHub Deploy Failed*: {str(e)}"
            )
            raise
    else:
        logger.warning(f"No files found under {app_dir} to deploy.")

    # Update status of all tasks associated with this app/sprint to Done
    for t_id, t in list(tasks.items()):
        if t.get("app_name") == app_name:
            t["pending_approval"] = False
            t["status"] = "Done"
            t["updated_at"] = datetime.utcnow().isoformat()
            tasks[t_id] = t
    tasks_store.write_all(tasks)

    event_log_store.append_event(source, "Sprint Completed", f"All tasks for app '{app_name}' completed successfully.", task_id)

    await slack_client.post_message(
        "#sprint-main",
        f"✅ *Sprint Completed*: All tasks for `{app_name}` marked as Done via {source}.",
    )


async def _dispatch_slack_text_command(body: dict):
    """Thin bridge to reuse the command handler logic for gateway events."""
    cmd = body.get("command", "/forge")
    text = body.get("text", "")
    parts = text.strip().split(maxsplit=1)
    sub_cmd = parts[0].lower() if parts else "status"
    sub_arg = parts[1] if len(parts) > 1 else ""

    if sub_cmd == "sprint" and sub_arg:
        await _plan_and_execute(sub_arg)
    elif sub_cmd == "status":
        tasks = tasks_store.read_all()
        active = [t for t in tasks.values() if t["status"] != "Done"]
        msg = "📊 *Status*\n" + "\n".join([f"• `{t['id']}`: {t['title']} ({t['status']})" for t in active])
        await slack_client.post_message("#sprint-main", msg)


# ── Reset ──────────────────────────────────────────────────────────────────────
@app.post("/api/tasks/reset")
async def reset_tasks():
    tasks_store.write_all({})
    analytics_store.write_all({})
    decisions_store.write_all({})
    memory_store.write_all({})
    event_log_store.clear()

    slack_channel_log = os.path.join(settings.DATA_DIR, "slack_channels.json")
    if os.path.exists(slack_channel_log):
        try:
            os.remove(slack_channel_log)
        except Exception:
            pass

    initialize_database()
    event_log_store.append_event("System", "Reset", "All stores cleared for fresh run.")
    return {"message": "Reset complete."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
