# Requirements Document

## Introduction

This feature refactors the AeroGuard backend and vision service to support a concurrent, synchronous
analysis architecture. The current design constructs a new model instance per request and runs analysis
inline. The new design initializes a shared `InferenceManager` at startup, splits the analysis pipeline
into four explicit stages (download → frame extraction → model scoring → Supabase insert), and uses
bounded concurrency primitives to safely handle multiple simultaneous `POST /analyze` requests on a
single host. Each request is accepted immediately by FastAPI, processed through the shared pipeline,
and returns only after the incident row has been inserted into Supabase. Backpressure is enforced via
semaphores and worker pools; if capacity is saturated the service returns `503` rather than silently
queuing unbounded work.

## Glossary

- **Analysis_Service**: The orchestration layer inside the backend that coordinates the four pipeline
  stages for a single `POST /analyze` request.
- **InferenceManager**: A process-level singleton that holds the loaded PyTorch model, device
  configuration, and threshold settings. Initialized once at application startup.
- **AnomalyDetector**: The existing vision-service detector class, refactored so model weights are
  loaded once into `InferenceManager` and per-request state is isolated in a lightweight session object.
- **AnalyzeRequest**: The validated Pydantic request body for `POST /analyze`, containing `stream_url`,
  `session_id`, `camera_id`, and optional metadata.
- **AnalyzeResult**: The typed Pydantic response model returned by `POST /analyze` and written to
  Supabase, containing `incident_type`, `risk_score`, `confidence`, `lat`, `lng`, and lifecycle
  timestamps.
- **Download_Semaphore**: An `asyncio.Semaphore` that limits the number of concurrent remote video
  fetches to `MAX_CONCURRENT_DOWNLOADS`.
- **Decode_Worker_Pool**: A `ThreadPoolExecutor` that limits concurrent OpenCV / video preprocessing
  operations to `MAX_CONCURRENT_DECODES`.
- **Inference_Semaphore**: An `asyncio.Semaphore` that limits concurrent PyTorch forward passes to
  `MAX_CONCURRENT_INFERENCES`.
- **Backpressure**: The behavior of returning `503 Service Unavailable` when all worker slots are
  occupied, preventing unbounded latency growth.
- **Request_Lifecycle**: The set of timestamps and identifiers attached to each request:
  `request_id` (or `session_id`), `download_start`, `download_end`, `analysis_start`, `analysis_end`,
  and `db_insert_result`.
- **Settings**: The centralized Pydantic `BaseSettings` model that reads all runtime configuration
  from environment variables.
- **CPU_Mode**: Runtime mode when no CUDA-capable GPU is detected; allows several concurrent
  inferences with worker count tied to CPU core count.
- **GPU_Mode**: Runtime mode when a CUDA-capable GPU is detected; preprocessing remains concurrent
  but model forward passes are serialized or tightly limited to avoid VRAM contention.
- **Temp_File**: A temporary file written to disk during video download and frame extraction,
  deleted in all success and failure paths.
- **Incident_Row**: A record inserted into the Supabase `incidents` table after scoring completes,
  conforming to the schema defined in `vision_service/README.md`.
- **Backend**: The FastAPI application at `aeroguard/backend/`.
- **Vision_Service**: The computer-vision component at `aeroguard/vision_service/`.
- **Supabase**: The hosted PostgreSQL backend-as-a-service used as the shared data layer.
- **Vision_Service_Client**: The HTTP client module inside the Backend responsible for calling the Vision_Service's `POST /analyze` endpoint. The Backend is the caller; the Vision_Service is the server.
- **Batch_Upload_Endpoint**: The new `POST /upload/videos` endpoint that accepts N video files with their camera associations, uploads all files to Supabase Storage, and fans out N concurrent calls to the Vision_Service_Client.
- **Fan_Out**: The concurrent dispatch of N independent `POST /analyze` calls to the Vision_Service, one per uploaded video, executed simultaneously rather than sequentially.
- **Batch_Result**: The aggregated response returned by the Batch_Upload_Endpoint containing per-video outcomes — each entry is either a success (with its `AnalyzeResult`) or a failure (with its error detail).
- **VideoUploadItem**: A single element in a batch request, pairing one video file with its associated `camera_id`.
- **Partial_Success**: The condition where at least one but not all videos in a batch are successfully analyzed; the Backend returns HTTP 207 with per-video success and failure entries.

