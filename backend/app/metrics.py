"""Prometheus metrics for the generation pipeline.

Labels are kept low-cardinality on purpose: never label with prompt,
error_message, user id or IP — every distinct value is a new time series.
Per-request detail lives in the Generation table.

Uses the default registry, which assumes a single uvicorn process. Running
with --workers N needs prometheus_client's multiprocess mode instead.
"""

from prometheus_client import Counter

GENERATIONS = Counter(
    "smi_generations",
    "Diagram generations by outcome",
    ["status", "renderer", "source"],
)


def record_generation(status: str, renderer: str | None, source: str = "server") -> None:
    """Count one generation outcome.

    source="client" marks failures reported by the browser via the public
    render-error endpoint, so alerts can ignore unauthenticated reports.
    """
    GENERATIONS.labels(status=status, renderer=renderer or "unknown", source=source).inc()


EDITOR_OPENS = Counter(
    "smi_editor_opens",
    "Generated diagrams opened in the draw-app editor (first open only)",
    ["renderer"],
)


def record_editor_open(renderer: str | None) -> None:
    EDITOR_OPENS.labels(renderer=renderer or "unknown").inc()
