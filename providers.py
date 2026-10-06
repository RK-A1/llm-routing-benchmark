"""One LiteLLM call for every provider: Anthropic, Fireworks (FireRouter and a fixed model), OpenRouter.

Returns (assistant_message, meta). The assistant message is OpenAI-shaped and goes straight
back into the history; meta holds the per-call log fields.

Cost comes from the provider when it reports one (FireRouter's x-litellm-response-cost
header, OpenRouter's usage.cost) and from LiteLLM's price map otherwise. LiteLLM's own figure
is logged too; for OpenRouter it simply passes through usage.cost.
"""

import os
import time

import litellm

from config import MAX_TOKENS

litellm.suppress_debug_info = True


def call(cfg, messages, tools):
    headers, extra_body = {}, {}
    if "routing_pref" in cfg:
        # FireRouter: 1 = max intelligence ... 5 = max savings.
        headers["x-routing-preference"] = str(cfg["routing_pref"])
        # Claude turns inside a FireRouter route bill to our own Anthropic key.
        if "opus" in cfg["model"]:
            headers["x-anthropic-api-key"] = os.environ["ANTHROPIC_API_KEY"]
    if cfg["model"].startswith("openrouter/"):
        extra_body["usage"] = {"include": True}  # OpenRouter returns the billed cost in usage.cost
        if "cost_tier" in cfg:  # Auto Router band: low, medium, high, xhigh or max
            extra_body["plugins"] = [{"id": "auto-router", "cost_tier": cfg["cost_tier"]}]

    start = time.perf_counter()
    resp = litellm.completion(model=cfg["model"], messages=messages, tools=tools, max_tokens=MAX_TOKENS,
                              extra_headers=headers or None, extra_body=extra_body or None,
                              num_retries=2, timeout=300)
    latency = time.perf_counter() - start

    msg = resp.choices[0].message
    usage = resp.usage
    hdrs = resp._hidden_params.get("additional_headers") or {}
    litellm_cost = resp._hidden_params.get("response_cost")
    provider_cost = hdrs.get("llm_provider-x-litellm-response-cost") or getattr(usage, "cost", None)
    # A provider-reported 0 for a paid model means the turn billed elsewhere (e.g. FireRouter's
    # Claude turns go to the Anthropic key), so fall back to LiteLLM's estimate.
    if provider_cost is not None and float(provider_cost) > 0:
        cost, source = float(provider_cost), "provider"
    else:
        cost, source = litellm_cost, "litellm"

    assistant = {"role": "assistant", "content": msg.content or None}  # None, not "", for Claude
    if msg.tool_calls:
        assistant["tool_calls"] = [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls]
    if getattr(msg, "thinking_blocks", None):
        assistant["thinking_blocks"] = msg.thinking_blocks  # Claude needs these replayed unchanged

    cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None)
    reasoning = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None)
    meta = {
        "chosen_model": resp.model,  # the model that actually served the call, for routers too
        "finish_reason": resp.choices[0].finish_reason,
        "prompt_tokens": usage.prompt_tokens,
        "cached_tokens": cached,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": reasoning,
        "cost_usd": round(cost, 6) if cost is not None else None,
        "cost_source": source if cost is not None else "unknown",
        "litellm_cost_usd": round(litellm_cost, 6) if litellm_cost is not None else None,
        "latency_s": round(latency, 2),
        "trace_id": hdrs.get("llm_provider-x-firerouter-trace-id") or resp.id,
    }
    return assistant, meta
