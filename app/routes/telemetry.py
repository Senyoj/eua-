from fastapi import APIRouter, Depends, status
from app.core.security import verify_api_key
from app.models.telemetry import TelemetryReportRequest, TelemetryReportResponse
from app.service.state_store import StateStore, get_state_store, utc_now_iso

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])


@router.post(
    "/report",
    response_model=TelemetryReportResponse,
    status_code=status.HTTP_200_OK,
    summary="ESP32 Telemetry & Sensor Uplink",
    description="Ingest periodic sensor readings, hopper distance, IMU, and network telemetry directly from the ESP32 robot.",
)
def ingest_telemetry_report(
    payload: TelemetryReportRequest,
    store: StateStore = Depends(get_state_store),
    api_key: str = Depends(verify_api_key),
):
    readings = payload.extract_water_quality_readings()
    telemetry = payload.extract_telemetry_data()

    hopper_dist = None
    hopper_err = False
    if payload.feed_hopper:
        hopper_dist = payload.feed_hopper.distance_cm
        hopper_err = bool(payload.feed_hopper.sensor_error)

    raw_voltages = None
    if payload.water_quality:
        raw_voltages = {
            "turbidity_voltage": payload.water_quality.turbidity_voltage,
            "ph_voltage": payload.water_quality.ph_voltage,
            "tds_voltage": payload.water_quality.tds_voltage,
        }

    store.ingest_full_report(
        readings=readings,
        telemetry=telemetry,
        feed_hopper_distance_cm=hopper_dist,
        feed_hopper_error=hopper_err,
        hopper_level_percent=payload.hopper_level_percent,
        device_id=payload.device_id,
        timestamp=payload.timestamp,
        raw_voltages=raw_voltages,
    )

    return TelemetryReportResponse(
        success=True,
        message="Telemetry report ingested successfully",
        timestamp=utc_now_iso(),
        device_id=payload.device_id,
    )
