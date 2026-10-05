# sql-agent-router-bench

This project asks a simple question: when an AI agent does multi-step work, does a model router pick the right
model for each step, and what does that save? To find out, I built one text-to-SQL agent and ran the same
24-question analyst session through five setups. One calls Claude Opus 5.5 directly, two use Fireworks' FireRouter,
one uses OpenRouter's auto router, and one uses GLM-5.3 Flash, a cheap open model with no routing at all. Every
answer is graded automatically, so the comparison comes down to accuracy, cost per correct answer, and which model
each router chose at each step. All calls go through [LiteLLM](https://github.com/BerriAI/litellm), and the whole
project is budgeted at under $20.

## Results

I ran the full session through every setup on October 5, 2026, three times for each router and once for each fixed
model. The whole project, including calibration, cost $2.78.

| Setup | Correct | Cost per correct answer | Model that actually answered |
|---|---|---|---|
| Claude Opus 5.5, direct | 96% (23 of 24) | $0.048 | Claude Opus 5.5 |
| FireRouter `firerouter/opus` | 97% (70 of 72) | $0.0043 | GLM-5.3 on every turn; Opus was never chosen |
| FireRouter `auto` | 100% (72 of 72) | $0.0042 | GLM-5.3, with GLM-5.3 Flash on a few easy turns |
| OpenRouter `auto` | 100% (72 of 72) | $0.0012 | DeepSeek V4.1 Flash on every call |
| GLM-5.3 Flash, no routing | 98% (47 of 48) | $0.0011 | GLM-5.3 Flash |

Every setup was accurate, and the real difference is cost, which spans a factor of forty. Claude Opus cost about five
cents per correct answer, roughly ten times as much as FireRouter and forty times as much as OpenRouter's router or
GLM-5.3 Flash on its own, and it was no more accurate. Its one miss was an expert question where it removed the
photo dated 2124 when finding an object's first and last year but still counted that photo, which is the same kind
of trap the cheaper models occasionally fell into. With samples this small, a difference of one or two answers
between setups is noise, so the fair reading is that all five are equally accurate on this workload.

Neither router escalated, and on this workload they were right not to. FireRouter's `firerouter/opus` route has
Claude Opus in its pool, but in 72 answers it never chose it, so the Anthropic key was never charged. FireRouter
changed models partway through 8 percent of conversations, dropping some easy turns to GLM-5.3 Flash, and for 92 to
96 percent of turns it made the same first choice in all three repeats. OpenRouter's router picked DeepSeek V4.1 Flash
for every call and never switched. Part of that difference is the defaults: with no cost tier set, OpenRouter routes
in roughly its lowest-cost band, while FireRouter's default preference is "balanced". I kept both on their defaults
because that is what a customer gets out of the box.

To find FireRouter's threshold, `route_probe.py` sends each question to the router alone and records which model it
picks. At routing preference 3, every SQL question, from the easiest to the most complex, went to GLM-5.3, and for the
hardest questions, removing the agent's system prompt and tools made no difference. At preference 2, an expert question occasionally went to Kimi K3, and at
preference 1 every request goes to Kimi K3. A control prompt asking for a mathematical proof went to Kimi K3 at both 2
and 3, so the router does escalate requests it judges to be hard; it simply doesn't judge SQL analytics to be hard. On
this workload, the routing preference decides which model runs far more than the difficulty of the question does.

Cost tracking held up through the routers. For both FireRouter routes and for OpenRouter, the cost the provider billed
matched LiteLLM's own calculation on every one of 709 calls, even though the router, not the caller, chose the
model. Anthropic doesn't return a cost, so the Claude figures are LiteLLM's.

One operational note: during the full run, Fireworks' GLM-5.3 Flash endpoint was overloaded, returning "service
overloaded" errors and taking about 48 seconds per call, so I stopped that part of the run. The GLM-5.3 Flash results
above come from two complete runs earlier the same day on the same questions and grader. The full report is in
`results/20261005_152037_full/report.md`.

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
python report.py results/<run_dir>   # accuracy, cost and routing tables, also written to report.md;
                                     # with several run folders, each setup comes from the last one given
python route_probe.py                # which model FireRouter picks for each question, for fractions of a cent
```

Each run writes `calls.csv` with one row per LLM call, `turns.csv` with one graded row per answer, and
`transcripts.jsonl` with every full conversation. A spend cap in `config.py` stops any run once the project as a
whole has spent $18, counting every run in `results/`. The full run cost $1.81.
