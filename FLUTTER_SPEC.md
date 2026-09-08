# Flutter Mobile Application Specification Document
**Project**: Eau — Autonomous Aquaculture Precision Monitoring & Control System  
**Client Target**: Android Mobile Application (`.apk`)  
**Backend Compatibility**: FastAPI (Python 3.11+, Pydantic V2)  
**Author / Standard**: Production Engineering Specification  

---

## 1. System Architecture & Tech Stack

The Flutter application serves as the single-operator monitoring and light-control dashboard for the autonomous aquaculture pond robot. The app communicates exclusively with the FastAPI backend over HTTP REST. Direct connection to the ESP32 microcontroller is strictly excluded for safety.

```
┌────────────────────────────────────────────────────────┐
│                   Flutter Mobile App                   │
│ ────────────────────────────────────────────────────── │
│ • State Management: flutter_riverpod 2.x               │
│ • Networking: dio with custom X-API-Key Interceptor    │
│ • Mapping: flutter_map + latlong2 (OpenStreetMap)      │
│ • Charts: fl_chart (Curved Bezier Trends)              │
│ • Local Storage: shared_preferences                    │
│ • UI Theme: Marine Dark (#0A192F) & Clean Light        │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP REST (JSON) + X-API-Key
                           ▼
┌────────────────────────────────────────────────────────┐
│                 FastAPI Cloud / LAN Backend            │
│ ────────────────────────────────────────────────────── │
│ • Base URL: http://<LAN_IP>:8000 (e.g. 10.0.2.2:8000)  │
│ • Endpoints: /api/readings, /api/robot, /api/feeding   │
└────────────────────────────────────────────────────────┘
```

### Core Dependencies (`pubspec.yaml`)
```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.1
  dio: ^5.4.3+1
  flutter_map: ^6.1.0
  latlong2: ^0.9.1
  fl_chart: ^0.68.0
  shared_preferences: ^2.2.3
  google_fonts: ^6.2.1
  flutter_animate: ^4.5.0
  intl: ^0.19.0
```

---

## 2. Directory Structure (`lib/`)

```
lib/
├── main.dart                          # App initialization, ProviderScope, theme binding
├── core/
│   ├── config/
│   │   ├── api_endpoints.dart         # Base URL management & path constants
│   │   └── constants.dart             # Default safe limits & timing constants
│   ├── network/
│   │   ├── api_client.dart            # Dio singleton with interceptors & retry logic
│   │   └── api_exceptions.dart        # Custom 401, 409, and timeout handlers
│   ├── theme/
│   │   ├── app_colors.dart            # Marine Navy (#0A192F), Cyan (#00E5FF), Alert Red
│   │   └── app_theme.dart             # Dark & Light ThemeData with Google Fonts (Inter)
│   └── utils/
│       ├── formatters.dart            # Date and unit formatters
│       └── status_helpers.dart        # Color mappings for "safe" | "warning" | "critical"
├── models/
│   ├── reading_model.dart             # Water quality parameters & history points
│   ├── robot_status_model.dart        # GPS coordinates, heading, battery, pond boundary
│   ├── feeding_model.dart             # ML reasoning, schedule, lockout & history
│   ├── alert_model.dart               # Active and past anomaly logs
│   └── threshold_model.dart           # Parameter boundaries
├── repositories/
│   ├── reading_repository.dart        # Network calls for sensor data
│   ├── robot_repository.dart          # Network calls for telemetry & GPS
│   ├── feeding_repository.dart        # Trigger feeding & history fetching
│   ├── alert_repository.dart          # Active & past alerts
│   └── settings_repository.dart       # Threshold getters & setters
├── providers/
│   ├── connection_provider.dart       # Base URL & API Key state (shared_preferences)
│   ├── reading_providers.dart         # 5-second polling timer for latest readings
│   ├── robot_providers.dart           # 5-second polling timer for GPS & battery
│   ├── alert_providers.dart           # Active alert state provider
│   └── feeding_providers.dart         # Feeding action state, cooldown timer
└── ui/
    ├── navigation/
    │   └── app_scaffold.dart          # 5-tab BottomNavigationBar shell
    ├── widgets/
    │   ├── metric_gauge_card.dart     # Circular/linear gauge for parameter values
    │   ├── alert_banner.dart          # Dismissible/persistent red alert strip
    │   ├── hold_to_feed_button.dart   # Long-press button with haptic feedback
    │   └── offline_indicator.dart     # Badge displayed when connectivity drops
    └── screens/
        ├── overview_screen.dart       # Dashboard snapshot, gauges & quick status
        ├── water_quality_screen.dart  # fl_chart time-series graphs (1h, 24h, 7d)
        ├── robot_map_screen.dart      # flutter_map pond boundary + live robot marker
        ├── feeding_screen.dart        # ML recommendation card, hopper gauge & feed history
        └── settings_screen.dart       # IP editor, API key, and threshold sliders
```

