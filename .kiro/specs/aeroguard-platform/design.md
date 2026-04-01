# Design Document — AeroGuard Platform

## Overview

AeroGuard is a FastAPI backend that sits at the center of an urban safety pipeline:

```
Vision_Service → Supabase (incidents table)
                      ↓
              FastAPI Backend
         ┌────────────────────────┐
         │  Risk Classification   │
         │  Drone Selection       │
         │  Dispatch + Simulation │
         │  Video Feed Proxy      │
         └────────────────────────┘
                      ↓
         Supabase Realtime → Dashboard (React)
```

The backend is the only component that applies business logic. The Vision_Service writes directly to Supabase. The Dashboard reads exclusively via Supabase Realtime and the anon key. The backend uses the service-role key for all server-side reads/writes.

The user's priority is: **backend connections, POST JSON endpoints, and Supabase integration first**. The UI is built separately in Stitch by teammates. The drone live video feed streaming is a new addition to the design.

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Supabase Project                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  PostgreSQL  │  │   Realtime   │  │  Storage (snapshots) │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ↑ service-role key                ↓ anon key (Realtime)
┌────────────────────┐             ┌──────────────────────────┐
│   FastAPI Backend  │             │   React Dashboard (Stitch)│
│  (Python 3.11+)    │◄────REST────│   react-leaflet, supabase │
│                    │             │   -js                     │
└────────────────────┘             └──────────────────────────┘
         ↑ writes incidents
┌────────────────────┐
│  Vision_Service    │
│  (Om — separate)   │
└────────────────────┘
         ↑ MJPEG / WebRTC
┌────────────────────┐
│  Drone / Camera    │
│  Hardware / Sim    │
└────────────────────┘
```

### Backend Internal Structure

```
backend/
├── main.py                  ← FastAPI app, router registration, CORS
├── db/
│   ├── supabase.py          ← Single Supabase client instance
│   ├── schema.sql           ← Full DDL for all 5 tables
│   └── seed.sql             ← 4 cameras + 4 drones
├── models/
│   └── schemas.py           ← All Pydantic request/response models
├── routers/
│   ├── cameras.py           ← GET/POST/PATCH /cameras
│   ├── incidents.py         ← GET/POST/PATCH /incidents
│   ├── drones.py            ← GET/POST/PATCH /drones
│   ├── monitoring.py        ← POST /monitoring/start|stop, GET /monitoring/sessions
│   └── stream.py            ← GET /stream/{drone_id} (video feed proxy)
├── services/
│   ├── risk.py              ← Risk score → risk_level classification
│   ├── dispatch.py          ← Drone selection algorithm + dispatch orchestration
│   └── simulation.py        ← Background asyncio tasks for drone movement
└── .env.example
```

### Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Web framework | FastAPI | 0.111.0 |
| ASGI server | Uvicorn (standard) | 0.29.0 |
| Database/Realtime | Supabase Python SDK | 2.4.2 |
| Data validation | Pydantic v2 | 2.7.1 |
| HTTP client | httpx | 0.27.0 |
| Distance calc | haversine | 2.8.1 |
| Env management | python-dotenv | 1.0.1 |
| Video streaming | httpx (async streaming proxy) | 0.27.0 |

---

## Components and Interfaces

### API Endpoints

#### Cameras — `routers/cameras.py`

| Method | Path | Request Body | Response | Description |
|---|---|---|---|---|
| GET | `/cameras` | — | `List[CameraOut]` | All camera records |
| POST | `/cameras` | `CameraCreate` | `CameraOut` | Register new camera |
| PATCH | `/cameras/{id}` | `CameraUpdate` | `CameraOut` | Update camera fields |

#### Incidents — `routers/incidents.py`

| Method | Path | Request Body | Response | Description |
|---|---|---|---|---|
| GET | `/incidents` | — | `List[IncidentOut]` | All incidents, `created_at` desc |
| POST | `/incidents` | `IncidentCreate` | `IncidentOut` | Manual incident creation (testing) |
| PATCH | `/incidents/{id}/status` | `StatusUpdate` | `IncidentOut` | Update incident status |

When `POST /incidents` is called, the backend runs risk classification and, if `risk_level = high`, triggers the dispatch workflow automatically.

#### Drones — `routers/drones.py`

| Method | Path | Request Body | Response | Description |
|---|---|---|---|---|
| GET | `/drones` | — | `List[DroneOut]` | All drones with current state |
| POST | `/drones/dispatch` | `DispatchRequest` | `DispatchOut` | Dispatch drone to incident |
| PATCH | `/drones/{id}/status` | `StatusUpdate` | `DroneOut` | Manual status override |

#### Monitoring — `routers/monitoring.py`

| Method | Path | Request Body | Response | Description |
|---|---|---|---|---|
| POST | `/monitoring/start` | `MonitoringStart` | `MonitoringSessionOut` | Start session for camera |
| POST | `/monitoring/stop` | `MonitoringStop` | `MonitoringSessionOut` | Stop active session |
| GET | `/monitoring/sessions` | — | `List[MonitoringSessionOut]` | All sessions, `started_at` desc |

#### Video Stream — `routers/stream.py`

| Method | Path | Response | Description |
|---|---|---|---|
| GET | `/stream/{drone_id}` | `StreamingResponse` | Proxy drone live video feed |
| GET | `/stream/camera/{camera_id}` | `StreamingResponse` | Proxy camera MJPEG feed |

### Service Layer

#### `services/risk.py`

```python
def classify_risk(risk_score: float) -> str:
    """Returns 'low', 'medium', or 'high'."""
    if risk_score < 0.4:
        return "low"
    elif risk_score <= 0.7:
        return "medium"
    else:
        return "high"
