from fastapi import APIRouter, HTTPException
from db.supabase import supabase
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: str
    incident_id: str
    risk_level: str
    message: str
    acknowledged: bool
    created_at: datetime | None = None


@router.get("", response_model=list[AlertOut])
def get_alerts():
    """Return all unacknowledged alerts, newest first."""
    resp = (
        supabase.table("alerts")
        .select("*")
        .eq("acknowledged", False)
        .execute()
    )
    return resp.data


@router.get("/all", response_model=list[AlertOut])
def get_all_alerts():
    """Return all alerts including acknowledged ones."""
    resp = supabase.table("alerts").select("*").execute()
    return resp.data


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: str):
    """Mark an alert as acknowledged."""
    existing = supabase.table("alerts").select("id").eq("id", alert_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    resp = (
        supabase.table("alerts")
        .update({"acknowledged": True})
        .eq("id", alert_id)
        .execute()
    )
    return resp.data[0]
