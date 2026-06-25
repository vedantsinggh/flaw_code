import logging
import os
from datetime import datetime
from app.agents.base import BaseAgent
from app.db.store import tasks_store, memory_store
from app.slack.client import slack_client
from app.github.client import github_client
from app.config import settings

logger = logging.getLogger("forgeos.developer")


class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Developer Agent", role="Code Implementation and Modification")

    async def execute_task(self, task_id: str) -> bool:
        tasks = tasks_store.read_all()
        task = tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found.")
            return False

        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Invoking: Developer Agent\n"
            "Reason:   Implementation Task\n"
            f"  Task ID: {task_id}\n"
            f"  Task:    {task['title']}\n"
            f"  Model:   {task['model']}\n"
            "──────────────────────────────"
        )
        slack_client.log_event("Developer", "Task Started", task["title"], task_id)

        await slack_client.post_message(
            "#agent-developer",
            f"🚀 *Task Started*: Developer Agent implementing \"{task['title']}\" with `{task['model']}`.",
        )
        await slack_client.post_message(
            "#sprint-main",
            f"💻 *Coding Started*: Developer Agent writing implementation for \"{task['title']}\".",
        )

        task["status"] = "In Progress"
        task["assigned_agent"] = "Developer Agent"
        tasks[task_id] = task
        tasks_store.write_all(tasks)

        # Build system prompt with injected skill rules
        from app.skills.engine import skill_engine
        task_skills = task.get("skills", ["fastapi", "backend"])
        injected_skills_prompt = skill_engine.get_injected_prompt(task_skills)
        system_prompt = (
            "You are the Lead Developer Agent of ForgeOS. Write clean, maintainable, "
            "production-grade Python/FastAPI code with proper typing and async structures."
            f"{injected_skills_prompt}"
        )
        prompt = f"Implement: {task['title']} — {task['description']}. Provide the code structure."
        code_response = await self.call_llm(prompt, system_prompt, task["model"])

        import re

        repo_root = "/home/mirage/Projects/forge2"
        files_written = []

        # Extract markdown code blocks
        code_blocks = re.findall(r"```([a-zA-Z0-9+#-]+)?\s*(.*?)\n(.*?)```", code_response, re.DOTALL)

        if code_blocks:
            for block_idx, (lang, header, content) in enumerate(code_blocks):
                lang = (lang or "").strip().lower()
                content = content.strip()
                if not content:
                    continue

                filename = None

                # Check for filepath comment inside the block
                comment_match = re.search(r"(?:#|//|<!--)\s*(?:filepath|file|path):\s*([a-zA-Z0-9_./-]+)", content, re.IGNORECASE)
                if comment_match:
                    filename = comment_match.group(1).strip()

                # Check preceding text if not found
                if not filename:
                    preceding_text = code_response.split(content)[0]
                    file_match = re.findall(r"(?:file|path|filename|write to):\s*`?([a-zA-Z0-9_./-]+)`?", preceding_text, re.IGNORECASE)
                    if file_match:
                        filename = file_match[-1].strip()

                # Resolve default fallback names
                if not filename:
                    if "html" in lang or "html" in task["title"].lower() or "html" in task["description"].lower():
                        filename = "index.html"
                    elif "css" in lang or "css" in task["title"].lower() or "css" in task["description"].lower():
                        filename = "style.css"
                    elif "js" in lang or "javascript" in lang or "js" in task["title"].lower() or "javascript" in task["description"].lower():
                        filename = "script.js"
                    elif "py" in lang or "python" in lang or "python" in task["title"].lower() or "fastapi" in task["description"].lower():
                        filename = "main.py"
                    else:
                        filename = f"task_{task_id}_{block_idx}.txt"

                filename = os.path.basename(filename) if "/" not in filename else filename
                if not os.path.isabs(filename):
                    full_path = os.path.abspath(os.path.join(repo_root, filename))
                else:
                    full_path = filename

                if not full_path.startswith(repo_root):
                    full_path = os.path.join(repo_root, os.path.basename(full_path))

                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    files_written.append(full_path)
                    logger.info(f"OpenClaw wrote file to {full_path}")
                except Exception as e:
                    logger.error(f"OpenClaw write failed for {full_path}: {e}")

        if not files_written:
            filename = "implementation.txt"
            if "html" in task["title"].lower() or "html" in task["description"].lower():
                filename = "index.html"
            elif "css" in task["title"].lower() or "css" in task["description"].lower():
                filename = "style.css"
            elif "js" in task["title"].lower() or "javascript" in task["title"].lower():
                filename = "script.js"
            elif "python" in task["title"].lower() or "fastapi" in task["title"].lower():
                filename = "main.py"

            full_path = os.path.join(repo_root, filename)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(code_response)
                files_written.append(full_path)
                logger.info(f"OpenClaw wrote fallback file to {full_path}")
            except Exception as e:
                logger.error(f"OpenClaw fallback write failed for {full_path}: {e}")

        files_written_names = ", ".join([os.path.basename(f) for f in files_written])
        slack_client.log_event("Developer", "Code Written", f"OpenClaw wrote {files_written_names}", task_id)

        # Git commit + PR
        branch_name = f"feature/{task_id}"
        # Create branch reference on GitHub first
        await github_client.create_branch(branch_name)

        git_success = await github_client.create_commit(
            branch=branch_name,
            commit_message=f"feat: implement {task['title'].lower()}",
            files_changed=files_written,
        )
        if git_success:
            slack_client.log_event("Git", "Commit Created", f"feat: implement {task['title'].lower()}", task_id)
            await slack_client.post_message(
                "#agent-developer",
                f"📦 *Git Commit*: Committed to branch `{branch_name}`.\n`feat: implement {task['title'].lower()}`",
            )
            pr_data = await github_client.create_pull_request(
                title=f"feat: implement {task['title'].lower()}",
                body=f"Implements task {task_id}: {task['description']}",
                head_branch=branch_name,
                base_branch="main",
            )
            slack_client.log_event("Git", "PR Opened", f"PR #{pr_data['id']}: {pr_data['title']}", task_id)
            await slack_client.post_message(
                "#sprint-main",
                f"🔀 *PR Opened*: PR #{pr_data['id']} \"{pr_data['title']}\"\n{pr_data['url']}",
            )

        task["status"] = "Review"
        tasks[task_id] = task
        tasks_store.write_all(tasks)

        await slack_client.post_message(
            "#agent-developer",
            f"✅ *Implementation Complete*: \"{task['title']}\" moved to Review.",
        )
        slack_client.log_event("Developer", "Task Complete", f"Moved to Review", task_id)
        return True


developer_agent = DeveloperAgent()
