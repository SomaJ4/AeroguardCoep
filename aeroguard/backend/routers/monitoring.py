from fastapi import APIRouter, HTTPException
from db.supabase import supabase
from models.schemas import MonitoringStart, MonitoringStop, MonitoringSessionOut

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.post("/start", response_model=MonitoringSessionOut, status_code=201)
def start_monitoring(body: MonitoringStart):
    camera = supabase.table("cameras").select("id").eq("id", body.camera_id).execute()
    if not camera.data:
        raise HTTPException(status_code=404, detail="Camera not found")
    resp = supabase.table("monitoring_sessions").insert({"camera_id": body.camera_id, "status": "active"}).execute()
    return resp.data[0]


@router.post("/stop", response_model=MonitoringSessionOut)
def stop_monitoring(body: MonitoringStop):
    existing = supabase.table("monitoring_sessions").select("id").eq("id", body.session_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Monitoring session not found")
    resp = (
        supabase.table("monitoring_sessions")
        .update({"status": "stopped", "ended_at": "now()"})
        .eq("id", body.session_id)
        .execute()
    )
    return resp.data[0]


@router.get("/sessions", response_model=list[MonitoringSessionOut])
def get_sessions():
    resp = supabase.table("monitoring_sessions").select("*").order("started_at", desc=True).execute()
    return resp.data