---

## Requirements

---

### Requirement 1: Startup-Time Model Initialization

**User Story:** As a backend operator, I want the PyTorch model to be loaded once at application
startup, so that individual requests do not pay the cost of model construction and VRAM allocation.

#### Acceptance Criteria

1. WHEN the FastAPI application starts, THE InferenceManager SHALL load model weights from the
   configured path exactly once and store the loaded model in process memory.
2. WHEN the FastAPI application starts, THE InferenceManager SHALL detect whether a CUDA-capable GPU
   is available and set the device accordingly (`cuda` or `cpu`).
3. WHILE the application is running, THE InferenceManager SHALL expose a single shared instance
   accessible to all request handlers without re-loading weights.
4. IF model weight loading fails at startup, THEN THE Backend SHALL log the error and exit with a
   non-zero status code rather than starting in a degraded state.
5. THE Settings SHALL read the model weights path from the `MODEL_WEIGHTS_PATH` environment variable.

---

### Requirement 2: Centralized Runtime Configuration

**User Story:** As a developer, I want all concurrency limits and timeout values read from environment
variables at startup, so that I can tune the service without code changes.

#### Acceptance Criteria

1. THE Settings SHALL expose the following configuration keys read exclusively from environment
   variables: `MAX_CONCURRENT_DOWNLOADS`, `MAX_CONCURRENT_DECODES`, `MAX_CONCURRENT_INFERENCES`,
   `REQUEST_TIMEOUT_SECONDS`, `DOWNLOAD_TIMEOUT_SECONDS`, `ANALYSIS_FRAMES`, `CALIBRATION_FRAMES`,
   `SUPABASE_TIMEOUT_SECONDS`.
2. WHEN an environment variable for a concurrency limit is absent, THE Settings SHALL apply a
   documented default value for that key.
3. THE Backend SHALL initialize the Download_Semaphore, Decode_Worker_Pool, and Inference_Semaphore
   using the values from Settings at application startup.
4. THE Settings module SHALL be the single source of truth for all runtime configuration; no other
   module SHALL hard-code concurrency limits or timeout values.

---

### Requirement 3: `POST /analyze` Endpoint (Vision_Service — called by Backend)

**User Story:** As a monitoring session controller, I want to submit a video stream URL and receive
a completed analysis result synchronously, so that the caller knows the incident has been persisted
before the HTTP response is returned.

> **Note:** The Vision_Service owns and implements `POST /analyze`. The Backend is the HTTP client
> that calls this endpoint via the Vision_Service_Client. The Backend does NOT implement this route.

#### Acceptance Criteria

1. THE Vision_Service SHALL expose `POST /analyze` accepting an `AnalyzeRequest` body containing at
   minimum `stream_url` (required), `session_id` (required), and `camera_id` (required).
2. WHEN `POST /analyze` is called with a missing or empty `stream_url`, THE Vision_Service SHALL
   return HTTP 400 with a descriptive validation error.
3. WHEN `POST /analyze` is called with a missing `camera_id`, THE Vision_Service SHALL return HTTP
   400 with a descriptive validation error.
4. WHEN `POST /analyze` completes successfully, THE Vision_Service SHALL return HTTP 200 with an
   `AnalyzeResult` body whose fields match the Incident_Row inserted into Supabase.
5. WHEN `POST /analyze` completes successfully, THE Vision_Service SHALL return the response only
   after the Incident_Row has been committed to Supabase.
6. WHEN the video source at `stream_url` is unreachable or returns an invalid media response,
   THE Vision_Service SHALL return HTTP 424 with a descriptive error message.
7. WHEN all worker slots are occupied at the time of the request, THE Vision_Service SHALL return
   HTTP 503 with `{"detail": "Service at capacity, retry later"}` without queuing the request.
