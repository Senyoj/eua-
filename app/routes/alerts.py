from typing import List
from fastapi import APIRouter, Depends, status
from app.models.alerts import ActiveAlertItem, AlertHistoryItem, AlertsHistoryResponse
from app.service.state_store import StateStore, get_state_store

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/active", response_model=List[ActiveAlertItem], status_code=status.HTTP_200_OK)
def get_active_alerts(store: StateStore = Depends(get_state_store)):
    raw_alerts = store.get_active_alerts()
    return [ActiveAlertItem(**alert) for alert in raw_alerts]


@router.get("/history", response_model=AlertsHistoryResponse, status_code=status.HTTP_200_OK)
def get_alerts_history(store: StateStore = Depends(get_state_store)):
    history_items = [AlertHistoryItem(**item) for item in store.alert_history]
    count = len(history_items)
    return AlertsHistoryResponse(
        total_anomalies_count=count,
        days_tracked=7,
        summary=f"{count} anomalies flagged over the last 7 days",
        alerts=history_items,
    )
