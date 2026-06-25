import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger("forgeos.skills")

class SkillEngine:
    def __init__(self):
        self.skills_base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills"
        )
        # Predefined skills list
        self.available_skills = [
            "backend", "frontend", "react", "fastapi", "database",
            "testing", "security", "documentation", "deployment",
            "github", "review", "architecture", "debugging", "python"
        ]

    def classify_and_load(self, task_description: str) -> List[str]:
        """
        Analyzes the task description, matches relevant skills,
        and dynamically loads their content (rules, checklist).
        """
        task_lower = task_description.lower()
        loaded = []

        # Comprehensive classification heuristics for 14 skills
        if any(w in task_lower for w in ["backend", "server", "logic", "route", "api"]):
            loaded.append("backend")
        if any(w in task_lower for w in ["frontend", "ui", "ux", "css", "interface", "client"]):
            loaded.append("frontend")
        if any(w in task_lower for w in ["fastapi", "endpoint", "crud", "query", "pydantic"]):
            loaded.append("fastapi")
            loaded.append("backend")
        if any(w in task_lower for w in ["react", "vite", "components", "jsx", "tsx", "tailwind"]):
            loaded.append("react")
            loaded.append("frontend")
        if any(w in task_lower for w in ["python", "py", "script", "pep8", "asyncio"]):
            loaded.append("python")
        if any(w in task_lower for w in ["db", "database", "sql", "postgres", "sqlite", "orm", "model"]):
            loaded.append("database")
        if any(w in task_lower for w in ["test", "pytest", "coverage", "mock", "unittest"]):
            loaded.append("testing")
        if any(w in task_lower for w in ["security", "bandit", "semgrep", "injection", "xss", "csrf", "audit", "vault", "keys", "tokens"]):
            loaded.append("security")
        if any(w in task_lower for w in ["doc", "readme", "markdown", "write", "summary"]):
            loaded.append("documentation")
        if any(w in task_lower for w in ["docker", "compose", "deploy", "kubernetes", "vps"]):
            loaded.append("deployment")
        if any(w in task_lower for w in ["git", "github", "pr", "commit", "branch"]):
            loaded.append("github")
        if any(w in task_lower for w in ["review", "approve", "sign-off", "merge", "pull request"]):
            loaded.append("review")
        if any(w in task_lower for w in ["debug", "error", "bug", "fix", "troubleshoot", "trace", "exception"]):
            loaded.append("debugging")
        if any(w in task_lower for w in ["architecture", "structure", "system", "uml", "mermaid", "flowchart"]):
            loaded.append("architecture")

        # Fallback to general skills if nothing matched
        if not loaded:
            loaded = ["architecture", "backend"]

        # De-duplicate
        loaded = list(set(loaded))
        return loaded

    def get_skill_rules(self, skill_name: str) -> Dict[str, str]:
        """
        Reads the SKILL.md, rules.md, and checklist.md from the file system
        to be injected into the LLM context.
        """
        skill_dir = os.path.join(self.skills_base_dir, skill_name)
        rules_content = ""
        checklist_content = ""

        rules_path = os.path.join(skill_dir, "rules.md")
        checklist_path = os.path.join(skill_dir, "checklist.md")

        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r") as f:
                    rules_content = f.read()
            except Exception:
                pass

        if os.path.exists(checklist_path):
            try:
                with open(checklist_path, "r") as f:
                    checklist_content = f.read()
            except Exception:
                pass

        return {
            "rules": rules_content or f"Follow general coding standards for {skill_name}.",
            "checklist": checklist_content or f"Verify functionality for {skill_name}."
        }

    def get_injected_prompt(self, skills: List[str]) -> str:
        """
        Builds a combined prompt string of rules and checklists for the loaded skills
        to be injected into the LLM system prompt.
        """
        injected = "\n\n=== DYNAMICALLY LOADED SKILLS & RULES ===\n"
        for skill in skills:
            data = self.get_skill_rules(skill)
            injected += f"\n--- Skill: {skill.upper()} ---\n"
            injected += f"Coding Rules:\n{data['rules']}\n"
            injected += f"Verification Checklist:\n{data['checklist']}\n"
        injected += "\n=========================================\n"
        return injected

    def log_loaded_skills(self, skills: List[str]):
        """
        Logs loading events for explainability.
        """
        for skill in skills:
            logger.info(f"[SKILL ENGINE] Dynamically loaded skill: '{skill}'")

skill_engine = SkillEngine()
