from unittest.mock import patch
from fastapi.testclient import TestClient


def get_client():
    from main import app
    return TestClient(app)


def test_monitoring_start_404_unknown_camera():
    with patch("routers.monitoring.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        resp = get_client().post("/monitoring/start", json={"camera_id": "nonexistent"})
        assert resp.status_code == 404


def test_monitoring_stop_404_unknown_session():
    with patch("routers.monitoring.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        resp = get_client().post("/monitoring/stop", json={"session_id": "nonexistent"})
        assert resp.status_code == 404


def test_monitoring_start_success():
    mock_session = {"id": "sess-1", "camera_id": "cam-1", "status": "active", "started_at": "2024-01-01T00:00:00", "ended_at": None}
    with patch("routers.monitoring.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "cam-1"}]
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [mock_session]
        resp = get_client().post("/monitoring/start", json={"camera_id": "cam-1"})
        assert resp.status_code == 201
        assert resp.json()["status"] == "active"


def test_get_sessions_returns_list():
    with patch("routers.monitoring.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = []
        resp = get_client().get("/monitoring/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
