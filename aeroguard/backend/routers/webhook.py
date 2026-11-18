from fastapi import APIRouter, HTTPException, Request
from db.supabase import supabase
from services.risk import classify_risk
from services.dispatch import dispatch_drone
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/incident-inserted")
async def incident_inserted(request: Request):
    """
    Supabase webhook endpoint — called when Vision Service inserts a new incident.
    Payload format: { "type": "INSERT", "record": { ...incident fields... } }
    """
    payload = await request.json()

    # Supabase sends { "type": "INSERT", "record": {...}, "old_record": null }
    if payload.get("type") != "INSERT":
        return {"status": "ignored", "reason": "not an INSERT event"}

    record = payload.get("record")
    if not record:
        raise HTTPException(status_code=400, detail="Missing record in payload")

    incident_id = record.get("id")
    risk_score = record.get("risk_score")

    if incident_id is None or risk_score is None:
        raise HTTPException(status_code=400, detail="Missing id or risk_score in record")

    # Skip if risk_level already set (avoid double-processing)
    if record.get("risk_level"):
        return {"status": "skipped", "reason": "risk_level already set"}

    # Classify and persist risk_level
    risk_level = classify_risk(float(risk_score))
    supabase.table("incidents").update({"risk_level": risk_level}).eq("id", incident_id).execute()

    logger.info("Webhook: incident %s classified as %s", incident_id, risk_level)

    if risk_level == "high":
        async def _dispatch_and_notify(inc_id: str, inc_type: str, lat: float, lng: float):
            try:
                await dispatch_drone(inc_id)
                logger.info("Webhook: auto-dispatch triggered for incident %s", inc_id)
            except Exception as e:
                logger.error("Webhook: dispatch failed for %s: %s", inc_id, e)
            try:
                from services.emergency_response import handle_emergency_response
                await handle_emergency_response(
                    incident_id=inc_id,
                    incident_type=inc_type,
                    risk_level="high",
                    lat=lat,
                    lng=lng,
                )
            except Exception as e:
                logger.error("Webhook: emergency response failed for %s: %s", inc_id, e)

        asyncio.create_task(_dispatch_and_notify(
            incident_id,
            record.get("incident_type", "unknown"),
            float(record.get("lat", 0)),
            float(record.get("lng", 0)),
        ))
    elif risk_level == "medium":
        # Push alert so dashboard can show manual dispatch prompt
        supabase.table("alerts").insert({
            "incident_id": incident_id,
            "risk_level": "medium",
            "message": f"Medium-risk incident detected. Manual drone dispatch required.",
        }).execute()
        logger.info("Webhook: medium-risk alert created for incident %s", incident_id)

    return {"status": "processed", "incident_id": incident_id, "risk_level": risk_level}