---

## 3. Data Models & API Contracts (Dart Mapping)

### A. Water Quality (`reading_model.dart`)
*Endpoint: `GET /api/readings/latest`*
```dart
class ParameterReading {
  final double value;
  final String unit;
  final String status; // "safe" | "warning" | "critical"
  final double safeMin;
  final double safeMax;

  ParameterReading.fromJson(Map<String, dynamic> json)
      : value = (json['value'] as num).toDouble(),
        unit = json['unit'],
        status = json['status'],
        safeMin = (json['safe_min'] as num).toDouble(),
        safeMax = (json['safe_max'] as num).toDouble();
}

class LatestReadingsResponse {
  final String timestamp;
  final bool isOnline;
  final int lastUpdatedSecondsAgo;
  final Map<String, ParameterReading> readings;

  LatestReadingsResponse.fromJson(Map<String, dynamic> json)
      : timestamp = json['timestamp'],
        isOnline = json['is_online'],
        lastUpdatedSecondsAgo = json['last_updated_seconds_ago'],
        readings = (json['readings'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, ParameterReading.fromJson(v)),
        );
}
```

*Endpoint: `GET /api/readings/history?param={param}&range={range}`*
```dart
class HistoryPoint {
  final DateTime timestamp;
  final double value;

  HistoryPoint.fromJson(Map<String, dynamic> json)
      : timestamp = DateTime.parse(json['timestamp']),
        value = (json['value'] as num).toDouble();
}

class HistoryResponse {
  final String parameter;
  final String unit;
  final String range;
  final double safeMin;
  final double safeMax;
  final List<HistoryPoint> points;

  HistoryResponse.fromJson(Map<String, dynamic> json)
      : parameter = json['parameter'],
        unit = json['unit'],
        range = json['range'],
        safeMin = (json['safe_min'] as num).toDouble(),
        safeMax = (json['safe_max'] as num).toDouble(),
        points = (json['points'] as List).map((p) => HistoryPoint.fromJson(p)).toList();
}
```

---

### B. Robot Telemetry & Map (`robot_status_model.dart`)
*Endpoint: `GET /api/robot/status`*
```dart
class RobotPosition {
  final double latitude;
  final double longitude;
  final double headingDegrees;
  final double speedMps;
  final String currentZone;

  RobotPosition.fromJson(Map<String, dynamic> json)
      : latitude = (json['latitude'] as num).toDouble(),
        longitude = (json['longitude'] as num).toDouble(),
        headingDegrees = (json['heading_degrees'] as num).toDouble(),
        speedMps = (json['speed_mps'] as num).toDouble(),
        currentZone = json['current_zone'];
}

class RobotStatusResponse {
  final bool isOnline;
  final String lastSeen;
  final int batteryPercent;
  final double solarInputWatts;
  final bool isCharging;
  final int wifiSignalDbm;
  final String wifiQuality;
  final String slamStatus;
  final RobotPosition position;
  final List<LatLng> pondBoundary;

  RobotStatusResponse.fromJson(Map<String, dynamic> json)
      : isOnline = json['is_online'],
        lastSeen = json['last_seen'],
        batteryPercent = json['battery_percent'],
        solarInputWatts = (json['solar_input_watts'] as num).toDouble(),
        isCharging = json['is_charging'],
        wifiSignalDbm = json['wifi_signal_dbm'],
        wifiQuality = json['wifi_quality'],
        slamStatus = json['slam_status'],
        position = RobotPosition.fromJson(json['position']),
        pondBoundary = (json['pond_boundary'] as List)
            .map((pt) => LatLng((pt['latitude'] as num).toDouble(), (pt['longitude'] as num).toDouble()))
            .toList();
}
```

---

### C. Feeding Subsystem (`feeding_model.dart`)
*Endpoint: `GET /api/feeding/schedule`*
```dart
class FeedingSchedule {
  final String nextFeedTime;
  final int predictedPortionGrams;
  final String mlReasoning;
  final String feederStatus;
  final int feedHopperLevelPercent;

  FeedingSchedule.fromJson(Map<String, dynamic> json)
      : nextFeedTime = json['next_feed_time'],
        predictedPortionGrams = json['predicted_portion_grams'],
        mlReasoning = json['ml_reasoning'],
        feederStatus = json['feeder_status'],
        feedHopperLevelPercent = json['feed_hopper_level_percent'];
}
```

