Eau — Autonomous Aquaculture Precision Monitoring & Control System
A complete developer reference and API contract for the FastAPI Backend Developer and Flutter Mobile Developer.

📌 Executive Summary
Product: Autonomous aquaculture robot monitoring & light-control Android mobile application (.apk).
Flutter Client: Android-only mobile app built with Flutter & Riverpod, using OpenStreetMap (flutter_map) for live GPS robot tracking and fl_chart for water quality trends.
Backend API: FastAPI (Python) serving RESTful JSON endpoints.
Data Flow: The mobile app communicates only with the FastAPI backend. It never talks directly to the ESP32 microcontroller or robot hardware.
Actuation: A single write action exists from App → Backend → Robot: the "Feed Now" manual override command. Direct teleoperation/motor steering is strictly excluded for safety.
🔐 Authentication Recommendation (Single-User Setup)
Do we need authentication for 1 user?
Recommendation: No full login/user database needed, BUT use a Pre-Shared API Key (X-API-Key).

Why?
Physical Actuator Safety: The robot dispenses physical fish food into an aquatic ecosystem. Overfeeding fouls the water and risks killing stock. If the FastAPI server is exposed on a pond Wi-Fi network or public IP, an open POST /api/feeding/trigger could be triggered accidentally or maliciously.
Zero UX Friction: The single operator does not need a registration or login screen. The app simply stores the pre-shared key in device storage (shared_preferences) or defaults to an environment key.
5 Minutes to Implement:
FastAPI: 5 lines using APIKeyHeader(name="X-API-Key").
Flutter: 1 line in Dio interceptor (options.headers['X-API-Key'] = storedKey).
🏗️ System Architecture
                                 ┌─────────────────────────────┐
                                 │   Aquaculture Robot         │
                                 │  - ESP32 (Sensors)          │
                                 │  - ESP32-CAM, GPS, IMU      │
                                 └──────────────┬──────────────┘
                                                │ Wi-Fi Push
                                                ▼
                                 ┌─────────────────────────────┐
                                 │    FastAPI Cloud Backend    │
                                 │  - REST Endpoints           │
                                 │  - Time-series DB / SQLite  │
                                 │  - ML Feeding Model         │
                                 └──────────────┬──────────────┘
                                                │ REST Polling (5-10s)
                                                ▼
                                 ┌─────────────────────────────┐
                                 │    Flutter Mobile App       │
                                 │  (Android APK)              │
                                 │  - Riverpod State Mgmt      │
                                 │  - OpenStreetMap (GPS Map)  │
                                 │  - fl_chart (Trends)        │
                                 └─────────────────────────────┘
