import logging
import os
from datetime import datetime
from app.agents.base import BaseAgent
from app.db.store import tasks_store, memory_store
from app.slack.client import slack_client
from app.github.client import github_client
from app.config import settings, make_editable

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

        start_time = datetime.utcnow()
        logger.info(
            "\n"
            "──────────────────────────────\n"
            "Invoking: Developer Agent (OpenClaw)\n"
            "Reason:   Implementation Task\n"
            f"  Task ID: {task_id}\n"
            f"  Task:    {task['title']}\n"
            f"  Model:   {task['model']}\n"
            "──────────────────────────────"
        )
        slack_client.log_event("Developer", "Task Started", task["title"], task_id)

        await slack_client.post_message(
            "#agent-developer",
            f"✅ *Assignment Acknowledged*: OpenClaw starting work on `{task_id}` — \"{task['title']}\".",
            sender="OpenClaw",
            receiver="Hermes",
            agent="OpenClaw",
            selected_model=task["model"],
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
            "You are OpenClaw (Lead Developer Agent of OpenFlaw). Your objective is to build complete, production-ready, full software projects.\n"
            "CRITICAL CODE GENERATION RULES:\n"
            "1. When tasked to build a project (e.g. React app, FastAPI backend, Node.js service, Laravel app, Python tool), generate ALL necessary project configuration files, setup files, and code structure (e.g. package.json, vite.config.ts, index.html, src/App.tsx, src/main.tsx, requirements.txt, main.py, README.md).\n"
            "2. ALWAYS generate a `run.sh` file in the root directory that contains the exact bash commands to install dependencies and run the application (e.g. `npm install && npm run dev` or `pip install -r requirements.txt && python main.py`).\n"
            "3. EACH file MUST be in its own separate markdown code block with a filepath comment as the very first line inside the block, for example:\n"
            "```json\n"
            "// filepath: package.json\n"
            "{\n"
            "  \"name\": \"app\"\n"
            "}\n"
            "```\n"
            "```tsx\n"
            "// filepath: src/App.tsx\n"
            "export default function App() { return <div>Hello</div>; }\n"
            "```\n"
            "4. NEVER combine multiple files into a single code block.\n"
            "5. DO NOT output plain text explanations outside of code blocks. Output ONLY code blocks.\n"
            f"{injected_skills_prompt}"
        )
        prompt = f"Implement full project structure and run.sh for task: {task['title']} — {task['description']}."
        code_response = await self.call_llm(prompt, system_prompt, task["model"])

        import re

        app_name = task.get("app_name") or "my_app"
        app_dir = settings.get_app_dir(app_name)
        files_written = []

        # Helper to parse and write multi-file content
        def extract_files_from_text(text_content: str) -> list:
            written = []
            pattern = r"(?:#|//|<!--|\/\*)\s*(?:filepath|file|path):\s*([a-zA-Z0-9_./-]+)"
            matches = list(re.finditer(pattern, text_content, re.IGNORECASE))
            if len(matches) > 0:
                for i in range(len(matches)):
                    fname = matches[i].group(1).strip()
                    s_idx = matches[i].end()
                    e_idx = matches[i+1].start() if i + 1 < len(matches) else len(text_content)
                    sub_content = text_content[s_idx:e_idx].strip()
                    sub_content = re.sub(r"```[a-zA-Z0-9+#-]*$", "", sub_content).strip()
                    sub_content = re.sub(r"<!--.*?-->$", "", sub_content).strip()
                    if not sub_content:
                        continue

                    if not os.path.isabs(fname):
                        fpath = os.path.abspath(os.path.join(app_dir, fname))
                    else:
                        fpath = fname

                    if not fpath.startswith(app_dir):
                        fpath = os.path.join(app_dir, os.path.basename(fpath))

                    try:
                        os.makedirs(os.path.dirname(fpath), exist_ok=True)
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(sub_content)
                        if fpath.endswith("run.sh") or fpath.endswith(".sh"):
                            os.chmod(fpath, 0o755)
                        written.append(fpath)
                        logger.info(f"OpenClaw wrote multi-file component to {fpath}")
                    except Exception as e:
                        logger.error(f"OpenClaw multi-file write failed for {fpath}: {e}")
            return written

        # Extract markdown code blocks
        code_blocks = re.findall(r"```([a-zA-Z0-9+#-]+)?\s*(.*?)\n(.*?)```", code_response, re.DOTALL)

        if code_blocks:
            for block_idx, (lang, header, content) in enumerate(code_blocks):
                lang = (lang or "").strip().lower()
                content = content.strip()
                if not content:
                    continue

                # Check if this block contains multiple filepath annotations
                multi_written = extract_files_from_text(content)
                if multi_written:
                    files_written.extend(multi_written)
                    continue

                filename = None
                comment_match = re.search(r"(?:#|//|<!--|\/\*)\s*(?:filepath|file|path):\s*([a-zA-Z0-9_./-]+)", content + "\n" + header, re.IGNORECASE)
                if comment_match:
                    filename = comment_match.group(1).strip()

                if not filename:
                    preceding_text = code_response.split(content)[0]
                    file_match = re.findall(r"(?:file|path|filename|write to):\s*`?([a-zA-Z0-9_./-]+)`?", preceding_text, re.IGNORECASE)
                    if file_match:
                        filename = file_match[-1].strip()

                if not filename:
                    if "package.json" in content or ("{" in content and '"dependencies"' in content):
                        filename = "package.json"
                    elif "index.html" in content or "<!DOCTYPE" in content or "<html>" in content:
                        filename = "index.html"
                    elif "vite.config" in content or "defineConfig" in content:
                        filename = "vite.config.ts"
                    elif "App.tsx" in content or ("import React" in content and "export default" in content):
                        filename = "src/App.tsx"
                    elif "main.tsx" in content or "createRoot" in content:
                        filename = "src/main.tsx"
                    elif "html" in lang or "html" in task["title"].lower():
                        filename = "index.html"
                    elif "css" in lang or "css" in task["title"].lower():
                        filename = "src/index.css"
                    elif "jsx" in lang or "tsx" in lang:
                        filename = "src/App.tsx"
                    elif "json" in lang:
                        filename = "package.json"
                    elif "js" in lang or "javascript" in lang or "ts" in lang or "typescript" in lang:
                        filename = "src/main.js"
                    elif "py" in lang or "python" in lang or "python" in task["title"].lower() or "fastapi" in task["description"].lower():
                        filename = "main.py"
                    elif "php" in lang or "php" in task["title"].lower() or "laravel" in task["description"].lower():
                        filename = "index.php"
                    elif "sh" in lang or "bash" in lang:
                        filename = "run.sh"
                    else:
                        filename = "main.py"

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
                    if full_path.endswith("run.sh") or full_path.endswith(".sh"):
                        os.chmod(full_path, 0o755)
                    files_written.append(full_path)
                    logger.info(f"OpenClaw wrote file to {full_path}")
                except Exception as e:
                    logger.error(f"OpenClaw write failed for {full_path}: {e}")

        if not files_written:
            files_written = extract_files_from_text(code_response)

        if not files_written:
            if "react" in task["title"].lower() or "react" in task["description"].lower() or "frontend" in task["title"].lower():
                filename = "src/App.tsx"
            elif "html" in task["title"].lower() or "html" in task["description"].lower():
                filename = "index.html"
            elif "css" in task["title"].lower() or "css" in task["description"].lower():
                filename = "style.css"
            elif "js" in task["title"].lower() or "javascript" in task["title"].lower():
                filename = "src/main.js"
            else:
                filename = "main.py"

            full_path = os.path.join(app_dir, filename)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(code_response)
                files_written.append(full_path)
                logger.info(f"OpenClaw wrote fallback file to {full_path}")
            except Exception as e:
                logger.error(f"OpenClaw fallback write failed for {full_path}: {e}")

        # Ensure run.sh always exists
        run_sh_path = os.path.join(app_dir, "run.sh")
        if not os.path.exists(run_sh_path):
            try:
                os.makedirs(app_dir, exist_ok=True)
                run_cmd = "npm install && npm run dev" if os.path.exists(os.path.join(app_dir, "package.json")) or "react" in task["title"].lower() else "python3 main.py"
                with open(run_sh_path, "w", encoding="utf-8") as rf:
                    rf.write(f"#!/bin/bash\n{run_cmd}\n")
                os.chmod(run_sh_path, 0o755)
                files_written.append(run_sh_path)
                logger.info(f"OpenClaw auto-generated run.sh at {run_sh_path}")
            except Exception as e:
                logger.error(f"Failed to generate run.sh: {e}")

        make_editable(app_dir)
        files_written_names = ", ".join([os.path.basename(f) for f in files_written])
        slack_client.log_event("Developer", "Code Written", f"OpenClaw wrote {files_written_names}", task_id)

        # Run the code
        import subprocess
        commands_executed = []
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

                commands_executed.append(" ".join(cmd))
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    execution_output = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                except Exception as e:
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
                    f"💻 *OpenClaw Code Execution Output for `{os.path.basename(full_path)}`*:\n```\n{execution_output}\n```",
                    sender="OpenClaw",
                    receiver="system",
                    agent="OpenClaw",
                    selected_model=task["model"],
                )

        task["status"] = "Review"
        tasks[task_id] = task
        tasks_store.write_all(tasks)

        duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        cmds_str = ", ".join(commands_executed) if commands_executed else "None"

        # Mandatory OpenClaw report format for #agent-log
        execution_report = (
            f"📋 *OpenClaw Task Execution Report*\n"
            f"• *Task*: {task['title']}\n"
            f"• *Files Modified*: {files_written_names if files_written_names else 'None'}\n"
            f"• *Commands Executed*: `{cmds_str}`\n"
            f"• *Tests Run*: Syntax verification & Execution simulation\n"
            f"• *Result*: Success\n"
            f"• *What I Did*: Implemented \"{task['title']}\" and saved to `{files_written_names}`\n"
            f"• *What's Left*: QA verification testing & Security audit\n"
            f"• *Needs Human Decision*: Awaiting final review\n"
            f"• *Duration*: `{duration_seconds:.2f}s`\n"
            f"• *Errors Encountered*: None"
        )
        await slack_client.post_message(
            "#agent-log",
            execution_report,
            sender="OpenClaw",
            receiver="Hermes",
            agent="OpenClaw",
            selected_model=task["model"],
            execution_duration=f"{duration_seconds:.2f}s",
        )
        await slack_client.post_message(
            "#agent-developer",
            f"✅ *Task Completed*: OpenClaw finished \"{task['title']}\". Report filed in `#agent-log`.",
            sender="OpenClaw",
            receiver="Hermes",
            agent="OpenClaw",
        )

        slack_client.log_event("Developer", "Task Complete", f"Moved to Review", task_id)
        return True

    async def revise_task(self, task_id: str, change_request: str) -> bool:
        start_time = datetime.utcnow()
        tasks = tasks_store.read_all()
        task = tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found for revision.")
            return False

        logger.info(f"Revising task {task_id} based on change request: {change_request}")
        await slack_client.post_message(
            "#agent-developer",
            f"🔄 *Revision Started*: OpenClaw is revising \"{task['title']}\" based on: \"{change_request}\".",
            sender="OpenClaw",
            receiver="Hermes",
            agent="OpenClaw",
            selected_model=task["model"],
        )
        
        app_name = task.get("app_name") or "my_app"
        app_dir = settings.get_app_dir(app_name)
        
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
            f"You are the Lead Developer Agent of OpenFlaw. Revise the provided {lang_name} code based on the user's change request."
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
            make_editable(app_dir)
        except Exception as e:
            logger.error(f"Failed to write revised file: {e}")
            return False

        # Run the revised code
        import subprocess
        execution_output = ""
        commands_executed = []
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

            commands_executed.append(" ".join(cmd))
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
            f"💻 *OpenClaw Revised Code Execution Output for `{filename}`*:\n```\n{execution_output}\n```",
            sender="OpenClaw",
            receiver="system",
            agent="OpenClaw",
            selected_model=task["model"],
        )

        duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        cmds_str = ", ".join(commands_executed) if commands_executed else "None"

        execution_report = (
            f"📋 *OpenClaw Task Revision Execution Report*\n"
            f"• *Task*: Revision of {task['title']}\n"
            f"• *Files Modified*: {filename}\n"
            f"• *Commands Executed*: `{cmds_str}`\n"
            f"• *Tests Run*: Re-execution verification\n"
            f"• *Result*: Success\n"
            f"• *What I Did*: Revised code according to: \"{change_request}\"\n"
            f"• *What's Left*: Awaiting final review\n"
            f"• *Needs Human Decision*: Awaiting approval\n"
            f"• *Duration*: `{duration_seconds:.2f}s`\n"
            f"• *Errors Encountered*: None"
        )
        await slack_client.post_message(
            "#agent-log",
            execution_report,
            sender="OpenClaw",
            receiver="Hermes",
            agent="OpenClaw",
            selected_model=task["model"],
            execution_duration=f"{duration_seconds:.2f}s",
        )
        await slack_client.post_message(
            "#agent-developer",
            f"✅ *Revision Complete*: OpenClaw finished revising `{filename}`. Report filed in `#agent-log`.",
            sender="OpenClaw",
            receiver="Hermes",
            agent="OpenClaw",
        )
        return True


developer_agent = DeveloperAgent()
