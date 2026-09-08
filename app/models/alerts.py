from typing import List, Literal, Optional
from pydantic import BaseModel

AlertSeverity = Literal["warning", "critical"]


class ActiveAlertItem(BaseModel):
    id: str
    parameter: str
    current_value: float
    unit: str
    threshold_breached: str
    severity: AlertSeverity
    triggered_at: str
    message: str


class AlertHistoryItem(BaseModel):
    id: str
    parameter: str
    value: float
    threshold: str
    severity: str
    started_at: str
    resolved_at: Optional[str] = None
    duration_minutes: Optional[int] = None


class AlertsHistoryResponse(BaseModel):
    total_anomalies_count: int
    days_tracked: int
    summary: str
    alerts: List[AlertHistoryItem]
