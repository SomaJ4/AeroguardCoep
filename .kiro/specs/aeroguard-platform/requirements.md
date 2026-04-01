# Requirements Document

## Introduction

AeroGuard is an AI-powered urban safety and surveillance platform that converts passive CCTV infrastructure
into an intelligent detection-to-response pipeline. An operator selects a camera source and starts monitoring
from a React dashboard. A vision service (developed separately) analyzes the video feed and writes incident
data to Supabase. The FastAPI backend applies risk-based decision logic and either logs the incident, alerts
the operator, or autonomously dispatches the nearest available drone. All state changes are pushed to the
dashboard in real time via Supabase Realtime, where operators see a live map, incident cards, drone status,
and ETA countdowns.

System flow: Monitoring → Detection → Decision → Dispatch → Live Visualization

## Glossary

- **System**: The AeroGuard platform as a whole
- **Backend**: The FastAPI application responsible for business logic, API endpoints, and Supabase interaction
- **Dashboard**: The React + Vite + Leaflet operator interface
- **Vision_Service**: The external computer-vision component (placeholder; developed by Om) that writes incident
  records directly to Supabase
- **Supabase**: The hosted PostgreSQL + Realtime + Storage backend-as-a-service used as the shared data layer
- **Operator**: A human user who monitors the dashboard and can manually dispatch drones or resolve incidents
- **Admin**: An operator with permission to start and stop monitoring sessions
- **Drone**: An autonomous aerial vehicle represented in the system; its movement is fully simulated
- **Incident**: A detected safety event produced by the Vision_Service and stored in Supabase
- **Monitoring_Session**: A record that tracks the active surveillance period for a given camera
- **Dispatch_Log**: A record that tracks a drone's assignment to an incident, including route and timing
- **Risk_Score**: A float in [0, 1] produced by the Vision_Service indicating the severity of an incident
- **Risk_Level**: A categorical label (low / medium / high) derived from Risk_Score thresholds
- **Haversine_Distance**: The great-circle distance in kilometres between two lat/lng coordinates
- **No_Fly_Zone**: A geographic area where drone flight is restricted, incurring a scoring penalty
- **ETA**: Estimated time of arrival of a drone at an incident location, in seconds
- **ORS**: OpenRouteService — the third-party routing API used to generate drone flight paths
- **MJPEG**: Motion JPEG — the streaming format used for camera feed previews
- **SOS_App**: The Flutter mobile application developed by a separate teammate on the same Supabase project


## Requirements

---

### Requirement 1: Monitoring Session Management

**User Story:** As an Admin, I want to start and stop monitoring sessions for a selected camera, so that the
system knows which camera feed is actively being analyzed.

#### Acceptance Criteria

1. WHEN the Admin sends `POST /monitoring/start` with a valid `camera_id`, THE Backend SHALL create a
   `monitoring_sessions` record in Supabase with `status = active` and `started_at` set to the current UTC
   timestamp.
2. WHEN the Admin sends `POST /monitoring/start` with a `camera_id` that does not exist in the `cameras`
   table, THE Backend SHALL return HTTP 404 with a descriptive error message.
3. WHEN the Admin sends `POST /monitoring/stop` with a valid `session_id`, THE Backend SHALL update the
   corresponding `monitoring_sessions` record setting `status = stopped` and `ended_at` to the current UTC
   timestamp.
4. WHEN the Admin sends `POST /monitoring/stop` with a `session_id` that does not exist, THE Backend SHALL
   return HTTP 404 with a descriptive error message.
5. WHILE a monitoring session is active for a camera, THE Backend SHALL accept incident writes from the
   Vision_Service for that `camera_id`.
6. THE Backend SHALL expose `GET /monitoring/sessions` returning all monitoring session records ordered by
   `started_at` descending.

---

### Requirement 2: Incident Ingestion

**User Story:** As the Vision_Service, I want to write incident records to Supabase, so that the Backend can
apply decision logic and the Dashboard can display them.

#### Acceptance Criteria

