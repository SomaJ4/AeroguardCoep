# Feature: aeroguard-platform, Property 11: Simulation Convergence — Drone Reaches Incident
# Feature: aeroguard-platform, Property 12: Simulation Convergence — Drone Returns Home

from hypothesis import given, settings
from hypothesis import strategies as st
from haversine import haversine, Unit
from services.simulation import move_toward

ARRIVAL_THRESHOLD_KM = 0.05


@given(
    st.floats(min_value=18.4, max_value=18.6),
    st.floats(min_value=73.8, max_value=74.0),
    st.floats(min_value=18.4, max_value=18.6),
    st.floats(min_value=73.8, max_value=74.0),
    st.floats(min_value=0.01, max_value=0.1),
)
@settings(max_examples=20)
def test_simulation_converges_to_incident(start_lat, start_lng, target_lat, target_lng, step_km):
    """Property 11: After enough steps, drone reaches within 0.05 km of target."""
    lat, lng = start_lat, start_lng
    max_steps = 10000
    for _ in range(max_steps):
        dist = haversine((lat, lng), (target_lat, target_lng), unit=Unit.KILOMETERS)
        if dist <= ARRIVAL_THRESHOLD_KM:
            break
        lat, lng = move_toward(lat, lng, target_lat, target_lng, step_km)
    dist = haversine((lat, lng), (target_lat, target_lng), unit=Unit.KILOMETERS)
    assert dist <= ARRIVAL_THRESHOLD_KM


@given(
    st.floats(min_value=18.4, max_value=18.6),
    st.floats(min_value=73.8, max_value=74.0),
    st.floats(min_value=18.4, max_value=18.6),
    st.floats(min_value=73.8, max_value=74.0),
    st.floats(min_value=0.01, max_value=0.1),
)
@settings(max_examples=20)
def test_simulation_returns_home(start_lat, start_lng, home_lat, home_lng, step_km):
    """Property 12: After enough steps, drone returns within 0.05 km of home."""
    lat, lng = start_lat, start_lng
    max_steps = 10000
    for _ in range(max_steps):
        dist = haversine((lat, lng), (home_lat, home_lng), unit=Unit.KILOMETERS)
        if dist <= ARRIVAL_THRESHOLD_KM:
            break
        lat, lng = move_toward(lat, lng, home_lat, home_lng, step_km)
    dist = haversine((lat, lng), (home_lat, home_lng), unit=Unit.KILOMETERS)
    assert dist <= ARRIVAL_THRESHOLD_KM
