# Implementation Plan: Vision Service Integration

## Overview

Build the AeroGuard backend client side for the Vision Service integration: a typed async HTTP
client (`VisionServiceClient`), Pydantic batch models, and a new `POST /upload/videos` endpoint
that uploads N files to Supabase Storage concurrently then fans out N parallel `POST /analyze`
calls to the Vision Service.

## Tasks

- [x] 1. Add Vision Service settings and env vars
  - Add `VISION_SERVICE_URL`, `VISION_SERVICE_MAX_RETRIES`, `VISION_SERVICE_RETRY_DELAY_SECONDS`,
    and `VISION_SERVICE_TIMEOUT_SECONDS` to `aeroguard/backend/.env.example` with documented defaults
  - Add corresponding `os.environ.get(...)` reads (with defaults) at the top of
    `services/vision_client.py` so all other modules import config from there
  - _Requirements: 17.2, 17.8_

- [x] 2. Implement `VisionServiceError` exception hierarchy
  - Create `aeroguard/backend/services/vision_client.py` with the four exception classes:
    `VisionServiceError` (base), `VisionServiceClientError` (400/424, carries `status_code` + `body`),
    `VisionServiceServerError` (500, carries `status_code` + `body`),
    `VisionServiceUnavailableError` (503 exhausted, carries `attempts`),
    `VisionServiceTimeoutError`
  - _Requirements: 17.5, 17.6, 17.7_

- [x] 3. Implement `VisionServiceClient.analyze()` with retry and timeout
  - Add `async def analyze(stream_url, camera_id, session_id) -> AnalyzeResult` to
    `services/vision_client.py`
  - Use `httpx.AsyncClient` with `timeout=VISION_SERVICE_TIMEOUT_SECONDS`
  - On HTTP 200: deserialize response body into `AnalyzeResult` and return
  - On HTTP 503: retry up to `VISION_SERVICE_MAX_RETRIES` with exponential back-off
    (`RETRY_DELAY * 2^attempt`); raise `VisionServiceUnavailableError` after exhaustion
  - On HTTP 400 / 424: raise `VisionServiceClientError` immediately, no retry
  - On HTTP 500: raise `VisionServiceServerError` immediately, no retry
  - On `httpx.TimeoutException`: raise `VisionServiceTimeoutError` immediately, no retry
  - _Requirements: 17.1, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [ ]* 3.1 Write property test for 503 retry count (Property 4)
    - **Property 4: 503 retry count**
    - **Validates: Requirements 15.7, 17.4**

  - [ ]* 3.2 Write property test for non-retryable errors 400/424 (Property 9)
    - **Property 9: Non-retryable errors (400/424) trigger exactly one attempt**
    - **Validates: Requirements 17.5**

  - [ ]* 3.3 Write property test for timeout single attempt (Property 10)
    - **Property 10: Timeout triggers exactly one attempt**
    - **Validates: Requirements 17.6**

- [x] 4. Add Pydantic batch models to `models/schemas.py`
  - Add `AnalyzeResult` (fields: `id`, `camera_id`, `incident_type`, `risk_score`, `confidence`,
    `lat`, `lng`, `snapshot_url`)
  - Add `BatchResultItem` (fields: `camera_id`, `url`, `status`, `result`, `error`)
  - Add `BatchResult` (field: `items: list[BatchResultItem]`)
  - _Requirements: 16.1, 16.2, 16.3, 17.3_

  - [ ]* 4.1 Write property test for AnalyzeResult round-trip (Property 8)
    - **Property 8: AnalyzeResult deserialization round-trip**
    - **Validates: Requirements 17.3**

- [x] 5. Implement `POST /upload/videos` endpoint in `routers/upload.py`
  - Add `@router.post("/videos")` to the existing `upload` router (do not modify `/video`)
  - Accept `files: list[UploadFile]` and `camera_ids: list[str]` from multipart form
  - Validate: non-empty files list, `len(files) == len(camera_ids)`, no empty/whitespace `camera_id`
    → HTTP 400 with descriptive detail for each case
  - Upload all files to Supabase Storage concurrently via `asyncio.gather`
  - Collect public URLs, generate one `session_id` (UUID) per file
  - Fan out `vision_client.analyze(url, camera_id, session_id)` for all N items via
    `asyncio.gather(*coros, return_exceptions=True)`
  - Map each result/exception to a `BatchResultItem`
  - Determine HTTP status: 200 (all success) / 207 (partial) / 502 (all failed)
  - Return `BatchResult` with `JSONResponse(status_code=..., content=...)`
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.8, 16.1, 16.4, 16.5, 16.6, 16.7, 16.8_

  - [ ]* 5.1 Write property test for empty camera_id rejection (Property 1)
    - **Property 1: Empty camera_id rejected for any batch size**
    - **Validates: Requirements 15.3**

  - [ ]* 5.2 Write property test for upload-then-fan-out ordering (Property 2)
    - **Property 2: Upload-then-fan-out ordering and payload correctness**
    - **Validates: Requirements 15.4, 15.5**

  - [ ]* 5.3 Write property test for fan-out failure isolation (Property 3)
    - **Property 3: Fan-out failure isolation**
    - **Validates: Requirements 15.6**

  - [ ]* 5.4 Write property test for response cardinality and order (Property 5)
    - **Property 5: Response cardinality and order preservation**
    - **Validates: Requirements 16.1, 16.8**

  - [ ]* 5.5 Write property test for result entry completeness (Property 6)
    - **Property 6: Result entry completeness**
    - **Validates: Requirements 16.2, 16.3**

  - [ ]* 5.6 Write property test for HTTP status aggregate outcome (Property 7)
    - **Property 7: HTTP status reflects aggregate outcome**
    - **Validates: Requirements 16.4, 16.5, 16.6, 16.7**

- [x] 6. Checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Create `tests/test_upload_batch.py` with unit tests
  - Mock Supabase Storage (`supabase.storage.from_().upload` and `.get_public_url`) and Vision
    Service HTTP calls (use `respx` or `httpx.MockTransport`) — no real network calls
  - `test_empty_files_returns_400`
  - `test_missing_camera_id_returns_400`
  - `test_all_success_returns_200` — 3 items, all vision calls succeed → 200, 3 result entries
  - `test_partial_success_returns_207` — 3 items, 1 fails → 207, correct statuses
  - `test_all_fail_returns_502` — 3 items, all fail → 502, all entries have `error` field
  - `test_vision_client_503_retries` — mock returns 503 R times then 200; verify R+1 calls
  - `test_vision_client_400_no_retry` — mock returns 400; verify exactly 1 call, typed exception
  - `test_vision_client_timeout_no_retry` — mock raises `httpx.TimeoutException`; verify 1 call
  - _Requirements: 15.2, 15.3, 15.6, 15.7, 16.4, 16.5, 16.6, 17.4, 17.5, 17.6_

- [x] 8. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- The existing `POST /upload/video` endpoint must not be modified
- All property tests use Hypothesis with a minimum of 100 iterations
- No real network calls in any test — mock both Supabase Storage and Vision Service HTTP
- Property tests live in `tests/test_upload_batch.py` alongside unit tests
