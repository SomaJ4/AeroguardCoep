"""
Rerouting engine.

Decision flow (runs after every severity update or new incident):

1. Find all en_route drones (dispatch_logs with arrived_at IS NULL).
2. For each en_route drone D assigned to incident A:
   a. Get current severity_A (with trend).
   b. Find all open unassigned incidents B (no active dispatch log).
   c. For each B where severity_B > severity_A + REROUTE_THRESHOLD
      AND severity_B.trend >= 0 (not already stabilising):
        i.  Check if any AVAILABLE drone can reach B with ETA ≤ D's ETA
            from its current position → if yes, dispatch that drone, skip reroute.
        ii. Otherwise execute reroute:
            - Stop D's simulation (via cancellation registry).
            - Mark old dispatch_log as abandoned.
            - Set incident A → 'abandoned'; try to find another drone for A.
            - Dispatch D from its CURRENT position to B.
3. Enforce 60-second cooldown per drone to prevent thrashing.
"""
import asyncio
import logging
from datetime import datetime, timezone

from haversine import haversine, Unit

from services.severity import REROUTE_THRESHOLD
from services.geometry import compute_route
from services.dispatch import effective_speed, drone_can_complete

logger = logging.getLogger(__name__)

# drone_id → datetime of last reroute (cooldown guard)
_last_rerouted: dict[str, datetime] = {}
REROUTE_COOLDOWN_SECS = 60

# drone_id → asyncio.Event  (set = stop current simulation)
_cancel_flags: dict[str, asyncio.Event] = {}


def get_cancel_flag(drone_id: str) -> asyncio.Event:
    if drone_id not in _cancel_flags:
        _cancel_flags[drone_id] = asyncio.Event()
    return _cancel_flags[drone_id]


def reset_cancel_flag(drone_id: str) -> asyncio.Event:
    """Clear old flag and return a fresh one."""
    flag = asyncio.Event()
    _cancel_flags[drone_id] = flag
    return flag


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def check_rerouting(trigger_incident_id: str | None = None) -> list[dict]:
    """
    Run the full rerouting check. Call after any severity update or new incident.
    Returns a list of rerouting actions taken (for logging/audit).
    """
    from db.supabase import supabase

    actions: list[dict] = []

    # --- Fetch en_route dispatch logs (not yet arrived) ---
    active_logs_resp = (
        supabase.table("dispatch_logs")
        .select("id, drone_id, incident_id")
        .is_("arrived_at", "null")
        .execute()
    )
    active_logs: list[dict] = active_logs_resp.data or []
    if not active_logs:
        return actions

    assigned_incident_ids = {log["incident_id"] for log in active_logs}

    # --- Fetch all open unassigned incidents ---
    open_resp = (
        supabase.table("incidents")
        .select("id, incident_type, risk_score, human_crowd, severity, severity_trend, lat, lng, created_at")
        .eq("status", "open")
        .execute()
    )
    open_incidents: list[dict] = open_resp.data or []
    # Only consider incidents with no active dispatch
    unassigned = [i for i in open_incidents if i["id"] not in assigned_incident_ids]
    if not unassigned:
        return actions

    # --- Fetch available drones ---
    avail_resp = supabase.table("drones").select("*").eq("status", "available").execute()
    available_drones: list[dict] = avail_resp.data or []

    # --- No-fly zones ---
    nfz_resp = supabase.table("no_fly_zones").select("*").eq("is_active", True).execute()
    no_fly_zones: list[dict] = nfz_resp.data or []

    for log in active_logs:
        drone_id = log["drone_id"]
        incident_a_id = log["incident_id"]

        # Cooldown check
        last = _last_rerouted.get(drone_id)
        if last:
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < REROUTE_COOLDOWN_SECS:
                continue

        # Fetch drone current position
        drone_resp = supabase.table("drones").select("*").eq("id", drone_id).single().execute()
        drone = drone_resp.data
        if not drone or drone["status"] != "en_route":
            continue

        # Fetch incident A severity
        inc_a_resp = (
            supabase.table("incidents")
            .select("severity, severity_trend")
            .eq("id", incident_a_id)
            .single()
            .execute()
        )
        inc_a = inc_a_resp.data or {}
        severity_a = float(inc_a.get("severity") or 0.0)

        drone_pos = (drone["lat"], drone["lng"])

        # Find best candidate B
        best_b = None
        best_b_eta = float("inf")

        for inc_b in unassigned:
            severity_b = float(inc_b.get("severity") or 0.0)
            trend_b = float(inc_b.get("severity_trend") or 0.0)

            # Must exceed threshold and not be stabilising
            if severity_b <= severity_a + REROUTE_THRESHOLD:
                continue
            if trend_b < -0.0001:  # actively decreasing — skip
                continue

            b_pos = (inc_b["lat"], inc_b["lng"])

            # ETA from drone's current position to B
            _, dist_d_to_b = compute_route(drone_pos, b_pos, no_fly_zones)
            speed = effective_speed(drone["speed_kmh"], drone_pos, b_pos)
            eta_d_to_b = (dist_d_to_b / speed) * 3600

            # Check if any available drone beats this ETA
            better_exists = False
            for avail in available_drones:
                avail_pos = (avail["lat"], avail["lng"])
                _, dist_avail = compute_route(avail_pos, b_pos, no_fly_zones)
                if not drone_can_complete(avail, dist_avail):
                    continue
                spd = effective_speed(avail["speed_kmh"], avail_pos, b_pos)
                eta_avail = (dist_avail / spd) * 3600
                if eta_avail <= eta_d_to_b:
                    better_exists = True
                    # Dispatch available drone to B directly
                    try:
                        from services.dispatch import dispatch_drone
                        await dispatch_drone(inc_b["id"], avail["id"])
                        logger.info(
                            "Available drone %s dispatched to %s (better ETA than reroute)",
                            avail["id"], inc_b["id"],
                        )
                        actions.append({
                            "action": "dispatch_available",
                            "drone_id": avail["id"],
                            "incident_id": inc_b["id"],
                        })
                    except Exception as e:
                        logger.warning("Failed to dispatch available drone: %s", e)
                    break

            if better_exists:
                continue

            # This B is a valid reroute candidate — pick highest severity
            if severity_b > best_b_eta or best_b is None:
                best_b = inc_b
                best_b_eta = eta_d_to_b

        if best_b is None:
            continue

        # --- Execute reroute ---
        action = await _execute_reroute(
            drone=drone,
            log_id=log["id"],
            incident_a_id=incident_a_id,
            incident_b=best_b,
            no_fly_zones=no_fly_zones,
            available_drones=available_drones,
        )
        if action:
            actions.append(action)
            _last_rerouted[drone_id] = datetime.now(timezone.utc)

    return actions