1. THE Vision_Service SHALL write incident records directly to the Supabase `incidents` table using the
   Supabase service-role key.
2. WHEN an incident record is inserted into the `incidents` table, THE incident record SHALL contain the
   fields: `id` (UUID), `camera_id` (UUID), `incident_type` (one of: fire, theft, accident, intrusion,
   patrol, animal), `risk_score` (float in [0, 1]), `confidence` (float in [0, 1]), `lat` (float),
   `lng` (float), `snapshot_url` (string or null), `status` (default: open), `created_at` (UTC timestamp).
3. WHEN an incident record is inserted with a `risk_score` outside the range [0, 1], THE Supabase database
   SHALL reject the record with a constraint violation error.
4. WHEN an incident record is inserted with an `incident_type` not in the allowed set, THE Supabase database
   SHALL reject the record with a constraint violation error.
5. THE Backend SHALL expose `POST /incidents` to allow manual incident creation for testing purposes.
6. THE Backend SHALL expose `GET /incidents` returning all incident records ordered by `created_at`
   descending.
7. THE Backend SHALL expose `PATCH /incidents/{id}/status` to update the `status` field of an incident.

---

### Requirement 3: Risk Classification

**User Story:** As an Operator, I want the system to automatically classify each incident by risk level, so
that the correct response action is triggered without manual triage.

#### Acceptance Criteria

1. WHEN an incident has `risk_score < 0.4`, THE Backend SHALL assign `risk_level = low` and log the incident
   without dispatching a drone or sending an alert.
2. WHEN an incident has `risk_score >= 0.4` AND `risk_score <= 0.7`, THE Backend SHALL assign
   `risk_level = medium` and push an alert to the Dashboard so the Operator can manually dispatch a drone.
3. WHEN an incident has `risk_score > 0.7`, THE Backend SHALL assign `risk_level = high` and automatically
   trigger the drone dispatch workflow without waiting for Operator input.
4. THE Backend SHALL persist the derived `risk_level` value alongside the incident record in Supabase.
5. WHEN a `risk_score` value of exactly `0.4` is received, THE Backend SHALL classify it as `medium`.
6. WHEN a `risk_score` value of exactly `0.7` is received, THE Backend SHALL classify it as `medium`.

---

### Requirement 4: Drone Selection Algorithm

**User Story:** As the System, I want to select the optimal available drone for dispatch, so that the
incident receives the fastest and most reliable response.

#### Acceptance Criteria

1. WHEN a drone dispatch is triggered, THE Backend SHALL query the `drones` table and filter to only drones
   where `status = available` AND `battery_pct > 30`.
2. IF no drones satisfy the availability and battery filter, THEN THE Backend SHALL return an error
   indicating no drones are available and log the failure without creating a `dispatch_logs` record.
3. WHEN eligible drones exist, THE Backend SHALL compute a selection score for each drone using the formula:
   `score = haversine_distance_km + (100 - battery_pct) * 0.01 + (0.5 if crosses_no_fly_zone else 0)`.
4. THE Backend SHALL select the drone with the lowest computed score.
5. WHEN two drones have equal scores, THE Backend SHALL select the drone with the higher `battery_pct`.
6. THE Backend SHALL compute ETA using the formula:
   `eta_seconds = (haversine_distance_km / speed_kmh) * 3600`, rounded to the nearest integer.

---

### Requirement 5: Drone Dispatch and Simulation

**User Story:** As an Operator, I want dispatched drones to move toward the incident in real time, so that I
can track their progress on the live map.

#### Acceptance Criteria

1. WHEN a drone is dispatched, THE Backend SHALL update the drone's `status` to `en_route` in the `drones`
   table.
2. WHEN a drone is dispatched, THE Backend SHALL create a `dispatch_logs` record containing `incident_id`,
   `drone_id`, `dispatched_at`, `eta_seconds`, and `route_geojson`.
3. WHEN a drone is dispatched, THE Backend SHALL start a background task that updates the drone's `lat` and
   `lng` in Supabase every 2 seconds, moving it incrementally toward the incident coordinates.
