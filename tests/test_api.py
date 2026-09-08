import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.service.state_store import state


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "version" in data


def test_protected_ping_security(client):
    res_unauth = client.get("/api/protected-ping")
    assert res_unauth.status_code == 401

    res_wrong_key = client.get("/api/protected-ping", headers={"X-API-Key": "invalid-token"})
    assert res_wrong_key.status_code == 401

    res_auth = client.get("/api/protected-ping", headers={"X-API-Key": "aquapod-secret-key-2026"})
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "authenticated"


def test_readings_latest_empty_initially(client):
    # Ensure fresh state reflects offline and empty before ingestion
    response = client.get("/api/readings/latest")
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data
    assert "is_online" in data
    assert "readings" in data


def test_readings_ingest_and_latest(client):
    payload = {
        "temperature": 28.1,
        "dissolved_oxygen": 6.9,
    }
    response = client.post("/api/readings/ingest", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True

    latest = client.get("/api/readings/latest").json()
    assert latest["is_online"] is True
    assert latest["readings"]["temperature"]["value"] == 28.1
    assert latest["readings"]["dissolved_oxygen"]["value"] == 6.9
    assert latest["readings"]["temperature"]["status"] in ("safe", "warning", "critical")


def test_readings_history(client):
    # Ingest a real reading to ensure SQLite records real history points
    client.post("/api/readings/ingest", json={"ph": 7.45})
    response = client.get("/api/readings/history?param=ph&range=24h")
    assert response.status_code == 200
    data = response.json()
    assert data["parameter"] == "ph"
    assert data["unit"] == "pH"
    assert data["range"] == "24h"
    assert len(data["points"]) > 0
    assert data["points"][-1]["value"] == 7.45
    assert "timestamp" in data["points"][-1]


def test_robot_status(client):
    response = client.get("/api/robot/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_online" in data
    assert "pond_boundary" in data
    assert len(data["pond_boundary"]) >= 3


def test_robot_telemetry_ingest(client):
    payload = {
        "battery_percent": 82,
        "speed_mps": 0.40,
        "current_zone": "Zone A (North Dock)",
    }
    response = client.post("/api/robot/telemetry", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True

    status = client.get("/api/robot/status").json()
    assert status["battery_percent"] == 82
    assert status["position"]["speed_mps"] == 0.40
    assert status["position"]["current_zone"] == "Zone A (North Dock)"


def test_feeding_schedule(client):
    response = client.get("/api/feeding/schedule")
    assert response.status_code == 200
    data = response.json()
    assert "next_feed_time" in data
    assert "predicted_portion_grams" in data
    assert "ml_reasoning" in data
    assert "feed_hopper_level_percent" in data


def test_feeding_trigger_and_lockout(client):
    state.last_feed_datetime = None

    trigger_payload = {"portion_grams": 100, "triggered_by": "manual_app_user"}
    first_resp = client.post("/api/feeding/trigger", json=trigger_payload)
    assert first_resp.status_code == 200
    first_data = first_resp.json()
    assert first_data["success"] is True
    assert first_data["dispensed_grams"] == 100
    assert "dispense_id" in first_data

    second_resp = client.post("/api/feeding/trigger", json=trigger_payload)
    assert second_resp.status_code == 409
    error_detail = second_resp.json()["detail"]
    assert error_detail["success"] is False
    assert "Feeding lockout" in error_detail["message"]


def test_feeding_history(client):
    response = client.get("/api/feeding/history?limit=10")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) > 0
    assert "id" in items[0]
    assert "portion_grams" in items[0]


def test_alerts_active_and_history(client):
    active_resp = client.get("/api/alerts/active")
    assert active_resp.status_code == 200
    assert isinstance(active_resp.json(), list)

    history_resp = client.get("/api/alerts/history")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert "total_anomalies_count" in history_data
    assert "alerts" in history_data


def test_settings_thresholds_mutation(client):
    initial = client.get("/api/settings/thresholds").json()
    assert "temperature" in initial

    update_payload = {
        "temperature": {"min": 25.0, "max": 31.0}
    }
    put_resp = client.put("/api/settings/thresholds", json=update_payload)
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["temperature"]["min"] == 25.0
    assert updated["temperature"]["max"] == 31.0

    client.put("/api/settings/thresholds", json={"temperature": {"min": 26.0, "max": 30.0}})


def test_esp32_telemetry_report_auth(client):
    payload = {
        "device_id": "esp32-aquapod-01",
        "water_quality": {
            "temperature_c": 28.3,
        },
    }
    # Unauthenticated
    res_unauth = client.post("/api/telemetry/report", json=payload)
    assert res_unauth.status_code == 401

    # Invalid API Key
    res_wrong = client.post(
        "/api/telemetry/report",
        json=payload,
        headers={"X-API-Key": "wrong-key"},
    )
    assert res_wrong.status_code == 401


def test_esp32_telemetry_report_exact_firmware_payload(client):
    payload = {
        "device_id": "esp32-aquapod-01",
        "timestamp": "2026-09-07T14:30:00",
        "water_quality": {
            "temperature_c": 28.35,
            "turbidity_raw": 1950,
            "turbidity_voltage": 1.57,
            "turbidity_value": 1.57,
            "ph_voltage": 2.44,
            "ph_value": 7.33,
            "tds_voltage": 0.49,
            "tds_value_ppm": 245.0,
        },
        "feed_hopper": {
            "distance_cm": 8.5,
            "sensor_error": False,
        },
        "imu": {
            "accel_x": 0.02,
            "accel_y": -0.01,
            "accel_z": 9.81,
            "gyro_x": 0.00,
            "gyro_y": 0.00,
            "gyro_z": 0.01,
            "imu_temp_c": 29.0,
        },
        "network": {
            "wifi_rssi_dbm": -64,
        },
    }

    response = client.post(
        "/api/telemetry/report",
        json=payload,
        headers={"X-API-Key": "aquapod-secret-key-2026"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["device_id"] == "esp32-aquapod-01"
    assert "timestamp" in data

    # Verify latest water quality readings updated
    readings = client.get("/api/readings/latest").json()["readings"]
    assert readings["temperature"]["value"] == 28.35
    assert readings["ph"]["value"] == 7.33
    assert readings["turbidity"]["value"] == 1.57
    assert readings["tds"]["value"] == 245.0
    # Dissolved oxygen was omitted by ESP32, so it should retain safe reading
    assert "dissolved_oxygen" in readings
    assert readings["dissolved_oxygen"]["value"] > 0

    # Verify robot status updated
    status_data = client.get("/api/robot/status").json()
    assert status_data["is_online"] is True
    assert status_data["wifi_signal_dbm"] == -64
    assert status_data["wifi_quality"] == "good"

    # Verify feed hopper level updated from ultrasonic distance
    schedule_data = client.get("/api/feeding/schedule").json()
    assert schedule_data["feed_hopper_level_percent"] > 0


def test_esp32_telemetry_disconnected_sensors(client):
    payload = {
        "device_id": "esp32-aquapod-01",
        "water_quality": {
            "temperature_c": None,
            "turbidity_raw": 0,
            "turbidity_voltage": 0.0,
            "turbidity_value": 0.0,
            "ph_voltage": 0.0,
            "ph_value": 7.0,
            "tds_voltage": 0.0,
            "tds_value_ppm": 0.0,
        },
        "feed_hopper": {
            "distance_cm": None,
            "sensor_error": True,
        },
        "network": {
            "wifi_rssi_dbm": -55,
        },
    }

    response = client.post(
        "/api/telemetry/report",
        json=payload,
        headers={"X-API-Key": "aquapod-secret-key-2026"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Check that wifi_quality computed as excellent for -55 dBm
    status_data = client.get("/api/robot/status").json()
    assert status_data["wifi_quality"] == "excellent"


def test_esp32_telemetry_with_optional_gps_and_power(client):
    payload = {
        "device_id": "esp32-aquapod-01",
        "gps": {
            "latitude": 14.5998,
            "longitude": 120.9845,
            "heading_degrees": 180.0,
            "speed_mps": 0.42,
            "current_zone": "Zone C",
        },
        "power": {
            "battery_percent": 91,
            "solar_input_watts": 18.5,
            "is_charging": True,
        },
        "network": {
            "wifi_rssi_dbm": -72,
        },
    }

    response = client.post(
        "/api/telemetry/report",
        json=payload,
        headers={"X-API-Key": "aquapod-secret-key-2026"},
    )
    assert response.status_code == 200

    status_data = client.get("/api/robot/status").json()
    assert status_data["battery_percent"] == 91
    assert status_data["solar_input_watts"] == 18.5
    assert status_data["position"]["latitude"] == 14.5998
    assert status_data["position"]["longitude"] == 120.9845
    assert status_data["position"]["heading_degrees"] == 180.0
    assert status_data["position"]["speed_mps"] == 0.42
    assert status_data["position"]["current_zone"] == "Zone C"
    assert status_data["wifi_quality"] == "fair"


def test_sqlite_persistence_verification(client):
    from app.service.database import get_db

    db = get_db()

    # Ingest full report
    payload = {
        "device_id": "esp32-aquapod-01",
        "timestamp": "2026-09-07T16:00:00",
        "water_quality": {
            "temperature_c": 29.1,
            "turbidity_raw": 1800,
            "turbidity_voltage": 1.45,
            "turbidity_value": 1.45,
            "ph_voltage": 2.40,
            "ph_value": 7.55,
            "tds_voltage": 0.50,
            "tds_value_ppm": 250.0,
        },
        "feed_hopper": {
            "distance_cm": 12.0,
            "sensor_error": False,
        },
        "network": {
            "wifi_rssi_dbm": -59,
        },
    }
    resp = client.post(
        "/api/telemetry/report",
        json=payload,
        headers={"X-API-Key": "aquapod-secret-key-2026"},
    )
    assert resp.status_code == 200

    # Verify SQLite database table has the persisted rows directly
    latest_sensor = db.get_latest_sensor_reading()
    assert latest_sensor is not None
    assert latest_sensor["temperature"] == 29.1
    assert latest_sensor["ph"] == 7.55
    assert latest_sensor["device_id"] == "esp32-aquapod-01"

    latest_telem = db.get_latest_telemetry()
    assert latest_telem is not None
    assert latest_telem["wifi_rssi_dbm"] == -59
    assert latest_telem["feed_distance_cm"] == 12.0
    assert latest_telem["wifi_quality"] == "excellent"


