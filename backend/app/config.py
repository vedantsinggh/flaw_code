import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "OpenFlaw"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # ── LLM providers ─────────────────────────────────────────────────────────
    # EastRouter API — unified cloud inference endpoint
    EASTROUTER_BASE_URL: str = "https://api.eastrouter.com/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Groq — fast cloud inference for heavy reasoning tasks
    GROQ_API_KEY: Optional[str] = None

    # Legacy keys — kept for .env compatibility, not used by agents
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # ── Integrations ───────────────────────────────────────────────────────────
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    EASTROUTER_API_KEY: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPOSITORY: Optional[str] = None
    TARGET_REPOSITORY: Optional[str] = None
    TARGET_BRANCH: Optional[str] = "main"
    OPENCLAW_WORKSPACE: Optional[str] = None
    PROJECTS_DIR: Optional[str] = None

    # ── Slack Channels Mapping ─────────────────────────────────────────────────
    SLACK_CHANNELS: dict = {
        "sprint-main": "#sprint-main",
        "agent-developer": "#agent-developer",
        "agent-coder": "#agent-developer",
        "agent-log": "#agent-log",
        "ci-cd": "#ci-cd",
        "human-review": "#human-review",
    }

    def get_slack_channel(self, name: str) -> str:
        clean_name = name.lstrip("#")
        return self.SLACK_CHANNELS.get(clean_name, f"#{clean_name}")

    def get_projects_base_dir(self) -> str:
        if self.PROJECTS_DIR:
            return self.PROJECTS_DIR
        base = self.OPENCLAW_WORKSPACE or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, "projects")

    def get_app_dir(self, app_name: str) -> str:
        base = self.get_projects_base_dir()
        path = os.path.join(base, app_name)
        os.makedirs(path, mode=0o777, exist_ok=True)
        try:
            os.chmod(path, 0o777)
        except Exception:
            pass
        return path

    # ── Mode ───────────────────────────────────────────────────────────────────
    # true  → fully offline simulation (no LLM calls, no API calls)
    # false → live: Ollama for Qwen/DeepSeek, Groq for complex tasks
    SIMULATION_MODE: bool = True

    # ── Data directories ───────────────────────────────────────────────────────
    DATA_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs"
    )
    MEMORY_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "memory"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def make_editable(path: str):
    """Recursively sets write/read/execute permissions (0777) so host machine users can edit Docker-generated files."""
    try:
        if os.path.isdir(path):
            os.chmod(path, 0o777)
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    try:
                        os.chmod(os.path.join(root, d), 0o777)
                    except Exception:
                        pass
                for f in files:
                    try:
                        os.chmod(os.path.join(root, f), 0o666 if not f.endswith(".sh") else 0o777)
                    except Exception:
                        pass
        elif os.path.isfile(path):
            os.chmod(path, 0o666 if not path.endswith(".sh") else 0o777)
    except Exception:
        pass


settings = Settings()

os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.MEMORY_DIR, exist_ok=True)
os.makedirs(settings.get_projects_base_dir(), mode=0o777, exist_ok=True)
make_editable(settings.get_projects_base_dir())