4. WHEN the simulated drone reaches the incident coordinates (within 0.05 km), THE Backend SHALL update the
   drone's `status` to `on_scene` and set `arrived_at` in the corresponding `dispatch_logs` record.
5. WHEN the Operator marks an incident as resolved, THE Backend SHALL update the incident `status` to
   `resolved` and start a background task moving the drone back to its `home_lat` / `home_lng`.
6. WHEN the drone returns to its home coordinates (within 0.05 km), THE Backend SHALL update the drone's
   `status` to `available`.
7. THE Backend SHALL expose `POST /drones/dispatch` accepting `incident_id` and optionally `drone_id` for
   manual operator dispatch.
8. THE Backend SHALL expose `GET /drones` returning all drone records with current status, position, and
   battery.
9. THE Backend SHALL expose `PATCH /drones/{id}/status` for manual status overrides.

---

### Requirement 6: Supabase Realtime Push

**User Story:** As an Operator, I want all state changes to appear on the Dashboard instantly, so that I
always have an accurate operational picture without refreshing.

#### Acceptance Criteria

1. THE Supabase project SHALL have Realtime enabled on the `incidents`, `drones`, and `dispatch_logs` tables.
2. WHEN a new incident is inserted into the `incidents` table, THE Dashboard SHALL receive the INSERT event
   via Supabase Realtime within 2 seconds.
3. WHEN a drone record is updated in the `drones` table, THE Dashboard SHALL receive the UPDATE event via
   Supabase Realtime within 2 seconds.
4. WHEN a new `dispatch_logs` record is inserted, THE Dashboard SHALL receive the INSERT event via Supabase
   Realtime within 2 seconds.
5. THE Dashboard SHALL use the Supabase anon key exclusively for all Realtime subscriptions and client-side
   queries.
6. THE Backend SHALL use the Supabase service-role key exclusively for all server-side database writes and
   reads.

---

### Requirement 7: Live Map Visualization

**User Story:** As an Operator, I want to see cameras, incidents, and drones on a live map, so that I can
understand the geographic context of each event.

#### Acceptance Criteria

1. THE Dashboard SHALL render a Leaflet map centered on the configured city coordinates on initial load.
2. THE Dashboard SHALL display a distinct marker for each active camera from the `cameras` table.
3. WHEN a new incident INSERT event is received, THE Dashboard SHALL add an incident marker at the incident's
   `lat` / `lng` with a color indicating its `risk_level` (green = low, amber = medium, red = high).
4. WHEN a drone UPDATE event is received, THE Dashboard SHALL move the drone marker to the updated `lat` /
   `lng` without a full re-render.
5. WHEN a `dispatch_logs` INSERT event is received, THE Dashboard SHALL call the ORS API with the drone's
   current position and the incident coordinates and render the returned route as a polyline on the map.
6. IF the ORS API call fails, THEN THE Dashboard SHALL draw a straight-line polyline between the drone and
   incident coordinates as a fallback.
7. THE Dashboard SHALL display the Leaflet map using `react-leaflet` and tile data from OpenStreetMap.

---

### Requirement 8: Incident Alert Panel

**User Story:** As an Operator, I want to see incident cards with risk badges and dispatch controls, so that
I can quickly assess and respond to medium-risk events.

#### Acceptance Criteria

1. THE Dashboard SHALL display an incident card for each incident received via Realtime, showing:
   `incident_type`, `risk_level` badge, `risk_score`, `confidence`, `created_at`, and `status`.
2. WHEN an incident card has `risk_level = medium`, THE Dashboard SHALL display a "Dispatch Drone" button on
   that card.
3. WHEN the Operator clicks "Dispatch Drone" on a medium-risk incident card, THE Dashboard SHALL call
   `POST /drones/dispatch` with the `incident_id` and disable the button to prevent duplicate dispatches.
4. WHEN an incident card has `risk_level = high`, THE Dashboard SHALL display a "Auto-Dispatched" label
   instead of a dispatch button.
