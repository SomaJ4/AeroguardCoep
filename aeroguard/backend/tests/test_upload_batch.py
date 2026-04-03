"""
Tests for POST /upload/videos batch endpoint and VisionServiceClient.

Unit tests cover specific examples; property-based tests (Hypothesis) verify
universal correctness properties across randomized inputs.
"""
import asyncio
import io
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_test_client():
    from main import app
    return TestClient(app)


def _make_analyze_result(camera_id: str = "cam-1") -> dict:
    return {
        "id": "result-id",
        "camera_id": camera_id,
        "incident_type": "fire",
        "risk_score": 0.8,
        "confidence": 0.9,
        "lat": 18.5,
        "lng": 73.9,
        "snapshot_url": None,
    }


def _setup_supabase_mock(mock_sb):
    """Configure supabase mock for storage upload + get_public_url."""
    mock_sb.storage.from_.return_value.upload.return_value = None
    mock_sb.storage.from_.return_value.get_public_url.return_value = "https://example.com/video.mp4"


def _make_multipart(camera_ids: list[str], n_files: int | None = None):
    """
    Build the multipart payload for POST /upload/videos.

    In httpx-based TestClient, both file fields and form fields must be
    passed together in the ``files`` parameter as a list of tuples.
    Form-only fields use ``(None, value)`` as the file tuple.
    """
    if n_files is None:
        n_files = len(camera_ids)
    file_parts = [
        ("files", (f"v{i}.mp4", b"fake-video-content", "video/mp4"))
        for i in range(n_files)
    ]
    form_parts = [("camera_ids", (None, cid)) for cid in camera_ids]
    return file_parts + form_parts


# ---------------------------------------------------------------------------
# Unit tests — endpoint
# ---------------------------------------------------------------------------

def test_empty_files_returns_400():
    """POST /upload/videos with zero files → 400 or 422 (FastAPI rejects missing required field)."""
    with patch("routers.upload.supabase") as mock_sb:
        _setup_supabase_mock(mock_sb)
        client = get_test_client()
        # No files at all — FastAPI returns 422 for missing required File(...)
        resp = client.post("/upload/videos", files=[("camera_ids", (None, "cam-1"))])
        assert resp.status_code in (400, 422)


def test_missing_camera_id_returns_400():
    """POST /upload/videos with one item having empty camera_id → 400."""
    with patch("routers.upload.supabase") as mock_sb:
        _setup_supabase_mock(mock_sb)
        client = get_test_client()
        payload = _make_multipart(camera_ids=[""])
        resp = client.post("/upload/videos", files=payload)
        assert resp.status_code == 400


def test_all_success_returns_200():
    """3 items, all vision calls succeed → 200, 3 result entries with status 'success'."""
    camera_ids = ["cam-1", "cam-2", "cam-3"]

    with patch("routers.upload.supabase") as mock_sb, \
         patch("routers.upload.vision_client.analyze", new_callable=AsyncMock) as mock_analyze:
        _setup_supabase_mock(mock_sb)
        from models.schemas import AnalyzeResult
        mock_analyze.side_effect = [AnalyzeResult(**_make_analyze_result(cid)) for cid in camera_ids]

        client = get_test_client()
        resp = client.post("/upload/videos", files=_make_multipart(camera_ids))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    for item in body["items"]:
        assert item["status"] == "success"
        assert item["result"] is not None
        assert item["error"] is None


def test_partial_success_returns_207():
    """3 items, 1 fails → 207, correct statuses."""
    camera_ids = ["cam-1", "cam-2", "cam-3"]

    with patch("routers.upload.supabase") as mock_sb, \
         patch("routers.upload.vision_client.analyze", new_callable=AsyncMock) as mock_analyze:
        _setup_supabase_mock(mock_sb)
        from models.schemas import AnalyzeResult
        from services.vision_client import VisionServiceClientError
        mock_analyze.side_effect = [
            AnalyzeResult(**_make_analyze_result("cam-1")),
            VisionServiceClientError(status_code=400, body="bad request"),
            AnalyzeResult(**_make_analyze_result("cam-3")),
        ]

        client = get_test_client()
        resp = client.post("/upload/videos", files=_make_multipart(camera_ids))

    assert resp.status_code == 207
    body = resp.json()
    assert len(body["items"]) == 3
    statuses = [item["status"] for item in body["items"]]
    assert statuses.count("success") == 2
    assert statuses.count("failed") == 1
    failed_item = next(item for item in body["items"] if item["status"] == "failed")
    assert failed_item["error"] is not None


