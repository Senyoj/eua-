from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_PATH = Path("data") / "eau_aquaculture.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_timestamp(ts: Optional[str]) -> str:
    if not ts or ts.strip().lower() in ("string", "null", "none"):
        return utc_now_iso()
    return ts


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_db(self) -> None:
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device_id TEXT,
                    temperature REAL,
                    ph REAL,
                    turbidity REAL,
                    tds REAL,
                    dissolved_oxygen REAL,
                    turbidity_voltage REAL,
                    ph_voltage REAL,
                    tds_voltage REAL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_readings(timestamp);

                CREATE TABLE IF NOT EXISTS robot_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device_id TEXT,
                    wifi_rssi_dbm INTEGER,
                    wifi_quality TEXT,
                    feed_distance_cm REAL,
                    hopper_level_percent INTEGER,
                    accel_x REAL,
                    accel_y REAL,
                    accel_z REAL,
                    gyro_x REAL,
                    gyro_y REAL,
                    gyro_z REAL,
                    imu_temp_c REAL,
                    latitude REAL,
                    longitude REAL,
                    heading_degrees REAL,
                    speed_mps REAL,
                    current_zone TEXT,
                    battery_percent INTEGER,
                    solar_input_watts REAL,
                    is_charging INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON robot_telemetry(timestamp);

                CREATE TABLE IF NOT EXISTS feed_history (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    portion_grams INTEGER NOT NULL,
                    trigger_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_feed_ts ON feed_history(timestamp);

                CREATE TABLE IF NOT EXISTS alert_history (
                    id TEXT PRIMARY KEY,
                    parameter TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    threshold_breached TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    resolved_at TEXT,
                    duration_minutes INTEGER,
                    message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_alert_ts ON alert_history(triggered_at);

                CREATE TABLE IF NOT EXISTS threshold_settings (
                    parameter TEXT PRIMARY KEY,
                    min_val REAL NOT NULL,
                    max_val REAL NOT NULL,
                    unit TEXT NOT NULL
                );
            """)

    def insert_sensor_reading(
        self,
        timestamp: str,
        device_id: Optional[str],
        readings: Dict[str, Optional[float]],
        raw_voltages: Optional[Dict[str, Optional[float]]] = None,
    ) -> None:
        raw = raw_voltages or {}
        now = utc_now_iso()
        valid_ts = normalize_timestamp(timestamp)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sensor_readings (
                    timestamp, device_id, temperature, ph, turbidity, tds, dissolved_oxygen,
                    turbidity_voltage, ph_voltage, tds_voltage, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    valid_ts,
                    device_id,
                    readings.get("temperature"),
                    readings.get("ph"),
                    readings.get("turbidity"),
                    readings.get("tds"),
                    readings.get("dissolved_oxygen"),
                    raw.get("turbidity_voltage"),
                    raw.get("ph_voltage"),
                    raw.get("tds_voltage"),
                    now,
                ),
            )

    def insert_robot_telemetry(
        self,
        timestamp: str,
        device_id: Optional[str],
        telemetry: Dict[str, Any],
        feed_distance_cm: Optional[float] = None,
        hopper_level_percent: Optional[int] = None,
    ) -> None:
        now = utc_now_iso()
        valid_ts = normalize_timestamp(timestamp)
        imu = telemetry.get("imu") or {}
        pos = telemetry.get("position") or {}

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO robot_telemetry (
                    timestamp, device_id, wifi_rssi_dbm, wifi_quality,
                    feed_distance_cm, hopper_level_percent,
                    accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, imu_temp_c,
                    latitude, longitude, heading_degrees, speed_mps, current_zone,
                    battery_percent, solar_input_watts, is_charging, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    valid_ts,
                    device_id,
                    telemetry.get("wifi_signal_dbm"),
                    telemetry.get("wifi_quality"),
                    feed_distance_cm,
                    hopper_level_percent,
                    imu.get("accel_x"),
                    imu.get("accel_y"),
                    imu.get("accel_z"),
                    imu.get("gyro_x"),
                    imu.get("gyro_y"),
                    imu.get("gyro_z"),
                    imu.get("imu_temp_c"),
                    telemetry.get("latitude") if telemetry.get("latitude") is not None else pos.get("latitude"),
                    telemetry.get("longitude") if telemetry.get("longitude") is not None else pos.get("longitude"),
                    telemetry.get("heading_degrees") if telemetry.get("heading_degrees") is not None else pos.get("heading_degrees"),
                    telemetry.get("speed_mps") if telemetry.get("speed_mps") is not None else pos.get("speed_mps"),
                    telemetry.get("current_zone") if telemetry.get("current_zone") is not None else pos.get("current_zone"),
                    telemetry.get("battery_percent"),
                    telemetry.get("solar_input_watts"),
                    1 if telemetry.get("is_charging") else 0 if telemetry.get("is_charging") is not None else None,
                    now,
                ),
            )

    def insert_feed(self, record: Dict[str, Any]) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO feed_history (
                    id, timestamp, portion_grams, trigger_type, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["timestamp"],
                    record["portion_grams"],
                    record["trigger_type"],
                    record["status"],
                    record.get("notes", ""),
                ),
            )

    def get_feed_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM feed_history ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def insert_alert(self, alert: Dict[str, Any]) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alert_history (
                    id, parameter, current_value, threshold_breached, severity,
                    triggered_at, resolved_at, duration_minutes, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert["id"],
                    alert["parameter"],
                    alert.get("current_value", alert.get("value", 0.0)),
                    alert.get("threshold_breached", alert.get("threshold", "")),
                    alert["severity"],
                    alert.get("triggered_at", alert.get("started_at", utc_now_iso())),
                    alert.get("resolved_at"),
                    alert.get("duration_minutes"),
                    alert.get("message", ""),
                ),
            )

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM alert_history ORDER BY triggered_at DESC LIMIT ?",
                (limit,),
            )
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["value"] = d.get("current_value")
                d["threshold"] = d.get("threshold_breached")
                d["started_at"] = d.get("triggered_at")
                results.append(d)
            return results

    def get_sensor_history(
        self,
        parameter: str,
        since_iso: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        if parameter not in ("temperature", "ph", "turbidity", "tds", "dissolved_oxygen"):
            return []

        query = f"""
            SELECT timestamp, {parameter} AS value
            FROM sensor_readings
            WHERE {parameter} IS NOT NULL
              AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, (since_iso, limit))
            return [{"timestamp": row["timestamp"], "value": row["value"]} for row in cursor.fetchall()]

    def get_latest_sensor_reading(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_latest_telemetry(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM robot_telemetry ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_thresholds(self, thresholds: Dict[str, Dict[str, Any]]) -> None:
        with self.get_connection() as conn:
            for param, vals in thresholds.items():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO threshold_settings (parameter, min_val, max_val, unit)
                    VALUES (?, ?, ?, ?)
                    """,
                    (param, vals["min"], vals["max"], vals["unit"]),
                )

    def load_thresholds(self) -> Dict[str, Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM threshold_settings")
            rows = cursor.fetchall()
            if not rows:
                return {}
            return {
                row["parameter"]: {
                    "min": row["min_val"],
                    "max": row["max_val"],
                    "unit": row["unit"],
                }
                for row in rows
            }


db = DatabaseManager()


def get_db() -> DatabaseManager:
    return db
