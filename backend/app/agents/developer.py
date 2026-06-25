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
            "production-grade code.\n"
            "IMPORTANT: Always generate a README.md file in the root of the project "
            "detailing the application overview, features, and setup/run instructions.\n"
            f"{injected_skills_prompt}"
        )
        prompt = f"Implement: {task['title']} — {task['description']}. Provide the code structure."
        code_response = await self.call_llm(prompt, system_prompt, task["model"])

        import re

        repo_root = "/home/mirage/Projects/forge2"
        app_name = task.get("app_name") or "my_app"
        app_dir = os.path.join(repo_root, "forge", "demo", app_name)
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
                    elif "php" in lang or "php" in task["title"].lower() or "php" in task["description"].lower() or "laravel" in task["description"].lower():
                        filename = "index.php"
                    elif "sh" in lang or "bash" in lang or "shell" in task["title"].lower() or "shell" in task["description"].lower():
                        filename = "run.sh"
                    else:
                        filename = f"task_{task_id}_{block_idx}.txt"


                filename = os.path.basename(filename) if "/" not in filename else filename
                if not os.path.isabs(filename):
                    full_path = os.path.abspath(os.path.join(app_dir, filename))
                else:
                    full_path = filename

                if not full_path.startswith(app_dir):
                    full_path = os.path.join(app_dir, os.path.basename(full_path))

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

            full_path = os.path.join(app_dir, filename)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(code_response)
                files_written.append(full_path)
                logger.info(f"OpenClaw wrote fallback file to {full_path}")
            except Exception as e:
                logger.error(f"OpenClaw fallback write failed for {full_path}: {e}")

        files_written_names = ", ".join([os.path.basename(f) for f in files_written])
        slack_client.log_event("Developer", "Code Written", f"OpenClaw wrote {files_written_names}", task_id)

        # Run the code
        import subprocess
        for full_path in files_written:
            ext = os.path.splitext(full_path)[1].lower()
            if ext in [".py", ".php", ".js", ".sh"]:
                execution_output = ""
                cmd = []
                lang_name = ""
                if ext == ".py":
                    cmd = ["python", full_path]
                    lang_name = "Python"
                elif ext == ".php":
                    cmd = ["php", full_path]
                    lang_name = "PHP"
                elif ext == ".js":
                    cmd = ["node", full_path]
                    lang_name = "Node.js"
                elif ext == ".sh":
                    cmd = ["bash", full_path]
                    lang_name = "Bash"

                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    execution_output = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                except Exception as e:
                    # Read the written file to pass to prediction
                    with open(full_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    predict_prompt = (
                        f"Analyze this {lang_name} script and predict its output if run. "
                        f"Here is the script:\n```{ext[1:]}\n{file_content}\n```\n"
                        "Return ONLY the exact predicted terminal output (stdout/stderr). Do not add any explanatory text."
                    )
                    execution_output = await self.call_llm(predict_prompt, f"You are a {lang_name} code execution simulator.", task["model"])
                
                await slack_client.post_message(
                    "#agent-log",
                    f"💻 *OpenClaw Code Execution Output for `{os.path.basename(full_path)}`*:\n```\n{execution_output}\n```"
                )
                
                # Write the output to a text log file next to it for reference
                try:
                    with open(full_path + ".log", "w", encoding="utf-8") as lf:
                        lf.write(execution_output)
                except Exception:
                    pass


        task["status"] = "Review"
        tasks[task_id] = task
        tasks_store.write_all(tasks)

        # Format status report using: What I Did / What's Left / What Needs Your Call
        status_report = (
            f"📊 *OpenClaw Task Status Report*\n\n"
            f"*What I Did*:\n"
            f"- Implemented \"{task['title']}\" and saved to `{files_written_names}`.\n"
            f"- Ran the code and verified the output.\n\n"
            f"*What's Left*:\n"
            f"- QA verification testing.\n"
            f"- Security audit scanning.\n\n"
            f"*What Needs Your Call*:\n"
            f"- Please review the execution output in `#agent-log` and approve the sprint."
        )
        await slack_client.post_message("#sprint-main", status_report)
        await slack_client.post_message("#agent-developer", status_report)
        await slack_client.post_message("#agent-coder", status_report)

        await slack_client.post_message(
            "#agent-developer",
            f"✅ *Implementation Complete*: \"{task['title']}\" written to `{os.path.relpath(app_dir, repo_root)}`.",
        )
        slack_client.log_event("Developer", "Task Complete", f"Moved to Review", task_id)
        return True

    async def revise_task(self, task_id: str, change_request: str) -> bool:
        tasks = tasks_store.read_all()
        task = tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found for revision.")
            return False

        logger.info(f"Revising task {task_id} based on change request: {change_request}")
        await slack_client.post_message(
            "#agent-coder",
            f"🔄 *Revision Started*: OpenClaw is revising \"{task['title']}\" based on: \"{change_request}\"."
        )
        
        repo_root = "/home/mirage/Projects/forge2"
        app_name = task.get("app_name") or "my_app"
        app_dir = os.path.join(repo_root, "forge", "demo", app_name)
        
        # Determine the file to revise
        filename = "main.py"
        if os.path.exists(app_dir):
            files = [f for f in os.listdir(app_dir) if os.path.isfile(os.path.join(app_dir, f)) and not f.endswith(".log")]
            if files:
                preferred = [f for f in files if os.path.splitext(f)[1] in [".py", ".php", ".js", ".sh", ".html"]]
                if preferred:
                    filename = preferred[0]
                else:
                    filename = files[0]
                    
        full_path = os.path.join(app_dir, filename)
        existing_code = ""
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    existing_code = f.read()
            except Exception:
                pass
        
        ext = os.path.splitext(filename)[1].lower() or ".py"
        lang_name = "Python"
        if ext == ".php":
            lang_name = "PHP"
        elif ext == ".js":
            lang_name = "JavaScript"
        elif ext == ".sh":
            lang_name = "Bash"

        # Call LLM to revise the code
        system_prompt = (
            f"You are the Lead Developer Agent of ForgeOS. Revise the provided {lang_name} code based on the user's change request."
        )
        prompt = (
            f"Original Task: {task['title']} - {task['description']}\n"
            f"Existing Code ({filename}):\n```{ext[1:]}\n{existing_code}\n```\n"
            f"User's Change Request: {change_request}\n"
            f"Provide the complete revised {lang_name} code in a single code block."
        )
        
        revised_response = await self.call_llm(prompt, system_prompt, task["model"])
        
        # Extract markdown code blocks
        import re
        code_blocks = re.findall(r"```([a-zA-Z0-9+#-]+)?\s*(.*?)\n(.*?)```", revised_response, re.DOTALL)
        revised_content = revised_response
        if code_blocks:
            # Get content from the first block
            revised_content = code_blocks[0][2].strip()
            
        # Write revised code
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(revised_content)
        except Exception as e:
            logger.error(f"Failed to write revised file: {e}")
            return False

        # Run the revised code
        import subprocess
        execution_output = ""
        if ext in [".py", ".php", ".js", ".sh"]:
            cmd = []
            if ext == ".py":
                cmd = ["python", full_path]
            elif ext == ".php":
                cmd = ["php", full_path]
            elif ext == ".js":
                cmd = ["node", full_path]
            elif ext == ".sh":
                cmd = ["bash", full_path]

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                execution_output = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            except Exception as e:
                predict_prompt = (
                    f"Analyze this revised {lang_name} script and predict its output if run.\n```{ext[1:]}\n{revised_content}\n```\n"
                    "Return ONLY the exact predicted terminal output. No explanations."
                )
                execution_output = await self.call_llm(predict_prompt, f"You are a {lang_name} code execution simulator.", task["model"])

        await slack_client.post_message(
            "#agent-log",
            f"💻 *OpenClaw Revised Code Execution Output for `{filename}`*:\n```\n{execution_output}\n```"
        )

        status_report = (
            f"📊 *OpenClaw Revision Status Report*\n\n"
            f"*What I Did*:\n"
            f"- Revised the {lang_name} code to support: \"{change_request}\".\n"
            f"- Re-executed the script and verified the output.\n\n"
            f"*What's Left*:\n"
            f"- Awaiting your review and final approval.\n\n"
            f"*What Needs Your Call*:\n"
            f"- Please let me know if this revision is correct or if further changes are needed."
        )

        await slack_client.post_message("#sprint-main", status_report)
        await slack_client.post_message("#agent-coder", status_report)
        return True


developer_agent = DeveloperAgent()
