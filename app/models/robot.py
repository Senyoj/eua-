from typing import List, Optional
from pydantic import BaseModel, Field


class Position(BaseModel):
    latitude: float
    longitude: float
    heading_degrees: float
    speed_mps: float
    current_zone: str


class PondBoundaryPoint(BaseModel):
    latitude: float
    longitude: float



class RobotStatusResponse(BaseModel):
    is_online: bool
    last_seen: Optional[str] = None
    battery_percent: Optional[int] = Field(default=None, ge=0, le=100)
    solar_input_watts: Optional[float] = 0.0
    is_charging: Optional[bool] = False
    wifi_signal_dbm: Optional[int] = None
    wifi_quality: str = "offline"
    last_slam_update: Optional[str] = None
    slam_status: str = "standby"
    position: Optional[Position] = None
    pond_boundary: List[PondBoundaryPoint] = []


class IngestTelemetryRequest(BaseModel):
    battery_percent: Optional[int] = Field(default=None, ge=0, le=100)
    solar_input_watts: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    heading_degrees: Optional[float] = None
    speed_mps: Optional[float] = None
    current_zone: Optional[str] = None