def test_all_fail_returns_502():
    """3 items, all fail → 502, all entries have 'failed' status and error field."""
    camera_ids = ["cam-1", "cam-2", "cam-3"]

    with patch("routers.upload.supabase") as mock_sb, \
         patch("routers.upload.vision_client.analyze", new_callable=AsyncMock) as mock_analyze:
        _setup_supabase_mock(mock_sb)
        from services.vision_client import VisionServiceUnavailableError
        mock_analyze.side_effect = [
            VisionServiceUnavailableError(attempts=4),
            VisionServiceUnavailableError(attempts=4),
            VisionServiceUnavailableError(attempts=4),
        ]

        client = get_test_client()
        resp = client.post("/upload/videos", files=_make_multipart(camera_ids))

    assert resp.status_code == 502
    body = resp.json()
    assert len(body["items"]) == 3
    for item in body["items"]:
        assert item["status"] == "failed"
        assert item["error"] is not None


# ---------------------------------------------------------------------------
# Unit tests — VisionServiceClient directly
# ---------------------------------------------------------------------------

def test_vision_client_503_retries():
    """
    Mock httpx to return 503 R times then 200; verify R+1 HTTP calls were made.
    Uses VISION_SERVICE_MAX_RETRIES=2 so we expect 3 total calls.
    """
    import services.vision_client as vc

    R = 2
    call_count = 0

    async def run():
        nonlocal call_count

        async def mock_post(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= R:
                return httpx.Response(503, text="unavailable")
            return httpx.Response(200, json=_make_analyze_result("cam-1"))

        with patch.object(httpx.AsyncClient, "post", new=mock_post), \
             patch.object(vc, "VISION_SERVICE_MAX_RETRIES", R), \
             patch.object(vc, "VISION_SERVICE_RETRY_DELAY_SECONDS", 0.0):
            result = await vc.analyze("http://example.com/video.mp4", "cam-1", "sess-1")
        return result

    result = asyncio.run(run())
    assert call_count == R + 1
    assert result.camera_id == "cam-1"


def test_vision_client_400_no_retry():
    """Mock returns 400; verify exactly 1 call, VisionServiceClientError raised."""
    import services.vision_client as vc
    from services.vision_client import VisionServiceClientError

    call_count = 0

    async def run():
        nonlocal call_count

        async def mock_post(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(400, text="bad request")

        with patch.object(httpx.AsyncClient, "post", new=mock_post):
            await vc.analyze("http://example.com/video.mp4", "cam-1", "sess-1")

    with pytest.raises(VisionServiceClientError):
        asyncio.run(run())

    assert call_count == 1


def test_vision_client_timeout_no_retry():
    """Mock raises httpx.TimeoutException; verify VisionServiceTimeoutError raised."""
    import services.vision_client as vc
    from services.vision_client import VisionServiceTimeoutError

    call_count = 0

    async def run():
        nonlocal call_count

        async def mock_post(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("timed out")

        with patch.object(httpx.AsyncClient, "post", new=mock_post):
            await vc.analyze("http://example.com/video.mp4", "cam-1", "sess-1")

    with pytest.raises(VisionServiceTimeoutError):
        asyncio.run(run())

    assert call_count == 1


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

# Feature: vision-service-integration, Property 5: Response cardinality and order preservation
@given(n=st.integers(min_value=1, max_value=6))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_response_cardinality(n):
    """BatchResult always contains exactly N items for N input files."""
    camera_ids = [f"cam-{i}" for i in range(n)]

    with patch("routers.upload.supabase") as mock_sb, \
         patch("routers.upload.vision_client.analyze", new_callable=AsyncMock) as mock_analyze:
        _setup_supabase_mock(mock_sb)
        from models.schemas import AnalyzeResult
        mock_analyze.side_effect = [
            AnalyzeResult(**_make_analyze_result(cid)) for cid in camera_ids
        ]

        client = get_test_client()
        resp = client.post("/upload/videos", files=_make_multipart(camera_ids))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == n


# Feature: vision-service-integration, Property 7: HTTP status reflects aggregate outcome
@given(outcomes=st.lists(st.booleans(), min_size=1, max_size=6))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_http_status_reflects_aggregate(outcomes):
    """200 if all succeed, 207 if partial, 502 if all fail."""
    n = len(outcomes)
    camera_ids = [f"cam-{i}" for i in range(n)]

    with patch("routers.upload.supabase") as mock_sb, \
         patch("routers.upload.vision_client.analyze", new_callable=AsyncMock) as mock_analyze:
        _setup_supabase_mock(mock_sb)
        from models.schemas import AnalyzeResult
        from services.vision_client import VisionServiceUnavailableError

        side_effects = []
        for i, success in enumerate(outcomes):
            if success:
                side_effects.append(AnalyzeResult(**_make_analyze_result(camera_ids[i])))
            else:
                side_effects.append(VisionServiceUnavailableError(attempts=4))
        mock_analyze.side_effect = side_effects

        client = get_test_client()
        resp = client.post("/upload/videos", files=_make_multipart(camera_ids))

    all_success = all(outcomes)
    all_fail = not any(outcomes)

    if all_success:
        assert resp.status_code == 200
    elif all_fail:
        assert resp.status_code == 502
    else:
        assert resp.status_code == 207
