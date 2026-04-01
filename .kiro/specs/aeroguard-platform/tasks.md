# Implementation Plan: AeroGuard Platform

## Overview

Incremental build of the FastAPI backend: schema → Supabase client → models → services → routers → main app → tests. Each task wires into the previous so there is no orphaned code.

## Tasks

- [x] 1. Database schema and seed SQL files
  - Create `backend/db/schema.sql` with all five tables: `cameras`, `drones`, `incidents`, `dispatch_logs`, `monitoring_sessions`
  - Include CHECK constraints on `risk_score` (0–1), `incident_type` enum, `battery_pct` (0–100), `status` enums, and `confidence` (0–1)
  - Add `stream_url TEXT` column to `drones` table
  - Add Realtime publication SQL for `incidents`, `drones`, `dispatch_logs`
  - Create `backend/db/seed.sql` with 4 Pune cameras and 4 drones (Alpha-1, Beta-2, Gamma-3, Delta-4) per spec
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 2.3, 2.4, 6.1_

- [x] 2. Supabase client module
  - Create `backend/db/supabase.py` that reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from environment via `python-dotenv` and exposes a single `supabase` client instance
  - _Requirements: 13.1, 16.1_

- [x] 3. Pydantic schemas
  - Create `backend/models/schemas.py` with all request/response models: `CameraCreate`, `CameraUpdate`, `CameraOut`, `IncidentCreate`, `IncidentOut`, `DroneOut`, `DispatchRequest`, `DispatchOut`, `MonitoringStart`, `MonitoringStop`, `MonitoringSessionOut`, `StatusUpdate`
  - Use `Literal` for `incident_type` and drone `status` fields; use `Field(ge=0.0, le=1.0)` for `risk_score` and `confidence`
  - _Requirements: 16.2, 2.2, 4.1_

- [x] 4. Risk classification service
  - Create `backend/services/risk.py` with `classify_risk(risk_score: float) -> str`
  - Implement thresholds: `< 0.4` → `"low"`, `0.4–0.7` inclusive → `"medium"`, `> 0.7` → `"high"`
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

  - [ ]* 4.1 Write property test for risk classification (Property 1)
    - **Property 1: Risk Classification Correctness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5, 3.6**
    - File: `backend/tests/test_risk.py`
    - Use `@given(st.floats(min_value=0.0, max_value=1.0))` with `settings(max_examples=100)`

- [x] 5. Dispatch service — drone selection algorithm and ETA
  - Create `backend/services/dispatch.py`
  - Implement `select_drone(drones: list, incident_lat, incident_lng) -> dict | None` filtering `status == "available"` AND `battery_pct > 30`, computing score per formula, tie-breaking on higher `battery_pct`
  - Implement `compute_eta(distance_km: float, speed_kmh: float) -> int` using `round((distance_km / speed_kmh) * 3600)`
  - Implement `dispatch_drone(incident_id, drone_id=None)` async function: query Supabase, select drone, update `status = en_route`, insert `dispatch_logs` record, launch simulation background task
  - Return 409 detail string when no eligible drones exist (caller raises `HTTPException`)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2_

  - [ ]* 5.1 Write property test for drone eligibility filter (Property 7)
    - **Property 7: Drone Selection Filters Eligibility Correctly**
    - **Validates: Requirements 4.1**
    - File: `backend/tests/test_dispatch.py`

  - [ ]* 5.2 Write property test for score minimization (Property 8)
    - **Property 8: Drone Selection Score Minimization**
    - **Validates: Requirements 4.3, 4.4, 4.5**
    - File: `backend/tests/test_dispatch.py`

  - [ ]* 5.3 Write property test for ETA calculation (Property 9)
    - **Property 9: ETA Calculation Correctness**
    - **Validates: Requirements 4.6**
    - Use `st.floats(min_value=0.1, max_value=100)` for distance and `st.floats(min_value=1, max_value=200)` for speed
    - File: `backend/tests/test_dispatch.py`

