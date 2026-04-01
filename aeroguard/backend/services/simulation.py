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
    Move current position toward target by step_km using linear interpolation.
    If distance to target <= step_km, return target coords directly.
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
) -> None:
    """
    Background task: moves drone toward incident every 2 seconds.
    Sets status to 'on_scene' and writes arrived_at when within 0.05 km.
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

            lat, lng = move_toward(lat, lng, target_lat, target_lng, step_km)

            supabase.table("drones").update({"lat": lat, "lng": lng}).eq("id", drone_id).execute()

            dist = haversine((lat, lng), (target_lat, target_lng), unit=Unit.KILOMETERS)
            if dist <= 0.05:
                supabase.table("drones").update({"status": "on_scene"}).eq("id", drone_id).execute()

                # Write arrived_at to the dispatch_log for this drone+incident
                supabase.table("dispatch_logs").update({"arrived_at": "now()"}).eq(
                    "drone_id", drone_id
                ).eq("incident_id", incident_id).execute()

                break
        except Exception:
            logger.exception("Error in simulate_drone_to_incident (drone=%s, incident=%s)", drone_id, incident_id)


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
