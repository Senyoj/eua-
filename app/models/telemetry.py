from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class WaterQualityTelemetry(BaseModel):
    model_config = ConfigDict(extra="allow")

    temperature_c: Optional[float] = None
    turbidity_raw: Optional[int] = None
    turbidity_voltage: Optional[float] = None
    turbidity_value: Optional[float] = None
    ph_voltage: Optional[float] = None
    ph_value: Optional[float] = None
    tds_voltage: Optional[float] = None
    tds_value_ppm: Optional[float] = None
    dissolved_oxygen: Optional[float] = None


class FeedHopperTelemetry(BaseModel):
    model_config = ConfigDict(extra="allow")

    distance_cm: Optional[float] = None
    sensor_error: Optional[bool] = False


class ImuTelemetry(BaseModel):
    model_config = ConfigDict(extra="allow")

    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None
    imu_temp_c: Optional[float] = None


class NetworkTelemetry(BaseModel):
    model_config = ConfigDict(extra="allow")

    wifi_rssi_dbm: Optional[int] = None


class GpsTelemetry(BaseModel):
    model_config = ConfigDict(extra="allow")

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    heading_degrees: Optional[float] = None
    speed_mps: Optional[float] = None
    current_zone: Optional[str] = None


class PowerTelemetry(BaseModel):
    model_config = ConfigDict(extra="allow")

    battery_percent: Optional[int] = Field(default=None, ge=0, le=100)
    solar_input_watts: Optional[float] = None
    is_charging: Optional[bool] = None


class TelemetryReportRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    device_id: Optional[str] = "esp32-aquapod-01"
    timestamp: Optional[str] = None

    # ESP32 nested telemetry blocks
    water_quality: Optional[WaterQualityTelemetry] = None
    feed_hopper: Optional[FeedHopperTelemetry] = None
    imu: Optional[ImuTelemetry] = None
    network: Optional[NetworkTelemetry] = None
    gps: Optional[GpsTelemetry] = None
    power: Optional[PowerTelemetry] = None

    # Flat fallback / alternate fields
    temperature: Optional[float] = None
    ph: Optional[float] = None
    turbidity: Optional[float] = None
    tds: Optional[float] = None
    dissolved_oxygen: Optional[float] = None
    battery_percent: Optional[int] = None
    solar_input_watts: Optional[float] = None
    is_charging: Optional[bool] = None
    wifi_signal_dbm: Optional[int] = None
    wifi_rssi_dbm: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    heading_degrees: Optional[float] = None
    speed_mps: Optional[float] = None
    current_zone: Optional[str] = None
    hopper_level_percent: Optional[int] = None

    def extract_water_quality_readings(self) -> Dict[str, Optional[float]]:
        readings: Dict[str, Optional[float]] = {}
        if self.water_quality:
            if self.water_quality.temperature_c is not None:
                readings["temperature"] = round(self.water_quality.temperature_c, 2)
            if self.water_quality.ph_value is not None:
                readings["ph"] = round(self.water_quality.ph_value, 2)
            if self.water_quality.turbidity_value is not None:
                readings["turbidity"] = round(self.water_quality.turbidity_value, 2)
            if self.water_quality.tds_value_ppm is not None:
                readings["tds"] = round(self.water_quality.tds_value_ppm, 1)
            if self.water_quality.dissolved_oxygen is not None:
                readings["dissolved_oxygen"] = round(self.water_quality.dissolved_oxygen, 2)

        # Allow flat values as fallback/direct inputs if present
        if self.temperature is not None:
            readings["temperature"] = self.temperature
        if self.ph is not None:
            readings["ph"] = self.ph
        if self.turbidity is not None:
            readings["turbidity"] = self.turbidity
        if self.tds is not None:
            readings["tds"] = self.tds
        if self.dissolved_oxygen is not None:
            readings["dissolved_oxygen"] = self.dissolved_oxygen

        return readings

    def extract_telemetry_data(self) -> Dict[str, Any]:
        telemetry: Dict[str, Any] = {}

        # Network RSSI
        if self.network and self.network.wifi_rssi_dbm is not None:
            telemetry["wifi_signal_dbm"] = self.network.wifi_rssi_dbm
        elif self.wifi_rssi_dbm is not None:
            telemetry["wifi_signal_dbm"] = self.wifi_rssi_dbm
        elif self.wifi_signal_dbm is not None:
            telemetry["wifi_signal_dbm"] = self.wifi_signal_dbm

        # GPS / Navigation
        if self.gps:
            for k in ("latitude", "longitude", "heading_degrees", "speed_mps", "current_zone"):
                v = getattr(self.gps, k, None)
                if v is not None:
                    telemetry[k] = v
        for k in ("latitude", "longitude", "heading_degrees", "speed_mps", "current_zone"):
            v = getattr(self, k, None)
            if v is not None:
                telemetry[k] = v

        # Power
        if self.power:
            for k in ("battery_percent", "solar_input_watts", "is_charging"):
                v = getattr(self.power, k, None)
                if v is not None:
                    telemetry[k] = v
        for k in ("battery_percent", "solar_input_watts", "is_charging"):
            v = getattr(self, k, None)
            if v is not None:
                telemetry[k] = v

        # IMU
        if self.imu:
            telemetry["imu"] = self.imu.model_dump(exclude_none=True)

        return telemetry


class TelemetryReportResponse(BaseModel):
    success: bool
    message: str
    timestamp: str
    device_id: Optional[str] = None
