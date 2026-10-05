"""Summarize one or more run directories: prints the tables and writes report.md.

Usage:
    python report.py results/<run_dir> [more run dirs]   # a config in several runs is taken from the last one
"""

import argparse
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()
TIERS = ["easy", "medium", "hard", "expert"]


def load(dirs):
    """Combine runs; when a config appears in several, the last directory given wins."""
    runs = [pd.read_csv(Path(d) / "turns.csv") for d in dirs]
    turns = pd.concat([t[~t["config"].isin(set().union(*(set(r["config"]) for r in runs[i + 1:])))]
                       for i, t in enumerate(runs)])
    turns["correct"] = turns["correct"].astype(str).str.lower() == "true"
    turns["model"] = turns["first_model"].astype(str).str.rsplit("/", n=1).str[-1]
    return turns


def pct(x):
    return (100 * x).round(0)


def accuracy(turns):
    t = turns.pivot_table(index="config", columns="tier", values="correct", aggfunc="mean").reindex(columns=TIERS)
    t["all"] = turns.groupby("config")["correct"].mean()
    return pct(t)


def cost(turns):
    g = turns.groupby("config")
    t = pd.DataFrame({
        "answers": g.size(),
        "correct": g["correct"].sum(),
        "total $": g["cost_usd"].sum().round(3),
        "LiteLLM-computed $": g["litellm_cost_usd"].sum().round(3),
        "$ / answer": g["cost_usd"].mean().round(4),
        "LLM calls / answer": g["steps"].mean().round(1),
        "LLM seconds / answer": g["latency_s"].mean().round(1),
    })
    t.insert(4, "$ / correct answer", (t["total $"] / t["correct"].where(t["correct"] > 0)).round(4))
    return t


def threshold(turns):
    """Which model served each turn's first call (when the router sees the new question), by tier."""
    rows = []
    for cfg, g in turns.groupby("config"):
        rows.append({"config": cfg, **{tier: ", ".join(f"{m} {s:.0%}" for m, s in g[g["tier"] == tier]["model"]
                                                       .value_counts(normalize=True).items()) for tier in TIERS}})
    return pd.DataFrame(rows).set_index("config")


def routing(turns):
    """Where does the router change models: inside a tool loop, between user turns, between repeats?"""
    per_conv = turns.groupby(["config", "item", "repeat"])["first_model"].nunique()
    per_turn = turns.groupby(["config", "turn_id"])["first_model"].nunique()
    t = pd.DataFrame({
        "answers with a switch inside the tool loop %": pct(turns.groupby("config")["n_switches"]
                                                            .apply(lambda s: (s > 0).mean())),
        "conversations whose turns start on different models %": pct((per_conv > 1).groupby("config").mean()),
        "turns that start on the same model in every repeat %": pct((per_turn == 1).groupby("config").mean())
        if turns["repeat"].max() > 1 else None,
    })
    return t


def failures(turns):
    wrong = turns[~turns["correct"]].copy()
    wrong["mode"] = wrong.apply(lambda r: r["end"] if r["end"] != "submitted" else
                                "final SQL error" if str(r["reason"]).startswith("final SQL") else "wrong result",
                                axis=1)
    t = wrong.pivot_table(index="config", columns="mode", values="turn_id", aggfunc="count", fill_value=0)
    g = turns.groupby("config")
    t["nudged"] = g["nudged"].apply(lambda s: s.astype(str).str.lower().eq("true").sum())
    t["SQL errors"] = g["failed_sql"].apply(lambda s: s.str.count('"error"').sum())
    t["repeated SQL"] = g["repeated_sql"].sum()
    return t


def per_turn(turns):
    t = turns.pivot_table(index=["tier", "turn_id"], columns="config", values="correct", aggfunc="mean")
    return pct(t).reindex(TIERS, level=0)


def show(title, df):
    if df.empty:
        return
    table = Table(title=title)
    flat = df.reset_index()
    for c in flat.columns:
        table.add_column(str(c), overflow="fold")
    for _, r in flat.iterrows():
        table.add_row(*["" if pd.isna(v) else str(v) for v in r])
    console.print(table)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dirs", nargs="+")
    a = p.parse_args()
    turns = load(a.dirs)
    sections = [
        ("Accuracy %", accuracy(turns)),
        ("Cost", cost(turns)),
        ("Routing threshold: model on each turn's first call, by tier", threshold(turns)),
        ("Routing behaviour", routing(turns)),
        ("Failure modes (wrong answers by cause, plus counters)", failures(turns)),
        ("Accuracy % per question", per_turn(turns)),
    ]
    md = [f"# Results\n\nRuns: {', '.join(Path(d).name for d in a.dirs)}\n"]
    for title, df in sections:
        show(title, df)
        if not df.empty:
            md.append(f"## {title}\n\n{df.to_markdown()}\n")
    out = Path(a.dirs[0]) / "report.md"
    out.write_text("\n".join(md))
    console.print(f"Wrote {out}")


if __name__ == "__main__":
    main()
