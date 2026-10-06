"""Which model does a router pick for each question, at each setting?

Sends every question once with the agent's system prompt and tools and asks for a single
token, so it costs little: the router decides before generation. FireRouter is probed at
routing preferences; OpenRouter's Auto Router at cost tiers ("default" sends no tier).
A hard reasoning prompt rides along as a control. Calls are logged to results/ so their
cost counts toward the project's spend cap.

Usage:
    python route_probe.py fireworks 2 3
    python route_probe.py openrouter default low medium high xhigh max
"""

import csv
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import litellm
from dotenv import load_dotenv

from agent import SYSTEM, TOOLS
from config import CONFIGS, RESULTS_DIR
from questions import TURNS

CONTROL = ("Prove or disprove: for every integer n > 1, there is a prime between n and 2n. "
           "Give a rigorous proof sketch and name the theorem.")
TIERS = ["easy", "medium", "hard", "expert", "control"]


def route(router, setting, question):
    kwargs = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
              "tools": TOOLS, "max_tokens": 1}
    if router == "fireworks":
        kwargs |= {"model": CONFIGS["fw-auto"]["model"], "extra_headers": {"x-routing-preference": setting}}
    else:
        body = {"usage": {"include": True}}
        if setting != "default":
            body["plugins"] = [{"id": "auto-router", "cost_tier": setting}]
        kwargs |= {"model": CONFIGS["or-auto"]["model"], "extra_body": body}
    resp = litellm.completion(**kwargs)
    cost = getattr(resp.usage, "cost", None) or resp._hidden_params.get("response_cost") or 0
    return resp.model.rsplit("/", 1)[-1], float(cost)


def main():
    load_dotenv()
    litellm.suppress_debug_info = True
    router, settings = sys.argv[1], sys.argv[2:]
    questions = [(tid, t["tier"], t["question"]) for tid, t in TURNS.items()] + [("control", "control", CONTROL)]
    jobs = [(setting, tid, tier, q) for setting in settings for tid, tier, q in questions]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda j: (j[0], j[1], j[2], *route(router, j[0], j[3])), jobs))

    out = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_route-probe-{router}"
    out.mkdir(parents=True)
    with (out / "calls.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["router", "setting", "turn_id", "tier", "chosen_model", "cost_usd"])
        w.writerows([router, *r] for r in results)

    picks = defaultdict(Counter)
    for setting, _, tier, model, _ in results:
        picks[(setting, tier)][model] += 1
    for setting in settings:
        print(f"{router} {setting}")
        for tier in TIERS:
            print(f"  {tier:<8} " + ", ".join(f"{m} x{n}" for m, n in picks[(setting, tier)].most_common()))
    print(f"cost ${sum(r[4] for r in results):.4f}; saved {out}/calls.csv")


if __name__ == "__main__":
    main()
