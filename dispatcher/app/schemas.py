"""Alertmanager webhook payload (version 4).

https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Alert(BaseModel):
    status: Literal["firing", "resolved"]
    labels: dict[str, str] = {}
    annotations: dict[str, str] = {}
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    generatorURL: str = ""
    fingerprint: str = ""


class AlertmanagerPayload(BaseModel):
    version: str = "4"
    status: Literal["firing", "resolved"]
    receiver: str = ""
    groupKey: str = ""
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}
    externalURL: str = ""
    alerts: list[Alert] = []
