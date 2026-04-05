"""
Advanced drone dispatch with:
- No-fly zone avoidance routing (geometry.py)
- Wind-adjusted ETA
- Battery sufficiency check
- Multi-incident priority dispatch
"""
import asyncio
import logging
from math import sqrt

from haversine import haversine, Unit

from services.geometry import compute_route

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Wind model (mock — easily swapped for a real weather API)
# ---------------------------------------------------------------------------
# Represents a 5 km/h northward wind component.
WIND_VECTOR = {"lat": 0.0, "lng": 5.0}


# ---------------------------------------------------------------------------
# Wind-adjusted speed
# ---------------------------------------------------------------------------

def effective_speed(drone_speed: float, start: tuple, end: tuple) -> float:
    """
    Adjust drone speed by projecting the wind vector onto the flight direction.

    start, end = (lat, lng) tuples.
    Returns speed in km/h, clamped to a minimum of 10 km/h.
    """
    dlat = end[0] - start[0]
    dlng = end[1] - start[1]
    magnitude = sqrt(dlat ** 2 + dlng ** 2)
    if magnitude < 1e-9:
        return drone_speed
    unit = (dlat / magnitude, dlng / magnitude)
    wind_component = unit[0] * WIND_VECTOR["lat"] + unit[1] * WIND_VECTOR["lng"]
    return max(10.0, drone_speed + wind_component)


# ---------------------------------------------------------------------------
# Battery sufficiency
# ---------------------------------------------------------------------------

def drone_can_complete(drone: dict, route_distance_km: float) -> bool:
    """
    True if the drone has enough battery to fly the route plus a 20% reserve
    for the return trip.

    Uses drone["full_range_km"] (default 20.0 if missing).
    """
    full_range = drone.get("full_range_km") or 20.0
    battery_consumed = (route_distance_km / full_range) * 100
    battery_needed = battery_consumed + 20  # 20% return reserve
    return drone["battery_pct"] >= battery_needed


# ---------------------------------------------------------------------------
# Drone selection
# ---------------------------------------------------------------------------

def select_drone(
    drones: list[dict],
    incident_lat: float,
    incident_lng: float,
    no_fly_zones: list[dict],
) -> dict | None:
    """
    Pick the best available drone for an incident.

    For each available drone:
      1. Compute collision-free route via geometry.compute_route.
      2. Check battery sufficiency.
      3. Compute wind-adjusted ETA.

    Returns the drone with the lowest ETA (tiebreaker: highest battery).
    Stores _computed_eta, _computed_route, _computed_distance on the dict.
    Returns None if no drone can complete the mission.
    """
    eligible = [d for d in drones if d["status"] == "available"]
    end = (incident_lat, incident_lng)

    candidates = []
    for drone in eligible:
        start = (drone["lat"], drone["lng"])
        route_waypoints, distance_km = compute_route(start, end, no_fly_zones)

        if not drone_can_complete(drone, distance_km):
            logger.debug("Drone %s skipped — insufficient battery for %.2f km", drone["id"], distance_km)
            continue

        speed = effective_speed(drone["speed_kmh"], start, end)
        eta_seconds = (distance_km / speed) * 3600

        drone["_computed_eta"] = eta_seconds
        drone["_computed_route"] = route_waypoints
        drone["_computed_distance"] = distance_km
        candidates.append(drone)

    if not candidates:
        return None

    return min(candidates, key=lambda d: (d["_computed_eta"], -d["battery_pct"]))


# ---------------------------------------------------------------------------
# Single dispatch
# ---------------------------------------------------------------------------

