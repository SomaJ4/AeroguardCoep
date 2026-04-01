# Feature: aeroguard-platform, Property 7: Drone Selection Filters Eligibility Correctly
# Feature: aeroguard-platform, Property 8: Drone Selection Score Minimization
# Feature: aeroguard-platform, Property 9: ETA Calculation Correctness

from hypothesis import given, settings
from hypothesis import strategies as st
from services.dispatch import select_drone, compute_eta


# Property 7
@given(st.lists(st.fixed_dictionaries({
    "id": st.uuids().map(str),
    "lat": st.floats(min_value=18.4, max_value=18.6),
    "lng": st.floats(min_value=73.8, max_value=74.0),
    "battery_pct": st.floats(min_value=0, max_value=100),
    "status": st.sampled_from(["available", "en_route", "on_scene", "charging"]),
    "speed_kmh": st.just(60.0),
}), min_size=0))
@settings(max_examples=20)
def test_dispatch_filters_eligible_drones(drones):
    """Validates: Requirements 5.1, 5.2"""
    result = select_drone(drones, 18.5074, 73.9286)
    if result is not None:
        assert result["status"] == "available"
        assert result["battery_pct"] > 30


# Property 8
@given(st.lists(st.fixed_dictionaries({
    "id": st.uuids().map(str),
    "lat": st.floats(min_value=18.4, max_value=18.6),
    "lng": st.floats(min_value=73.8, max_value=74.0),
    "battery_pct": st.floats(min_value=31, max_value=100),
    "status": st.just("available"),
    "speed_kmh": st.just(60.0),
}), min_size=1))
@settings(max_examples=20)
def test_dispatch_selects_lowest_score(drones):
    """Validates: Requirements 5.3"""
    from haversine import haversine, Unit
    result = select_drone(drones, 18.5074, 73.9286)
    assert result is not None
    result_score = (
        haversine((result["lat"], result["lng"]), (18.5074, 73.9286), unit=Unit.KILOMETERS)
        + (100 - result["battery_pct"]) * 0.01
    )
    for d in drones:
        d_score = (
            haversine((d["lat"], d["lng"]), (18.5074, 73.9286), unit=Unit.KILOMETERS)
            + (100 - d["battery_pct"]) * 0.01
        )
        assert result_score <= d_score + 1e-9


# Property 9
@given(
    st.floats(min_value=0.1, max_value=100.0),
    st.floats(min_value=1.0, max_value=200.0)
)
@settings(max_examples=20)
def test_eta_calculation(distance_km, speed_kmh):
    """Validates: Requirements 5.4"""
    result = compute_eta(distance_km, speed_kmh)
    expected = round((distance_km / speed_kmh) * 3600)
    assert result == expected
