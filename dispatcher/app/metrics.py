"""Prometheus metrics for the dispatcher — the agent gets monitored too."""

from prometheus_client import Counter

ALERTS = Counter(
    "smi_dispatcher_alerts",
    "Alert groups handled by the agent dispatcher, by result",
    ["result"],
)


def record(result: str) -> None:
    """result: dispatched | cooldown | busy | ignored | error | unauthorized"""
    ALERTS.labels(result=result).inc()