8. WHEN an unexpected error occurs during inference or Supabase insert, THE Vision_Service SHALL
   return HTTP 500 with a descriptive error message and log the full traceback.

---

### Requirement 4: Four-Stage Analysis Pipeline

**User Story:** As a developer, I want the analysis flow split into four explicit stages, so that
each stage can be independently tested, monitored, and replaced.

#### Acceptance Criteria

1. THE Analysis_Service SHALL execute requests through exactly four sequential stages in order:
   `download_video` → `extract_and_calibrate_frames` → `model_scoring` → `supabase_insert`.
2. WHEN the `download_video` stage starts, THE Analysis_Service SHALL acquire the Download_Semaphore
   before initiating any network I/O and release it immediately after the video file is written to a
   Temp_File.
3. WHEN the `extract_and_calibrate_frames` stage runs, THE Analysis_Service SHALL submit the work to
   the Decode_Worker_Pool and await completion before proceeding to model scoring.
4. WHEN the `model_scoring` stage starts, THE Analysis_Service SHALL acquire the Inference_Semaphore
   before calling any PyTorch forward pass and release it immediately after scoring completes.
5. WHEN the `supabase_insert` stage runs, THE Analysis_Service SHALL insert the Incident_Row using
   the Supabase service-role key and await confirmation before returning the result.
6. IF any stage raises an exception, THEN THE Analysis_Service SHALL delete the Temp_File (if it
   exists) and re-raise the exception so the endpoint can return the appropriate HTTP error.
7. WHEN the pipeline completes successfully, THE Analysis_Service SHALL delete the Temp_File before
   returning the AnalyzeResult.

---

### Requirement 5: Bounded Concurrency

**User Story:** As a platform engineer, I want concurrency bounded by explicit semaphores and worker
pools, so that the service degrades gracefully under load instead of exhausting memory or VRAM.

#### Acceptance Criteria

1. THE Download_Semaphore SHALL limit simultaneous remote video fetches to `MAX_CONCURRENT_DOWNLOADS`
   at any point in time.
2. THE Decode_Worker_Pool SHALL limit simultaneous OpenCV / video preprocessing threads to
   `MAX_CONCURRENT_DECODES` at any point in time.
3. THE Inference_Semaphore SHALL limit simultaneous PyTorch forward passes to
   `MAX_CONCURRENT_INFERENCES` at any point in time.
4. WHILE running in CPU_Mode, THE Backend SHALL set the default `MAX_CONCURRENT_INFERENCES` to a
   value derived from the available CPU core count.
5. WHILE running in GPU_Mode, THE Backend SHALL set the default `MAX_CONCURRENT_INFERENCES` to 1
   to serialize forward passes and prevent VRAM contention.
6. WHEN a request attempts to acquire the Download_Semaphore or Inference_Semaphore and all slots
   are occupied, THE Backend SHALL return HTTP 503 immediately rather than blocking the request.

---

### Requirement 6: Detector Refactoring — Shared Model, Isolated State

**User Story:** As a developer, I want the AnomalyDetector refactored so model weights are loaded
once and per-request state is isolated, so that concurrent requests do not share mutable state.

#### Acceptance Criteria

1. THE InferenceManager SHALL hold the following shared state: loaded model weights, device
   (`cuda` or `cpu`), and threshold configuration.
2. THE Analysis_Service SHALL create a new per-request session object for each `POST /analyze` call
   that holds: baseline value, smoothing buffer, per-frame scores, and Temp_File path.
3. THE per-request session object SHALL NOT hold a reference to the model weights or device; it
   SHALL receive scoring results by calling `InferenceManager.analyze_video(request)`.
4. WHEN two concurrent requests are in the `model_scoring` stage, THE InferenceManager SHALL
   process each request's frames using the same loaded model without mutating shared state.
5. THE InferenceManager SHALL expose a single public method:
   `analyze_video(request: AnalyzeRequest) -> AnalyzeResult`.

---

### Requirement 7: Request Lifecycle Metadata

**User Story:** As an operator, I want each request to carry lifecycle timestamps and a unique
identifier, so that I can trace slow or failed requests through logs.

