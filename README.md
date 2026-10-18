# Banking Agent Observability

A GitHub-ready demonstration of a read-only retail banking assistant built with **Google Agent Development Kit (ADK)**. It combines multi-agent delegation, policy RAG, SQLite-backed customer data and durable ADK sessions, OpenTelemetry instrumentation, Arize AX trace export, and deterministic evaluations at span, trace, and session scope.

> **Safety boundary:** This repository is a synthetic engineering demonstration, not a bank product. It cannot move money, change customer records, authenticate real customers, or provide financial advice. Every seeded customer, account, and transaction is fictional. Do not connect it to production customer data.

## What is included

- **Google ADK multi-agent system:** `banking_assistant` routes to account, transaction, and policy specialists.
- **RAG:** approved policy passages are indexed in SQLite FTS5. Retrieval returns stable passage IDs used for citations and evaluation.
- **Persistence:** the demo banking database stores synthetic records; ADK conversation sessions use `DatabaseSessionService` with SQLite and survive restarts.
- **Deep traces:** OpenInference instruments Google ADK and custom OpenTelemetry spans cover API requests, tool calls, and policy retrieval. Spans go to Arize AX when configured, otherwise to the local console.
- **Evaluation:** deterministic checks score individual interactions (span), agent routing and retrieval (trace), and full conversations (session). Reports can be generated from stored sessions or retrieved from the API.
- **Runnable service:** FastAPI REST API, Docker Compose, command-line evaluation, tests, and GitHub Actions CI.

## Quick start

Requirements: Python 3.11–3.13, a Google AI Studio API key, and (optionally) an Arize AX Space ID and API key.

```bash
git clone https://github.com/YOUR_ACCOUNT/banking-agent-observability.git
cd banking-agent-observability
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
cp .env.example .env
```

Set `GOOGLE_API_KEY` in `.env`. For Arize AX, also set `ARIZE_SPACE_ID`, `ARIZE_API_KEY`, and `ARIZE_PROJECT_NAME`. The Arize credentials are optional: without them, OpenTelemetry spans are written to the console. The key names in `.env.example` are configuration prompts, not usable credentials.

Start the API:

```bash
banking-agent
# or: uvicorn banking_agent.api:app --host 0.0.0.0 --port 8000
```

Check health and submit a request:

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Demo-Customer-ID: cust_1001' \
  -d '{"message":"What is my checking balance?"}'
```

A chat response includes `session_id`, `interaction_id`, `response`, and `trace_id`. Pass the returned `session_id` to continue the same ADK conversation:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Demo-Customer-ID: cust_1001' \
  -d '{"message":"Show my recent transactions","session_id":"SESSION_ID_FROM_FIRST_REPLY"}'
```

Demo identities are `cust_1001` and `cust_1002`. The header is a local demo selector, **not authentication**. The app rejects other IDs and every tool query is scoped server-side to the selected seeded customer. Replace this mechanism with verified identity, authorization, rate limits, and audit controls before any non-demo use.

Interactive API documentation is available at `http://localhost:8000/docs`.

## Docker Compose

After creating `.env` and adding `GOOGLE_API_KEY`, start the API:

```bash
docker compose up --build
```

The SQLite databases persist in the `banking-data` Docker volume. For local development without Docker, the databases are created under `data/` on first start. Both locations are git-ignored.

## Project layout

```text
src/banking_agent/
  agent.py                 ADK coordinator and specialist agents
  api.py                   FastAPI endpoints and demo identity guard
  config.py                Environment-backed settings
  database.py              Schema, synthetic fixtures, interaction store
  retrieval.py             SQLite FTS5 policy retrieval
  service.py               ADK Runner, sessions, and run-level spans
  tools.py                 Customer-scoped read-only tools
  tracing.py               Arize AX / local OTel configuration
  evaluation/              Span, trace, and session checks, scoring CLI, dataset runner
data/policies/             Versioned policy source text
  evaluation_set.jsonl     Synthetic evaluation prompts and expected behavior
docs/                      Architecture, AX eval setup, safety boundary
 tests/                     Retrieval, isolation, and evaluator tests
```

## OpenTelemetry and Arize AX

The app uses `openinference-instrumentation-google-adk` to capture ADK agent handoffs and model/tool activity. Custom spans named `banking.chat`, `banking.tool.*`, and `banking.retriever.policy` add application-level context. With AX settings present, `arize-otel` registers the Arize exporter and creates/uses the configured AX project. Without AX credentials, a standard OpenTelemetry SDK console exporter is used for local tracing.

Set these variables in `.env` to connect to AX:

```dotenv
ARIZE_SPACE_ID=your_space_id
ARIZE_API_KEY=your_api_key
ARIZE_PROJECT_NAME=banking-agent-observability
```

The default `CAPTURE_TRACE_CONTENT=false` keeps OpenInference inputs and outputs hidden. This is the safe starting point but means content-based evaluations in AX need not have visible prompt/response fields. For **synthetic demo data only**, set `CAPTURE_TRACE_CONTENT=true`, restart the service, and confirm that the data and retention settings in your AX space are appropriate. Never export real account data, credentials, full card numbers, authentication codes, or other sensitive information.

See [`docs/arize-ax-evaluations.md`](docs/arize-ax-evaluations.md) for creating AX-native span, trace, and session evaluation tasks and aligning them with the bundled local evaluators.

## Run evaluations

The API stores synthetic interaction records locally so results can be reproduced without querying AX. Replay the bundled prompt set against a running API, then score all recorded turns:

```bash
banking-eval-set
banking-eval
banking-eval --session-id SESSION_ID
banking-eval --output evaluation-report.json
```

The report emits three kinds of results:

- **Span:** prohibited-action/credential-collection patterns and citation consistency for one response.
- **Trace:** expected specialist tool or policy-retrieval path for one turn.
- **Session:** safety and completion across the conversation's turns.

These are transparent deterministic baseline checks, not a substitute for human review or an LLM judge. The AX setup guide describes equivalent AX evaluator criteria to run against captured traces and sessions.

## Tests and style

The tests run without a Google or Arize credential:

```bash
pytest
ruff check .
```

Use the fictional fixtures for demos and tests. The test suite covers policy search, tenant/customer scoping, and evaluation behavior.

## API reference

- `GET /health` — readiness and configured model/trace destination status.
- `POST /v1/chat` — run a chat turn. Header: `X-Demo-Customer-ID: cust_1001` or `cust_1002`.
- `GET /v1/sessions/{session_id}/turns` — local synthetic interaction history for the selected demo customer.
- `GET /v1/sessions/{session_id}/evaluations` — deterministic span, trace, and session evaluation results.

## Security and production boundary

This repository intentionally implements only read operations. It does not use a real bank API, execute transactions, or treat the demo header as authentication. The SQLite dataset and policy corpus are synthetic and non-authoritative. Before adapting any part for a real system, conduct security, privacy, legal, model-risk, and banking compliance reviews; use an authenticated identity provider and server-side authorization; define data retention/redaction for traces; and prevent model-generated text from authorizing financial actions.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