*Endpoint: `POST /api/feeding/trigger`*
- **Request Body**: `{"portion_grams": 100, "triggered_by": "manual_app_user"}`
- **Success Response (HTTP 200)**:
  ```json
  {
    "success": true,
    "message": "Feed command queued and dispatched to robot relay",
    "dispense_id": "feed_20260906_032500",
    "dispensed_grams": 100,
    "timestamp": "2026-09-06T03:25:00Z"
  }
  ```
- **Lockout Response (HTTP 409 Conflict)**:
  ```json
  {
    "detail": {
      "success": false,
      "message": "Feeding lockout: a feeding was completed less than 15 minutes ago. Next manual feed allowed at 03:40:00Z."
    }
  }
  ```

---

## 4. UI Screens & Behavioral Specifications

### Screen 1: Overview Dashboard (`overview_screen.dart`)
1. **Top Alert Banner**: Displays conditionally when `activeAlertsProvider` is non-empty with red pulse animation.
2. **Key Metric Grid**: 5 gauge cards for Temperature, pH, Dissolved Oxygen, Turbidity, and TDS:
   - Safe: Teal/Green badge (`#00E676`).
   - Warning: Amber badge (`#FFD600`).
   - Critical: Crimson badge (`#FF1744`).
3. **Robot Health Mini-Card**: Battery %, Solar Watts, and online indicator with "Updated X seconds ago".

### Screen 2: Water Quality Trends (`water_quality_screen.dart`)
1. **Parameter Selector Tabs**: Horizontally scrollable selector chips for the 5 parameters.
2. **Range Toggle**: Segmented button: `1h` | `24h` | `7d`.
3. **Interactive Graph (`fl_chart`)**:
   - Bezier smooth curves with gradient fill under the line.
   - Horizontal dotted indicator lines for `safe_min` and `safe_max`.
   - Tooltips on touch displaying exact time and reading.

### Screen 3: Live Robot Navigation Map (`robot_map_screen.dart`)
1. **Pond Boundary Polygon**: Renders a filled polygon from `pondBoundary` points with semi-transparent cyan boundary line.
2. **Robot Marker**:
   - Positioned at `position.latitude`, `position.longitude`.
   - Directional heading arrow rotating by `position.heading_degrees`.
3. **Telemetry Overlay Card**: Floating bottom sheet displaying speed ($m/s$), current pond zone, and SLAM navigation state.

### Screen 4: Feeding & ML Control (`feeding_screen.dart`)
1. **ML Portion Insight Card**: Displays `predicted_portion_grams` and `ml_reasoning` in a card with a brain/AI badge.
2. **Hopper Level Progress**: Circular gauge showing food reserve ($0-100\%$).
3. **"Hold-to-Feed" Button**:
   - Requires holding for **1.5 seconds** with progress ring filling up.
   - Prevents accidental pocket clicks.
   - If server returns **HTTP 409 Conflict**, button transitions to a disabled state showing a countdown timer until the lockout expires.
4. **Historical Feeding Log**: List of recent feeds showing timestamp, portion grams, and trigger type (`auto_ml` vs `manual_app`).

### Screen 5: Settings & Configuration (`settings_screen.dart`)
1. **Server Connection**:
   - Base URL input (defaults to `http://10.0.2.2:8000` on emulator or `http://192.168.x.x:8000`).
   - Pre-shared API Key input (`aquapod-secret-key-2026`).
   - "Test Connection" button calling `GET /health` and `GET /api/protected-ping`.
2. **Threshold Sliders**: Sliders allowing the operator to adjust min/max safe ranges, saving via `PUT /api/settings/thresholds`.

---

## 5. Network Layer & Polling Logic

```dart
class ApiClient {
  late final Dio dio;

  ApiClient(String baseUrl, String apiKey) {
    dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 5),
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
    ));

    dio.interceptors.add(InterceptorsWrapper(
      onError: (DioException error, handler) {
        if (error.response?.statusCode == 409) {
          return handler.next(error);
        }
        return handler.next(error);
      },
    ));
  }
}
```

### Polling Provider Pattern
```dart
final latestReadingsProvider = StreamProvider.autoDispose<LatestReadingsResponse>((ref) async* {
  final repo = ref.watch(readingRepositoryProvider);
  while (true) {
    try {
      final data = await repo.getLatestReadings();
      yield data;
    } catch (_) {}
    await Future.delayed(const Duration(seconds: 5));
  }
});
```

---

## 6. Verification Checklist
- [ ] Connect Android device/emulator to same Wi-Fi as your PC.
- [ ] Backend running: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
- [ ] Simulator running: `python scripts/simulate_robot.py`.
- [ ] Verify Flutter app polls data every 5 seconds and updates the map marker continuously.
- [ ] Trigger manual feeding from Flutter UI and verify the 15-minute lockout countdown appears on consecutive clicks.