```

Boundary values: `0.4` → medium, `0.7` → medium (per requirements 3.5, 3.6).

#### `services/dispatch.py`

Responsibilities:
1. Query `drones` where `status = available` AND `battery_pct > 30`
2. For each eligible drone, compute selection score
3. Select lowest-score drone (tie-break: higher `battery_pct`)
4. Update drone `status = en_route` in Supabase
5. Insert `dispatch_logs` record with `eta_seconds` and `route_geojson`
6. Launch background simulation task via `services/simulation.py`

Score formula:
```
score = haversine_km(drone, incident)
      + (100 - battery_pct) * 0.01
      + (0.5 if crosses_no_fly_zone else 0)
```

ETA formula:
```
eta_seconds = round((haversine_km / speed_kmh) * 3600)
```

Default `speed_kmh = 60` (configurable via env var).

#### `services/simulation.py`

Two async background tasks managed by FastAPI's `BackgroundTasks`:

**`simulate_drone_to_incident(drone_id, incident_id, target_lat, target_lng)`**
- Every 2 seconds: compute next position (linear interpolation toward target)
- Update `drones.lat`, `drones.lng` in Supabase
- When within 0.05 km of target: set `status = on_scene`, write `arrived_at` to `dispatch_logs`

**`simulate_drone_return(drone_id, home_lat, home_lng)`**
- Triggered when incident is resolved
- Same 2-second tick, moves drone back to `home_lat`/`home_lng`
- When within 0.05 km of home: set `status = available`

Step size per tick: `step_km = speed_kmh * (2/3600)` ≈ 0.033 km per tick at 60 km/h.

### Video Feed Streaming

#### Design Decision

The drone live video feed is proxied through the FastAPI backend rather than exposed directly from the drone. This keeps the drone's network address internal and allows the backend to add auth, logging, and fallback behavior.

**Supported stream types:**
- **MJPEG** (primary): drone/camera exposes an HTTP endpoint returning `multipart/x-mixed-replace; boundary=frame`. The backend proxies this as a `StreamingResponse`.
- **WebRTC** (future): signaling can be added via a `/stream/{drone_id}/offer` endpoint using `aiortc`. Not implemented in v1 but the router is structured to accommodate it.

#### MJPEG Proxy Implementation

```
Client (Dashboard)
    GET /stream/{drone_id}
         ↓
