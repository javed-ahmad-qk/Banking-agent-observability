import argparse
import json
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path

from banking_agent.config import PROJECT_ROOT


def submit_turn(base_url: str, customer_id: str, message: str, session_id: str) -> dict:
    payload = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat",
        data=payload,
        headers={"Content-Type": "application/json", "X-Demo-Customer-ID": customer_id},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Chat request failed with HTTP {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay the synthetic banking evaluation set through a running API server."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--dataset", type=Path, default=PROJECT_ROOT / "data" / "evaluation_set.jsonl"
    )
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    session_ids: dict[str, str] = defaultdict(lambda: "")
    for row in rows:
        customer_id = row["customer_id"]
        if not session_ids[customer_id]:
            session_ids[customer_id] = f"eval-{customer_id}-{uuid.uuid4().hex[:10]}"
        result = submit_turn(args.base_url, customer_id, row["message"], session_ids[customer_id])
        print(
            json.dumps(
                {
                    "eval_id": row["id"],
                    "session_id": result["session_id"],
                    "interaction_id": result["interaction_id"],
                    "trace_id": result.get("trace_id"),
                    "response": result["response"],
                },
                ensure_ascii=False,
            )
        )
    print(
        "Evaluation prompts completed. Run `banking-eval` to score stored spans, traces, and sessions."
    )


if __name__ == "__main__":
    main()
