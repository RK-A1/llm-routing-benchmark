"""Run the question set through the configs and log every LLM call.

Writes to results/<timestamp>_<label>/:
    calls.csv          one row per LLM call (rewritten after every call)
    turns.csv          one row per graded answer (config, item, turn, repeat)
    transcripts.jsonl  full message history per conversation, for reading failures

Spend is a project-wide ledger: every calls.csv under results/ counts toward SPEND_CAP.

Usage:
    python -m bench.run --configs scripted               # offline pipeline test, no API calls
    python -m bench.run                                  # the plan: each config at its own repeat count
    python -m bench.run --configs glm-flash --items c2   # one conversation, a quick look
    python -m bench.run --configs fw-auto --repeats 1
"""

import argparse
import csv
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from rich.console import Console

from . import providers
from .agent import TOOLS, run_conversation
from .check import grade, load_expected
from .config import CONFIGS, DEFAULT_PLAN, RESULTS_DIR, ROOT, SPEND_CAP
from .db import DB
from .questions import TURNS, conversations

console = Console()


def scripted_call(messages):
    """Offline stand-in that answers with the reference SQL: list_tables, run_sql, submit_answer."""
    last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
    sql = next(t["sql"] for t in TURNS.values() if t["question"] == messages[last_user]["content"])
    n = sum(m["role"] == "assistant" for m in messages[last_user:])
    name, args = [("list_tables", {}), ("run_sql", {"sql": sql}), ("submit_answer", {"sql": sql})][min(n, 2)]
    msg = {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"call_{len(messages)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
    return msg, {"chosen_model": "scripted", "finish_reason": "tool_calls", "cost_usd": 0.0, "latency_s": 0.0}


def prior_spend():
    files = list(RESULTS_DIR.glob("*/calls.csv"))
    return sum(pd.read_csv(f)["cost_usd"].fillna(0).sum() for f in files if f.stat().st_size)


class Run:
    """Shared state across config threads: rows, files and the spend ledger."""

    def __init__(self, out_dir, cap):
        self.dir = out_dir
        self.calls, self.turns = [], []
        self.spent = prior_spend()
        self.cap = cap
        self.lock = threading.Lock()

    def budget_ok(self):
        return self.spent < self.cap

    def save(self, rows, name):
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with (self.dir / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    def log_call(self, row):
        with self.lock:
            self.spent += row.get("cost_usd") or 0
            row["project_spend_usd"] = round(self.spent, 4)
            self.calls.append(row)
            self.save(self.calls, "calls.csv")

    def log_turn(self, row):
        with self.lock:
            self.turns.append(row)
            self.save(self.turns, "turns.csv")

    def log_transcript(self, config, item, rep, messages):
        with self.lock, (self.dir / "transcripts.jsonl").open("a") as f:
            f.write(json.dumps({"config": config, "item": item, "repeat": rep, "messages": messages},
                               default=str) + "\n")


def run_config(name, items, repeats, run, expected):
    call = scripted_call if name == "scripted" else (lambda messages: providers.call(CONFIGS[name], messages, TOOLS))
    db = DB()  # one connection per thread
    for rep in range(1, repeats + 1):
        for item in items:
            if not run.budget_ok():
                console.print(f"[red]{name}: spend cap ${run.cap} reached, stopping[/red]")
                return
            base = {"config": name, "item": item["id"], "topic": item["topic"], "repeat": rep}

            def on_call(turn, step, meta):
                run.log_call({**base, "turn_id": turn["id"], "tier": turn["tier"], "step": step,
                              "ts": datetime.now().isoformat(timespec="seconds"), **meta})

            for n, (turn, s, messages) in enumerate(
                    run_conversation(call, db, item["turns"], on_call, run.budget_ok), 1):
                correct, reason = False, s["end"]
                if s["final_sql"]:
                    try:
                        _, rows, _ = db.query(s["final_sql"], 5000)
                        correct, reason = grade(expected[turn["id"]]["rows"], rows, turn.get("tol", 1e-6))
                    except Exception as e:
                        reason = f"final SQL failed: {str(e).splitlines()[0][:200]}"
                models = s.pop("models")
                run.log_turn({**base, "turn_id": turn["id"], "turn": n, "tier": turn["tier"],
                              "correct": correct, "reason": reason, **s,
                              "first_model": models[0] if models else None, "models": "|".join(models),
                              "n_switches": sum(a != b for a, b in zip(models, models[1:])),
                              "failed_sql": json.dumps(s["failed_sql"])})
                mark = "[green]ok[/green]" if correct else f"[red]x[/red] {reason}"
                console.print(f"{name:<19} r{rep} {turn['id']:<5} {mark}  steps={s['steps']} ${s['cost_usd']:.4f}  "
                              f"{','.join(dict.fromkeys(m.rsplit('/', 1)[-1] for m in models))}  "
                              f"(project ${run.spent:.2f})")
            run.log_transcript(name, item["id"], rep, messages)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--configs", default=",".join(DEFAULT_PLAN),
                   help=f"comma-separated, default the plan ({', '.join(DEFAULT_PLAN)}); also: "
                        f"{', '.join(n for n in CONFIGS if n not in DEFAULT_PLAN)}, scripted")
    p.add_argument("--items", help="comma-separated conversation ids, e.g. c1,c3 (default: all)")
    p.add_argument("--repeats", type=int, help="override every config's repeat count")
    p.add_argument("--label", default="run")
    args = p.parse_args()

    load_dotenv(ROOT / ".env")
    names = args.configs.split(",")
    if unknown := [n for n in names if n not in CONFIGS and n != "scripted"]:
        raise SystemExit(f"unknown config(s): {unknown}")
    # Fail before spending anything rather than logging every question as an API error.
    for n in names:
        model = CONFIGS.get(n, {}).get("model", "")
        need = {k for prefix, k in [("anthropic/", "ANTHROPIC_API_KEY"), ("fireworks_ai/", "FIREWORKS_API_KEY"),
                                    ("openrouter/", "OPENROUTER_API_KEY")] if model.startswith(prefix)}
        if "opus" in model:
            need.add("ANTHROPIC_API_KEY")
        if missing := [k for k in need if not os.environ.get(k)]:
            raise SystemExit(f"{n}: set {', '.join(missing)} in .env (or leave {n} out of --configs)")
    items = conversations()
    if args.items:
        items = [c for c in items if c["id"] in args.items.split(",")]
    expected = load_expected()

    out = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{args.label}"
    out.mkdir(parents=True)
    run = Run(out, SPEND_CAP)
    console.print(f"{len(names)} config(s) x {len(items)} item(s); project spend so far "
                  f"${run.spent:.2f} of ${SPEND_CAP} -> {out}")
    with ThreadPoolExecutor(len(names)) as pool:
        futures = [pool.submit(run_config, n, items,
                               args.repeats or CONFIGS.get(n, {}).get("repeats", 1), run, expected)
                   for n in names]
        for f in futures:
            f.result()
    console.print(f"\nDone. Project spend ${run.spent:.2f} of ${SPEND_CAP}. Report: python -m bench.report {out}")


if __name__ == "__main__":
    main()