5. WHEN an incident card has `risk_level = low`, THE Dashboard SHALL display a "Logged" label with no action
   button.
6. THE Dashboard SHALL display incident cards sorted by `created_at` descending, with the most recent
   incident at the top.
7. WHEN the Operator clicks "Mark Resolved" on an incident card, THE Dashboard SHALL call
   `PATCH /incidents/{id}/status` with `status = resolved`.

---

### Requirement 9: Drone Status Panel

**User Story:** As an Operator, I want to see the status, battery level, and ETA of each drone, so that I
can monitor fleet readiness at a glance.

#### Acceptance Criteria

1. THE Dashboard SHALL display a drone card for each drone in the `drones` table, showing: `name`, `status`
   badge, `battery_pct` as a visual progress bar, and current coordinates.
2. WHEN a drone UPDATE event is received, THE Dashboard SHALL update the corresponding drone card in real
   time without a page reload.
3. WHEN a drone has `status = en_route`, THE Dashboard SHALL display an ETA countdown on the drone card,
   decrementing by 1 every second from the `eta_seconds` value in the latest `dispatch_logs` record.
4. WHEN the ETA countdown reaches 0, THE Dashboard SHALL display "Arrived" on the drone card.
5. WHEN a drone has `battery_pct <= 30`, THE Dashboard SHALL render the battery bar in red to indicate low
   battery.
6. THE Dashboard SHALL display drone status badges with distinct colors: available = green, en_route = blue,
   on_scene = amber, charging = grey.

---

### Requirement 10: Monitoring Control Bar

**User Story:** As an Admin, I want a camera selector and Start/Stop Monitoring controls in the dashboard, so
that I can initiate and terminate surveillance sessions without leaving the UI.

#### Acceptance Criteria

1. THE Dashboard SHALL display a dropdown populated with all cameras from the `cameras` table on load.
2. WHEN the Admin selects a camera and clicks "Start Monitoring", THE Dashboard SHALL call
   `POST /monitoring/start` with the selected `camera_id` and display a visual indicator that monitoring is
   active.
3. WHEN the Admin clicks "Stop Monitoring", THE Dashboard SHALL call `POST /monitoring/stop` with the active
   `session_id` and remove the active monitoring indicator.
4. WHILE a monitoring session is active, THE Dashboard SHALL disable the "Start Monitoring" button to prevent
   duplicate sessions.
5. THE Dashboard SHALL display a placeholder camera feed area using an `<img>` tag pointing to the camera's
   `stream_url` to simulate an MJPEG stream.

---

### Requirement 11: Camera Management API

**User Story:** As an Admin, I want API endpoints to manage camera records, so that new cameras can be
registered and existing ones updated without direct database access.

#### Acceptance Criteria

1. THE Backend SHALL expose `GET /cameras` returning all camera records from the `cameras` table.
2. THE Backend SHALL expose `POST /cameras` accepting `name`, `location_desc`, `lat`, `lng`, `stream_url`,
   and `is_active`, and inserting a new record into the `cameras` table.
3. WHEN `POST /cameras` is called with missing required fields (`name`, `lat`, `lng`), THE Backend SHALL
   return HTTP 422 with a field-level validation error.
4. THE Backend SHALL expose `PATCH /cameras/{id}` to update any mutable field of a camera record.

---

### Requirement 12: Database Schema and Seed Data

**User Story:** As a Developer, I want a SQL schema file and seed data script, so that I can set up a fresh
Supabase project and have a working demo environment immediately.

#### Acceptance Criteria

1. THE Backend SHALL include a `db/schema.sql` file that creates all five tables: `cameras`, `incidents`,
   `drones`, `dispatch_logs`, and `monitoring_sessions` with the column definitions, types, and constraints
   described in the Glossary.
2. THE `incidents` table schema SHALL enforce a CHECK constraint that `risk_score` is between 0 and 1
   inclusive.
