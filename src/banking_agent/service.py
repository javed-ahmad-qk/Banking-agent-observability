import uuid
from datetime import UTC, datetime
from functools import lru_cache

from banking_agent.tracing import configure_tracing

configure_tracing()

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import DatabaseSessionService  # noqa: E402
from google.genai import types  # noqa: E402
from opentelemetry import trace  # noqa: E402

from banking_agent.agent import build_root_agent  # noqa: E402
from banking_agent.config import get_settings  # noqa: E402
from banking_agent.database import record_interaction  # noqa: E402


@lru_cache(maxsize=1)
def get_session_service() -> DatabaseSessionService:
    settings = get_settings()
    settings.adk_sessions_db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{settings.adk_sessions_db_path.resolve()}"
    return DatabaseSessionService(db_url=url)


def _text_from_event(event) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(part.text for part in parts if getattr(part, "text", None))


async def chat(*, customer_id: str, message: str, session_id: str | None = None) -> dict:
    """Run one user turn through the ADK coordinator and persist a local evaluation record."""
    session_service = get_session_service()
    app_name = get_settings().app_name
    user_id = customer_id
    session_id = session_id or uuid.uuid4().hex
    existing = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if existing is None:
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

    audit: list[dict[str, str]] = []
    agent = build_root_agent(customer_id, audit=audit)
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    interaction_id = uuid.uuid4().hex
    tracer = trace.get_tracer("banking_agent.api")
    assistant_output = ""
    trace_id: str | None = None
    with tracer.start_as_current_span("banking.chat") as span:
        span.set_attribute("banking.session_id", session_id)
        span.set_attribute("banking.customer_id", customer_id)
        span.set_attribute("banking.interaction_id", interaction_id)
        span.set_attribute("banking.agent_name", "banking_assistant")
        span.set_attribute("banking.environment", get_settings().environment)
        trace_id = f"{span.get_span_context().trace_id:032x}"
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        ):
            if event.is_final_response():
                assistant_output = _text_from_event(event).strip()
        if not assistant_output:
            assistant_output = "I could not produce a response for that request. Please try again."
        span.set_attribute("banking.response_chars", len(assistant_output))
        span.set_attribute("banking.tool_count", len(audit))

    record_interaction(
        interaction_id=interaction_id,
        session_id=session_id,
        customer_id=customer_id,
        created_at=datetime.now(UTC).isoformat(),
        user_input=message,
        assistant_output=assistant_output,
        retrieved_chunks=[entry["chunk_id"] for entry in audit if entry.get("chunk_id")],
        tool_names=[entry["tool_name"] for entry in audit],
        trace_id=trace_id,
        metadata={"agent": "banking_assistant", "model": get_settings().model_name},
    )
    return {
        "session_id": session_id,
        "interaction_id": interaction_id,
        "response": assistant_output,
        "trace_id": trace_id,
    }
