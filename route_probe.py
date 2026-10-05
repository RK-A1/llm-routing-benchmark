"""Which model does FireRouter pick for each question, at a given routing preference?

Sends every question once with the agent's system prompt and tools, asking for a single
token, so it costs fractions of a cent: the router decides before generation. A hard
reasoning prompt rides along as a control.

Usage:
    python route_probe.py           # preferences 2 and 3, two tries each
    python route_probe.py 1 2 3
"""

import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import litellm
from dotenv import load_dotenv

from agent import SYSTEM, TOOLS
from config import CONFIGS
from questions import TURNS

CONTROL = ("Prove or disprove: for every integer n > 1, there is a prime between n and 2n. "
           "Give a rigorous proof sketch and name the theorem.")
TIERS = ["easy", "medium", "hard", "expert", "control"]


def route(question, pref):
    resp = litellm.completion(
        model=CONFIGS["fw-auto"]["model"], max_tokens=1, tools=TOOLS,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
        extra_headers={"x-routing-preference": str(pref)})
    return resp.model.rsplit("/", 1)[-1], resp._hidden_params.get("response_cost") or 0


def main():
    load_dotenv()
    litellm.suppress_debug_info = True
    prefs = [int(p) for p in sys.argv[1:]] or [2, 3]
    questions = [(t["tier"], t["question"]) for t in TURNS.values()] + [("control", CONTROL)]
    jobs = [(tier, q, pref) for tier, q in questions for pref in prefs for _ in range(2)]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda j: (j[0], j[2], *route(j[1], j[2])), jobs))

    picks, cost = defaultdict(Counter), 0.0
    for tier, pref, model, c in results:
        picks[(tier, pref)][model] += 1
        cost += c
    for pref in prefs:
        print(f"preference {pref}")
        for tier in TIERS:
            print(f"  {tier:<8} " + ", ".join(f"{m} x{n}" for m, n in picks[(tier, pref)].most_common()))
    print(f"cost ${cost:.4f}")


if __name__ == "__main__":
    main()