🌐 API Specification & Data Contract
Base URL: Configurable in Flutter app (e.g. http://192.168.1.100:8000 or https://api.aquapod.io)
Header: X-API-Key: <YOUR_SECRET_TOKEN> (optional during local dev, recommended in production)
Data Format: application/json for all requests and responses. Timestamps are ISO 8601 UTC strings (YYYY-MM-DDTHH:MM:SSZ).

1. Water Quality & Sensor Readings
GET /api/readings/latest
Returns current real-time readings for all water quality parameters.

Response 200 OK:

{
  "timestamp": "2026-08-31T12:00:00Z",
  "is_online": true,
  "last_updated_seconds_ago": 4,
  "readings": {
    "temperature": {
      "value": 27.8,
      "unit": "°C",
      "status": "safe",
      "safe_min": 26.0,
      "safe_max": 30.0
    },
    "ph": {
      "value": 7.4,
      "unit": "pH",
      "status": "safe",
      "safe_min": 6.5,
      "safe_max": 8.5
    },
    "turbidity": {
      "value": 18.2,
      "unit": "NTU",
      "status": "safe",
      "safe_min": 0.0,
      "safe_max": 50.0
    },
    "tds": {
      "value": 240.0,
      "unit": "ppm",
      "status": "safe",
      "safe_min": 100.0,
      "safe_max": 400.0
    },
    "dissolved_oxygen": {
      "value": 6.8,
      "unit": "mg/L",
      "status": "safe",
      "safe_min": 5.0,
      "safe_max": 14.0
    }
  }
}
Note on status values: "safe" | "warning" | "critical"

GET /api/readings/history
Query historical points for time-series charts (fl_chart).

Query Parameters:

param (required): temperature | ph | turbidity | tds | dissolved_oxygen
range (optional, default 24h): 1h | 24h | 7d
Response 200 OK:

{
  "parameter": "ph",
  "unit": "pH",
  "range": "24h",
  "safe_min": 6.5,
  "safe_max": 8.5,
  "points": [
    { "timestamp": "2026-08-30T12:00:00Z", "value": 7.2 },
    { "timestamp": "2026-08-30T16:00:00Z", "value": 7.5 },
    { "timestamp": "2026-08-30T20:00:00Z", "value": 7.8 },
    { "timestamp": "2026-08-31T00:00:00Z", "value": 7.6 },
    { "timestamp": "2026-08-31T06:00:00Z", "value": 7.1 },
    { "timestamp": "2026-08-31T12:00:00Z", "value": 7.4 }
  ]
}
2. Robot Telemetry & Navigation
GET /api/robot/status
Returns robot power status, network telemetry, GPS coordinates, and SLAM navigation health.

Response 200 OK:

{
  "is_online": true,
  "last_seen": "2026-08-31T11:59:52Z",
  "battery_percent": 84,
  "solar_input_watts": 14.2,
  "is_charging": true,
  "wifi_signal_dbm": -58,
  "wifi_quality": "good",
  "last_slam_update": "2026-08-31T11:59:50Z",
  "slam_status": "tracking",
  "position": {
    "latitude": 14.599512,
    "longitude": 120.984222,
    "heading_degrees": 142.5,
    "speed_mps": 0.35,
    "current_zone": "Zone B (Deep Center)"
  },
  "pond_boundary": [
    { "latitude": 14.600000, "longitude": 120.983500 },
    { "latitude": 14.600000, "longitude": 120.985000 },
    { "latitude": 14.599000, "longitude": 120.985000 },
    { "latitude": 14.599000, "longitude": 120.983500 }
  ]
}
3. Feeding Subsystem
GET /api/feeding/schedule
Returns next scheduled feeding time and ML portion prediction with reasoning.

Response 200 OK:

{
  "next_feed_time": "2026-08-31T14:00:00Z",
  "predicted_portion_grams": 150,
  "ml_reasoning": "Portion increased by 15% due to optimal water temp (27.8°C) and elevated daytime fish activity.",
  "feeder_status": "ready",
  "feed_hopper_level_percent": 72
}
POST /api/feeding/trigger
Triggers an immediate manual feed action.
Requires user confirmation in Flutter UI before calling.

Request Body:

{
  "portion_grams": 100,
  "triggered_by": "manual_app_user"
}
Response 200 OK:

{
  "success": true,
  "message": "Feed command queued and dispatched to robot relay",
  "dispense_id": "feed_20260831_120100",
  "dispensed_grams": 100,
  "timestamp": "2026-08-31T12:01:00Z"
}
Error Response 409 Conflict (Safety Lockout):

{
  "success": false,
  "message": "Feeding lockout: a feeding was completed less than 15 minutes ago. Next manual feed allowed at 12:15:00Z."
}
GET /api/feeding/history
Returns historical feeding log (both automatic and manual triggers).

Query Parameters:

limit (default 20): Integer
Response 200 OK:

[
  {
    "id": "feed_102",
    "timestamp": "2026-08-31T08:00:00Z",
    "portion_grams": 140,
    "trigger_type": "auto_ml",
    "status": "success",
    "notes": "Optimal morning feed"
  },
  {
    "id": "feed_101",
    "timestamp": "2026-08-30T18:00:00Z",
    "portion_grams": 100,
    "trigger_type": "manual_app",
    "status": "success",
    "notes": "Manual operator supplement"
  }
]
4. Alerts & Anomalies
GET /api/alerts/active
Returns currently breached parameters. If empty ([]), the system is nominal. When non-empty, Flutter displays a persistent red warning banner.

Response 200 OK:

[
  {
    "id": "alert_20260831_01",
    "parameter": "dissolved_oxygen",
    "current_value": 4.2,
    "unit": "mg/L",
    "threshold_breached": "< 5.0 mg/L",
    "severity": "critical",
    "triggered_at": "2026-08-31T11:45:00Z",
    "message": "Dissolved Oxygen critical: 4.2 mg/L is below safe minimum (5.0 mg/L)."
  }
]
GET /api/alerts/history
Historical log of past anomalies for reporting and analysis.

Response 200 OK:

{
  "total_anomalies_count": 14,
  "days_tracked": 7,
  "summary": "14 anomalies flagged over the last 7 days",
  "alerts": [
    {
      "id": "alert_20260830_02",
      "parameter": "temperature",
      "value": 31.4,
      "threshold": "> 30.0 °C",
      "severity": "warning",
      "started_at": "2026-08-30T13:10:00Z",
      "resolved_at": "2026-08-30T15:30:00Z",
      "duration_minutes": 140
    }
  ]
]
5. Settings & Threshold Configuration
GET /api/settings/thresholds
Returns user-configurable safe ranges.

Response 200 OK:

{
  "temperature": { "min": 26.0, "max": 30.0, "unit": "°C" },
  "ph": { "min": 6.5, "max": 8.5, "unit": "pH" },
  "turbidity": { "min": 0.0, "max": 50.0, "unit": "NTU" },
  "tds": { "min": 100.0, "max": 400.0, "unit": "ppm" },
  "dissolved_oxygen": { "min": 5.0, "max": 14.0, "unit": "mg/L" }
}
PUT /api/settings/thresholds
Update threshold configuration.

Request Body:

{
  "temperature": { "min": 25.5, "max": 30.5 },
  "ph": { "min": 6.8, "max": 8.2 }
}

6. ESP32 Telemetry & Sensor Uplink
POST /api/telemetry/report
Periodic sensor and telemetry report ingested directly from the ESP32 microcontroller firmware (~6s cadence).
Header: X-API-Key: aquapod-secret-key-2026

Request Body (Matching ESP32 Firmware JSON):

{
  "device_id": "esp32-aquapod-01",
  "timestamp": "2026-09-07T12:00:00",
  "water_quality": {
    "temperature_c": 28.3,
    "turbidity_raw": 1950,
    "turbidity_voltage": 1.57,
    "turbidity_value": 1.57,
    "ph_voltage": 2.44,
    "ph_value": 7.33,
    "tds_voltage": 0.49,
    "tds_value_ppm": 245.0
  },
  "feed_hopper": {
    "distance_cm": 8.5,
    "sensor_error": false
  },
  "imu": {
    "accel_x": 0.02,
    "accel_y": -0.01,
    "accel_z": 9.81,
    "gyro_x": 0.00,
    "gyro_y": 0.00,
    "gyro_z": 0.01,
    "imu_temp_c": 29.0
  },
  "network": {
    "wifi_rssi_dbm": -64
  }
}

Response 200 OK:

{
  "success": true,
  "message": "Telemetry report ingested successfully",
  "timestamp": "2026-09-07T12:00:01Z",
  "device_id": "esp32-aquapod-01"
}

📱 Flutter Mobile Architecture (Android)
Tech Stack
Framework: Flutter 3.x (Dart 3.x) targeting Android SDK 34 (minSdkVersion 21)
State Management: flutter_riverpod (v2.x with StateNotifier / AsyncNotifier)
Networking: dio with custom retry interceptor & Base URL manager
Maps: flutter_map + latlong2 (OpenStreetMap vector tiles — requires NO Google Maps API key)
Charts: fl_chart (custom Bezier smooth curves, gradient fills, interactive touch tooltips)
Local Storage: shared_preferences (persisting server URL, API key, user threshold tweaks)
Styling: Ocean Dark & Modern Light Themes, google_fonts (Inter / Outfit)
Folder Structure
lib/
├── core/
│   ├── config/api_endpoints.dart     # Base URL, timeout durations, headers
│   ├── network/api_client.dart       # Dio instance with error interceptors
│   ├── theme/app_theme.dart          # Marine color palette, cards, typography
│   └── utils/formatters.dart         # Date and sensor unit formatters
├── models/
│   ├── sensor_reading.dart
│   ├── robot_status.dart
│   ├── feeding_info.dart
│   ├── alert_model.dart
│   └── threshold_config.dart
├── repositories/
│   ├── sensor_repository.dart
│   ├── robot_repository.dart
│   ├── feeding_repository.dart
│   └── alerts_repository.dart
├── providers/
│   ├── sensor_providers.dart         # Polling timer provider (every 5s)
│   ├── robot_providers.dart          # Telemetry & GPS stream
│   ├── feeding_providers.dart        # Feed action state & history
│   └── alert_providers.dart          # Active alert banner state
└── ui/
    ├── navigation/app_scaffold.dart   # Bottom navigation bar (5 primary tabs)
    ├── widgets/                      # MetricCard, AlertBanner, ConfirmModal, SensorGauge
    └── screens/
        ├── overview_screen.dart      # Quick dashboard snapshot & system status
        ├── water_quality_screen.dart # Interactive fl_chart & parameter cards
        ├── feeding_screen.dart       # ML reasoning card, Hold-to-Feed button, log
        ├── robot_map_screen.dart     # Interactive OpenStreetMap & telemetry
        ├── alerts_screen.dart        # Anomaly log & severity filters
        └── settings_screen.dart      # Base URL editor, API key, threshold sliders
🐍 FastAPI Backend Implementation Guide
Recommended Structure
backend/
├── app/
│   ├── main.py              # FastAPI app definition & CORS middleware
│   ├── core/config.py       # Pydantic Settings (.env, API keys)
│   ├── core/security.py     # Simple X-API-Key verification dependency
│   ├── models/schemas.py    # Pydantic models (match the JSON schemas above)
│   ├── routers/
│   │   ├── readings.py      # /api/readings/latest & /api/readings/history
│   │   ├── robot.py         # /api/robot/status
│   │   ├── feeding.py       # /api/feeding/*
│   │   ├── alerts.py        # /api/alerts/*
│   │   └── settings.py      # /api/settings/*
│   └── services/
│       ├── esp32_receiver.py # Ingestion endpoint or MQTT worker for robot data
│       └── ml_feeder.py     # ML feeding logic / portion calculations
├── requirements.txt
└── Dockerfile
FastAPI CORS Configuration
Ensure CORS allows mobile app access:

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Eau Aquaculture API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow mobile devices on LAN
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Simple API Key Authentication Dependency
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY = "aquapod-secret-key-2026"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    # During early development you can toggle this off if needed
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return api_key
⚡ Android Build & Packaging
Run in Debug Mode
flutter pub get
flutter run
Build Production APK
flutter build apk --release
# Output APK location:
# build/app/outputs/flutter-apk/app-release.apk
🤝 Collaboration Workflow Between Backend & Flutter Dev
Mock Data First: Backend dev ensures endpoints return sample JSON matching the schemas in this README immediately so the Flutter dev can wire up UI and Riverpod providers without waiting for real ESP32 sensor hardware.
Offline Degradation: Flutter dev handles empty/null responses and connectivity drops gracefully, rendering "Last known values" and "Offline since [timestamp]".
Safety Verification: The Flutter app will always show a confirmation prompt before dispatching POST /api/feeding/trigger. Backend will validate that no concurrent feeds are running.