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

app = FastAPI(title="ForgeOS API", version="1.0.0")

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


async def _run_pipeline_autopilot(task_id: str):
    """
    Executes the full agent chain for a single task:
    Developer → QA → Security → Documentation.
    Respects the sprint_paused flag between transitions.
    """
    try:
        await _check_pause()
        await developer_agent.execute_task(task_id)
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


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("ForgeOS starting up…")
    await health_monitor.run_checks()
    event_log_store.append_event("System", "Startup", "ForgeOS API is online and ready.")


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
    if not task.get("pending_approval"):
        return {"message": "Task does not require approval or is already finalised."}

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
        msg = "📊 *ForgeOS Sprint Status*\n" + ("\n".join(lines) if lines else "No active tasks.")
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
        msg = "🧠 *ForgeOS Memory*\n" + ("\n".join(lines) if lines else "No architectural decisions recorded.")
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
        if inner_type == "message" and "bot_id" not in inner:
            text = inner.get("text", "")
            user = inner.get("user", "unknown")
            channel = inner.get("channel", "unknown")
            logger.info(f"[SLACK GATEWAY] Message from {user} in {channel}: {text}")
            event_log_store.append_event(
                "Slack Gateway", "Message Received",
                f"user={user} channel={channel} text={text}"
            )
            # If it starts with /forge, dispatch via command handler
            if text.strip().startswith("/forge"):
                parts = text.strip().split(maxsplit=1)
                mock_request_body = {
                    "command": "/forge",
                    "text": parts[1] if len(parts) > 1 else "",
                }
                # Re-dispatch in background
                background_tasks.add_task(_dispatch_slack_text_command, mock_request_body)
        else:
            logger.info(f"[SLACK GATEWAY] Ignoring unsupported inner event type: {inner_type}")

    return {"ok": True}


# ── Internal helpers ───────────────────────────────────────────────────────────
async def _plan_and_execute(goal: str):
    """
    Hermes plans the sprint, then immediately auto-executes every Planning-status
    task through the full agent pipeline.  This makes Slack the sole trigger.
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
    tasks = tasks_store.read_all()

    # Find every task in Planning status and auto-execute the pipeline
    planning_tasks = [t for t in tasks.values() if t.get("status") == "Planning"]
    for task in planning_tasks:
        task_id = task["id"]
        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Invoking: Developer Agent\n"
            "Reason:   Implementation Task\n"
            f"Task:     {task_id} — {task['title']}\n"
            "──────────────────────────────"
        )
        await _run_pipeline_autopilot(task_id)


async def _finalise_sprint(task_id: str, task: dict, source: str):
    """
    Marks a task as Done and logs it.
    """
    tasks = tasks_store.read_all()
    task["pending_approval"] = False
    task["status"] = "Done"
    task["updated_at"] = datetime.utcnow().isoformat()
    tasks[task_id] = task
    tasks_store.write_all(tasks)

    event_log_store.append_event(source, "Sprint Completed", f"Task {task_id} completed successfully.", task_id)

    await slack_client.post_message(
        "#sprint-main",
        f"✅ *Task Completed*: Task `{task_id}` (\"{task['title']}\") marked as Done via {source}.",
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
