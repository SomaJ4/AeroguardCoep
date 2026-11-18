"""
Emergency response orchestrator.

Called after a high-risk incident is confirmed. It:
1. Finds the nearest emergency services via Overpass/OSM.
2. Stores an emergency_notification record in Supabase.
3. Sends an SMS via Twilio.

Only triggers for HIGH risk_level incidents.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def handle_emergency_response(
    incident_id: str,
    incident_type: str,
    risk_level: str,
    lat: float,
    lng: float,
) -> list[dict]:
    """
    Full emergency response flow. Returns list of notification records created.
    Non-raising — logs errors and returns empty list on failure.
    """
    if risk_level != "high":
        return []

    from services.emergency_contacts import get_emergency_contacts
    from services.twilio_notify import send_emergency_sms
    from db.supabase import supabase

    try:
        contacts = await get_emergency_contacts(incident_type, lat, lng)
    except Exception as e:
        logger.exception("Failed to fetch emergency contacts: %s", e)
        return []

    if not contacts:
        logger.info("No OSM contacts found for '%s' — sending SMS with location only", incident_type)
        # Still send SMS with just the location info
        contacts = []

    # Send SMS (single message covering all contacts)
    sms_sent = await send_emergency_sms(
        incident_type=incident_type,
        risk_level=risk_level,
        lat=lat,
        lng=lng,
        contacts=contacts,
        incident_id=incident_id,
    )

    # Persist each contact as a notification record
    records = []
    for contact in contacts:
        try:
            row = supabase.table("emergency_notifications").insert({
                "incident_id":   incident_id,
                "amenity":       contact["amenity"],
                "facility_name": contact["name"],
                "facility_lat":  contact["lat"],
                "facility_lng":  contact["lng"],
                "distance_km":   contact["distance_km"],
                "phone":         contact.get("phone"),
                "sms_sent":      sms_sent,
            }).execute()
            records.append(row.data[0] if row.data else {})
        except Exception as e:
            logger.error("Failed to store emergency notification: %s", e)
    logger.info(
        "Emergency response for incident %s: %d contact(s), SMS=%s",
        incident_id, len(contacts), sms_sent,
    )
    return records
