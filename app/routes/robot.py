from fastapi import APIRouter, Depends, status
from app.models.robot import IngestTelemetryRequest, RobotStatusResponse
from app.service.state_store import StateStore, get_state_store, utc_now_iso

router = APIRouter(prefix="/api/robot", tags=["Robot"])


@router.get("/status", response_model=RobotStatusResponse, status_code=status.HTTP_200_OK)
def get_robot_status(store: StateStore = Depends(get_state_store)):
    telemetry = store.robot_status.copy()
    telemetry["last_seen"] = utc_now_iso()
    return telemetry


@router.post("/telemetry", status_code=status.HTTP_200_OK)
def ingest_telemetry(
    payload: IngestTelemetryRequest,
    store: StateStore = Depends(get_state_store),
):
    store.update_telemetry(payload.model_dump(exclude_unset=True))
    return {"success": True}
