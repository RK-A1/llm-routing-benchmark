"""Configs, limits and the budget. Everything a run depends on lives here."""

from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
LOCAL_DB = DATA_DIR / "jwst.duckdb"
EXPECTED = ROOT / "expected.json"  # reference answers, frozen by check.py --freeze

# Agent limits.
MAX_STEPS = 12          # LLM calls per user turn
MAX_TOKENS = 8000       # per LLM call, thinking included
ROW_CAP = 50            # rows shown to the model per run_sql
CHAR_CAP = 6000         # characters shown to the model per tool result
SQL_TIMEOUT_S = 20

# Hard stop for the whole project, in USD: every run in results/ counts toward it.
SPEND_CAP = 18.0

# Every config is one LiteLLM model string. Fixed models run once; routers run 3 times
# so routing consistency can be measured.
FIREWORKS_ROUTERS = "fireworks_ai/accounts/fireworks/routers"
CONFIGS = {
    # Quality ceiling: everything on Claude Opus 5.5 (default effort, medium).
    "claude-opus": {"model": "anthropic/claude-opus-5-5", "repeats": 1},
    # FireRouter, may escalate to Opus. Those turns bill to our own Anthropic key.
    "fw-firerouter-opus": {"model": f"{FIREWORKS_ROUTERS}/firerouter/opus", "routing_pref": 3, "repeats": 3},
    # FireRouter, open models only.
    "fw-auto": {"model": f"{FIREWORKS_ROUTERS}/auto", "routing_pref": 3, "repeats": 3},
    # OpenRouter's Auto Router. With no cost_tier set it routes "roughly the low band" and
    # prefers the model a conversation already landed on ("session stickiness").
    "or-auto": {"model": "openrouter/openrouter/auto", "repeats": 3},
    # Cost floor: one cheap open model, no routing.
    "glm-flash": {"model": "fireworks_ai/accounts/fireworks/models/glm-5p3-flash", "repeats": 1},
}

# OpenRouter's Auto Router at higher cost tiers. Not part of the default plan: run them by name.
# route_probe.py showed each tier picks one model for every SQL question (medium: GLM 5.2,
# high: Claude Sonnet 5.5, xhigh: Claude Opus 5.5, max: GPT-6 Astra Pro, about $0.02 a call).
for _tier in ("medium", "high", "xhigh", "max"):
    CONFIGS[f"or-auto-{_tier}"] = {"model": "openrouter/openrouter/auto", "cost_tier": _tier, "repeats": 1,
                                   "extra": True}
DEFAULT_PLAN = [name for name, cfg in CONFIGS.items() if not cfg.get("extra")]
