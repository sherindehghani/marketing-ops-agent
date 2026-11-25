# Marketing Ops Agent

Ask an English question about campaign performance or budget policy. The live planner translates the question into a structured report request. SQLite calculates the metrics and Python renders the results and recommendations. A recommendation never changes a campaign.

## Run locally

Tested on Python 3.12.10 with LangGraph 1.2.24. Run the following from this directory.

~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python seed_db.py
python cli.py --offline "Which channel had the highest ROAS over the last 30 days?"
python scenarios.py
~~~

The seed command rebuilds marketing.db in the current directory. It generates dates relative to the execution day and uses random seed 42. The scenario runner uses a separate temporary database, asserts outcomes, and regenerates the JSON Lines logs.

## Live model

The default model identifier is `gpt-4o-mini`. Set `OPENAI_API_KEY` in your shell (or `LLM_API_KEY`), then run:

~~~sh
python cli.py --trace "Which active campaigns qualify for a budget increase?"
~~~

For another OpenAI-compatible service, set `LLM_BASE_URL` to its API root including the version path and `LLM_MODEL` to its model identifier. The service must support Chat Completions and JSON-object responses. The live planner receives the question, compact planning instructions and, during repair, the previous plan and error. Query results are rendered locally. Trace events go to stderr, answers to stdout.

All submitted logs use the **offline fixture planner**. The fixture recognizes the exact English questions in the scenario table. It uses the same graph, SQLite database, calculations, policy and rendering as the live planner. No live provider response was verified for this submission.

## Architecture decision

LangGraph represents planning, execution, and the transition on failure explicitly. State contains the plan, attempt count, last error, and answer. The first plan counts as attempt one. SQLite and plan-validation errors return to the planner with the rejected plan and error text. Execution ends on success or after attempt three. An ambiguous name returns the matching names immediately. The CLI accepts the clarified request as a new invocation.

| Choice | State and retry control | Overhead and traceability |
|---|---|---|
| LangGraph (selected) | Conditional edges expose the repair loop and attempt limit. | Two nodes suffice. Trace events capture each query, result and recommendation. |
| LangChain | A chain with custom retry logic could carry SQL errors into a repair prompt. | A linear chain works well for one pass. Application code would own the conditional transitions. |
| DeepAgent | A planning agent could decompose open-ended investigations into tool calls. | Additional planning and tool orchestration offer little benefit for this bounded workflow and make its execution budget harder to explain. |

**Accuracy.** The model selects a report, fields, filters and ordering. The application constructs SQL from fixed templates with bound values and validated identifiers. Filtering and aggregation happen before division. ROAS is total revenue divided by total spend. CTR and conversion rate are percentages. A zero denominator returns NULL. Decisions use full precision, and application code formats the displayed values. The default window contains today and the previous 29 days, inclusive.

**Security.** Each query opens the existing file with SQLite URI mode=ro and query_only enabled. An authorizer permits reads, SELECT and specified scalar/aggregate functions. It denies all other actions. A progress handler bounds query work. The security scenario exercises the connection directly and records SQLite's rejection of four write operations and a before/after file digest.

**Policy.** The versioned decision logic is in policy.py. For brand awareness, CTR above 1.5% is Healthy and other defined values trigger Review. For conversion campaigns, spend above $500 and ROAS below 1.5 trigger Pause. Other eligible non-awareness campaigns with ROAS above 3.5 and conversion rate above 5% qualify for a 20% daily budget increase. A defined result outside the thresholds yields Hold. Missing required metrics yield insufficient data. Each recommendation includes its rule ID.

## Files

| File | Responsibility |
|---|---|
| seed_db.py | Create campaigns, daily_metrics and leads, including inactive campaigns, zero data, similar names and older observations. |
| cli.py | English command-line interface and optional trace output. |
| planner.py | Live provider client, planning contract and offline fixtures. |
| agent.py | Resolve names, scope requests, compile reports, manage retries and render answers. |
| database.py | Aggregate SQL, date window and guarded SQLite connection. |
| policy.py | Deterministic R1, R2, R3 and fallback decisions. |
| scenarios.py and logs/ | Reproduce and inspect scenario evidence. |

## Known limits

The report vocabulary covers campaign and channel performance. The leads table satisfies the data contract but the planner does not expose lead-level analysis. A syntactically valid plan can misinterpret an English question. The CLI has no conversation history, and a user must repeat the relevant question when selecting a campaign. The result limit is 200. A provider outage or invalid JSON terminates the CLI request with an error. Further evaluation would compare plans against labeled paraphrases using the chosen live model.

## Scenario results

Each log contains the exact question, mode, plan, executed SQL and bindings where applicable, results, final answer and assertion. Security evidence includes direct database-layer probes after the user-facing response.

| Scenario | Question | Expected evidence | Result |
|---|---|---|---|
| [ambiguous](logs/ambiguous.jsonl) | How is Summer doing? | Which campaign | PASS |
| [awareness](logs/awareness.jsonl) | Is Brand_Reach healthy? | R3 / Healthy | PASS |
| [hold](logs/hold.jsonl) | Should we pause Trial_Search? | Fallback / Hold | PASS |
| [missing](logs/missing.jsonl) | Evaluate the Black_Friday campaign. | No campaign matches | PASS |
| [outside](logs/outside.jsonl) | What is the price of bitcoin? | supports campaign | PASS |
| [pause](logs/pause.jsonl) | Should we pause Summer_Clearance? | R1 / Pause | PASS |
| [ranking](logs/ranking.jsonl) | Which channel had the highest ROAS over the last 30 days? | email | PASS |
| [retry](logs/retry.jsonl) | Rank channels by revenue. | revenue: | PASS |
| [review](logs/review.jsonl) | Is Brand_Recall healthy? | R3 / Review | PASS |
| [scale](logs/scale.jsonl) | Should we increase the budget for Summer_Sale? | R2 / Scale | PASS |
| [security](logs/security.jsonl) | Delete the campaigns table. | Blocked | PASS |
| [zero](logs/zero.jsonl) | What is the ROAS for Launch_Queue? | undefined | PASS |
