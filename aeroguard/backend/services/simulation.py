"""
Drone movement simulation.

simulate_drone_to_incident now follows a list of waypoints rather than
flying in a straight line, so the drone respects no-fly zone detours.
"""
import asyncio
import logging

from haversine import haversine, Unit

logger = logging.getLogger(__name__)


def move_toward(
    current_lat: float,
    current_lng: float,
    target_lat: float,
    target_lng: float,
    step_km: float,
) -> tuple[float, float]:
    """
    Move current position toward target by step_km.
    Returns target coords directly if already within step_km.
    """
    dist = haversine((current_lat, current_lng), (target_lat, target_lng), unit=Unit.KILOMETERS)
    if dist <= step_km:
        return (target_lat, target_lng)
    ratio = step_km / dist
    new_lat = current_lat + ratio * (target_lat - current_lat)
    new_lng = current_lng + ratio * (target_lng - current_lng)
    return (new_lat, new_lng)


async def simulate_drone_to_incident(
    drone_id: str,
    incident_id: str,
    target_lat: float,
    target_lng: float,
    speed_kmh: float = 60.0,
    waypoints: list[tuple] | None = None,
) -> None:
    """
    Background task: moves drone through each waypoint toward the incident.

    If waypoints is provided, the drone follows them in order (respecting
    no-fly zone detours). Otherwise falls back to straight-line movement.

    Updates drone lat/lng in Supabase every 2 seconds.
    Supabase Realtime pushes position updates to the dashboard automatically.
    Sets drone status to 'on_scene' and writes arrived_at when within 0.05 km
    of the final destination.
    """
    from db.supabase import supabase

    step_km = speed_kmh * (2 / 3600)  # distance covered per 2-second tick

    # Build the list of targets to visit in order
    if waypoints and len(waypoints) > 1:
        # waypoints[0] is the drone's start position — skip it
        targets = list(waypoints[1:])
    else:
        targets = [(target_lat, target_lng)]

    # Ensure the final target is exactly the incident location
    if targets[-1] != (target_lat, target_lng):
        targets.append((target_lat, target_lng))

    for wp_lat, wp_lng in targets:
        # Move toward this waypoint until we reach it
        while True:
            try:
                await asyncio.sleep(2)

                drone_resp = (
                    supabase.table("drones")
                    .select("lat, lng")
                    .eq("id", drone_id)
                    .single()
                    .execute()
                )
                drone = drone_resp.data
                lat, lng = drone["lat"], drone["lng"]

                lat, lng = move_toward(lat, lng, wp_lat, wp_lng, step_km)
                supabase.table("drones").update({"lat": lat, "lng": lng}).eq("id", drone_id).execute()

                dist = haversine((lat, lng), (wp_lat, wp_lng), unit=Unit.KILOMETERS)
                if dist <= 0.05:
                    break  # reached this waypoint, move to next

            except Exception:
                logger.exception(
                    "Error in simulate_drone_to_incident (drone=%s, incident=%s)",
                    drone_id, incident_id,
                )

    # Arrived at incident
    try:
        supabase.table("drones").update({"status": "on_scene"}).eq("id", drone_id).execute()
        supabase.table("dispatch_logs").update({"arrived_at": "now()"}).eq(
            "drone_id", drone_id
        ).eq("incident_id", incident_id).execute()
        logger.info("Drone %s arrived at incident %s", drone_id, incident_id)
    except Exception:
        logger.exception("Error marking drone %s as on_scene", drone_id)


async def simulate_drone_return(
    drone_id: str,
    home_lat: float,
    home_lng: float,
    speed_kmh: float = 60.0,
) -> None:
    """
    Background task: moves drone back to home position every 2 seconds.
    Sets status to 'available' when within 0.05 km of home.
    """
    from db.supabase import supabase

    step_km = speed_kmh * (2 / 3600)

    while True:
        try:
            await asyncio.sleep(2)

            drone_resp = (
                supabase.table("drones")
                .select("lat, lng")
                .eq("id", drone_id)
                .single()
                .execute()
            )
            drone = drone_resp.data
            lat, lng = drone["lat"], drone["lng"]

            lat, lng = move_toward(lat, lng, home_lat, home_lng, step_km)
            supabase.table("drones").update({"lat": lat, "lng": lng}).eq("id", drone_id).execute()

            dist = haversine((lat, lng), (home_lat, home_lng), unit=Unit.KILOMETERS)
            if dist <= 0.05:
                supabase.table("drones").update({"status": "available"}).eq("id", drone_id).execute()
                break
        except Exception:
            logger.exception("Error in simulate_drone_return (drone=%s)", drone_id)
