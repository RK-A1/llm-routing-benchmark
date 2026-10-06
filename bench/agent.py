"""The text-to-SQL agent: one loop, the same prompt and tools for every provider.

For each user turn the agent explores with list_tables / describe_table / run_sql and ends
the turn by calling submit_answer with the one query whose result answers it. The grader
re-runs that query, so prose answers are never parsed. In a multi-turn conversation the
whole history, tool calls included, carries over to the next user turn.
"""

import json
import re
from collections import Counter

from .config import MAX_STEPS

SYSTEM = """You answer questions about a database of James Webb Space Telescope photos by writing SQL.

The database is DuckDB. It is read-only. Explore it with the tools, check your assumptions against \
the data, and then call submit_answer with the single SQL query whose result answers the question. \
The user may ask follow-up questions that refer to earlier answers.

Today is 2026-10-05. The data has quality problems, such as values that can't be right. Sanity-check \
what you find, and leave out values that are clearly errors.

The submitted query's result is the answer, so make it return exactly the rows asked for. Extra \
columns are fine. Don't round unless the question asks you to."""

NUDGE = "Please call submit_answer with the SQL query that answers the question."


def fn(name, description, properties=None, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": list(required)}}}


SQL_PARAM = {"sql": {"type": "string", "description": "One read-only SQL query."}}
TOOLS = [
    fn("list_tables", "List the tables in the database with row counts and descriptions."),
    fn("describe_table", "Show a table's columns and types.",
       {"table": {"type": "string", "description": "Table name."}}, ["table"]),
    fn("run_sql", "Run a read-only SQL query and see up to 50 rows of its result.", SQL_PARAM, ["sql"]),
    fn("submit_answer", "Submit the final SQL query for the current question. Its full result is your answer. "
       "Call this once, last.", SQL_PARAM, ["sql"]),
]


def sql_from_text(text):
    """Fallback when a model answers in prose: take its last ```sql block."""
    blocks = re.findall(r"```(?:sql)?\s*(.*?)```", text or "", flags=re.DOTALL | re.IGNORECASE)
    return blocks[-1].strip() if blocks else None


def run_tool(db, name, args, s):
    """Execute one tool call; returns the text the model sees."""
    if name == "list_tables":
        return db.list_tables()
    if name == "describe_table":
        return db.describe_table(str(args.get("table", "")))
    if name == "run_sql":
        sql = str(args.get("sql", ""))
        r = db.run_sql(sql)
        s["n_sql"] += 1
        s["sql_time_s"] += r["elapsed_s"]
        s["_seen"][sql.strip()] += 1
        if not r["ok"]:
            s["failed_sql"].append({"sql": sql, "error": r["error"]})
        return r["text"]
    if name == "submit_answer":
        s["final_sql"], s["answer_source"] = str(args.get("sql", "")), "submit"
        return "Submitted."
    return f"ERROR: unknown tool {name!r}."


def run_turn(call, db, messages, question, on_call, budget_ok):
    """Append one user turn and run the tool loop until the agent submits. Returns the turn summary."""
    messages.append({"role": "user", "content": question})
    s = {"final_sql": None, "answer_source": None, "end": None, "steps": 0, "n_sql": 0, "failed_sql": [],
         "sql_time_s": 0.0, "nudged": False, "models": [], "cost_usd": 0.0, "litellm_cost_usd": 0.0,
         "latency_s": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "_seen": Counter()}

    for step in range(1, MAX_STEPS + 1):
        if not budget_ok():
            s["end"] = "spend_cap"
            break
        try:
            assistant, meta = call(messages)
        except Exception as e:
            on_call(step, {"chosen_model": f"ERROR: {e.__class__.__name__}", "error": str(e)[:500]})
            s["end"], s["error"] = "api_error", f"{e.__class__.__name__}: {str(e)[:300]}"
            break
        s["steps"] = step
        s["models"].append(meta["chosen_model"])
        for k in ("cost_usd", "litellm_cost_usd", "latency_s", "prompt_tokens", "completion_tokens"):
            s[k] += meta.get(k) or 0
        on_call(step, meta)
        messages.append(assistant)

        calls = assistant.get("tool_calls") or []
        if not calls:
            if meta["finish_reason"] == "length":
                s["end"] = "truncated"
                break
            if not s["nudged"]:
                # One reminder, the same for every provider. Reported as a failure mode.
                s["nudged"] = True
                messages.append({"role": "user", "content": NUDGE})
                continue
            if sql := sql_from_text(assistant.get("content")):
                s["final_sql"], s["answer_source"] = sql, "text"
            s["end"] = "text_answer" if sql else "no_answer"
            break

        for tc in calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
                result = run_tool(db, tc["function"]["name"], args, s)
            except json.JSONDecodeError:
                result = "ERROR: arguments were not valid JSON."
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
        if s["answer_source"] == "submit":
            s["end"] = "submitted"
            break
    else:
        s["end"] = "max_steps"

    s["repeated_sql"] = sum(n - 1 for n in s.pop("_seen").values())
    for k in ("sql_time_s", "cost_usd", "litellm_cost_usd", "latency_s"):
        s[k] = round(s[k], 6)
    return s


def run_conversation(call, db, turns, on_call, budget_ok=lambda: True):
    """Run every user turn in one shared history. Yields (turn, summary); stops on API errors or the budget."""
    messages = [{"role": "system", "content": SYSTEM}]
    for turn in turns:
        s = run_turn(call, db, messages, turn["question"], lambda step, meta: on_call(turn, step, meta), budget_ok)
        yield turn, s, messages
        if s["end"] in ("api_error", "spend_cap"):
            return