# ---------------------------------------------------------------------------
# Execute a single reroute
# ---------------------------------------------------------------------------

async def _execute_reroute(
    drone: dict,
    log_id: str,
    incident_a_id: str,
    incident_b: dict,
    no_fly_zones: list[dict],
    available_drones: list[dict],
) -> dict | None:
    from db.supabase import supabase
    from services.dispatch import dispatch_drone
    from services.simulation import simulate_drone_to_incident

    drone_id = drone["id"]
    incident_b_id = incident_b["id"]

    logger.info(
        "REROUTING drone %s from incident %s → %s",
        drone_id, incident_a_id, incident_b_id,
    )

    try:
        # 1. Signal simulation to stop
        get_cancel_flag(drone_id).set()

        # 2. Mark old dispatch log as abandoned
        supabase.table("dispatch_logs").update({
            "abandoned_incident_id": incident_a_id,
        }).eq("id", log_id).execute()

        # 3. Set incident A → abandoned
        supabase.table("incidents").update({"status": "abandoned"}).eq("id", incident_a_id).execute()

        # 4. Try to find another drone for A
        for avail in available_drones:
            if avail["id"] == drone_id:
                continue
            try:
                await dispatch_drone(incident_a_id, avail["id"])
                logger.info("Replacement drone %s dispatched to abandoned incident %s", avail["id"], incident_a_id)
                break
            except Exception:
                pass
        else:
            # No replacement — create alert
            supabase.table("alerts").insert({
                "incident_id": incident_a_id,
                "risk_level": "high",
                "message": f"Incident abandoned — drone rerouted to higher-priority incident {incident_b_id}. Manual dispatch required.",
            }).execute()

        # 5. Compute new route from drone's CURRENT position to B
        drone_pos = (drone["lat"], drone["lng"])
        b_pos = (incident_b["lat"], incident_b["lng"])
        route_waypoints, distance_km = compute_route(drone_pos, b_pos, no_fly_zones)
        speed = effective_speed(drone["speed_kmh"], drone_pos, b_pos)
        eta_seconds = round((distance_km / speed) * 3600)

        route_geojson = {
            "type": "LineString",
            "coordinates": [[lng, lat] for lat, lng in route_waypoints],
        }

        # 6. Insert new dispatch log
        new_log_resp = supabase.table("dispatch_logs").insert({
            "incident_id": incident_b_id,
            "drone_id": drone_id,
            "eta_seconds": eta_seconds,
            "route_geojson": route_geojson,
            "rerouted_from_incident_id": incident_a_id,
        }).execute()
        new_log = new_log_resp.data[0]

        # 7. Reset cancel flag and launch new simulation
        new_flag = reset_cancel_flag(drone_id)
        asyncio.create_task(
            simulate_drone_to_incident(
                drone_id,
                incident_b_id,
                incident_b["lat"],
                incident_b["lng"],
                drone.get("speed_kmh", 60.0),
                route_waypoints,
                cancel_flag=new_flag,
            )
        )

        logger.info(
            "Reroute complete: drone %s → incident %s, ETA %ds",
            drone_id, incident_b_id, eta_seconds,
        )

        return {
            "action": "rerouted",
            "drone_id": drone_id,
            "from_incident": incident_a_id,
            "to_incident": incident_b_id,
            "new_log_id": new_log["id"],
            "eta_seconds": eta_seconds,
        }

    except Exception:
        logger.exception("Reroute failed for drone %s", drone_id)
        return None