#### Acceptance Criteria

1. THE Analysis_Service SHALL attach a `request_id` to each `POST /analyze` call; if `session_id`
   is provided in the request body it SHALL be used as the `request_id`, otherwise a UUID SHALL
   be generated.
2. THE Analysis_Service SHALL record the following timestamps for each request: `download_start`,
   `download_end`, `analysis_start`, `analysis_end`.
3. THE Analysis_Service SHALL log the `request_id`, `camera_id`, stage durations, queue wait time,
   inference time, and final status as a single structured log entry upon request completion.
4. WHEN a request fails at any stage, THE Analysis_Service SHALL log the `request_id`, the failed
   stage name, and the exception message at ERROR level.

---

### Requirement 8: Temp File Cleanup

**User Story:** As a platform engineer, I want temporary video files deleted in all code paths, so
that disk space is not leaked by failed or cancelled requests.

#### Acceptance Criteria

1. WHEN the `download_video` stage completes, THE Analysis_Service SHALL record the Temp_File path
   in the per-request session object.
2. WHEN the pipeline completes successfully, THE Analysis_Service SHALL delete the Temp_File.
3. WHEN any pipeline stage raises an exception, THE Analysis_Service SHALL delete the Temp_File if
   it exists before propagating the exception.
4. IF the Temp_File does not exist at cleanup time, THE Analysis_Service SHALL log a warning and
   continue without raising an additional exception.

---

### Requirement 9: Supabase Insert and Response Alignment

**User Story:** As a developer, I want the API response body to be derived from the persisted
Supabase row, so that the caller's view of the incident is always consistent with the database.

#### Acceptance Criteria

1. THE Analysis_Service SHALL insert the Incident_Row into Supabase only after model scoring
   completes and a valid `AnalyzeResult` has been produced.
2. THE `AnalyzeResult` returned in the HTTP response SHALL be constructed from the data returned
   by the Supabase insert operation, not from the pre-insert in-memory object.
3. THE Incident_Row inserted into Supabase SHALL include: `camera_id`, `incident_type`, `risk_score`,
   `confidence`, `lat`, `lng`, and optionally `snapshot_url`.
4. WHEN the Supabase insert fails, THE Backend SHALL return HTTP 500 and SHALL NOT return a
   partially constructed `AnalyzeResult` to the caller.

---

### Requirement 10: Error Handling and HTTP Status Codes

**User Story:** As an API consumer, I want predictable HTTP status codes for every failure mode,
so that I can implement correct retry and alerting logic.

#### Acceptance Criteria

1. WHEN `POST /analyze` receives a request body with missing required fields, THE Backend SHALL
   return HTTP 400.
2. WHEN the video source at `stream_url` is unreachable or returns a non-video response, THE
   Backend SHALL return HTTP 424.
3. WHEN all concurrency slots are saturated, THE Backend SHALL return HTTP 503.
4. WHEN an unexpected error occurs during inference or DB insert, THE Backend SHALL return HTTP 500.
5. THE Backend SHALL never return HTTP 200 for a request whose Incident_Row was not successfully
   committed to Supabase.

---

### Requirement 11: Observability — Structured Logging and Metrics

**User Story:** As a platform engineer, I want structured logs and basic metrics counters for every
request, so that I can diagnose performance issues and monitor queue health.

#### Acceptance Criteria

1. THE Backend SHALL emit a structured log entry per request containing: `request_id`, `camera_id`,
   `download_duration_ms`, `decode_duration_ms`, `inference_duration_ms`, `db_insert_duration_ms`,
   `queue_wait_ms`, and `final_status`.
2. THE Backend SHALL maintain the following in-process counters: `active_requests`,
   `queue_depth_downloads`, `queue_depth_inferences`, `total_requests`, `failed_requests`.
3. THE Backend SHALL expose `GET /metrics` returning the current values of all counters as JSON.
4. WHEN a request fails, THE Backend SHALL increment `failed_requests` and record the `failure_reason`
   in the structured log entry.

---

### Requirement 12: Blocking Work Execution Model

