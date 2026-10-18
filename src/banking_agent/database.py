import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from banking_agent.config import PROJECT_ROOT, get_settings


def _policy_directory() -> Path:
    configured = get_settings().policy_data_dir
    if configured.is_dir():
        return configured
    packaged = Path(__file__).resolve().parent / "policies"
    if packaged.is_dir():
        return packaged
    return PROJECT_ROOT / "data" / "policies"


def _load_policy_files() -> list[tuple[str, str, str, str]]:
    """Read the version-controlled Markdown policy corpus and extract stable chunk IDs."""
    directory = _policy_directory()
    policies = []
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8").strip()
        heading = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
        chunk = re.search(r"^Policy chunk:\s*`(policy-[\w-]+)`\s*$", content, flags=re.MULTILINE)
        if not heading or not chunk:
            raise ValueError(f"Policy document must include a title and stable chunk ID: {path}")
        body = content[: chunk.start()].strip()
        body = re.sub(r"^#\s+.+\n", "", body, count=1).strip()
        if not body:
            raise ValueError(f"Policy document has no searchable content: {path}")
        policies.append((chunk.group(1), heading.group(1), body, path.name))
    if not policies:
        raise FileNotFoundError(f"No policy Markdown files found in {directory}")
    return policies


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_settings().database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def database(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(path: Path | None = None, *, seed: bool = True) -> None:
    with database(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                segment TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES customers(customer_id),
                product_name TEXT NOT NULL,
                currency TEXT NOT NULL,
                balance_minor INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                opened_on TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                posted_on TEXT NOT NULL,
                description TEXT NOT NULL,
                amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'posted'
            );
            CREATE INDEX IF NOT EXISTS idx_transactions_account_date
                ON transactions(account_id, posted_on DESC);
            CREATE TABLE IF NOT EXISTS policy_chunks (
                chunk_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'internal_policy'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS policy_search USING fts5(
                chunk_id UNINDEXED, title, body, tokenize='unicode61'
            );
            CREATE TABLE IF NOT EXISTS agent_interactions (
                interaction_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                user_input TEXT NOT NULL,
                assistant_output TEXT NOT NULL,
                retrieved_chunks TEXT NOT NULL DEFAULT '[]',
                tool_names TEXT NOT NULL DEFAULT '[]',
                trace_id TEXT,
                metadata TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_interactions_session
                ON agent_interactions(session_id, created_at);
            """
        )
        if seed:
            _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    customers = [
        ("cust_1001", "Jordan Lee", "Everyday Banking"),
        ("cust_1002", "Taylor Morgan", "Everyday Banking"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO customers(customer_id, display_name, segment) VALUES (?, ?, ?)",
        customers,
    )
    accounts = [
        ("acct_41001", "cust_1001", "Everyday Checking", "USD", 284531, "open", "2022-04-15"),
        ("acct_41002", "cust_1001", "High-Yield Savings", "USD", 1842500, "open", "2021-09-03"),
        ("acct_42001", "cust_1002", "Everyday Checking", "USD", 93744, "open", "2023-01-21"),
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO accounts
        (account_id, customer_id, product_name, currency, balance_minor, status, opened_on)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        accounts,
    )
    if conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
        today = date.today()
        txns = [
            (
                "txn_81001",
                "acct_41001",
                (today - timedelta(days=1)).isoformat(),
                "Northstar Market",
                -6842,
                "USD",
                "groceries",
                "posted",
            ),
            (
                "txn_81002",
                "acct_41001",
                (today - timedelta(days=3)).isoformat(),
                "Metro Transit Pass",
                -3200,
                "USD",
                "transport",
                "posted",
            ),
            (
                "txn_81003",
                "acct_41001",
                (today - timedelta(days=5)).isoformat(),
                "Payroll Deposit - Aster Labs",
                245000,
                "USD",
                "income",
                "posted",
            ),
            (
                "txn_81004",
                "acct_41002",
                (today - timedelta(days=8)).isoformat(),
                "Monthly Interest Credit",
                412,
                "USD",
                "interest",
                "posted",
            ),
            (
                "txn_81005",
                "acct_41001",
                (today - timedelta(days=11)).isoformat(),
                "Harbor Coffee Roasters",
                -1275,
                "USD",
                "dining",
                "posted",
            ),
            (
                "txn_81006",
                "acct_41001",
                (today - timedelta(days=14)).isoformat(),
                "Lumen Electric Utility",
                -9360,
                "USD",
                "utilities",
                "posted",
            ),
            (
                "txn_81007",
                "acct_41001",
                (today - timedelta(days=18)).isoformat(),
                "Cedar Pharmacy",
                -2380,
                "USD",
                "health",
                "posted",
            ),
            (
                "txn_82001",
                "acct_42001",
                (today - timedelta(days=2)).isoformat(),
                "Willow Books",
                -2450,
                "USD",
                "shopping",
                "posted",
            ),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO transactions
            (transaction_id, account_id, posted_on, description, amount_minor, currency, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            txns,
        )
    for chunk_id, title, body, source in _load_policy_files():
        conn.execute(
            """INSERT INTO policy_chunks(chunk_id, title, body, source) VALUES (?, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                title=excluded.title, body=excluded.body, source=excluded.source""",
            (chunk_id, title, body, source),
        )
        conn.execute("DELETE FROM policy_search WHERE chunk_id = ?", (chunk_id,))
        conn.execute(
            "INSERT INTO policy_search(chunk_id, title, body) VALUES (?, ?, ?)",
            (chunk_id, title, body),
        )


def record_interaction(
    *,
    interaction_id: str,
    session_id: str,
    customer_id: str,
    created_at: str,
    user_input: str,
    assistant_output: str,
    retrieved_chunks: list[str],
    tool_names: list[str],
    trace_id: str | None,
    metadata: dict,
    path: Path | None = None,
) -> None:
    with database(path) as conn:
        conn.execute(
            """INSERT INTO agent_interactions
            (interaction_id, session_id, customer_id, created_at, user_input, assistant_output,
             retrieved_chunks, tool_names, trace_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                interaction_id,
                session_id,
                customer_id,
                created_at,
                user_input,
                assistant_output,
                json.dumps(retrieved_chunks),
                json.dumps(tool_names),
                trace_id,
                json.dumps(metadata),
            ),
        )
