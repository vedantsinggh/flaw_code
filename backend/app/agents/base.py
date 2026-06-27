import logging
from app.config import settings

logger = logging.getLogger("forgeos.agent")

# ── Model name → provider mapping ─────────────────────────────────────────────
# ── Model name → provider mapping ─────────────────────────────────────────────
EASTROUTER_MODELS = {
    "glm-4.6":             "z-ai/glm-4.6",
    "z-ai/glm-4.6":        "z-ai/glm-4.6",
    "qwen2.5-coder":       "qwen/qwen-2.5-coder-32b-instruct",
    "qwen2.5-coder:7b":    "qwen/qwen-2.5-coder-32b-instruct",
    "deepseek-r1":         "deepseek/deepseek-r1",
    "deepseek-r1:1.5b":    "z-ai/glm-4.6",
}

# Groq cloud models (fast inference)
GROQ_MODELS = {
    "groq/llama-3.3-70b":           "llama-3.3-70b-versatile",
    "groq/deepseek-r1-distill-70b": "deepseek-r1-distill-llama-70b",
    "groq/llama-3.1-8b":            "llama-3.1-8b-instant",
    "groq/qwen-qwq-32b":            "qwen-qwq-32b",
    "groq/mixtral-8x7b":            "mixtral-8x7b-32768",
}


def _resolve_eastrouter_model(model_key: str) -> str:
    """Returns the model tag for EastRouter API."""
    key = model_key.lower()
    for k, v in EASTROUTER_MODELS.items():
        if k in key:
            return v
    return model_key


class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    async def call_llm(self, prompt: str, system_prompt: str, model: str) -> str:
        """
        Executes an LLM request against the configured provider stack:
        1. If model starts with "groq/" → Groq API (requires GROQ_API_KEY)
        2. Otherwise → EastRouter API (requires EASTROUTER_API_KEY)
        """
        from app.slack.client import slack_client
        from app.db.store import event_log_store
        
        logger.info(f"[{self.name}] model={model} prompt_len={len(prompt)}")
        
        await slack_client.post_message(
            "#agent-log",
            f"⏳ *[{self.name}]* Calling `{model}` API... (request size: {len(prompt)} chars)"
        )
        event_log_store.append_event(self.name, "LLM Request", f"Calling model {model}")

        if settings.SIMULATION_MODE:
            raise RuntimeError(f"[{self.name}] Simulation mode is enabled, but mock data and simulation fallbacks have been removed.")

        try:
            result = await self._call_live(prompt, system_prompt, model)
            if not result:
                raise RuntimeError(f"[{self.name}] Live LLM call returned empty response")
            return result
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[{self.name}] Live LLM call failed ({model}): {err_msg}")
            
            await slack_client.post_message(
                "#sprint-main",
                f"⚠️ *[{self.name}]* LLM call to `{model}` failed: `{err_msg}`."
            )
            event_log_store.append_event("System", "LLM Failure", f"Model {model} failed: {err_msg}")
            
            if not model.lower().startswith("groq/"):
                fallback_model = "groq/deepseek-r1-distill-70b"
                logger.warning(f"[{self.name}] Falling back to Groq API ({fallback_model})...")
                await slack_client.post_message(
                    "#agent-log",
                    f"🔄 *[{self.name}]* Falling back to Groq API using model `{fallback_model}`..."
                )
                event_log_store.append_event(self.name, "LLM Fallback", f"Calling fallback {fallback_model}")
                try:
                    fallback_result = await self._call_groq(prompt, system_prompt, fallback_model)
                    if fallback_result:
                        logger.info(f"[{self.name}] Fallback to Groq succeeded.")
                        await slack_client.post_message(
                            "#agent-log",
                            f"✅ *[{self.name}]* Fallback to Groq succeeded."
                        )
                        return fallback_result
                except Exception as fallback_err:
                    fallback_err_msg = f"{type(fallback_err).__name__}: {str(fallback_err)}"
                    logger.error(f"[{self.name}] Fallback to Groq also failed: {fallback_err_msg}")
                    await slack_client.post_message(
                        "#sprint-main",
                        f"❌ *[{self.name}]* Fallback to Groq also failed: `{fallback_err_msg}`"
                    )
                    event_log_store.append_event("System", "Fallback Failure", f"Groq fallback failed: {fallback_err_msg}")
                    raise fallback_err
            raise e

    async def _call_live(self, prompt: str, system_prompt: str, model: str) -> str:
        """Routes to the correct provider and returns raw response text."""
        model_lower = model.lower()

        if model_lower.startswith("groq/"):
            return await self._call_groq(prompt, system_prompt, model_lower)

        return await self._call_eastrouter(prompt, system_prompt, model)

    async def _call_groq(self, prompt: str, system_prompt: str, model: str) -> str:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in .env")

        groq_model = GROQ_MODELS.get(model)
        if not groq_model:
            groq_model = model.replace("groq/", "")

        logger.info(f"[{self.name}] → Groq: {groq_model}")

        import httpx
        async with httpx.AsyncClient(timeout=180.0) as client:
            res = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": groq_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 4096,
                },
            )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"] or ""

    async def _call_eastrouter(self, prompt: str, system_prompt: str, model: str) -> str:
        if not settings.EASTROUTER_API_KEY:
            raise RuntimeError("EASTROUTER_API_KEY is not set in .env")

        eastrouter_model = _resolve_eastrouter_model(model)
        eastrouter_url = getattr(settings, "EASTROUTER_BASE_URL", "https://eastrouter.ai/v1")
        logger.info(f"[{self.name}] → EastRouter API: {eastrouter_model}")
        
        import httpx
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                payload = {
                    "model": eastrouter_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                }
                
                res = await client.post(
                    f"{eastrouter_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.EASTROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                
                if res.status_code != 200:
                    logger.error(f"[{self.name}] EastRouter returned {res.status_code}: {res.text}")
                    res.raise_for_status()
                
                data = res.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    logger.warning(f"[{self.name}] Empty response from EastRouter API")
                return content
                
        except Exception as e:
            logger.error(f"[{self.name}] EastRouter API error: {type(e).__name__}: {e}")
            raise