**User Story:** As a developer, I want all blocking I/O and CPU-bound work run in thread pools so
that FastAPI's event loop is not blocked and can accept new requests while analysis is in progress.

#### Acceptance Criteria

1. THE Analysis_Service SHALL run the `download_video` stage using `run_in_threadpool` or an
   executor so the event loop is not blocked during network I/O.
2. THE Analysis_Service SHALL run the `extract_and_calibrate_frames` stage in the Decode_Worker_Pool
   so the event loop is not blocked during OpenCV processing.
3. THE Analysis_Service SHALL run the `model_scoring` stage using `run_in_threadpool` or an executor
   so the event loop is not blocked during PyTorch forward passes.
4. WHILE blocking work is executing in a thread pool, THE FastAPI event loop SHALL remain free to
   accept and begin processing additional `POST /analyze` requests.

---

### Requirement 13: Round-Trip Consistency — Response Matches DB Row

**User Story:** As a developer, I want a verifiable guarantee that the API response fields match
the inserted Supabase row, so that clients and the database are never out of sync.

#### Acceptance Criteria

1. FOR ALL successful `POST /analyze` calls, the `incident_type`, `risk_score`, `confidence`, `lat`,
   and `lng` fields in the HTTP response SHALL equal the corresponding fields in the Incident_Row
   returned by Supabase.
2. FOR ALL successful `POST /analyze` calls, the `id` field in the HTTP response SHALL equal the
   `id` assigned by Supabase to the inserted Incident_Row.
3. THE Pretty_Printer SHALL be able to serialize any `AnalyzeResult` to a JSON object and
   deserialize it back to an equivalent `AnalyzeResult` without data loss (round-trip property).

---

### Requirement 14: Concurrency Correctness

**User Story:** As a platform engineer, I want concurrent requests to be processed independently
without shared mutable state, so that one request's failure or slowness does not affect others.

#### Acceptance Criteria

1. WHEN 5 or more concurrent `POST /analyze` requests are in flight, each request SHALL produce
   an independent `AnalyzeResult` and Incident_Row without interfering with other in-flight requests.
2. WHEN one in-flight request fails at any pipeline stage, THE remaining in-flight requests SHALL
   complete normally and return their own results.
3. THE InferenceManager SHALL NOT reload model weights between requests regardless of how many
   concurrent requests are processed.
4. WHEN the worker queue is saturated and a new request arrives, THE Backend SHALL return HTTP 503
   for the new request without affecting the requests already being processed.


---

### Requirement 15: Multi-Video Batch Upload and Fan-Out

**User Story:** As a platform operator, I want to upload N videos in a single request and have all
of them dispatched concurrently to the Vision_Service, so that analysis throughput scales with the
number of cameras rather than being limited to one video at a time.

#### Acceptance Criteria

1. THE Batch_Upload_Endpoint SHALL expose `POST /upload/videos` accepting a multipart form body
   containing one or more `VideoUploadItem` entries, each pairing a video file with a `camera_id`.
2. WHEN `POST /upload/videos` is called with zero video files, THE Batch_Upload_Endpoint SHALL
   return HTTP 400 with a descriptive validation error.
3. WHEN `POST /upload/videos` is called with any `VideoUploadItem` whose `camera_id` is absent or
   empty, THE Batch_Upload_Endpoint SHALL return HTTP 400 with a descriptive validation error
   identifying the offending item.
4. WHEN `POST /upload/videos` is called with N valid `VideoUploadItem` entries, THE
   Batch_Upload_Endpoint SHALL upload all N video files to Supabase Storage concurrently and obtain
   a public URL for each before dispatching any Vision_Service calls.
5. WHEN all N public URLs have been obtained, THE Batch_Upload_Endpoint SHALL dispatch exactly N
   concurrent `POST /analyze` calls to the Vision_Service via the Vision_Service_Client, one per
   video, each carrying the corresponding `camera_id` and public URL as `stream_url`.
6. THE Fan_Out SHALL use `asyncio.gather` with `return_exceptions=True` so that a failure in one
   Vision_Service call does not cancel the remaining in-flight calls.
