from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    session_id: str | None = Field(default=None, min_length=8, max_length=80)


class ChatResponse(BaseModel):
    session_id: str
    interaction_id: str
    response: str
    trace_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str
    arize_enabled: bool


class EvaluationReport(BaseModel):
    scope: str
    interaction_id: str | None = None
    session_id: str | None = None
    label: str
    score: float
    explanation: str
