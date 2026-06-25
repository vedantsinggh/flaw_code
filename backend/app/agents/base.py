import logging
from app.config import settings

logger = logging.getLogger("forgeos.agent")

# ── Model name → provider mapping ─────────────────────────────────────────────
# Ollama local models
OLLAMA_MODELS = {
    "qwen2.5-coder:7b":    "qwen2.5-coder:7b",
    "deepseek-r1:1.5b":    "qwen2.5-coder:7b",
}

# Groq cloud models (fast inference)
GROQ_MODELS = {
    "groq/llama-3.3-70b":           "llama-3.3-70b-versatile",
    "groq/deepseek-r1-distill-70b": "deepseek-r1-distill-llama-70b",
    "groq/llama-3.1-8b":            "llama-3.1-8b-instant",
    "groq/qwen-qwq-32b":            "qwen-qwq-32b",
    "groq/mixtral-8x7b":            "mixtral-8x7b-32768",
}


def _resolve_ollama_model(model_key: str) -> str:
    """Returns the Ollama model tag for a given router model name."""
    key = model_key.lower()
    for k, v in OLLAMA_MODELS.items():
        if k in key:
            return v
    # Sensible fallback
    if "deepseek" in key:
        return "deepseek-r1:1.5b"
    if "qwen" in key:
        return "qwen2.5-coder:7b"
    return model_key


class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    async def call_llm(self, prompt: str, system_prompt: str, model: str) -> str:
        """
        Executes an LLM request against the configured provider stack:

        Provider selection (SIMULATION_MODE=false):
        1. If model starts with "groq/" → Groq API (requires GROQ_API_KEY)
        2. If model matches a known Ollama model → Ollama local API
        3. Fallback → Ollama with qwen2.5-coder
        """
        logger.info(f"[{self.name}] model={model} prompt_len={len(prompt)}")

        if settings.SIMULATION_MODE:
            raise RuntimeError(f"[{self.name}] Simulation mode is enabled, but mock data and simulation fallbacks have been removed.")

        try:
            result = await self._call_live(prompt, system_prompt, model)
            if not result:
                raise RuntimeError(f"[{self.name}] Live LLM call returned empty response")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Live LLM call failed ({model}): {e}")
            raise

    async def _call_live(self, prompt: str, system_prompt: str, model: str) -> str:
        """Routes to the correct provider and returns the raw response text."""
        model_lower = model.lower()

        # ── Groq ──────────────────────────────────────────────────────────────
        if model_lower.startswith("groq/"):
            return await self._call_groq(prompt, system_prompt, model_lower)

        # ── Ollama (Qwen / DeepSeek local) ────────────────────────────────────
        return await self._call_ollama(prompt, system_prompt, model)

    async def _call_groq(self, prompt: str, system_prompt: str, model: str) -> str:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in .env")

        groq_model = GROQ_MODELS.get(model)
        if not groq_model:
            # Accept any groq/ prefixed model name as-is after stripping the prefix
            groq_model = model.replace("groq/", "")

        logger.info(f"[{self.name}] → Groq: {groq_model}")

        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
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

    async def _call_ollama(self, prompt: str, system_prompt: str, model: str) -> str:
        ollama_model = _resolve_ollama_model(model)
        logger.info(f"[{self.name}] → Ollama: {ollama_model}")
        
        import httpx
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.2},
                }
                
                # Log the request
                logger.info(f"[{self.name}] Sending request to Ollama")
                
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                )
                
                # Log response status
                logger.info(f"[{self.name}] Response status: {res.status_code}")
                
                # Check if response is valid
                if res.status_code != 200:
                    logger.error(f"[{self.name}] Ollama returned {res.status_code}: {res.text}")
                    res.raise_for_status()
                
                # Parse response
                try:
                    data = res.json()
                    logger.info(f"[{self.name}] Response parsed successfully")
                    content = data.get("message", {}).get("content", "")
                    if not content:
                        logger.warning(f"[{self.name}] Empty response from Ollama")
                    return content
                except Exception as json_err:
                    logger.error(f"[{self.name}] Failed to parse JSON: {json_err}")
                    logger.error(f"[{self.name}] Response text: {res.text[:500]}")
                    raise
                
        except httpx.TimeoutException as e:
            logger.error(f"[{self.name}] Ollama timeout: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.name}] HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[{self.name}] Unexpected error: {type(e).__name__}: {e}")
            logger.error(f"[{self.name}] Error details: {str(e)}")
            raise