7. WHEN the Vision_Service returns HTTP 503 for a given video, THE Vision_Service_Client SHALL
   retry that call up to `VISION_SERVICE_MAX_RETRIES` times with exponential back-off before
   recording the item as failed.
8. THE Batch_Upload_Endpoint SHALL wait for all N Vision_Service calls (including retries) to
   settle before constructing and returning the Batch_Result.

---

### Requirement 16: Batch Response Aggregation

**User Story:** As an API consumer, I want a single response that reports the outcome for every
video in the batch, so that I can identify which analyses succeeded and which failed without
issuing additional requests.

#### Acceptance Criteria

1. THE Batch_Upload_Endpoint SHALL return a `Batch_Result` containing exactly N entries, one per
   input `VideoUploadItem`, preserving the original submission order.
2. FOR EACH successful Vision_Service call, THE Batch_Result entry SHALL include the `camera_id`,
   the Supabase public URL, and the full `AnalyzeResult` returned by the Vision_Service.
3. FOR EACH failed Vision_Service call, THE Batch_Result entry SHALL include the `camera_id`, the
   Supabase public URL, a `status` of `"failed"`, and a human-readable `error` field describing
   the failure reason (e.g., HTTP status code and response body excerpt).
4. WHEN all N calls succeed, THE Batch_Upload_Endpoint SHALL return HTTP 200.
5. WHEN at least one call succeeds and at least one fails (Partial_Success), THE
   Batch_Upload_Endpoint SHALL return HTTP 207 with the full `Batch_Result`.
6. WHEN all N calls fail, THE Batch_Upload_Endpoint SHALL return HTTP 502 with the full
   `Batch_Result` so the caller can inspect per-video failure reasons.
7. THE Batch_Upload_Endpoint SHALL never return HTTP 200 unless every entry in the `Batch_Result`
   has a `status` of `"success"`.
8. FOR ALL `Batch_Result` responses, the count of entries in the response SHALL equal the count of
   `VideoUploadItem` entries in the request (round-trip cardinality property).

---

### Requirement 17: Vision Service Client

**User Story:** As a developer, I want a dedicated HTTP client module that encapsulates all
communication with the Vision_Service, so that retry logic, timeout handling, and error mapping
are defined in one place and reused by both single-video and batch code paths.

#### Acceptance Criteria

1. THE Vision_Service_Client SHALL be a standalone module inside the Backend that exposes a single
   async function: `analyze(stream_url: str, camera_id: str, session_id: str) -> AnalyzeResult`.
2. THE Vision_Service_Client SHALL read the Vision_Service base URL from the
   `VISION_SERVICE_URL` environment variable via Settings; no other module SHALL hard-code this URL.
3. WHEN the Vision_Service returns HTTP 200, THE Vision_Service_Client SHALL deserialize the
   response body into an `AnalyzeResult` and return it to the caller.
4. WHEN the Vision_Service returns HTTP 503, THE Vision_Service_Client SHALL retry the request
   after a back-off delay; the number of retries SHALL be controlled by the
   `VISION_SERVICE_MAX_RETRIES` setting and the initial delay by `VISION_SERVICE_RETRY_DELAY_SECONDS`.
5. WHEN the Vision_Service returns HTTP 400 or HTTP 424, THE Vision_Service_Client SHALL NOT retry
   and SHALL raise a typed exception carrying the HTTP status code and response body.
6. WHEN the Vision_Service does not respond within `VISION_SERVICE_TIMEOUT_SECONDS`, THE
   Vision_Service_Client SHALL raise a timeout exception without retrying.
7. WHEN all retries are exhausted and the Vision_Service has not returned HTTP 200, THE
   Vision_Service_Client SHALL raise a typed exception so the caller can record the item as failed
   in the Batch_Result.
8. THE Settings SHALL expose `VISION_SERVICE_URL`, `VISION_SERVICE_MAX_RETRIES`,
   `VISION_SERVICE_RETRY_DELAY_SECONDS`, and `VISION_SERVICE_TIMEOUT_SECONDS` read from environment
   variables with documented defaults.