FastAPI StreamingResponse (async generator)
         ↓
httpx.AsyncClient.stream("GET", drone_stream_url)
         ↓
Drone onboard camera HTTP server (MJPEG)
```

The `drones` table stores a `stream_url` column. The backend looks up the drone's `stream_url`, opens an async streaming HTTP connection, and yields chunks to the client.

```python
# routers/stream.py (sketch)
@router.get("/{drone_id}")
async def drone_feed(drone_id: str):
    drone = await get_drone(drone_id)
    if not drone or not drone["stream_url"]:
        raise HTTPException(404, "No stream available")

    async def stream_generator():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", drone["stream_url"]) as r:
                async for chunk in r.aiter_bytes(chunk_size=8192):
                    yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
```

**Fallback behavior**: If the drone's `stream_url` is null or unreachable, the endpoint returns HTTP 503 with `{"detail": "Stream unavailable"}`. The Dashboard `<img>` tag will show a broken image placeholder.

**Camera feed proxy**: `GET /stream/camera/{camera_id}` works identically, reading `stream_url` from the `cameras` table. This replaces the static `<img>` tag approach in the Dashboard.

---

## Data Models

### Pydantic Schemas (`models/schemas.py`)

#### Camera

```python
class CameraCreate(BaseModel):
    name: str
    location_desc: str | None = None
    lat: float
    lng: float
    stream_url: str | None = None
    is_active: bool = True

class CameraUpdate(BaseModel):
    name: str | None = None
    location_desc: str | None = None
    lat: float | None = None
    lng: float | None = None
    stream_url: str | None = None
    is_active: bool | None = None

class CameraOut(CameraCreate):
    id: str
    created_at: datetime
```

#### Incident

```python
class IncidentCreate(BaseModel):
    camera_id: str
    incident_type: Literal["fire","theft","accident","intrusion","patrol","animal"]
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    lat: float
    lng: float
    snapshot_url: str | None = None

class IncidentOut(IncidentCreate):
    id: str
    status: str
    risk_level: str
    created_at: datetime
