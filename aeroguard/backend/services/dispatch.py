from haversine import haversine, Unit


def select_drone(drones: list[dict], incident_lat: float, incident_lng: float) -> dict | None:
    """
    Select the best available drone for an incident.

    Eligibility: status == "available" AND battery_pct > 30
    Score: haversine_km + (100 - battery_pct) * 0.01 + (0.5 if crosses_no_fly_zone else 0)
    Tie-break: higher battery_pct wins (lower score wins overall).
    Returns None if no eligible drones.
    """
    eligible = [
        d for d in drones
        if d["status"] == "available" and d["battery_pct"] > 30
    ]
    if not eligible:
        return None

    def score(drone: dict) -> tuple[float, float]:
        dist_km = haversine(
            (drone["lat"], drone["lng"]),
            (incident_lat, incident_lng),
            unit=Unit.KILOMETERS,
        )
        crosses_no_fly_zone = False  # not implemented yet
        s = dist_km + (100 - drone["battery_pct"]) * 0.01 + (0.5 if crosses_no_fly_zone else 0)
        # tie-break: negate battery so higher battery wins
        return (s, -drone["battery_pct"])

    return min(eligible, key=score)


def compute_eta(distance_km: float, speed_kmh: float) -> int:
    """Return ETA in seconds: round((distance_km / speed_kmh) * 3600)."""
    return round((distance_km / speed_kmh) * 3600)


async def dispatch_drone(incident_id: str, drone_id: str | None = None) -> dict:
    """
    Orchestrate drone dispatch for an incident.

    - If drone_id provided, validate it is available with battery > 30.
    - Otherwise select the best drone via select_drone().
    - Raises ValueError if no eligible drone found.
    - Updates drone status to "en_route" in Supabase.
    - Inserts a dispatch_logs record.
    - Launches simulation background task.
    - Returns dispatch details dict.
    """
    import asyncio
    from db.supabase import supabase

    if drone_id is not None:
        drone_resp = (
            supabase.table("drones")
            .select("*")
            .eq("id", drone_id)
            .single()
            .execute()
        )
        drone = drone_resp.data
        if drone is None or drone["status"] != "available" or drone["battery_pct"] <= 30:
            raise ValueError("No available drones with sufficient battery")
    else:
        # Fetch incident coords first for proper drone selection
        incident_resp = (
            supabase.table("incidents")
            .select("lat, lng")
            .eq("id", incident_id)
            .single()
            .execute()
        )
        incident = incident_resp.data
        drones_resp = supabase.table("drones").select("*").execute()
        drone = select_drone(drones_resp.data or [], incident["lat"], incident["lng"])
        if drone is None:
            raise ValueError("No available drones with sufficient battery")

    # Fetch incident coords
    incident_resp = (
        supabase.table("incidents")
        .select("lat, lng")
        .eq("id", incident_id)
        .single()
        .execute()
    )
    incident = incident_resp.data

    distance_km = haversine(
        (drone["lat"], drone["lng"]),
        (incident["lat"], incident["lng"]),
        unit=Unit.KILOMETERS,
    )
    eta_seconds = compute_eta(distance_km, drone.get("speed_kmh", 60.0))

    # Update drone status
    supabase.table("drones").update({"status": "en_route"}).eq("id", drone["id"]).execute()

    # Insert dispatch log
    log_resp = (
        supabase.table("dispatch_logs")
        .insert({
            "incident_id": incident_id,
            "drone_id": drone["id"],
            "eta_seconds": eta_seconds,
            "route_geojson": None,
        })
        .execute()
    )
    log = log_resp.data[0]

    # Launch simulation as a fire-and-forget asyncio task
    from services.simulation import simulate_drone_to_incident
    asyncio.create_task(simulate_drone_to_incident(
        drone["id"],
        incident_id,
        incident["lat"],
        incident["lng"],
        drone.get("speed_kmh", 60.0),
    ))

    return {
        "dispatch_log_id": log["id"],
        "drone_id": drone["id"],
        "incident_id": incident_id,
        "eta_seconds": eta_seconds,
        "route_geojson": None,
    }
