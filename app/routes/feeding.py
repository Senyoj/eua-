from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.models.feeding import (
    FeedHistoryItem,
    FeedingScheduleResponse,
    FeedTriggerRequest,
    FeedTriggerResponse,
)
from app.service.ml_feeder import predict_feed_portion
from app.service.state_store import StateStore, get_state_store

router = APIRouter(prefix="/api/feeding", tags=["Feeding"])


from datetime import datetime, timedelta, timezone


@router.get("/schedule", response_model=FeedingScheduleResponse, status_code=status.HTTP_200_OK)
def get_feeding_schedule(store: StateStore = Depends(get_state_store)):
    temp = store.current_readings.get("temperature")
    dissolved_oxygen = store.current_readings.get("dissolved_oxygen")
    hopper_level = store.hopper_level_percent if store.hopper_level_percent is not None else 0

    if temp is not None:
        do_val = dissolved_oxygen if dissolved_oxygen is not None else 6.5
        pred_grams, reasoning = predict_feed_portion(temp, do_val, hopper_level)
    else:
        pred_grams = 100
        reasoning = "Awaiting live sensor data from ESP32; maintaining baseline portion."

    now = datetime.now(timezone.utc)
    t_08 = now.replace(hour=8, minute=0, second=0, microsecond=0)
    t_14 = now.replace(hour=14, minute=0, second=0, microsecond=0)
    if now < t_08:
        next_dt = t_08
    elif now < t_14:
        next_dt = t_14
    else:
        next_dt = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)

    if not store.robot_status.get("is_online"):
        status_str = "offline"
    elif hopper_level <= 5:
        status_str = "low_hopper"
    else:
        status_str = "ready"

    return FeedingScheduleResponse(
        next_feed_time=next_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        predicted_portion_grams=pred_grams,
        ml_reasoning=reasoning,
        feeder_status=status_str,
        feed_hopper_level_percent=hopper_level,
    )


@router.post("/trigger", response_model=FeedTriggerResponse, status_code=status.HTTP_200_OK)
def trigger_feeding(
    payload: FeedTriggerRequest,
    store: StateStore = Depends(get_state_store),
):
    allowed, lockout_msg = store.can_feed(lockout_minutes=15)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "message": lockout_msg},
        )

    record = store.record_feeding(payload.portion_grams, payload.triggered_by)

    return FeedTriggerResponse(
        success=True,
        message="Feed command queued and dispatched to robot relay",
        dispense_id=record["id"],
        dispensed_grams=payload.portion_grams,
        timestamp=record["timestamp"],
    )


@router.get("/history", response_model=List[FeedHistoryItem], status_code=status.HTTP_200_OK)
def get_feeding_history(
    limit: int = Query(default=20, ge=1, le=100),
    store: StateStore = Depends(get_state_store),
):
    return store.feed_history[:limit]
