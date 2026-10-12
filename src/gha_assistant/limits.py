"""Every limit of one run in one place: how much it may cost, how long it may take, how
much it may do at once. A node reads its limit from here; nothing is configuration.

The runner kills a job after `timeout-minutes` (15, see `docs/PROJECT_GOAL.md`), and a
killed run publishes nothing, so the numbers below are chosen so that a run without
failures fits well inside it.

Time budget. One attempt is `*_TIMEOUT_SECONDS`, a node gets `AGENT_MAX_ATTEMPTS`:

- `review_code`, one worker per file, `MAX_CONCURRENCY` (5) at a time. Normal: about a
  minute a round (assumed; one 9-line diff took ~6 s). Worst case: 4 min a round
  (2 attempts x 2 min).
- `review_intent`, one run, in the same step as `review_code`. Normal: minutes (at most
  100 turns; not measured). Worst case: 10 min (2 attempts x 5 min).
- `verify_finding`, only `high` Findings, at most `MAX_VERIFICATIONS` (10), so 2 rounds
  of 5. Normal: ~15 s a Finding (two measured). Worst case: 8 min (2 rounds x 4 min).
- `judge_findings`: code, no model, instant.
- `publish`: seconds; 3 attempts on a GitHub error.

A normal run of 30 files is about 6 review rounds and 2 verify rounds: roughly 7 min.
In the worst case every attempt runs into its timeout, and then the run does not fit:
the review stage takes max(rounds x 4, 10) min and verification adds 8, so 15 min is
exceeded already for one file with Intent files, and from 6 files without them. We do not
promise that case: the runner kills the process, nothing is published, and the next push
runs again. A timed out attempt is retried and costs another budget (up to
2 x `MAX_BUDGET_USD` for a worker, 2 x `REVIEW_INTENT_MAX_BUDGET_USD` for `review_intent`).
"""

# Agent runs (`agent.run_agent`). Hard caps on one attempt, enforced by the CLI: a run
# that hits one ends with `error_max_turns` / `error_max_budget_usd`, which is permanent
# (a retry would only spend it again).
DEFAULT_MAX_TURNS = 30
MAX_BUDGET_USD = 0.5

# `review_intent` is the one agent that goes through every changed file in one run, so
# it gets more room than the per-file and per-Finding agents.
REVIEW_INTENT_MAX_TURNS = 100
REVIEW_INTENT_MAX_BUDGET_USD = 0.75

# Per attempt, enforced on the node (`add_node(timeout=...)`): LangGraph raises
# NodeTimeoutError there, and the cancelled `query()` takes the CLI with it (spike: the
# child process was gone right after the cancellation).
NODE_TIMEOUT_SECONDS = 120  # review_code, verify_finding
REVIEW_INTENT_TIMEOUT_SECONDS = 300  # reads Intent files and many files in one run

# Attempts per node with a model (`agent.AGENT_RETRY`).
AGENT_MAX_ATTEMPTS = 2

# Fan-out. `max_concurrency` bounds the `Send` workers running at once, so it bounds the
# load on the API as well.
MAX_CONCURRENCY = 5

# Only `high` Findings are verified, and at most this many.
MAX_VERIFICATIONS = 10

# At most this many Findings reach the Review; the most severe ones win.
MAX_FINDINGS = 15

# A generated or vendored file can have a huge diff; past this the tail is cut and the
# model is told so, rather than failing the attempt on the context limit.
MAX_DIFF_CHARS = 60_000
