from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


def get_client():
    from main import app
    return TestClient(app)


MOCK_DRONE = {
    "id": "drone-1", "name": "Alpha-1", "lat": 18.5074, "lng": 73.9286,
    "home_lat": 18.5074, "home_lng": 73.9286, "battery_pct": 92,
    "status": "available", "speed_kmh": 60, "stream_url": None,
    "created_at": "2024-01-01T00:00:00",
}


def test_get_drones_returns_list():
    with patch("routers.drones.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.execute.return_value.data = [MOCK_DRONE]
        resp = get_client().get("/drones")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_dispatch_no_drones_available():
    with patch("routers.drones.dispatch_drone", new_callable=AsyncMock) as mock_dispatch:
        mock_dispatch.side_effect = ValueError("No available drones with sufficient battery")
        resp = get_client().post("/drones/dispatch", json={"incident_id": "inc-1"})
        assert resp.status_code == 409


def test_patch_drone_status_404():
    with patch("routers.drones.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        resp = get_client().patch("/drones/nonexistent/status", json={"status": "available"})
        assert resp.status_code == 404


def test_stream_endpoint_503_no_stream_url():
    with patch("routers.stream.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"stream_url": None}
        resp = get_client().get("/stream/drone-1")
        assert resp.status_code == 503


def test_global_exception_handler_returns_500():
    from main import app
    from fastapi.testclient import TestClient

    @app.get("/test-error")
    def raise_error():
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test-error")
    assert resp.status_code == 500
