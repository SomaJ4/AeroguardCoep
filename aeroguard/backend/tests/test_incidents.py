from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


def get_client():
    from main import app
    return TestClient(app)


MOCK_INCIDENT = {
    "id": "inc-1", "camera_id": "cam-1", "incident_type": "fire",
    "risk_score": 0.9, "confidence": 0.8, "risk_level": "high",
    "lat": 18.5, "lng": 73.9, "snapshot_url": None,
    "status": "open", "created_at": "2024-01-01T00:00:00",
}


def test_post_incidents_manual_creation():
    payload = {"camera_id": "cam-1", "incident_type": "fire", "risk_score": 0.9, "confidence": 0.8, "lat": 18.5, "lng": 73.9}
    with patch("routers.incidents.supabase") as mock_sb, \
         patch("routers.incidents.dispatch_drone", new_callable=AsyncMock):
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [MOCK_INCIDENT]
        resp = get_client().post("/incidents", json=payload)
        assert resp.status_code == 201
        assert resp.json()["risk_level"] == "high"


def test_get_incidents_returns_list():
    with patch("routers.incidents.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = [MOCK_INCIDENT]
        resp = get_client().get("/incidents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_patch_incident_status_404():
    with patch("routers.incidents.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        resp = get_client().patch("/incidents/nonexistent/status", json={"status": "resolved"})
        assert resp.status_code == 404


def test_invalid_incident_type_rejected():
    payload = {"camera_id": "cam-1", "incident_type": "explosion", "risk_score": 0.5, "confidence": 0.8, "lat": 18.5, "lng": 73.9}
    resp = get_client().post("/incidents", json=payload)
    assert resp.status_code == 422


def test_invalid_risk_score_rejected():
    payload = {"camera_id": "cam-1", "incident_type": "fire", "risk_score": 1.5, "confidence": 0.8, "lat": 18.5, "lng": 73.9}
    resp = get_client().post("/incidents", json=payload)
    assert resp.status_code == 422
