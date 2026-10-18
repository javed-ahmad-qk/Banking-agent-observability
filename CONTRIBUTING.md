# Contributing

Contributions should preserve the synthetic-only, read-only banking boundary. Do not add real customer records, credentials, payment execution, or traces containing personal financial data.

Before submitting a pull request:

1. Install the development dependencies with `pip install -e '.[dev]'`.
2. Run `pytest` and `ruff check .`.
3. Update architecture or AX guidance when behavior changes.
4. Add a test for new database, retrieval, security, or evaluation behavior.

Keep secrets in local environment variables. Never attach `.env`, SQLite files, trace exports, or customer-identifiable data to an issue or pull request.
