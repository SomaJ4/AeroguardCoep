"""
Twilio SMS notification service.

Sends an SMS alert to a configured number when a high-risk incident
requires emergency services.

Required env vars:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_FROM_NUMBER   — your Twilio phone number (E.164, e.g. +1234567890)
  EMERGENCY_TO_NUMBER  — recipient number (E.164)
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def send_emergency_sms(
    incident_type: str,
    risk_level: str,
    lat: float,
    lng: float,
    contacts: list[dict],
    incident_id: str,
) -> bool:
    """
    Send an SMS alert via Twilio.
    Returns True on success, False on failure (non-raising).
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    to_number   = os.environ.get("EMERGENCY_TO_NUMBER", "")

    if not all([account_sid, auth_token, from_number, to_number]):
        logger.warning("Twilio credentials not configured — SMS skipped")
        return False

    contact_lines = []
    for c in contacts:
        line = f"  • {c['amenity'].upper()}: {c['name']} ({c['distance_km']} km away)"
        if c.get("phone"):
            line += f" — {c['phone']}"
        contact_lines.append(line)

    body = (
        f"[AEROGUARD ALERT] HIGH-RISK INCIDENT DETECTED\n"
        f"Type: {incident_type.upper().replace('_', ' ')}\n"
        f"Risk: {risk_level.upper()}\n"
        f"Location: {lat:.4f}°N, {lng:.4f}°E\n"
        f"ID: {incident_id[:8]}\n"
        f"\nNEAREST EMERGENCY SERVICES:\n"
        + "\n".join(contact_lines or ["  No nearby services found"])
    )

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                data={
                    "From": f"whatsapp:{from_number}",
                    "To":   f"whatsapp:{to_number}",
                    "Body": body,
                },
                auth=(account_sid, auth_token),
            )
            if resp.status_code in (200, 201):
                logger.info("Emergency SMS sent for incident %s", incident_id)
                return True
            else:
                logger.error("Twilio error %s: %s", resp.status_code, resp.text[:500])
                return False
    except Exception as e:
        logger.exception("Failed to send emergency SMS: %s", e)
        return False