- [x] 6. Simulation service
  - Create `backend/services/simulation.py`
  - Implement `simulate_drone_to_incident(drone_id, incident_id, target_lat, target_lng, speed_kmh)` async function: 2-second tick loop, linear interpolation toward target, update `drones.lat`/`lng` in Supabase, set `status = on_scene` and write `arrived_at` when within 0.05 km
  - Implement `simulate_drone_return(drone_id, home_lat, home_lng, speed_kmh)` async function: same tick loop back to home coords, set `status = available` when within 0.05 km
  - Wrap loop body in try/except to prevent task crash from killing the process
  - _Requirements: 5.3, 5.4, 5.5, 5.6_

  - [ ]* 6.1 Write property test for simulation convergence to incident (Property 11)
    - **Property 11: Simulation Convergence — Drone Reaches Incident**
    - **Validates: Requirements 5.3, 5.4**
    - File: `backend/tests/test_simulation.py`
    - Test the pure movement logic (not the async loop) with arbitrary start/target positions

  - [ ]* 6.2 Write property test for simulation return home (Property 12)
    - **Property 12: Simulation Convergence — Drone Returns Home**
    - **Validates: Requirements 5.5, 5.6**
    - File: `backend/tests/test_simulation.py`

- [x] 7. Cameras router
  - Create `backend/routers/cameras.py` with `GET /cameras`, `POST /cameras`, `PATCH /cameras/{id}`
  - Import schemas from `models/schemas.py` and Supabase client from `db/supabase.py`
  - Return 404 when camera not found on PATCH; return 422 automatically via Pydantic for missing required fields
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 7.1 Write property test for camera creation round-trip (Property 13)
    - **Property 13: Camera Creation Round-Trip**
    - **Validates: Requirements 11.2**
    - File: `backend/tests/test_cameras.py`

  - [ ]* 7.2 Write property test for camera validation (Property 14)
    - **Property 14: Camera Validation Rejects Missing Required Fields**
    - **Validates: Requirements 11.3**
    - File: `backend/tests/test_cameras.py`

  - [ ]* 7.3 Write property test for PATCH partial update (Property 15)
    - **Property 15: PATCH Endpoints Update Only Supplied Fields**
    - **Validates: Requirements 2.7, 5.9, 11.4**
    - File: `backend/tests/test_cameras.py`

- [x] 8. Incidents router with risk classification trigger
  - Create `backend/routers/incidents.py` with `GET /incidents`, `POST /incidents`, `PATCH /incidents/{id}/status`
  - On `POST /incidents`: call `classify_risk(risk_score)`, persist `risk_level` to Supabase, and if `risk_level == "high"` call `dispatch_drone(incident_id)` via `BackgroundTasks`
  - Return incidents ordered by `created_at` descending
  - _Requirements: 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4_

  - [ ]* 8.1 Write property test for risk level persisted on incident creation (Property 2)
    - **Property 2: Risk Level Persisted on Incident Creation**
    - **Validates: Requirements 3.4**
    - File: `backend/tests/test_risk.py`

  - [ ]* 8.2 Write property test for invalid incident data rejected (Property 3)
    - **Property 3: Invalid Incident Data Rejected by Database**
    - **Validates: Requirements 2.3, 2.4**
    - File: `backend/tests/test_incidents.py`

  - [ ]* 8.3 Write property test for incident list ordering (Property 4)
    - **Property 4: Incident List Ordering**
    - **Validates: Requirements 2.6**
    - File: `backend/tests/test_incidents.py`

- [x] 9. Drones router including dispatch endpoint
  - Create `backend/routers/drones.py` with `GET /drones`, `POST /drones/dispatch`, `PATCH /drones/{id}/status`
  - `POST /drones/dispatch`: call `dispatch_drone(incident_id, drone_id)` from `services/dispatch.py`; raise `HTTPException(409)` when no drones available; launch simulation via `BackgroundTasks`
  - Return 404 when drone not found on PATCH
  - _Requirements: 5.7, 5.8, 5.9, 4.2_

  - [ ]* 9.1 Write property test for dispatch invariants (Property 10)
    - **Property 10: Dispatch Invariants**
    - **Validates: Requirements 5.1, 5.2**
    - File: `backend/tests/test_dispatch.py`

