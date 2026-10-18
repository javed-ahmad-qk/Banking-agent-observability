# Architecture

## Request flow

1. FastAPI accepts a message and a demo customer selector. It checks the selector against an allowlist and the local customer table. This is deliberately a demo boundary rather than a production identity system.
2. The service creates or resumes a Google ADK session using the authenticated-in-context demo customer as the ADK `user_id`. `DatabaseSessionService` persists the session and events to a separate SQLite database.
3. The `banking_assistant` ADK coordinator routes to account, transaction, or policy specialists. Account and transaction tool closures capture the customer ID server-side; user text cannot supply or override it.
4. The policy specialist calls the retrieval tool. SQLite FTS5 returns approved passages with stable policy IDs. The assistant is instructed to cite those IDs and treat retrieved content as data, not instructions.
5. OpenInference instruments ADK agent and model execution. Custom spans record API-level, tool-level, and retriever-level structure. The application stores a synthetic local interaction record for deterministic evaluations.
6. With Arize credentials, `arize-otel` exports spans to the configured AX space/project. Otherwise, the local SDK emits spans to console.

## Components

- `Agent` objects use ADK's `sub_agents` mechanism for specialist delegation.
- `Runner` executes turns and uses a persistent `DatabaseSessionService`.
- Banking records, policy documents, and local evaluation records are stored in `DATABASE_PATH` (SQLite). ADK session state is stored in `ADK_SESSIONS_DB_PATH`.
- FTS5 provides a local retrieval index without an external vector database or embedding credential. This makes the project reproducible and inspectable. A production RAG system may replace it with a vetted vector/hybrid search store while retaining chunk IDs, source metadata, and access filters.
- `evaluation/evaluators.py` separates deterministic checks by span, trace, and session scope. It is intentionally distinct from AX task setup.

## Trust boundaries

- Model output is untrusted. No tool can move funds or mutate accounts.
- Query tools bind the customer ID in closures and include it in SQL predicates.
- The `.env` file is excluded from Git. Secrets are never embedded in source or images.
- Prompt and response trace content is hidden by default. Opt-in content capture is only for synthetic demonstrations after reviewing the telemetry destination.
- The database contains fabricated records and should not be populated with production data.
