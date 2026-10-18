import logging
from functools import lru_cache

from banking_agent.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def configure_tracing():
    """Configure an Arize AX or local OpenTelemetry provider and ADK instrumentor."""
    settings = get_settings()
    if settings.capture_trace_content:
        logger.warning(
            "Trace content capture is enabled. This synthetic demo may export prompts and outputs; "
            "never enable it for real customer data without privacy and retention approval."
        )
    try:
        if settings.arize_configured:
            from arize.otel import register

            kwargs = {
                "space_id": settings.arize_space_id,
                "api_key": settings.arize_api_key,
                "project_name": settings.arize_project_name,
            }
            if settings.arize_endpoint:
                kwargs["endpoint"] = settings.arize_endpoint
            provider = register(**kwargs)
            destination = "Arize AX"
        else:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

            provider = TracerProvider(resource=Resource.create({"service.name": settings.app_name}))
            if settings.trace_console:
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)
            destination = "console" if settings.trace_console else "disabled"

        from openinference.instrumentation.google_adk import GoogleADKInstrumentor

        # Content fields are required for useful AX evaluations. Keep them opt-in for privacy.
        instrumentor = GoogleADKInstrumentor()
        if settings.capture_trace_content:
            instrumentor.instrument(tracer_provider=provider)
        else:
            instrumentor.instrument(
                tracer_provider=provider,
                hide_inputs=True,
                hide_outputs=True,
            )
        logger.info("OpenTelemetry configured; destination=%s", destination)
        return provider
    except Exception:
        logger.exception("Unable to configure OpenTelemetry instrumentation")
        raise
