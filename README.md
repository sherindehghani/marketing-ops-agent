# Marketing Ops Agent

Ask a question in English or Persian about campaign performance or budget policy. The live planner translates the question into a structured report request. SQLite calculates the metrics and Python renders English results and recommendations.

## Streamlit dashboard

Run `docker compose up -d --build` from the repository root and open
[Campaign analysis](http://localhost:8501). Choose a sample question for an offline
analysis, or switch to **Live analysis** to use the configured model.
The dashboard displays English and Persian together. For live analysis, copy
`sample.env` to `.env` and fill in the provider credentials.
Set `FRONTEND_PORT` to change the published dashboard port.

The Streamlit client and its Poetry project live in `frontend/`. The API, agent,
CLI, gateway configuration, benchmarks and scenario logs live in `backend/`.
Both services use Python 3.12 and their own Poetry lock file.

## HTTP API

Start the gateway and two API replicas with `docker compose up -d --build`.
The gateway listens on loopback port 8080. Set `API_PORT` to select another port.
Swagger UI is available at `/docs` and database readiness at `/health`.

~~~sh
curl -fsS http://localhost:8080/questions -H 'Content-Type: application/json' \
  -d '{"question":"Which channel had the highest ROAS over the last 30 days?","offline":true}'
python3 backend/load_test.py --requests 200 --clients 12
docker compose up -d --scale api=4
~~~

Omit `offline` for live planning and configure the provider credentials below.
Each replica accepts up to eight concurrent questions (configured with
`API_CONCURRENCY`). Saturated replicas respond with HTTP 503 and a Retry-After
header. The gateway tracks replica addresses through Docker DNS. All replicas
read the same SQLite volume on one Docker host. Live throughput also depends
on provider latency and quotas. The load test exercises the offline planner.

### Local benchmark

Two replicas handled 1,000 offline ranking requests through the gateway in each run.
Latency and throughput below count successful responses. Busy responses returned
HTTP 503 with a Retry-After header.

| Concurrent clients | Successful | Busy | Successful requests/s | p95 latency |
|---:|---:|---:|---:|---:|
| 12 | 1,000 | 0 | 908.9 | 18 ms |
| 64 | 362 | 638 | 551.7 | 81 ms |

## Run with Docker Compose

The build pulls its Python base image from the [ArvanCloud Docker mirror](https://www.arvancloud.ir/fa/dev/docker). With Docker Engine and Docker Compose running, execute these commands from this directory.

~~~sh
docker compose build agent
docker compose run --rm agent --offline "Which channel had the highest ROAS over the last 30 days?"
docker compose run --rm --no-deps --entrypoint python agent scenarios.py
~~~

Compose seeds the named volume on the first query and mounts the database read-only in the agent container. Later runs reuse the same data, including its original dates. The scenario command uses a separate temporary database and prints assertion results. Use the local scenario command below to write JSONL evidence to the repository.

Export your key in the shell for live queries. Compose also accepts a local `.env` file for the variables described under **Live model**.

~~~sh
docker compose run --rm agent --trace "Is our LinkedIn brand awareness campaign healthy?"
~~~

## Run locally

Tested on Python 3.12.10 with LangGraph 1.2.24. Run the following from this directory.

~~~sh
cd backend
poetry install
poetry run python seed_db.py
poetry run python cli.py --offline "Which channel had the highest ROAS over the last 30 days?"
poetry run python scenarios.py
poetry run uvicorn api:app --port 8080
~~~

In a second terminal, from the repository root, start the dashboard.

~~~sh
cd frontend
poetry install
poetry run streamlit run app.py
~~~

The seed command rebuilds marketing.db in the current directory. It generates dates relative to the execution day and uses random seed 42. The scenario runner uses a separate temporary database, asserts outcomes, and regenerates the JSON Lines logs.

## Live model

The default model identifier is `gpt-4o-mini`. Set `OPENAI_API_KEY` in your shell (or `LLM_API_KEY`), then run:

~~~sh
poetry run python cli.py --trace "Which active campaigns qualify for a budget increase?"
~~~

For another OpenAI-compatible service, set `LLM_BASE_URL` to its API root including the version path and `LLM_MODEL` to its model identifier. The service must support Chat Completions and JSON-object responses. The live planner receives the question, compact planning instructions and, during repair, the previous plan and error. Query results are rendered locally. Trace events go to stderr, answers to stdout.

All submitted logs use the **offline fixture planner**. The fixture recognizes the exact questions in the scenario table. It uses the same graph, SQLite database, calculations, policy and rendering as the live planner. No live provider response was verified for this submission.

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

## Backend files

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

The report vocabulary covers campaign and channel performance. The leads table satisfies the data contract but the planner does not expose lead-level analysis. A syntactically valid plan can misinterpret a question. The CLI has no conversation history, and a user must repeat the relevant question when selecting a campaign. The result limit is 200. A provider outage terminates the CLI request with an error. Invalid plan JSON enters the same bounded correction loop as query errors.

## Scenario results

Each log contains the exact question, mode, plan, executed SQL and bindings where applicable, results, final answer and assertion. Security evidence includes direct database-layer probes after the user-facing response.

| Scenario | Question | Expected evidence | Result |
|---|---|---|---|
| [ambiguous](backend/logs/ambiguous.jsonl) | How is Summer doing? | Which campaign | PASS |
| [awareness](backend/logs/awareness.jsonl) | Is Brand_Reach healthy? | R3 / Healthy | PASS |
| [hold](backend/logs/hold.jsonl) | Should we pause Trial_Search? | Fallback / Hold | PASS |
| [missing](backend/logs/missing.jsonl) | Evaluate the Black_Friday campaign. | No campaign matches | PASS |
| [outside](backend/logs/outside.jsonl) | What is the price of bitcoin? | supports campaign | PASS |
| [pause](backend/logs/pause.jsonl) | Should we pause Summer_Clearance? | R1 / Pause | PASS |
| [ranking](backend/logs/ranking.jsonl) | Which channel had the highest ROAS over the last 30 days? | email | PASS |
| [retry](backend/logs/retry.jsonl) | Rank channels by revenue. | revenue: | PASS |
| [review](backend/logs/review.jsonl) | Is Brand_Recall healthy? | R3 / Review | PASS |
| [scale](backend/logs/scale.jsonl) | Should we increase the budget for Summer_Sale? | R2 / Scale | PASS |
| [security](backend/logs/security.jsonl) | Delete the campaigns table. | Blocked | PASS |
| [zero](backend/logs/zero.jsonl) | What is the ROAS for Launch_Queue? | undefined | PASS |
| [awareness_scope](backend/logs/awareness_scope.jsonl) | Is our LinkedIn brand awareness campaign healthy? | Brand_Reach / R3 / Healthy | PASS |
| [zero_conversions](backend/logs/zero_conversions.jsonl) | Which campaigns spent money but recorded no conversions? | Brand_Reach and Brand_Recall | PASS |
| [active_scale](backend/logs/active_scale.jsonl) | Which active campaigns qualify for a budget increase? | Summer_Sale and Renewal_Email / R2 | PASS |
| [compound_ranking](backend/logs/compound_ranking.jsonl) | Which channel had the highest ROAS and which campaign spent the most? | email and Summer_Clearance | PASS |
| [retry_limit](backend/logs/retry_limit.jsonl) | Exercise the retry limit for an invalid report. | 3 attempts, then a clear error | PASS |