async def dispatch_drone(incident_id: str, drone_id: str | None = None) -> dict:
    """
    Dispatch a drone to an incident.

    If drone_id is provided, use that specific drone (manual override).
    Otherwise, auto-select the best drone via select_drone().

    Returns dispatch log details including the computed route GeoJSON.
    """
    from db.supabase import supabase
    from services.simulation import simulate_drone_to_incident
    from services.rerouting import reset_cancel_flag

    # Fetch active no-fly zones
    nfz_resp = supabase.table("no_fly_zones").select("*").eq("is_active", True).execute()
    no_fly_zones: list[dict] = nfz_resp.data or []

    # Fetch incident
    incident_resp = (
        supabase.table("incidents").select("lat, lng").eq("id", incident_id).single().execute()
    )
    incident = incident_resp.data
    incident_lat, incident_lng = incident["lat"], incident["lng"]
    end = (incident_lat, incident_lng)

    if drone_id is not None:
        # Manual override — validate and compute route for this drone
        drone_resp = (
            supabase.table("drones").select("*").eq("id", drone_id).single().execute()
        )
        drone = drone_resp.data
        if drone is None or drone["status"] != "available":
            raise ValueError("Specified drone is not available")

        start = (drone["lat"], drone["lng"])
        route_waypoints, distance_km = compute_route(start, end, no_fly_zones)

        if not drone_can_complete(drone, distance_km):
            raise ValueError(
                f"Drone {drone['name']} has insufficient battery for {distance_km:.2f} km route"
            )

        speed = effective_speed(drone["speed_kmh"], start, end)
        eta_seconds = round((distance_km / speed) * 3600)
    else:
        # Auto-select
        drones_resp = supabase.table("drones").select("*").execute()
        drone = select_drone(drones_resp.data or [], incident_lat, incident_lng, no_fly_zones)

        if drone is None:
            raise ValueError("No available drone can reach this incident")

        route_waypoints = drone["_computed_route"]
        eta_seconds = round(drone["_computed_eta"])

    # Build GeoJSON LineString from waypoints
    route_geojson = {
        "type": "LineString",
        "coordinates": [[lng, lat] for lat, lng in route_waypoints],
    }

    # Update drone status
    supabase.table("drones").update({"status": "en_route"}).eq("id", drone["id"]).execute()

    # Insert dispatch log
    log_resp = (
        supabase.table("dispatch_logs")
        .insert({
            "incident_id": incident_id,
            "drone_id": drone["id"],
            "eta_seconds": eta_seconds,
            "route_geojson": route_geojson,
        })
        .execute()
    )
    log = log_resp.data[0]

    # Register a fresh cancellation flag for this drone's simulation
    cancel_flag = reset_cancel_flag(drone["id"])

    # Launch waypoint-following simulation
    asyncio.create_task(
        simulate_drone_to_incident(
            drone["id"],
            incident_id,
            incident_lat,
            incident_lng,
            drone.get("speed_kmh", 60.0),
            route_waypoints,
            cancel_flag=cancel_flag,
        )
    )

    logger.info(
        "Dispatched drone %s to incident %s — ETA %ds, route %d waypoints",
        drone["id"], incident_id, eta_seconds, len(route_waypoints),
    )

    return {
        "dispatch_log_id": log["id"],
        "drone_id": drone["id"],
        "incident_id": incident_id,
        "eta_seconds": eta_seconds,
        "route_geojson": route_geojson,
    }


# ---------------------------------------------------------------------------
# Multi-incident dispatch
# ---------------------------------------------------------------------------

async def dispatch_multiple(incidents: list[dict]) -> list[dict]:
    """
    Dispatch drones to multiple incidents in priority order (highest risk first).

    Each drone is assigned at most once. Incidents that cannot be served
    are returned with status "pending".
    """
    from db.supabase import supabase

    # Sort by risk_score descending
    sorted_incidents = sorted(incidents, key=lambda i: i.get("risk_score", 0), reverse=True)

    nfz_resp = supabase.table("no_fly_zones").select("*").eq("is_active", True).execute()
    no_fly_zones: list[dict] = nfz_resp.data or []

    drones_resp = supabase.table("drones").select("*").execute()
    all_drones: list[dict] = drones_resp.data or []

    dispatched_ids: set[str] = set()
    results: list[dict] = []

    for inc in sorted_incidents:
        available = [d for d in all_drones if d["status"] == "available" and d["id"] not in dispatched_ids]
        drone = select_drone(available, inc["lat"], inc["lng"], no_fly_zones)

        if drone:
            try:
                result = await dispatch_drone(inc["id"], drone["id"])
                dispatched_ids.add(drone["id"])
                results.append({**result, "status": "dispatched"})
            except Exception as e:
                results.append({"incident_id": inc["id"], "status": "pending", "reason": str(e)})
        else:
            results.append({
                "incident_id": inc["id"],
                "status": "pending",
                "reason": "no available drone",
            })

    return results
