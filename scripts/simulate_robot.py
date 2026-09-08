from datetime import datetime, timezone
import math
import sys
import time
import requests

SERVER_URL = "http://127.0.0.1:8000"
API_KEY = "aquapod-secret-key-2026"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}

WAYPOINTS = [
    (14.600000, 120.983500),
    (14.600000, 120.985000),
    (14.599000, 120.985000),
    (14.599000, 120.983500),
]


def calculate_heading(p1, p2):
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    d_lon = lon2 - lon1
    y = math.sin(d_lon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360


def run_simulator(interval_seconds=5):
    current_wp_idx = 0
    progress = 0.0
    step = 0.05
    battery = 95.0
    tick = 0

    print(f"Starting ESP32 & Robot Telemetry Simulator against {SERVER_URL}...")

    while True:
        p1 = WAYPOINTS[current_wp_idx]
        p2 = WAYPOINTS[(current_wp_idx + 1) % len(WAYPOINTS)]

        curr_lat = p1[0] + (p2[0] - p1[0]) * progress
        curr_lon = p1[1] + (p2[1] - p1[1]) * progress
        heading = round(calculate_heading(p1, p2), 1)

        progress += step
        if progress >= 1.0:
            progress = 0.0
            current_wp_idx = (current_wp_idx + 1) % len(WAYPOINTS)

        battery = max(15.0, battery - 0.02)
        temp = round(27.5 + 0.5 * math.sin(tick * 0.1), 2)
        ph = round(7.4 + 0.1 * math.cos(tick * 0.08), 2)
        turbidity = round(18.0 + 1.2 * math.sin(tick * 0.05), 1)
        tds = round(240.0 + 4.0 * math.cos(tick * 0.05), 1)
        do_val = round(6.8 + 0.3 * math.sin(tick * 0.12), 2)

        report_payload = {
            "device_id": "esp32-aquapod-01",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "water_quality": {
                "temperature_c": temp,
                "turbidity_raw": int(turbidity * 100),
                "turbidity_voltage": round(turbidity / 100.0, 3),
                "turbidity_value": turbidity,
                "ph_voltage": round(ph * 0.33, 3),
                "ph_value": ph,
                "tds_voltage": round(tds / 500.0, 3),
                "tds_value_ppm": tds,
                "dissolved_oxygen": do_val,
            },
            "feed_hopper": {
                "distance_cm": round(8.0 + 2.0 * math.sin(tick * 0.1), 1),
                "sensor_error": False,
            },
            "imu": {
                "accel_x": 0.05,
                "accel_y": -0.02,
                "accel_z": 9.81,
                "gyro_x": 0.01,
                "gyro_y": 0.00,
                "gyro_z": -0.01,
                "imu_temp_c": round(temp + 1.0, 1),
            },
            "network": {
                "wifi_rssi_dbm": -62,
            },
            "gps": {
                "latitude": round(curr_lat, 6),
                "longitude": round(curr_lon, 6),
                "heading_degrees": heading,
                "speed_mps": 0.35,
                "current_zone": f"Zone {chr(65 + current_wp_idx)}",
            },
            "power": {
                "battery_percent": int(battery),
                "solar_input_watts": round(14.0 + 2.0 * math.sin(tick * 0.05), 1),
                "is_charging": True,
            },
        }

        try:
            r = requests.post(
                f"{SERVER_URL}/api/telemetry/report",
                json=report_payload,
                headers=HEADERS,
                timeout=3,
            )
            if r.status_code == 200:
                print(f"[TICK {tick}] ESP32 report sent -> Robot at ({curr_lat:.6f}, {curr_lon:.6f}) Heading: {heading}° | Temp: {temp}°C | DO: {do_val} mg/L")
            else:
                print(f"[WARN] HTTP {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[WARN] Connection to {SERVER_URL} failed: {e}")

        tick += 1
        time.sleep(interval_seconds)


if __name__ == "__main__":
    interval = 5
    if len(sys.argv) > 1:
        interval = float(sys.argv[1])
    run_simulator(interval)
