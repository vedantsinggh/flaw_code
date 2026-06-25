import logging
from typing import Dict, Any

logger = logging.getLogger("forgeos.router")


class IntelligentRouter:
    """
    Routes tasks to one of three tiers:

    Tier 1 — Easy   → qwen2.5-coder:7b  (Ollama local, fastest, free)
    Tier 2 — Medium → deepseek-r1:14b   (Ollama local, strong reasoning, free)
    Tier 3 — Hard   → groq/deepseek-r1-distill-70b  (Groq cloud, heaviest reasoning)

    All cost figures are estimates based on Groq public pricing.
    Ollama local tiers cost $0.00.
    """

    PRICES = {
        "qwen2.5-coder:7b":                  {"input": 0.0000, "output": 0.0000},  # local
        "deepseek-r1:1.5b":                  {"input": 0.0000, "output": 0.0000},  # local
        "groq/deepseek-r1-distill-70b":      {"input": 0.00075, "output": 0.00099},  # Groq
        "groq/llama-3.3-70b":               {"input": 0.00059, "output": 0.00079},  # Groq
        "groq/qwen-qwq-32b":                {"input": 0.00029, "output": 0.00039},  # Groq
    }

    def route_task(self, task_description: str) -> Dict[str, Any]:
        """
        Analyses the task description and returns a routing decision.
        """
        task_lower = task_description.lower()

        # ── Feature analysis ───────────────────────────────────────────────────
        reasoning_complexity = "Low"
        architectural_impact = "Low"
        ambiguity            = "Low"
        dependency_count     = 0
        expected_loc         = 80

        if any(w in task_lower for w in ["auth", "security", "encrypt", "refactor", "migrate"]):
            reasoning_complexity = "Medium"
            dependency_count += 2

        if any(w in task_lower for w in ["database", "migration", "docker", "compose", "kafka"]):
            architectural_impact = "Medium"
            dependency_count += 3

        if any(w in task_lower for w in ["architect", "design", "full system", "pipeline", "orchestrat", "distributed"]):
            reasoning_complexity = "High"
            ambiguity            = "Medium"
            architectural_impact = "High"

        if "fastapi" in task_lower or "crud" in task_lower:
            expected_loc = 150
        elif "react" in task_lower or "dashboard" in task_lower:
            expected_loc = 350

        # ── Tier selection ─────────────────────────────────────────────────────
        # Tier 1 — Qwen2.5-Coder local (easy, fast code tasks)
        selected_model = "qwen2.5-coder:7b"
        difficulty     = "Easy"
        reason         = "Simple, well-scoped code task routed to Qwen2.5-Coder 7B running locally via Ollama."
        confidence     = 0.95
        est_tokens     = 2500
        est_time       = 300
        budget         = 0.00

        # Tier 2 — DeepSeek-R1 local (medium reasoning, dependency-heavy)
        if reasoning_complexity == "Medium" or expected_loc > 100 or dependency_count > 2:
            selected_model = "deepseek-r1:1.5b"
            difficulty     = "Medium"
            reason         = "Medium complexity with dependency or reasoning requirements routed to DeepSeek-R1 1.5B locally via Ollama."
            confidence     = 0.90
            est_tokens     = 6000
            est_time       = 180
            budget         = 0.00

        # Tier 3 — Groq DeepSeek-R1 distill 70B (architectural / high complexity)
        if reasoning_complexity == "High" or architectural_impact == "High" or ambiguity == "Medium":
            selected_model = "groq/deepseek-r1-distill-70b"
            difficulty     = "Complex"
            reason         = "High-complexity architectural reasoning routed to DeepSeek-R1-Distill 70B on Groq for fast cloud inference."
            confidence     = 0.88
            est_tokens     = 15000
            est_time       = 90   # Groq is very fast even at 70B
            budget         = 0.02

        # ── Cost estimate ──────────────────────────────────────────────────────
        rates      = self.PRICES.get(selected_model, {"input": 0.0, "output": 0.0})
        input_tok  = int(est_tokens * 0.4)
        output_tok = int(est_tokens * 0.6)
        est_cost   = (input_tok / 1_000_000) * rates["input"] * 1000 + \
                     (output_tok / 1_000_000) * rates["output"] * 1000

        decision = {
            "selected_model":                 selected_model,
            "difficulty":                     difficulty,
            "reason":                         reason,
            "estimated_tokens":               est_tokens,
            "estimated_cost":                 round(est_cost, 6),
            "estimated_completion_time_seconds": est_time,
            "confidence":                     confidence,
            "expected_loc":                   expected_loc,
            "dependency_count":               dependency_count,
            "reasoning_complexity":           reasoning_complexity,
            "architectural_impact":           architectural_impact,
            "ambiguity":                      ambiguity,
            "budget":                         budget,
        }

        logger.info(f"[ROUTER] {selected_model} | {difficulty} | tokens≈{est_tokens} | cost≈${est_cost:.6f}")
        return decision


intelligent_router = IntelligentRouter()