- [x] 10. Monitoring router
  - Create `backend/routers/monitoring.py` with `POST /monitoring/start`, `POST /monitoring/stop`, `GET /monitoring/sessions`
  - `POST /monitoring/start`: verify camera exists (404 if not), insert `monitoring_sessions` record with `status = active`
  - `POST /monitoring/stop`: verify session exists (404 if not), update `status = stopped` and `ended_at`
  - Return sessions ordered by `started_at` descending
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [ ]* 10.1 Write property test for monitoring session lifecycle (Property 5)
    - **Property 5: Monitoring Session Lifecycle Round-Trip**
    - **Validates: Requirements 1.1, 1.3**
    - File: `backend/tests/test_monitoring.py`

  - [ ]* 10.2 Write property test for monitoring sessions ordering (Property 6)
    - **Property 6: Monitoring Sessions Ordering**
    - **Validates: Requirements 1.6**
    - File: `backend/tests/test_monitoring.py`

- [x] 11. Video stream proxy router
  - Create `backend/routers/stream.py` with `GET /stream/{drone_id}` and `GET /stream/camera/{camera_id}`
  - Look up `stream_url` from `drones` / `cameras` table; return 404 if record not found, 503 if `stream_url` is null or empty
  - Use `httpx.AsyncClient` async streaming generator and return `StreamingResponse` with `media_type="multipart/x-mixed-replace; boundary=frame"`
  - _Requirements: 10.5 (camera feed), 5.7 (drone feed)_

- [x] 12. FastAPI main.py — app setup, CORS, global exception handler, router registration
  - Create `backend/main.py`: instantiate `FastAPI`, add `CORSMiddleware` allowing all origins (configurable), register all five routers (`cameras`, `incidents`, `drones`, `monitoring`, `stream`)
  - Register global exception handler that catches `Exception`, logs traceback, returns `JSONResponse(500, {"detail": str(exc)})`
  - Load `.env` via `python-dotenv` at startup
  - _Requirements: 15.3, 16.3, 16.4, 13.1_

- [ ] 13. Checkpoint — core backend wired up
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Test infrastructure and unit tests
  - Create `backend/tests/conftest.py` with shared fixtures: `TestClient` wrapping the FastAPI app, mock Supabase responses using `unittest.mock`
  - Write unit tests in the appropriate test files:
    - `test_monitoring_start_404_unknown_camera`
    - `test_monitoring_stop_404_unknown_session`
    - `test_dispatch_no_drones_available` (expects 409)
    - `test_post_incidents_manual_creation`
    - `test_get_cameras_returns_list`
    - `test_get_drones_returns_list`
    - `test_global_exception_handler_returns_500`
    - `test_stream_endpoint_503_no_stream_url`
  - _Requirements: 1.2, 1.4, 4.2, 2.5, 11.1, 5.8, 15.3_

- [x] 15. Vision service placeholder
  - Create `aeroguard/vision_service/README.md` documenting: purpose (developed separately by Om), communication method (writes directly to Supabase `incidents` table using service-role key), and the exact `incidents` table schema the Vision_Service must conform to
  - Ensure no application source code files exist in `vision_service/`
  - _Requirements: 14.1, 14.2, 14.3_

- [x] 16. Environment example files and .gitignore
  - Verify/update `backend/.env.example` lists `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ORS_API_KEY`, `DRONE_SPEED_KMH` with placeholder values and no real secrets
  - Create `dashboard/.env.local.example` listing `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_ORS_API_KEY` with placeholder values
  - Verify/update `.gitignore` excludes `.env`, `.env.local`, `*.env`
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [x] 17. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with `settings(max_examples=100)`; tag format: `# Feature: aeroguard-platform, Property <N>: <text>`
- Unit tests use `pytest` with `TestClient` and mocked Supabase calls — no live Supabase connection required for tests
- The design document uses Python/FastAPI throughout; no language selection prompt was needed
