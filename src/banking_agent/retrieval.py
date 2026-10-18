import re
import sqlite3
from pathlib import Path

from banking_agent.config import get_settings
from banking_agent.database import connect


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[\w-]+", query.lower())
    return " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:12])


def search_policy(
    query: str, *, limit: int = 4, path: Path | None = None
) -> list[dict[str, str | float]]:
    """Retrieve relevant banking policy passages from the indexed policy corpus."""
    expression = _fts_query(query)
    if not expression:
        return []
    conn = connect(path or get_settings().database_path)
    try:
        rows = conn.execute(
            """SELECT p.chunk_id, p.title, p.body, bm25(policy_search) AS rank
            FROM policy_search AS p WHERE policy_search MATCH ?
            ORDER BY rank LIMIT ?""",
            (expression, limit),
        ).fetchall()
        if rows:
            return [
                {
                    "chunk_id": row["chunk_id"],
                    "title": row["title"],
                    "text": row["body"],
                    "score": round(float(row["rank"]), 6),
                }
                for row in rows
            ]
        # FTS phrase parsing can fail to match rare terms; deterministic substring fallback.
        terms = [token for token in re.findall(r"[\w-]+", query.lower()) if len(token) > 2]
        if not terms:
            return []
        candidates = conn.execute("SELECT chunk_id, title, body FROM policy_chunks").fetchall()
        scored = []
        for row in candidates:
            text = f"{row['title']} {row['body']}".lower()
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["chunk_id"]))
        return [
            {
                "chunk_id": row["chunk_id"],
                "title": row["title"],
                "text": row["body"],
                "score": float(score),
            }
            for score, row in scored[:limit]
        ]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