```

#### Drone

```python
class DroneOut(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    home_lat: float
    home_lng: float
    battery_pct: float
    status: Literal["available","en_route","on_scene","charging"]
    speed_kmh: float
    stream_url: str | None
    created_at: datetime
```

#### Dispatch

```python
class DispatchRequest(BaseModel):
    incident_id: str
    drone_id: str | None = None   # optional manual override

class DispatchOut(BaseModel):
    dispatch_log_id: str
    drone_id: str
    incident_id: str
    eta_seconds: int
    route_geojson: dict | None
```

#### Monitoring

```python
class MonitoringStart(BaseModel):
    camera_id: str

class MonitoringStop(BaseModel):
    session_id: str

class MonitoringSessionOut(BaseModel):
    id: str
    camera_id: str
    status: str
    started_at: datetime
    ended_at: datetime | None
```

#### Status Update (shared)

```python
class StatusUpdate(BaseModel):
    status: str
```

---

### Database Schema

#### `cameras`

```sql
CREATE TABLE cameras (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    location_desc TEXT,
    lat           DOUBLE PRECISION NOT NULL,
    lng           DOUBLE PRECISION NOT NULL,
    stream_url    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `drones`

```sql
CREATE TABLE drones (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    home_lat    DOUBLE PRECISION NOT NULL,
    home_lng    DOUBLE PRECISION NOT NULL,
    battery_pct DOUBLE PRECISION NOT NULL CHECK (battery_pct >= 0 AND battery_pct <= 100),
    status      TEXT NOT NULL DEFAULT 'available'
                    CHECK (status IN ('available','en_route','on_scene','charging')),
    speed_kmh   DOUBLE PRECISION NOT NULL DEFAULT 60,
    stream_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Note: `stream_url` added to `drones` to support live video feed proxying.

#### `incidents`

```sql
CREATE TABLE incidents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id     UUID REFERENCES cameras(id),
    incident_type TEXT NOT NULL
                      CHECK (incident_type IN ('fire','theft','accident','intrusion','patrol','animal')),
    risk_score    DOUBLE PRECISION NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
    confidence    DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    risk_level    TEXT CHECK (risk_level IN ('low','medium','high')),
    lat           DOUBLE PRECISION NOT NULL,
    lng           DOUBLE PRECISION NOT NULL,
    snapshot_url  TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open','resolved','acknowledged')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `dispatch_logs`

```sql
CREATE TABLE dispatch_logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id  UUID NOT NULL REFERENCES incidents(id),
    drone_id     UUID NOT NULL REFERENCES drones(id),
    dispatched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    arrived_at   TIMESTAMPTZ,
    eta_seconds  INTEGER NOT NULL,
    route_geojson JSONB
);
```

#### `monitoring_sessions`

```sql
CREATE TABLE monitoring_sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id  UUID NOT NULL REFERENCES cameras(id),
    status     TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','stopped')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at   TIMESTAMPTZ
);
```

#### Supabase Realtime Configuration

Enable Realtime on these tables via the Supabase dashboard or SQL:

```sql
-- Enable realtime for required tables
ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
ALTER PUBLICATION supabase_realtime ADD TABLE drones;
ALTER PUBLICATION supabase_realtime ADD TABLE dispatch_logs;
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Risk Classification Correctness

*For any* `risk_score` value in [0, 1], `classify_risk(score)` must return exactly `"low"` when `score < 0.4`, `"medium"` when `0.4 <= score <= 0.7`, and `"high"` when `score > 0.7`. The boundary values `0.4` and `0.7` must both map to `"medium"`.

**Validates: Requirements 3.1, 3.2, 3.3, 3.5, 3.6**

---

### Property 2: Risk Level Persisted on Incident Creation

*For any* valid incident payload submitted to `POST /incidents`, the returned record must contain a `risk_level` field whose value equals `classify_risk(risk_score)` applied to the submitted `risk_score`.

**Validates: Requirements 3.4**

---

### Property 3: Invalid Incident Data Rejected by Database

*For any* `risk_score` value outside [0, 1] or any `incident_type` string not in `{fire, theft, accident, intrusion, patrol, animal}`, the database must reject the insert with a constraint violation and no record should be created.

**Validates: Requirements 2.3, 2.4**

---

### Property 4: Incident List Ordering

*For any* set of incidents in the database, `GET /incidents` must return them ordered by `created_at` descending — the most recently created incident must always appear first.

**Validates: Requirements 2.6**

---

### Property 5: Monitoring Session Lifecycle Round-Trip

*For any* valid `camera_id`, calling `POST /monitoring/start` followed by `POST /monitoring/stop` must result in a `monitoring_sessions` record where `status = "stopped"`, `started_at` is set, and `ended_at > started_at`.

**Validates: Requirements 1.1, 1.3**

---

### Property 6: Monitoring Sessions Ordering

*For any* set of monitoring sessions, `GET /monitoring/sessions` must return them ordered by `started_at` descending.

**Validates: Requirements 1.6**

---

### Property 7: Drone Selection Filters Eligibility Correctly

*For any* set of drones in the database, the dispatch algorithm must only consider drones where `status = "available"` AND `battery_pct > 30`. No ineligible drone should ever be selected regardless of its score.

**Validates: Requirements 4.1**

---

### Property 8: Drone Selection Score Minimization

*For any* set of eligible drones and a given incident location, the dispatch algorithm must select the drone with the lowest computed score (`haversine_km + (100 - battery_pct) * 0.01 + no_fly_penalty`). When two drones have equal scores, the one with higher `battery_pct` must be selected.

**Validates: Requirements 4.3, 4.4, 4.5**

---

### Property 9: ETA Calculation Correctness

*For any* drone with a known `speed_kmh` and a given incident at distance `d` km, the computed `eta_seconds` must equal `round((d / speed_kmh) * 3600)`.

**Validates: Requirements 4.6**

---

### Property 10: Dispatch Invariants

*For any* successful dispatch, the following must all hold simultaneously: the selected drone's `status` is updated to `"en_route"` in the `drones` table, and a `dispatch_logs` record is created containing `incident_id`, `drone_id`, `dispatched_at`, and `eta_seconds`.

**Validates: Requirements 5.1, 5.2**

---

### Property 11: Simulation Convergence — Drone Reaches Incident

*For any* dispatched drone starting at position P and incident at position Q, after sufficient simulation ticks the drone's position must come within 0.05 km of Q, at which point `status` must be set to `"on_scene"` and `arrived_at` must be written to the `dispatch_logs` record.

**Validates: Requirements 5.3, 5.4**

---

### Property 12: Simulation Convergence — Drone Returns Home

*For any* drone in `"on_scene"` state whose incident is resolved, after sufficient simulation ticks the drone's position must come within 0.05 km of its `home_lat`/`home_lng`, at which point `status` must be set to `"available"`.

**Validates: Requirements 5.5, 5.6**

---

### Property 13: Camera Creation Round-Trip

*For any* valid camera payload submitted to `POST /cameras`, the record must be retrievable via `GET /cameras` with all submitted fields intact and an assigned `id`.

**Validates: Requirements 11.2**

---

### Property 14: Camera Validation Rejects Missing Required Fields

*For any* `POST /cameras` request missing `name`, `lat`, or `lng`, the backend must return HTTP 422 with a field-level validation error and no record should be created.

**Validates: Requirements 11.3**

---

### Property 15: PATCH Endpoints Update Only Supplied Fields

*For any* PATCH request to `/cameras/{id}`, `/incidents/{id}/status`, or `/drones/{id}/status`, only the fields present in the request body must be modified; all other fields must remain unchanged.

**Validates: Requirements 2.7, 5.9, 11.4**

---

## Error Handling

### HTTP Error Codes

| Scenario | HTTP Status | Response Body |
|---|---|---|
| Resource not found (camera, session, drone, incident) | 404 | `{"detail": "<resource> not found"}` |
| Missing required fields in request body | 422 | Pydantic field-level validation errors |
| No eligible drones for dispatch | 409 | `{"detail": "No available drones with sufficient battery"}` |
| Drone stream URL unavailable | 503 | `{"detail": "Stream unavailable"}` |
| Unhandled server exception | 500 | `{"detail": "<exception message>"}` |

### Global Exception Handler

`main.py` registers a global exception handler that catches any unhandled `Exception`, logs the traceback, and returns HTTP 500 with a descriptive message. This prevents the process from crashing (Requirement 15.3).

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

### Supabase Error Handling

All Supabase SDK calls are wrapped in try/except. Constraint violations (risk_score out of range, invalid incident_type) surface as 400 errors with the Supabase error message forwarded to the client.

### Background Task Error Handling

Simulation tasks catch all exceptions internally and log them without crashing the main process. If a simulation task fails mid-flight, the drone remains in its last known state until a manual `PATCH /drones/{id}/status` override is issued.

---

## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are required. They are complementary:
- Unit tests catch concrete bugs with specific known inputs
- Property tests verify general correctness across the full input space

### Property-Based Testing

**Library**: `hypothesis` (Python) — the standard PBT library for Python, no need to implement from scratch.

**Configuration**: Each property test runs a minimum of 100 examples (`settings(max_examples=100)`).

**Tag format** (comment above each test):
```
# Feature: aeroguard-platform, Property <N>: <property_text>
```

Each correctness property from the design document maps to exactly one `@given`-decorated test function.

#### Property Test Mapping

| Design Property | Test Function | Hypothesis Strategy |
|---|---|---|
| Property 1: Risk Classification | `test_risk_classification_correctness` | `st.floats(min_value=0.0, max_value=1.0)` |
| Property 2: Risk Level Persisted | `test_risk_level_persisted_on_create` | `st.builds(IncidentCreate, ...)` |
| Property 3: Invalid Data Rejected | `test_invalid_incident_rejected` | `st.floats().filter(lambda x: x < 0 or x > 1)` |
| Property 4: Incident List Ordering | `test_incidents_ordered_by_created_at` | `st.lists(st.builds(Incident, ...))` |
| Property 5: Session Lifecycle | `test_monitoring_session_lifecycle` | `st.uuids()` (camera_id) |
| Property 6: Sessions Ordering | `test_sessions_ordered_by_started_at` | `st.lists(st.builds(Session, ...))` |
| Property 7: Drone Eligibility Filter | `test_dispatch_filters_eligible_drones` | `st.lists(st.builds(Drone, ...))` |
| Property 8: Score Minimization | `test_dispatch_selects_lowest_score` | `st.lists(st.builds(Drone, ...), min_size=1)` |
| Property 9: ETA Calculation | `test_eta_calculation` | `st.floats(min_value=0.1, max_value=100)` (distance), `st.floats(min_value=1, max_value=200)` (speed) |
| Property 10: Dispatch Invariants | `test_dispatch_creates_log_and_sets_en_route` | `st.builds(DispatchRequest, ...)` |
| Property 11: Simulation to Incident | `test_simulation_converges_to_incident` | `st.builds(DronePosition, ...)` |
| Property 12: Simulation Return Home | `test_simulation_returns_home` | `st.builds(DronePosition, ...)` |
| Property 13: Camera Round-Trip | `test_camera_creation_round_trip` | `st.builds(CameraCreate, ...)` |
| Property 14: Camera Validation | `test_camera_missing_fields_rejected` | `st.fixed_dictionaries({...}).filter(missing_required)` |
| Property 15: PATCH Partial Update | `test_patch_only_updates_supplied_fields` | `st.builds(CameraUpdate, ...)` |

### Unit Tests

Unit tests focus on specific examples, integration points, and error conditions that are not well-covered by property tests:

- `test_monitoring_start_404_unknown_camera` — verifies 404 for nonexistent camera_id
- `test_monitoring_stop_404_unknown_session` — verifies 404 for nonexistent session_id
- `test_dispatch_no_drones_available` — verifies 409 when no eligible drones exist
- `test_post_incidents_manual_creation` — verifies `POST /incidents` creates a record
- `test_get_cameras_returns_list` — verifies `GET /cameras` returns a list
- `test_get_drones_returns_list` — verifies `GET /drones` returns a list
- `test_global_exception_handler_returns_500` — verifies unhandled exceptions return 500
- `test_stream_endpoint_404_no_stream_url` — verifies 503 when drone has no stream_url
- `test_seed_data_cameras_present` — verifies 4 Pune cameras exist after seeding
- `test_seed_data_drones_present` — verifies 4 drones exist after seeding

### Test Organization

```
backend/
└── tests/
    ├── test_risk.py          ← Property tests for risk classification (Properties 1, 2)
    ├── test_dispatch.py      ← Property tests for drone selection (Properties 7, 8, 9, 10)
    ├── test_simulation.py    ← Property tests for simulation convergence (Properties 11, 12)
    ├── test_incidents.py     ← Property + unit tests for incident endpoints (Properties 3, 4)
    ├── test_cameras.py       ← Property + unit tests for camera endpoints (Properties 13, 14, 15)
    ├── test_monitoring.py    ← Property + unit tests for monitoring (Properties 5, 6)
    └── conftest.py           ← Shared fixtures (test Supabase client, FastAPI TestClient)
```

### Running Tests

```bash
cd backend
pip install pytest hypothesis pytest-asyncio
pytest tests/ -v
```
