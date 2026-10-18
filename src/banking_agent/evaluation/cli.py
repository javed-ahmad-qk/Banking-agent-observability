import argparse
import json
from pathlib import Path

from banking_agent.config import get_settings
from banking_agent.database import connect, initialize_database
from banking_agent.evaluation.evaluators import evaluate_all


def load_interactions(session_id: str | None = None) -> list[dict]:
    conn = connect()
    try:
        sql = "SELECT * FROM agent_interactions"
        params: tuple = ()
        if session_id:
            sql += " WHERE session_id = ?"
            params = (session_id,)
        sql += " ORDER BY created_at, interaction_id"
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                **dict(row),
                "retrieved_chunks": json.loads(row["retrieved_chunks"]),
                "tool_names": json.loads(row["tool_names"]),
                "metadata": json.loads(row["metadata"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate stored banking-agent sessions, traces, and turns."
    )
    parser.add_argument("--session-id", help="Evaluate only one conversation session.")
    parser.add_argument(
        "--output", type=Path, help="Write the JSON evaluation report to this path."
    )
    args = parser.parse_args()
    initialize_database()
    interactions = load_interactions(args.session_id)
    report = {
        "service": get_settings().app_name,
        "interaction_count": len(interactions),
        "results": [result.to_dict() for result in evaluate_all(interactions)],
    }
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
