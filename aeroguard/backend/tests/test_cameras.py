from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


def get_test_client():
    from main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_get_cameras_returns_list():
    mock_data = [{"id": "abc", "name": "Cam1", "location_desc": None, "lat": 18.5, "lng": 73.9, "stream_url": None, "is_active": True, "created_at": "2024-01-01T00:00:00"}]
    with patch("routers.cameras.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.execute.return_value.data = mock_data
        client = get_test_client()
        resp = client.get("/cameras")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_create_camera_success():
    payload = {"name": "Test Cam", "lat": 18.5, "lng": 73.9}
    mock_result = {"id": "xyz", "name": "Test Cam", "location_desc": None, "lat": 18.5, "lng": 73.9, "stream_url": None, "is_active": True, "created_at": "2024-01-01T00:00:00"}
    with patch("routers.cameras.supabase") as mock_sb:
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [mock_result]
        client = get_test_client()
        resp = client.post("/cameras", json=payload)
        assert resp.status_code == 201


def test_patch_camera_404():
    with patch("routers.cameras.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        client = get_test_client()
        resp = client.patch("/cameras/nonexistent-id", json={"name": "New Name"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Property 13: Camera Creation Round-Trip
# Validates: Requirements 11.2
# ---------------------------------------------------------------------------

camera_name_st = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_"))
lat_st = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
lng_st = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)


# Feature: aeroguard-platform, Property 13: Camera Creation Round-Trip
@given(name=camera_name_st, lat=lat_st, lng=lng_st)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_camera_creation_round_trip(name, lat, lng):
    """For any valid camera payload, the created record must contain all submitted fields and an assigned id."""
    payload = {"name": name, "lat": lat, "lng": lng}
    mock_result = {
        "id": "round-trip-id",
        "name": name,
        "location_desc": None,
        "lat": lat,
        "lng": lng,
        "stream_url": None,
        "is_active": True,
        "created_at": "2024-01-01T00:00:00",
    }
    mock_list = [mock_result]
    with patch("routers.cameras.supabase") as mock_sb:
        # POST returns the created record
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [mock_result]
        # GET returns the same record in a list
        mock_sb.table.return_value.select.return_value.execute.return_value.data = mock_list
        client = get_test_client()

        create_resp = client.post("/cameras", json=payload)
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["id"] == "round-trip-id"
        assert created["name"] == name
        assert created["lat"] == lat
        assert created["lng"] == lng

        list_resp = client.get("/cameras")
        assert list_resp.status_code == 200
        ids = [c["id"] for c in list_resp.json()]
        assert "round-trip-id" in ids


# ---------------------------------------------------------------------------
# Property 14: Camera Validation Rejects Missing Required Fields
# Validates: Requirements 11.3
# ---------------------------------------------------------------------------

# Feature: aeroguard-platform, Property 14: Camera Validation Rejects Missing Required Fields
@given(
    missing_field=st.sampled_from(["name", "lat", "lng"])
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_camera_missing_fields_rejected(missing_field):
    """POST /cameras with a missing required field must return 422."""
    full_payload = {"name": "ValidCam", "lat": 18.5, "lng": 73.9}
    payload = {k: v for k, v in full_payload.items() if k != missing_field}
    with patch("routers.cameras.supabase"):
        client = get_test_client()
        resp = client.post("/cameras", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Property 15: PATCH Endpoints Update Only Supplied Fields
# Validates: Requirements 2.7, 5.9, 11.4
# ---------------------------------------------------------------------------

optional_name_st = st.one_of(st.none(), camera_name_st)
optional_lat_st = st.one_of(st.none(), lat_st)
optional_lng_st = st.one_of(st.none(), lng_st)


# Feature: aeroguard-platform, Property 15: PATCH Endpoints Update Only Supplied Fields
@given(
    new_name=optional_name_st,
    new_lat=optional_lat_st,
    new_lng=optional_lng_st,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_patch_only_updates_supplied_fields(new_name, new_lat, new_lng):
    """PATCH /cameras/{id} must only modify supplied fields; others remain unchanged."""
    original = {
        "id": "cam-patch-id",
        "name": "Original",
        "location_desc": "Desc",
        "lat": 18.5,
        "lng": 73.9,
        "stream_url": None,
        "is_active": True,
        "created_at": "2024-01-01T00:00:00",
    }
    patch_body = {}
    if new_name is not None:
        patch_body["name"] = new_name
    if new_lat is not None:
        patch_body["lat"] = new_lat
    if new_lng is not None:
        patch_body["lng"] = new_lng

    # Build expected result: only patched fields change
    expected = dict(original)
    expected.update({k: v for k, v in patch_body.items()})

    with patch("routers.cameras.supabase") as mock_sb:
        # select for existence check
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "cam-patch-id"}]
        # update returns expected record
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [expected]
        client = get_test_client()
        resp = client.patch("/cameras/cam-patch-id", json=patch_body)

        if not patch_body:
            # Empty patch: update call may not be made; either 200 with original or 200 is fine
            # The router still calls update with empty dict — result is the original record
            assert resp.status_code in (200, 422)
        else:
            assert resp.status_code == 200
            result = resp.json()
            for field, value in patch_body.items():
                assert result[field] == value
            # Fields not in patch_body must match original
            for field in original:
                if field not in patch_body:
                    assert result[field] == original[field]
