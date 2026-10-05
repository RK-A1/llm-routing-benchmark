# sql-agent-router-bench

This project asks a simple question: when an AI agent does multi-step work, does a model router pick the right
model for each step, and what does that save? To find out, I built one text-to-SQL agent and ran the same
24-question analyst session through five setups. One calls Claude Opus 5.5 directly, two use Fireworks' FireRouter,
one uses OpenRouter's auto router, and one uses GLM-5.3 Flash, a cheap open model with no routing at all. Every
answer is graded automatically, so the comparison comes down to accuracy, cost per correct answer, and which model
each router chose at each step. All calls go through [LiteLLM](https://github.com/BerriAI/litellm), and the whole
project is budgeted at under $20.

## What I've found so far

The full run is still pending, because the Claude Opus and OpenRouter setups need API credits. Calibration runs on
the open models, which have cost less than a dollar, already show a clear pattern.

| Accuracy by difficulty | Easy | Medium | Hard | Expert |
|---|---|---|---|---|
| GLM-5.3 Flash, no routing (2 runs) | 100% | 100% | 88% | 100% |
| FireRouter `auto` (1 run) | 100% | 100% | 100% | 100% |

The cheapest model is close to enough for this workload. I made the questions harder three times, adding multi-step
SQL, data errors that the question doesn't mention, and long compound requests, and GLM-5.3 Flash still answered 88
to 100 percent of each difficulty tier correctly.

FireRouter reaches the same conclusion on its own. At routing preference 3, it sent every SQL question, from the
easiest to the most complex, to GLM-5.3, and removing the agent's system prompt and tools made no difference. At
preference 2, an expert question occasionally went to Kimi K3, and at preference 1 every request goes to Kimi K3. A
control prompt asking for a mathematical proof went to Kimi K3 at both 2 and 3, so the router does escalate requests
it judges to be hard; it simply doesn't judge SQL analytics to be hard. On this workload, the routing preference
decides which model runs far more than the difficulty of the question does.

The open questions for the full run are what Claude Opus buys on top of that, and whether OpenRouter's router makes
different choices.

## How it works

The data is a small warehouse of James Webb Space Telescope photos from my
[jwst-image-pipeline](https://github.com/RK-A1/jwst-image-pipeline) project. It has 4,345 photos, 1,077
model-generated labels and 481 published images, stored as parquet files in `data/` and loaded into DuckDB.

The agent in `agent.py` is a single tool-calling loop that every setup shares, with the same system prompt and the
same four tools. It can list the tables, describe a table and run read-only SQL, and it finishes each question by
submitting the one query whose result is its answer. The grader in `check.py` re-runs that query and compares the
result with a reference answer, so nothing depends on parsing prose. Row order, column names and extra columns don't
affect the grade, and numbers are compared with a small tolerance.

The questions in `questions.py` form four analyst conversations of six turns each. The history carries over from one
turn to the next, so later questions can refer to earlier answers. Every conversation follows the same difficulty
pattern: easy, medium, hard, easy, expert, easy. An easy question needs a single count, a medium one needs a join or
a grouping, a hard one needs window functions or a ranking within groups, and an expert one asks for three or four
related results at once. The hard and expert questions also run into real problems in the data that the question
never mentions, such as photos dated in the year 2124, instrument values like "unknown" that aren't instruments, and
the same galaxy spelled two different ways. The system prompt gives every model the same warning that the data
contains errors, along with today's date.

Every LLM call is logged with the model that actually served it, its token counts and latency, and two cost figures:
the cost the provider reported and the cost LiteLLM computed from its own price list. Comparing the two shows
whether a gateway's cost tracking still holds when a router chooses the model. On FireRouter they have matched
exactly so far.

## Setups

| Setup | LiteLLM model | Runs |
|---|---|---|
| `claude-opus` | `anthropic/claude-opus-5-5` | 1 |
| `fw-firerouter-opus` | `fireworks_ai/accounts/fireworks/routers/firerouter/opus`, preference 3 | 3 |
| `fw-auto` | `fireworks_ai/accounts/fireworks/routers/auto`, preference 3 | 3 |
| `or-auto` | `openrouter/openrouter/auto` | 3 |
| `glm-flash` | `fireworks_ai/accounts/fireworks/models/glm-5p3-flash` | 1 |

The routers run three times so I can see whether they make the same choice for the same question. The fixed models
run once.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env                 # add Fireworks, Anthropic and OpenRouter keys
python build_local.py                # build data/jwst.duckdb from the parquet files
python check.py --freeze --selftest  # compute the reference answers and test the grader
python run.py --configs scripted     # a free end-to-end check that replays the reference SQL

python run.py --label full           # the full run
python report.py results/<run_dir>   # accuracy, cost and routing tables, also written to report.md
python route_probe.py                # which model FireRouter picks for each question, for fractions of a cent
```

Each run writes `calls.csv` with one row per LLM call, `turns.csv` with one graded row per answer, and
`transcripts.jsonl` with every full conversation. A spend cap in `config.py` stops any run once the project as a
whole has spent $18, counting every run in `results/`. I expect the full run to cost between $5 and $10.
