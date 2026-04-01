from fastapi import APIRouter, HTTPException
from db.supabase import supabase
from models.schemas import DroneOut, DispatchRequest, DispatchOut, StatusUpdate
from services.dispatch import dispatch_drone

router = APIRouter(prefix="/drones", tags=["drones"])


@router.get("", response_model=list[DroneOut])
def get_drones():
    resp = supabase.table("drones").select("*").execute()
    return resp.data


@router.post("/dispatch", response_model=DispatchOut)
async def dispatch(body: DispatchRequest):
    try:
        result = await dispatch_drone(body.incident_id, body.drone_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return result


@router.patch("/{drone_id}/status", response_model=DroneOut)
def update_drone_status(drone_id: str, body: StatusUpdate):
    existing = supabase.table("drones").select("id").eq("id", drone_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Drone not found")
    resp = supabase.table("drones").update({"status": body.status}).eq("id", drone_id).execute()
    return resp.data[0]
