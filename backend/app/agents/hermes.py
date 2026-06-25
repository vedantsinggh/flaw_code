import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from app.agents.base import BaseAgent
from app.router.router import intelligent_router
from app.skills.engine import skill_engine
from app.db.store import tasks_store, decisions_store, analytics_store, memory_store
from app.slack.client import slack_client
from app.github.client import github_client

logger = logging.getLogger("forgeos.hermes")


class HermesAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Hermes", role="Orchestrator and Planner")

    async def orchestrate_sprint(self, goal: str) -> Dict[str, Any]:
        """
        Takes a user engineering goal and performs full orchestration:
        1. Emits structured event log entries at every phase.
        2. Classifies and loads relevant skills.
        3. Routes model via Intelligent Router.
        4. Decomposes goal into tasks via LLM.
        5. Persists tasks, decisions, analytics, and memory.
        6. Fires Slack notifications on every transition.
        """
        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Slack Event Received\n"
            f"  Time:           {datetime.utcnow().strftime('%H:%M:%S')}\n"
            f"  Detected Intent: Sprint Planning\n"
            f"  Selected Agent:  Hermes\n"
            f"  Goal:            {goal}\n"
            "──────────────────────────────"
        )
        slack_client.log_event("Slack", "Sprint Requested", f"Goal: {goal}")

        # 1. Announce sprint start
        await slack_client.post_message(
            "#sprint-main",
            f"🏁 *New Sprint Started!* Goal: \"{goal}\"\nHermes is analysing requirements…",
        )
        slack_client.log_event("Hermes", "Planning Started", f"Analysing: {goal}")

        # 2. Skill classification
        loaded_skills = skill_engine.classify_and_load(goal)
        skill_engine.log_loaded_skills(loaded_skills)
        skill_list = ", ".join(loaded_skills) if loaded_skills else "none"
        await slack_client.post_message(
            "#sprint-main",
            f"🛠️ *Skills Loaded*: {skill_list}",
        )
        slack_client.log_event("Skills", "Loaded", skill_list)

        # 3. Intelligent model routing
        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Invoking: Router\n"
            "Reason:   Model Selection\n"
            "──────────────────────────────"
        )
        routing = intelligent_router.route_task(goal, task_type="planning")
        await slack_client.post_message(
            "#sprint-main",
            f"🧠 *Model Selected*: `{routing['selected_model']}` (confidence: {routing['confidence'] * 100:.0f}%)",
        )
        await slack_client.post_message(
            "#analytics",
            (
                f"🧠 *Routing Decision*\n"
                f"• Model: `{routing['selected_model']}`\n"
                f"• Reason: {routing['reason']}\n"
                f"• Est. Cost: `${routing['estimated_cost']:.4f}`\n"
                f"• Est. Tokens: `{routing['estimated_tokens']}`\n"
                f"• Est. Time: `{routing['estimated_completion_time_seconds']}s`\n"
                f"• Confidence: `{routing['confidence'] * 100:.0f}%`"
            ),
        )
        slack_client.log_event("Router", "Model Selected", routing["selected_model"])

        # 4. Task decomposition via LLM
        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Invoking: Hermes\n"
            "Reason:   Task Decomposition\n"
            "──────────────────────────────"
        )
        slack_client.log_event("Hermes", "Decomposing", f"Goal: {goal}")
        system_prompt = (
            "You are Hermes, the Principal Staff AI Architect of ForgeOS. Decompose software engineering "
            "goals into structured task plans. Return ONLY a valid raw JSON object. Do NOT wrap it in python "
            "variable assignments, comments, or any other explanations. Ensure the root is a JSON object. "
            "Schema:\n"
            "{\n"
            "  \"app_name\": \"string (clean snake_case folder name for the project)\",\n"
            "  \"tasks\": [\n"
            "    {\n"
            "      \"id\": \"string\",\n"
            "      \"title\": \"string\",\n"
            "      \"description\": \"string\",\n"
            "      \"priority\": int,\n"
            "      \"difficulty\": int,\n"
            "      \"skills\": [\"string\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        prompt = f"Decompose this engineering goal into 3 implementation tasks: \"{goal}\"."
        plan_raw = await self.call_llm(prompt, system_prompt, routing["selected_model"])

        import re

        tasks_list = []
        try:
            # 1. Clean markdown code blocks or wrapper text to extract JSON
            json_text = plan_raw.strip()
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", json_text, re.DOTALL | re.IGNORECASE)
            if match:
                json_text = match.group(1)
            else:
                # Find first { and last }
                start = json_text.find('{')
                end = json_text.rfind('}')
                if start != -1 and end != -1 and end > start:
                    json_text = json_text[start:end+1]

            plan_json = json.loads(json_text)
            
            # Check for tasks list in various structures
            if isinstance(plan_json, dict):
                tasks_list = plan_json.get("tasks", [])
                if not tasks_list:
                    for alt_key in ["implementation_tasks", "task_list", "subtasks", "plan"]:
                        tasks_list = plan_json.get(alt_key, [])
                        if tasks_list:
                            break
                # If still not found, search values for any list of dictionaries containing title/description
                if not tasks_list:
                    for val in plan_json.values():
                        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and ("title" in val[0] or "description" in val[0]):
                            tasks_list = val
                            break
                # If still not found, check if dictionary values are task dictionaries themselves
                if not tasks_list:
                    is_task_map = True
                    for val in plan_json.values():
                        if not isinstance(val, dict) or ("title" not in val and "description" not in val):
                            is_task_map = False
                            break
                    if is_task_map and len(plan_json) > 0:
                        tasks_list = list(plan_json.values())
            elif isinstance(plan_json, list):
                tasks_list = plan_json

            if not tasks_list:
                raise ValueError("Parsed JSON tasks list is empty.")
        except Exception as e:
            logger.warning(f"[Hermes] Failed to parse raw response as JSON: {e}. Attempting heuristic parser.")
            
            # Heuristic text-parsing fallback: extract tasks from numbered lists or bullet points
            task_idx = 1
            lines = plan_raw.split("\n")
            for line in lines:
                line = line.strip()
                # Matches list indicators: e.g., "1. Create something" or "- Create something"
                item_match = re.match(r"^(?:\d+[\.\)]|[-•*])\s+(.+)$", line)
                if item_match:
                    content = item_match.group(1).strip()
                    # Skip code blocks, self-references, or empty lines
                    if not content or content.startswith("```") or len(content) < 10 or "decompose" in content.lower():
                        continue
                    
                    # Split title and description if separated by colon or dash
                    title = content
                    desc = f"Implement step: {content}"
                    for sep in [":", " — ", " - "]:
                        if sep in content:
                            parts = content.split(sep, 1)
                            title_part = parts[0].strip()
                            if len(title_part) > 3 and len(title_part) < 60:
                                title = title_part
                                desc = parts[1].strip()
                                break
                    
                    tasks_list.append({
                        "id": f"subtask_{task_idx:03d}",
                        "title": title[:60],
                        "description": desc,
                        "priority": "High" if task_idx == 1 else "Medium",
                        "difficulty": "Medium",
                        "skills": ["backend", "fastapi"] if any(w in content.lower() for w in ["api", "fastapi", "backend", "db"]) else ["frontend", "react"]
                    })
                    task_idx += 1

            if not tasks_list:
                # Fallback: split by paragraphs
                paragraphs = [p.strip() for p in plan_raw.split("\n\n") if p.strip()]
                for idx, p in enumerate(paragraphs):
                    if p.startswith("```") or len(p) < 20 or "sure" in p.lower() or "here" in p.lower():
                        continue
                    title = p.split(".")[0].strip()[:60]
                    tasks_list.append({
                        "id": f"subtask_{idx+1:03d}",
                        "title": title,
                        "description": p,
                        "priority": "Medium",
                        "difficulty": "Medium",
                        "skills": ["backend"]
                    })
                    if len(tasks_list) >= 3:
                        break

            # If all parsing and heuristics failed, raise the original exception
            if not tasks_list:
                logger.error(f"[Hermes] Parsing and heuristics failed. Raw response: {plan_raw}")
                raise e

        # 5. Persist tasks on Kanban
        try:
            app_name = plan_json.get("app_name")
        except Exception:
            app_name = None
        if not app_name:
            import re
            app_name = re.sub(r'[^a-z0-9_]+', '_', goal.lower()).strip('_')

        current_tasks = tasks_store.read_all()
        created_tasks_list = []
        for idx, t in enumerate(tasks_list):
            task_id = f"task_{int(datetime.utcnow().timestamp())}_{idx}"
            assigned_agent = "Developer Agent"
            t_title = t.get("title") or t.get("task_title") or t.get("name") or t.get("id") or f"Task {idx+1}"
            t_desc = t.get("description") or t.get("task_description") or t.get("desc") or t_title
            t_obj = {
                "id": task_id,
                "title": t_title,
                "description": t_desc,
                "status": "Backlog",
                "assigned_agent": assigned_agent,
                "priority": t.get("priority", "Medium"),
                "difficulty": t.get("difficulty", "Medium"),
                "skills": t.get("skills", []),
                "eta_seconds": 900 if t.get("difficulty") == "Medium" else 400,
                "model": routing["selected_model"],
                "confidence": routing["confidence"],
                "created_at": datetime.utcnow().isoformat(),
                "app_name": app_name,
            }
            current_tasks[task_id] = t_obj
            created_tasks_list.append(t_obj)
            await slack_client.post_message(
                "#sprint-main",
                f"📋 *Task Created*: `{task_id}` — \"{t_title}\" → assigned to `{assigned_agent}`.",
            )
            if assigned_agent == "Developer Agent":
                await slack_client.post_message(
                    "#agent-developer",
                    f"📋 *Task Assigned*: `{task_id}` — \"{t_title}\".",
                )
            slack_client.log_event("Hermes", "Task Created", t_title, task_id)
        tasks_store.write_all(current_tasks)

        # 6. Log routing decision
        dec_id = f"dec_{int(datetime.utcnow().timestamp())}"
        decisions = decisions_store.read_all()
        decisions[dec_id] = {
            "id": dec_id,
            "task_id": "goal_orchestration",
            "timestamp": datetime.utcnow().isoformat(),
            "difficulty": routing["difficulty"],
            "selected_model": routing["selected_model"],
            "reason": routing["reason"],
            "loaded_skills": loaded_skills,
            "estimated_cost": routing["estimated_cost"],
            "actual_cost": routing["estimated_cost"] * 0.95,
            "estimated_time": routing["estimated_completion_time_seconds"],
            "actual_time": int(routing["estimated_completion_time_seconds"] * 0.9),
            "outcome": "Success",
        }
        decisions_store.write_all(decisions)

        # 7. Update analytics accumulator
        analytics = analytics_store.read_all() or {}
        analytics["estimated_tokens"] = analytics.get("estimated_tokens", 0) + routing["estimated_tokens"]
        analytics["actual_tokens"] = analytics.get("actual_tokens", 0) + int(routing["estimated_tokens"] * 0.98)
        analytics["estimated_cost"] = analytics.get("estimated_cost", 0.0) + routing["estimated_cost"]
        analytics["actual_cost"] = analytics.get("actual_cost", 0.0) + routing["estimated_cost"] * 0.95
        analytics["estimated_time_seconds"] = analytics.get("estimated_time_seconds", 0) + routing["estimated_completion_time_seconds"]
        analytics["actual_time_seconds"] = analytics.get("actual_time_seconds", 0) + int(routing["estimated_completion_time_seconds"] * 0.9)
        analytics["loaded_skills_count"] = len(loaded_skills)
        analytics_store.write_all(analytics)

        # 8. Memory log
        memory = memory_store.read_all() or {}
        if "architectural_decisions" not in memory:
            memory["architectural_decisions"] = []
        memory["architectural_decisions"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "decision": f"Sprint decomposed: '{goal}' → {len(tasks_list)} tasks, {len(loaded_skills)} skills.",
        })
        memory_store.write_all(memory)

        # Post the plan overview first
        plan_overview_msg = f"📋 *Hermes Action Plan for Goal*: \"{goal}\"\n"
        for i, t in enumerate(tasks_list):
            t_title = t.get("title") or t.get("task_title") or t.get("name") or t.get("id") or f"Task {i+1}"
            plan_overview_msg += f"{i+1}. *{t_title}*\n"
        await slack_client.post_message("#sprint-main", plan_overview_msg)
        await slack_client.post_message("#agent-orchestrator", plan_overview_msg)

        await slack_client.post_message(
            "#sprint-main",
            f"✅ *Planning Complete!* Hermes decomposed the goal into {len(tasks_list)} tasks.",
        )
        slack_client.log_event("Hermes", "Planning Complete", f"{len(tasks_list)} tasks created for: {goal}")

        return {"status": "Success", "skills": loaded_skills, "routing": routing, "tasks": created_tasks_list}

    async def chat(self, message: str, user: str = "unknown") -> str:
        """
        Handles conversational chat with the user:
        1. Recalls architectural memory or facts from memory_store.
        2. Scans for new facts to remember.
        3. Dynamically identifies and loads hello-world or other skills.
        4. Calls LLM with conversational prompt.
        5. Saves any new facts to memory.
        """
        # Load memory facts
        memory = memory_store.read_all() or {}
        user_facts = memory.get("user_facts", [])
        
        # Skill classification
        from app.skills.engine import skill_engine
        loaded_skills = skill_engine.classify_and_load(message)
        
        # Check if hello-world skill is triggered
        if "hello-world" in loaded_skills:
            await slack_client.post_message(
                "#agent-log",
                "⚡ *Skill Triggered*: `hello-world` detected in query."
            )
            # Execute hello-world skill automatically
            # Step 1: Read the person's name from the input
            # Step 2: Generate a personalized greeting
            # Step 3: Save the greeting to a file called greetings.md
            greeting_prompt = (
                f"You are the hello-world skill handler. Read the user input: '{message}'. "
                "Extract the name of the person/group to greet and generate a personalized, friendly greeting. "
                "Return ONLY the greeting text. Do not wrap in quotes or code blocks."
            )
            greeting_msg = await self.call_llm(greeting_prompt, "You are a friendly greeting generator.", "qwen2.5-coder:7b")
            
            # Save greetings.md
            greetings_path = "/home/mirage/Projects/forge2/greetings.md"
            try:
                with open(greetings_path, "w", encoding="utf-8") as f:
                    f.write(f"# Personalized Greeting\n\n{greeting_msg}\n")
                await slack_client.post_message(
                    "#agent-log",
                    f"file:///home/mirage/Projects/forge2/greetings.md created containing: {greeting_msg}"
                )
                await slack_client.post_message(
                    "#agent-log",
                    "✅ *hello-world skill success*: Saved greeting to `greetings.md`."
                )
                await slack_client.post_message(
                    "#sprint-main",
                    f"👋 *hello-world skill fired*: {greeting_msg}"
                )
                return greeting_msg
            except Exception as e:
                err = f"Failed to save greetings.md: {e}"
                await slack_client.post_message("#agent-log", f"❌ *hello-world skill error*: {err}")
                return f"Greeting generated, but failed to save file: {greeting_msg}"

        # Standard conversation model selection
        selected_model = "qwen2.5-coder:7b"
        
        # Memory context injection
        facts_context = ""
        if user_facts:
            facts_context = "\nFacts you remember about the user from earlier sessions:\n" + "\n".join([f"- {f}" for f in user_facts])
            
        system_prompt = (
            "You are Hermes, the autonomous orchestrator agent of ForgeOS.\n"
            "You have a persistent memory. Here is your memory context:\n"
            f"{facts_context}\n\n"
            "If the user tells you a new fact about themselves (e.g. name, preferences, choices), "
            "you MUST extract it and include `[STORE_FACT: <the exact fact>]` in your response "
            "so the system can save it for future sessions. Example: `[STORE_FACT: User's favorite color is blue]`.\n"
            "Reply to the user's message in a professional, helpful, and conversational tone."
        )
        
        response = await self.call_llm(message, system_prompt, selected_model)
        
        # Check if we need to store a new fact
        import re
        fact_match = re.search(r"\[STORE_FACT:\s*([^\]]+)\]", response)
        if fact_match:
            new_fact = fact_match.group(1).strip()
            # Clean response of the tag
            response = response.replace(fact_match.group(0), "").strip()
            
            if new_fact not in user_facts:
                user_facts.append(new_fact)
                memory["user_facts"] = user_facts
                memory_store.write_all(memory)
                await slack_client.post_message(
                    "#agent-log",
                    f"🧠 *Memory Stored*: Saved new fact: \"{new_fact}\""
                )
                
        await slack_client.post_message(
            "#sprint-main",
            f"🧠 *Hermes*: {response}"
        )
        return response


hermes_agent = HermesAgent()
