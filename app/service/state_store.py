from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from app.service.database import DatabaseManager, get_db, utc_now_iso


class StateStore:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self._lock = Lock()
        self.db = db or get_db()
        self.last_feed_datetime: Optional[datetime] = None

        # Load persisted threshold configurations or initialize defaults
        saved_thresholds = self.db.load_thresholds()
        self.thresholds: Dict[str, Dict[str, Any]] = saved_thresholds or {
            "temperature": {"min": 26.0, "max": 30.0, "unit": "°C"},
            "ph": {"min": 6.5, "max": 8.5, "unit": "pH"},
            "turbidity": {"min": 0.0, "max": 50.0, "unit": "NTU"},
            "tds": {"min": 100.0, "max": 400.0, "unit": "ppm"},
            "dissolved_oxygen": {"min": 5.0, "max": 14.0, "unit": "mg/L"},
        }
        if not saved_thresholds:
            self.db.save_thresholds(self.thresholds)

        # Real sensor readings — empty on startup until ESP32 reports
        self.current_readings: Dict[str, float] = {}
        self.last_reading_time: Optional[datetime] = None
        self.hopper_level_percent: Optional[int] = None

        # Real robot status — uninitialized/offline until ESP32 reports
        self.robot_status: Dict[str, Any] = {
            "is_online": False,
            "last_seen": None,
            "battery_percent": None,
            "solar_input_watts": 0.0,
            "is_charging": False,
            "wifi_signal_dbm": None,
            "wifi_quality": "offline",
            "last_slam_update": None,
            "slam_status": "standby",
            "position": None,
            "pond_boundary": [
                {"latitude": 14.600000, "longitude": 120.983500},
                {"latitude": 14.600000, "longitude": 120.985000},
                {"latitude": 14.599000, "longitude": 120.985000},
                {"latitude": 14.599000, "longitude": 120.983500},
            ],
        }

        # Restore latest state from database if available (persisted from previous runs)
        latest_sensor = self.db.get_latest_sensor_reading()
        if latest_sensor:
            for k in ("temperature", "ph", "turbidity", "tds", "dissolved_oxygen"):
                if latest_sensor.get(k) is not None:
                    self.current_readings[k] = latest_sensor[k]
            if latest_sensor.get("timestamp"):
                try:
                    ts_str = latest_sensor["timestamp"].replace("Z", "+00:00")
                    self.last_reading_time = datetime.fromisoformat(ts_str)
                except Exception:
                    pass

        latest_telem = self.db.get_latest_telemetry()
        if latest_telem:
            if latest_telem.get("hopper_level_percent") is not None:
                self.hopper_level_percent = latest_telem["hopper_level_percent"]
            if latest_telem.get("wifi_rssi_dbm") is not None:
                self.robot_status["wifi_signal_dbm"] = latest_telem["wifi_rssi_dbm"]
                self.robot_status["wifi_quality"] = latest_telem.get("wifi_quality", "offline")
            if latest_telem.get("battery_percent") is not None:
                self.robot_status["battery_percent"] = latest_telem["battery_percent"]
            if latest_telem.get("solar_input_watts") is not None:
                self.robot_status["solar_input_watts"] = latest_telem["solar_input_watts"]
            if latest_telem.get("latitude") is not None and latest_telem.get("longitude") is not None:
                self.robot_status["position"] = {
                    "latitude": latest_telem["latitude"],
                    "longitude": latest_telem["longitude"],
                    "heading_degrees": latest_telem.get("heading_degrees") or 0.0,
                    "speed_mps": latest_telem.get("speed_mps") or 0.0,
                    "current_zone": latest_telem.get("current_zone") or "Zone A",
                }
            if latest_telem.get("timestamp"):
                self.robot_status["last_seen"] = latest_telem["timestamp"]

        # Restore feed and alert logs from SQLite (clean empty lists on a fresh database)
        self.feed_history: List[Dict[str, Any]] = self.db.get_feed_history(limit=20)
        if self.feed_history:
            try:
                self.last_feed_datetime = datetime.fromisoformat(self.feed_history[0]["timestamp"].replace("Z", "+00:00"))
            except Exception:
                pass

        self.alert_history: List[Dict[str, Any]] = self.db.get_alert_history(limit=50)

    def compute_status(self, param: str, value: float) -> str:
        thresh = self.thresholds.get(param)
        if not thresh:
            return "safe"
        s_min, s_max = thresh["min"], thresh["max"]
        if value < s_min or value > s_max:
            dev = (s_min - value) if value < s_min else (value - s_max)
            span = max(1.0, s_max - s_min)
            return "critical" if (dev / span) > 0.15 else "warning"
        return "safe"

    def get_latest_readings_payload(self) -> Dict[str, Any]:
        with self._lock:
            if not self.last_reading_time or not self.current_readings:
                return {
                    "timestamp": utc_now_iso(),
                    "is_online": False,
                    "last_updated_seconds_ago": None,
                    "readings": {},
                }

            last_tz = self.last_reading_time if self.last_reading_time.tzinfo else self.last_reading_time.replace(tzinfo=timezone.utc)
            secs_ago = max(0, int((datetime.now(timezone.utc) - last_tz).total_seconds()))
            is_online = (secs_ago <= 30)

            readings = {}
            for k, val in self.current_readings.items():
                if val is not None and k in self.thresholds:
                    t = self.thresholds[k]
                    readings[k] = {
                        "value": val,
                        "unit": t["unit"],
                        "status": self.compute_status(k, val),
                        "safe_min": t["min"],
                        "safe_max": t["max"],
                    }
            return {
                "timestamp": utc_now_iso(),
                "is_online": is_online,
                "last_updated_seconds_ago": secs_ago,
                "readings": readings,
            }

    def get_history_points(self, param: str, range_str: str) -> List[Dict[str, Any]]:
        with self._lock:
            now = datetime.now(timezone.utc)
            if range_str == "1h":
                since = now - timedelta(hours=1)
            elif range_str == "7d":
                since = now - timedelta(days=7)
            else:
                since = now - timedelta(hours=24)

            since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            return self.db.get_sensor_history(param, since_iso=since_iso)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        with self._lock:
            alerts = []
            for param, val in self.current_readings.items():
                if val is None or param not in self.thresholds:
                    continue
                status = self.compute_status(param, val)
                if status in ("warning", "critical"):
                    t = self.thresholds[param]
                    thresh_str = f"< {t['min']} {t['unit']}" if val < t["min"] else f"> {t['max']} {t['unit']}"
                    alerts.append({
                        "id": f"alert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{param[:3]}",
                        "parameter": param,
                        "current_value": val,
                        "unit": t["unit"],
                        "threshold_breached": thresh_str,
                        "severity": status,
                        "triggered_at": utc_now_iso(),
                        "message": f"{param.replace('_', ' ').title()} {status}: {val} {t['unit']} is outside safe range ({t['min']} - {t['max']} {t['unit']}).",
                    })
            return alerts

    def can_feed(self, lockout_minutes: int = 15) -> Tuple[bool, Optional[str]]:
        with self._lock:
            if not self.last_feed_datetime:
                return True, None
            feed_tz = self.last_feed_datetime if self.last_feed_datetime.tzinfo else self.last_feed_datetime.replace(tzinfo=timezone.utc)
            elapsed = datetime.now(timezone.utc) - feed_tz
            if elapsed < timedelta(minutes=lockout_minutes):
                next_allowed = (feed_tz + timedelta(minutes=lockout_minutes)).strftime("%H:%M:%SZ")
                return False, f"Feeding lockout: a feeding was completed less than {lockout_minutes} minutes ago. Next manual feed allowed at {next_allowed}."
            return True, None

    def record_feeding(self, portion_grams: int, triggered_by: str) -> Dict[str, Any]:
        with self._lock:
            now = datetime.now(timezone.utc)
            self.last_feed_datetime = now
            dispense_id = f"feed_{now.strftime('%Y%m%d_%H%M%S')}"
            record = {
                "id": dispense_id,
                "timestamp": utc_now_iso(),
                "portion_grams": portion_grams,
                "trigger_type": triggered_by,
                "status": "success",
                "notes": f"Manual feed triggered via {triggered_by}",
            }
            self.feed_history.insert(0, record)
            if self.hopper_level_percent is not None:
                self.hopper_level_percent = max(0, self.hopper_level_percent - 2)
            self.db.insert_feed(record)
            return record

    def update_hopper_level(self, level: int) -> None:
        with self._lock:
            self.hopper_level_percent = max(0, min(100, int(level)))

    def update_hopper_from_distance(self, distance_cm: float, empty_cm: float = 25.0, full_cm: float = 4.0) -> int:
        with self._lock:
            span = max(1.0, empty_cm - full_cm)
            clamped_dist = max(full_cm, min(empty_cm, distance_cm))
            pct = int(round(((empty_cm - clamped_dist) / span) * 100))
            self.hopper_level_percent = max(0, min(100, pct))
            self.robot_status["hopper_distance_cm"] = distance_cm
            return self.hopper_level_percent

    def update_readings(
        self,
        readings: Dict[str, Optional[float]],
        timestamp: Optional[str] = None,
        device_id: Optional[str] = None,
        raw_voltages: Optional[Dict[str, Optional[float]]] = None,
    ) -> None:
        with self._lock:
            now_dt = datetime.now(timezone.utc)
            now_iso = timestamp or utc_now_iso()

            has_new_val = False
            for k, v in readings.items():
                if v is not None and k in self.thresholds:
                    self.current_readings[k] = v
                    has_new_val = True

                    status = self.compute_status(k, v)
                    if status in ("warning", "critical"):
                        t = self.thresholds[k]
                        thresh_str = f"< {t['min']} {t['unit']}" if v < t["min"] else f"> {t['max']} {t['unit']}"
                        alert = {
                            "id": f"alert_{now_dt.strftime('%Y%m%d_%H%M%S')}_{k[:3]}",
                            "parameter": k,
                            "current_value": v,
                            "threshold_breached": thresh_str,
                            "severity": status,
                            "triggered_at": now_iso,
                            "message": f"{k.replace('_', ' ').title()} {status}: {v} {t['unit']} is outside safe range ({t['min']} - {t['max']} {t['unit']}).",
                        }
                        self.alert_history.insert(0, alert)
                        self.db.insert_alert(alert)

            if has_new_val:
                self.last_reading_time = now_dt
                self.db.insert_sensor_reading(
                    timestamp=now_iso,
                    device_id=device_id,
                    readings=readings,
                    raw_voltages=raw_voltages,
                )

    def update_telemetry(
        self,
        telemetry: Dict[str, Any],
        timestamp: Optional[str] = None,
        device_id: Optional[str] = None,
        feed_dist: Optional[float] = None,
        hopper_pct: Optional[int] = None,
    ) -> None:
        with self._lock:
            pos_fields = ("latitude", "longitude", "heading_degrees", "speed_mps", "current_zone")
            pos_updates = {k: v for k, v in telemetry.items() if k in pos_fields and v is not None}
            if pos_updates:
                if self.robot_status.get("position") is None:
                    self.robot_status["position"] = {
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "heading_degrees": 0.0,
                        "speed_mps": 0.0,
                        "current_zone": "Zone A",
                    }
                self.robot_status["position"].update(pos_updates)

            for k in (
                "battery_percent",
                "solar_input_watts",
                "is_charging",
                "wifi_signal_dbm",
                "wifi_quality",
                "slam_status",
                "imu",
                "device_id",
                "hopper_distance_cm",
            ):
                if k in telemetry and telemetry[k] is not None:
                    self.robot_status[k] = telemetry[k]

            if "wifi_signal_dbm" in telemetry and telemetry["wifi_signal_dbm"] is not None and "wifi_quality" not in telemetry:
                rssi = telemetry["wifi_signal_dbm"]
                if rssi >= -60:
                    self.robot_status["wifi_quality"] = "excellent"
                elif rssi >= -70:
                    self.robot_status["wifi_quality"] = "good"
                elif rssi >= -85:
                    self.robot_status["wifi_quality"] = "fair"
                else:
                    self.robot_status["wifi_quality"] = "poor"

            self.robot_status["is_online"] = True
            self.robot_status["last_seen"] = timestamp or utc_now_iso()

            self.db.insert_robot_telemetry(
                timestamp=timestamp or utc_now_iso(),
                device_id=device_id or self.robot_status.get("device_id"),
                telemetry=self.robot_status,
                feed_distance_cm=feed_dist or self.robot_status.get("hopper_distance_cm"),
                hopper_level_percent=hopper_pct or self.hopper_level_percent,
            )

    def ingest_full_report(
        self,
        readings: Dict[str, Optional[float]],
        telemetry: Dict[str, Any],
        feed_hopper_distance_cm: Optional[float] = None,
        feed_hopper_error: bool = False,
        hopper_level_percent: Optional[int] = None,
        device_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        raw_voltages: Optional[Dict[str, Optional[float]]] = None,
    ) -> None:
        if hopper_level_percent is not None:
            self.update_hopper_level(hopper_level_percent)
        elif feed_hopper_distance_cm is not None and not feed_hopper_error:
            self.update_hopper_from_distance(feed_hopper_distance_cm)

        if readings:
            self.update_readings(
                readings,
                timestamp=timestamp,
                device_id=device_id,
                raw_voltages=raw_voltages,
            )

        if device_id:
            telemetry["device_id"] = device_id

        self.update_telemetry(
            telemetry,
            timestamp=timestamp,
            device_id=device_id,
            feed_dist=feed_hopper_distance_cm,
            hopper_pct=self.hopper_level_percent,
        )

        if timestamp:
            with self._lock:
                self.robot_status["last_hardware_timestamp"] = timestamp

    def update_thresholds(self, updates: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            for param, vals in updates.items():
                if param in self.thresholds:
                    if vals.get("min") is not None:
                        self.thresholds[param]["min"] = vals["min"]
                    if vals.get("max") is not None:
                        self.thresholds[param]["max"] = vals["max"]
            self.db.save_thresholds(self.thresholds)
            return self.thresholds


state = StateStore()


def get_state_store() -> StateStore:
    return state
