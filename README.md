# sql-agent-router-bench

I built a text-to-SQL agent and ran the same 24 questions through five model setups to measure what model routers
actually do. A model router is a single model ID that you call like any other LLM. Behind it, the router picks which
real model answers each request, so that easy work goes to cheap models and hard work goes to expensive ones.

The five setups are Claude Opus 5.5 called directly, two routes of Fireworks' FireRouter, OpenRouter's Auto Router,
and GLM-5.3 Flash, a cheap open model with no routing. A grader checks every answer automatically, so I can compare
accuracy, cost per correct answer, and which model each router chose. Every call goes through
[LiteLLM](https://github.com/BerriAI/litellm). The whole project cost $6.07 in API fees.

## Results

I ran each router three times, Claude Opus once, and GLM-5.3 Flash twice.

| Setup | Correct | Cost per correct answer | Model that actually answered |
|---|---|---|---|
| Claude Opus 5.5, direct | 96% (23 of 24) | $0.048 | Claude Opus 5.5 |
| FireRouter `firerouter/opus` | 97% (70 of 72) | $0.0043 | GLM-5.3 on every turn; never Opus |
| FireRouter `auto` | 100% (72 of 72) | $0.0042 | GLM-5.3, with GLM-5.3 Flash on a few easy turns |
| OpenRouter `auto` | 100% (72 of 72) | $0.0012 | DeepSeek V4.1 Flash on every call |
| GLM-5.3 Flash, no routing | 98% (47 of 48) | $0.0011 | GLM-5.3 Flash |

**All five setups were equally accurate, but Opus cost about 40 times as much per correct answer.** Opus cost about
five cents per correct answer, ten times as much as FireRouter and forty times as much as OpenRouter's router or GLM-5.3
Flash. Opus missed one expert question: it dropped a photo dated 2124 when it found an object's first and last year,
but still counted that photo. The cheaper models fell for the same kind of trap now and then. With samples this small,
a gap of one or two answers is noise.

**Neither router escalated to a bigger model, and neither needed to.** FireRouter's `firerouter/opus` route can send
work to Claude Opus, but it never did in 72 answers, so it never charged the Anthropic key. FireRouter switched models
partway through 8% of conversations, sending some easy turns to GLM-5.3 Flash. For 92% to 96% of turns, it chose the
same first model in all three runs. OpenRouter's router used DeepSeek V4.1 Flash for every call. Both routers ran on
their defaults, which differ: FireRouter's default preference is "balanced", while OpenRouter's default routes roughly
like its cheapest cost tier.

**The router's setting decides the model, not the difficulty of the question.** `route_probe.py` sends each question
to a router once and records which model it picks. At FireRouter's default preference of 3, every SQL question, from
the easiest to the most complex, went to GLM-5.3. For the hard and expert questions, removing the agent's system
prompt and tools made no difference. At preference 2, an expert question occasionally went to Kimi K3, and at
preference 1, every request goes to Kimi K3. A control prompt that asks for a mathematical proof went to Kimi K3 at
preferences 2 and 3. So FireRouter does escalate requests it judges to be hard; it just doesn't judge SQL analytics
to be hard.

**Paying for a higher OpenRouter cost tier made answers more expensive, not more accurate.** OpenRouter's Auto Router
has five cost tiers. I probed every question at each tier, then ran the full session once at each tier that picked a
different model. I ran the most expensive tier, `max`, on one six-turn conversation only, because each call cost
several cents.

| OpenRouter cost tier | Model it picked | Correct | Cost per correct answer |
|---|---|---|---|
| default or `low` | DeepSeek V4.1 Flash | 100% (72 of 72) | $0.0012 |
| `medium` | GLM 5.2, with GPT-6.1 Sol on 7 of 24 turns | 96% (23 of 24) | $0.0058 |
| `high` | Claude Sonnet 5.5, with GPT-6.1 Sol on 2 turns | 100% (24 of 24) | $0.023 |
| `xhigh` | Claude Opus 5.5 | 96% (23 of 24) | $0.047 |
| `max` | GPT-6 Astra Pro | 100% (6 of 6) | $0.13 |

Each tier cost more than the one below it, and `max` cost more than a hundred times the default per correct answer.
Within a tier, the probe sent every SQL question to the same model, apart from two picks of an older DeepSeek Flash
version at the default tier. The math-proof control moved to Kimi K3 at `medium` and `high`. The `xhigh` tier is
effectively Claude Opus through OpenRouter: it cost $0.047 per correct answer against $0.048 for Opus called directly.
Its one miss repeated a mistake that Opus also made when called directly: on the same hard question, it submitted a
query it had never run, and the query failed.

**Trust the router's reported cost, not a gateway's price list.** For both FireRouter routes, LiteLLM's price list,
applied to the model that actually answered, reproduced the billed cost exactly on all 455 calls. For OpenRouter,
LiteLLM doesn't calculate the cost at all; it copies the cost that OpenRouter reports. When I priced those calls from
LiteLLM's price list instead, the default tier came out 37% too high and the `medium` tier 32% too low, while the
Claude tiers matched. Anthropic doesn't report a cost, so the Claude figures come from LiteLLM's price list.

During the main run, Fireworks' GLM-5.3 Flash endpoint was overloaded: it returned "service overloaded" errors and
took about 48 seconds per call. I stopped that part of the run and used two complete GLM-5.3 Flash runs from earlier
the same day, with the same questions and grader. The full reports are in `results/*/report.md`.

## How it works

**Data.** The database holds James Webb Space Telescope photos from my
[jwst-image-pipeline](https://github.com/RK-A1/jwst-image-pipeline) project: 4,345 photos, 1,077 model-generated
labels, and 481 published images. `build_local.py` loads the parquet files in `data/` into a local DuckDB file.

**Agent.** `agent.py` runs one tool-calling loop, with the same system prompt and tools for every setup. The agent
can list the tables, describe a table, and run read-only SQL. It ends each question by calling `submit_answer` with
the one SQL query whose result is its answer. The system prompt tells every model that the data contains errors and
gives today's date.

**Questions.** `questions.py` holds four conversations of six questions each. The agent keeps the full history, so
later questions can say "of those" or "among them". Each conversation follows the same difficulty pattern: easy,
medium, hard, easy, expert, easy. An easy question needs one count. A medium question needs a join or a GROUP BY. A
hard question needs a window function or a ranking within groups. An expert question asks for three or four related
results at once. The hard and expert questions also hit real problems in the data that the question doesn't mention,
such as photos dated in the year 2124, instrument values like "unknown" that aren't instruments, and one galaxy
spelled two ways.

**Grading.** `check.py` runs the submitted query and compares its result with a reference answer frozen in
`expected.json`. It ignores row order, column names, and extra columns, and it compares numbers with a small
tolerance.

**Logging.** Each run writes three files to `results/`. `calls.csv` has one row per LLM call, with the model that
answered, token counts, latency, cost, and the provider's trace or request ID. `turns.csv` has one graded row per
answer.
`transcripts.jsonl` has every full conversation.

## Setups

| Setup | LiteLLM model | Runs |
|---|---|---|
| `claude-opus` | `anthropic/claude-opus-5-5` | 1 |
| `fw-firerouter-opus` | `fireworks_ai/accounts/fireworks/routers/firerouter/opus`, preference 3 | 3 |
| `fw-auto` | `fireworks_ai/accounts/fireworks/routers/auto`, preference 3 | 3 |
| `or-auto` | `openrouter/openrouter/auto` | 3 |
| `glm-flash` | `fireworks_ai/accounts/fireworks/models/glm-5p3-flash` | 1 |

The routers run three times to show whether they pick the same model for the same question. The OpenRouter tier
setups (`or-auto-medium`, `or-auto-high`, `or-auto-xhigh`, and `or-auto-max`) run only when you name them.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                 # add your Fireworks, Anthropic, and OpenRouter keys
python build_local.py                # build data/jwst.duckdb from the parquet files
python check.py --freeze --selftest  # compute the reference answers and test the grader
python run.py --configs scripted     # free end-to-end check that replays the reference SQL

python run.py --label full           # run the five setups (about $2)
python report.py results/<run_dir>   # print accuracy, cost, and routing tables, and write report.md
python route_probe.py fireworks 2 3  # see which model FireRouter picks at preferences 2 and 3
python route_probe.py openrouter default low medium high xhigh max   # the same for OpenRouter's tiers
```

`report.py` accepts several run folders. If a setup appears in more than one, it uses the last folder you give. A spend
cap in `config.py` stops any run once the whole project has spent $18, counting every run in `results/`.
