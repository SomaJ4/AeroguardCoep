from fastapi import APIRouter, HTTPException, BackgroundTasks
from db.supabase import supabase
from models.schemas import IncidentCreate, IncidentOut, StatusUpdate
from services.risk import classify_risk
from services.dispatch import dispatch_drone

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def get_incidents():
    resp = supabase.table("incidents").select("*").order("created_at", desc=True).execute()
    return resp.data


@router.post("", response_model=IncidentOut, status_code=201)
async def create_incident(body: IncidentCreate, background_tasks: BackgroundTasks):
    risk_level = classify_risk(body.risk_score)
    data = body.model_dump()
    data["risk_level"] = risk_level
    resp = supabase.table("incidents").insert(data).execute()
    incident = resp.data[0]
    if risk_level == "high":
        background_tasks.add_task(dispatch_drone, incident["id"])
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentOut)
async def update_incident_status(incident_id: str, body: StatusUpdate, background_tasks: BackgroundTasks):
    existing = supabase.table("incidents").select("*").eq("id", incident_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    resp = supabase.table("incidents").update({"status": body.status}).eq("id", incident_id).execute()
    incident = resp.data[0]
    if body.status == "resolved":
        # Find the active dispatch log for this incident and trigger drone return
        log_resp = (
            supabase.table("dispatch_logs")
            .select("drone_id, drones(home_lat, home_lng, speed_kmh)")
            .eq("incident_id", incident_id)
            .order("dispatched_at", desc=True)
            .limit(1)
            .execute()
        )
        if log_resp.data:
            log = log_resp.data[0]
            drone = log.get("drones") or {}
            from services.simulation import simulate_drone_return
            background_tasks.add_task(
                simulate_drone_return,
                log["drone_id"],
                drone.get("home_lat", 0),
                drone.get("home_lng", 0),
                drone.get("speed_kmh", 60.0),
            )
    return incident
