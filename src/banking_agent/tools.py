from opentelemetry import trace

from banking_agent.config import get_settings
from banking_agent.database import connect
from banking_agent.retrieval import search_policy


def _money(amount_minor: int, currency: str) -> str:
    return f"{currency} {amount_minor / 100:,.2f}"


def _audit(audit: list[dict[str, str]] | None, name: str, **values: str) -> None:
    if audit is not None:
        audit.append({"tool_name": name, **values})


def account_tools(customer_id: str, *, audit: list[dict[str, str]] | None = None) -> list:
    """Return closures that can query only the current customer's accounts."""

    def list_accounts() -> dict:
        """List account names, demo account IDs, balances, currencies, and statuses for this customer."""
        with trace.get_tracer(__name__).start_as_current_span("banking.tool.list_accounts") as span:
            span.set_attribute("banking.tool.name", "list_accounts")
            conn = connect()
            try:
                rows = conn.execute(
                    """SELECT account_id, product_name, currency, balance_minor, status, opened_on
                    FROM accounts WHERE customer_id = ? ORDER BY account_id""",
                    (customer_id,),
                ).fetchall()
                result = {
                    "accounts": [
                        {
                            "account_id": row["account_id"],
                            "product_name": row["product_name"],
                            "currency": row["currency"],
                            "balance": _money(row["balance_minor"], row["currency"]),
                            "status": row["status"],
                            "opened_on": row["opened_on"],
                        }
                        for row in rows
                    ]
                }
                span.set_attribute("banking.result_count", len(rows))
                _audit(audit, "list_accounts")
                return result
            finally:
                conn.close()

    return [list_accounts]


def transaction_tools(customer_id: str, *, audit: list[dict[str, str]] | None = None) -> list:
    """Return closures that can query only transactions tied to this customer's accounts."""

    def list_recent_transactions(limit: int = 5, category: str = "") -> dict:
        """List recent posted transactions. Optionally filter by a category such as groceries or income."""
        safe_limit = max(1, min(int(limit), 20))
        with trace.get_tracer(__name__).start_as_current_span(
            "banking.tool.list_recent_transactions"
        ) as span:
            span.set_attribute("banking.tool.name", "list_recent_transactions")
            span.set_attribute("banking.requested_limit", safe_limit)
            conn = connect()
            try:
                rows = conn.execute(
                    """SELECT t.transaction_id, t.posted_on, t.description, t.amount_minor,
                              t.currency, t.category, t.status, a.account_id
                       FROM transactions t JOIN accounts a ON a.account_id = t.account_id
                       WHERE a.customer_id = ? AND (? = '' OR lower(t.category) = lower(?))
                       ORDER BY t.posted_on DESC, t.transaction_id LIMIT ?""",
                    (customer_id, category.strip(), category.strip(), safe_limit),
                ).fetchall()
                result = {
                    "transactions": [
                        {
                            "transaction_id": row["transaction_id"],
                            "date": row["posted_on"],
                            "description": row["description"],
                            "amount": _money(row["amount_minor"], row["currency"]),
                            "category": row["category"],
                            "status": row["status"],
                            "account_id": row["account_id"],
                        }
                        for row in rows
                    ]
                }
                span.set_attribute("banking.result_count", len(rows))
                _audit(audit, "list_recent_transactions")
                return result
            finally:
                conn.close()

    return [list_recent_transactions]


def policy_tools(*, audit: list[dict[str, str]] | None = None) -> list:
    """Return the policy retrieval tool used by the RAG specialist."""

    def retrieve_banking_policy(query: str, limit: int = 4) -> dict:
        """Search the approved banking policy corpus and return passages with citation IDs."""
        with trace.get_tracer(__name__).start_as_current_span("banking.retriever.policy") as span:
            span.set_attribute("banking.retriever.name", "banking_policy_fts5")
            results = search_policy(query, limit=max(1, min(int(limit), 6)))
            span.set_attribute("banking.retriever.result_count", len(results))
            ids = [str(item["chunk_id"]) for item in results]
            for chunk_id in ids:
                span.add_event("retrieved_policy_chunk", {"banking.policy.chunk_id": chunk_id})
            _audit(audit, "retrieve_banking_policy")
            if audit is not None:
                for chunk_id in ids:
                    audit.append({"tool_name": "retrieve_banking_policy", "chunk_id": chunk_id})
            return {
                "results": results,
                "message": "No matching policy passages found." if not results else "",
            }

    return [retrieve_banking_policy]


def validate_demo_customer(customer_id: str) -> bool:
    """Check the allowlist and backing store before creating any agent with a customer-scoped tool."""
    if customer_id not in get_settings().demo_customer_ids:
        return False
    conn = connect()
    try:
        return (
            conn.execute("SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
            is not None
        )
    finally:
        conn.close()
