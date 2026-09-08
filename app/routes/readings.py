from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.models.readings import (
    HistoryPoint,
    HistoryResponse,
    IngestReadingsRequest,
    LatestReadingsResponse,
)
from app.service.state_store import StateStore, get_state_store, utc_now_iso

router = APIRouter(prefix="/api/readings", tags=["Readings"])


@router.get("/latest", response_model=LatestReadingsResponse, status_code=status.HTTP_200_OK)
def get_latest_readings(store: StateStore = Depends(get_state_store)):
    return store.get_latest_readings_payload()


@router.get("/history", response_model=HistoryResponse, status_code=status.HTTP_200_OK)
def get_readings_history(
    param: Literal["temperature", "ph", "turbidity", "tds", "dissolved_oxygen"] = Query(...),
    range: Literal["1h", "24h", "7d"] = Query(default="24h"),
    store: StateStore = Depends(get_state_store),
):
    if param not in store.thresholds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {param}",
        )

    thresh = store.thresholds[param]
    raw_points = store.get_history_points(param, range)
    points = [HistoryPoint(**pt) for pt in raw_points]

    return HistoryResponse(
        parameter=param,
        unit=thresh["unit"],
        range=range,
        safe_min=thresh["min"],
        safe_max=thresh["max"],
        points=points,
    )


@router.post("/ingest", status_code=status.HTTP_200_OK)
def ingest_readings(
    payload: IngestReadingsRequest,
    store: StateStore = Depends(get_state_store),
):
    store.update_readings(payload.model_dump(exclude_unset=True))
    return {"success": True, "timestamp": utc_now_iso()}
