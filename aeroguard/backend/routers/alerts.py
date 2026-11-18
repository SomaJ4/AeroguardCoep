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


class EmergencyTestRequest(BaseModel):
    incident_type: str = "vehicle_collision"
    lat: float = 18.5074
    lng: float = 73.9286


@router.post("/test-emergency")
async def test_emergency_response(body: EmergencyTestRequest):
    """
    Test endpoint — triggers emergency contact lookup + SMS for a fake high-risk incident.
    """
    import uuid
    import os
    from services.emergency_response import handle_emergency_response
    from services.emergency_contacts import get_emergency_contacts

    fake_id = str(uuid.uuid4())

    # Debug: check credentials are loaded
    creds = {
        "TWILIO_ACCOUNT_SID": bool(os.environ.get("TWILIO_ACCOUNT_SID")),
        "TWILIO_AUTH_TOKEN":  bool(os.environ.get("TWILIO_AUTH_TOKEN")),
        "TWILIO_FROM_NUMBER": os.environ.get("TWILIO_FROM_NUMBER", "NOT SET"),
        "EMERGENCY_TO_NUMBER": os.environ.get("EMERGENCY_TO_NUMBER", "NOT SET"),
    }

    # Debug: fetch contacts separately so we can return them
    contacts = await get_emergency_contacts(body.incident_type, body.lat, body.lng)

    # Test Twilio directly
    from services.twilio_notify import send_emergency_sms
    sms_result = await send_emergency_sms(
        incident_type=body.incident_type,
        risk_level="high",
        lat=body.lat,
        lng=body.lng,
        contacts=contacts,
        incident_id=fake_id,
    )

    return {
        "incident_id": fake_id,
        "credentials_present": creds,
        "contacts_found": contacts,
        "sms_sent": sms_result,
    }