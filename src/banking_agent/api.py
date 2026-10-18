import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from banking_agent.config import get_settings
from banking_agent.database import connect, initialize_database
from banking_agent.evaluation.cli import load_interactions
from banking_agent.evaluation.evaluators import evaluate_all
from banking_agent.schemas import ChatRequest, ChatResponse, EvaluationReport, HealthResponse
from banking_agent.tools import validate_demo_customer
from banking_agent.tracing import configure_tracing

logger = logging.getLogger(__name__)
configure_tracing()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Banking Agent Observability API",
    description="Synthetic read-only banking assistant built with Google ADK, RAG, and OpenTelemetry.",
    version="1.0.0",
    lifespan=lifespan,
)
try:
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    logger.exception("FastAPI OpenTelemetry instrumentation could not be initialized")


def customer_header(x_demo_customer_id: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not x_demo_customer_id or x_demo_customer_id not in settings.demo_customer_ids:
        raise HTTPException(
            status_code=401,
            detail="Use X-Demo-Customer-ID: cust_1001 or cust_1002 for this synthetic demo.",
        )
    if not validate_demo_customer(x_demo_customer_id):
        raise HTTPException(status_code=403, detail="Demo customer is not available.")
    return x_demo_customer_id


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        model=settings.model_name,
        arize_enabled=settings.arize_configured,
    )


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, customer_id: str = Depends(customer_header)) -> ChatResponse:
    settings = get_settings()
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message must contain non-whitespace text.")
    if len(message) > settings.max_request_chars:
        raise HTTPException(status_code=413, detail="Message exceeds the configured request limit.")
    if not settings.google_api_key:
        raise HTTPException(
            status_code=503, detail="Set GOOGLE_API_KEY in .env before starting chat requests."
        )
    from banking_agent.service import chat as run_chat

    try:
        result = await run_chat(
            customer_id=customer_id, message=message, session_id=request.session_id
        )
    except Exception as exc:
        logger.exception("Agent run failed")
        raise HTTPException(
            status_code=502, detail="The agent could not complete this request. Check service logs."
        ) from exc
    return ChatResponse(**result)


@app.get("/v1/sessions/{session_id}/evaluations", response_model=list[EvaluationReport])
def session_evaluations(session_id: str, customer_id: str = Depends(customer_header)):
    conn = connect()
    try:
        exists = conn.execute(
            "SELECT 1 FROM agent_interactions WHERE session_id = ? AND customer_id = ? LIMIT 1",
            (session_id, customer_id),
        ).fetchone()
    finally:
        conn.close()
    if not exists:
        raise HTTPException(status_code=404, detail="Session was not found for this demo customer.")
    interactions = [
        row for row in load_interactions(session_id) if row["customer_id"] == customer_id
    ]
    return [EvaluationReport(**result.to_dict()) for result in evaluate_all(interactions)]


@app.get("/v1/sessions/{session_id}/turns")
def session_turns(session_id: str, customer_id: str = Depends(customer_header)):
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT interaction_id, session_id, created_at, user_input, assistant_output,
                      retrieved_chunks, tool_names, trace_id
               FROM agent_interactions WHERE session_id = ? AND customer_id = ? ORDER BY created_at""",
            (session_id, customer_id),
        ).fetchall()
        if not rows:
            raise HTTPException(
                status_code=404, detail="Session was not found for this demo customer."
            )
        return [
            {
                **dict(row),
                "retrieved_chunks": __import__("json").loads(row["retrieved_chunks"]),
                "tool_names": __import__("json").loads(row["tool_names"]),
            }
            for row in rows
        ]
    finally:
        conn.close()