3. THE `incidents` table schema SHALL enforce a CHECK constraint that `incident_type` is one of: fire, theft,
   accident, intrusion, patrol, animal.
4. THE Backend SHALL include a `db/seed.sql` file that inserts the four Pune camera records and four drone
   records specified in the project brief.
5. THE `drones` seed data SHALL include: Alpha-1 (18.5074, 73.9286, 92%, available), Beta-2 (18.5200,
   73.9100, 78%, available), Gamma-3 (18.4900, 73.9450, 45%, charging), Delta-4 (18.5400, 73.9500, 88%,
   available).
6. THE `cameras` seed data SHALL include: Gate A Magarpatta (18.5074, 73.9286), Parking Amanora (18.5018,
   73.9357), Industrial Hadapsar (18.4965, 73.9406), Residential Kharadi (18.5513, 73.9413).

---

### Requirement 13: Environment Configuration and Security

**User Story:** As a Developer, I want all secrets managed via environment variables with example files, so
that credentials are never committed to the repository.

#### Acceptance Criteria

1. THE Backend SHALL read `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `ORS_API_KEY` exclusively from
   environment variables loaded via `python-dotenv`.
2. THE Dashboard SHALL read `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_ORS_API_KEY`
   exclusively from `.env.local` environment variables.
3. THE repository `.gitignore` SHALL exclude `.env`, `.env.local`, and any file matching `*.env` from version
   control.
4. THE Backend SHALL include a `backend/.env.example` file listing all required variable names with
   placeholder values and no real secrets.
5. THE Dashboard SHALL include a `dashboard/.env.local.example` file listing all required variable names with
   placeholder values and no real secrets.
6. THE Backend SHALL never expose the Supabase service-role key to any client-facing API response.

---

### Requirement 14: Vision Service Placeholder

**User Story:** As a Developer, I want the `vision_service/` directory to exist as a clearly documented
placeholder, so that Om can develop the vision component independently without merge conflicts.

#### Acceptance Criteria

1. THE repository SHALL contain a `vision_service/` directory with a `README.md` explaining that this
   component is developed separately and communicates with the rest of the system exclusively via Supabase.
2. THE `vision_service/README.md` SHALL document the exact Supabase `incidents` table schema that the
   Vision_Service must write to.
3. THE `vision_service/` directory SHALL contain no application source code files.

---

### Requirement 15: Non-Functional — API Response Times

**User Story:** As an Operator, I want API responses to be fast enough for real-time operations, so that the
dashboard feels responsive during an active incident.

#### Acceptance Criteria

1. WHEN the Backend receives any `GET` request under normal load (fewer than 10 concurrent requests), THE
   Backend SHALL respond within 500ms.
2. WHEN the Backend receives `POST /drones/dispatch`, THE Backend SHALL respond within 1000ms, excluding the
   background simulation task.
3. THE Backend SHALL return HTTP 500 with a descriptive error message for any unhandled server-side
   exception, rather than crashing the process.

---

### Requirement 16: Non-Functional — Code Quality and Maintainability

**User Story:** As a Developer, I want the codebase to follow consistent conventions, so that a first-year
student can read, understand, and extend it under hackathon time pressure.

#### Acceptance Criteria

1. THE Backend SHALL initialize the Supabase client in a single module (`db/supabase.py`) and all other
   modules SHALL import the client from that module rather than creating new instances.
2. THE Backend SHALL define all Pydantic request and response schemas in `models/schemas.py`.
3. THE Backend SHALL organize API routes into separate router files: `routers/incidents.py`,
   `routers/drones.py`, `routers/cameras.py`, and `routers/monitoring.py`.
4. THE Backend SHALL organize business logic into service files: `services/dispatch.py`,
   `services/risk.py`, and `services/simulation.py`.
5. THE Dashboard SHALL organize UI into separate component files: `MapView`, `AlertPanel`, `DronePanel`,
   `MonitoringBar`, and `CameraFeed`.
6. THE Dashboard SHALL initialize the Supabase client in a single module and all components SHALL import
   from that module.
