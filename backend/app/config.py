import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ForgeOS"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # ── LLM providers ─────────────────────────────────────────────────────────
    # Local models via Ollama (Qwen, DeepSeek run here)
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
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPOSITORY: Optional[str] = None

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


settings = Settings()

os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.MEMORY_DIR, exist_ok=True)
