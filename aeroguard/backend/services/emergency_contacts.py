"""
Emergency contacts service.

Uses the Overpass API (OpenStreetMap) to find the nearest hospital
and/or police station to a given coordinate.

Incident type → required services mapping:
  vehicle_collision / accident → hospital + police
  fire                         → hospital (fire brigade via police)
  theft / intrusion            → police
  crowd_gathering              → police
  animal                       → police
  patrol / normal / unknown    → (no emergency contact)
"""
import logging
from math import radians, sin, cos, sqrt, atan2

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Incident type → which services to contact
INCIDENT_SERVICES: dict[str, list[str]] = {
    "vehicle_collision": ["hospital", "police"],
    "accident":          ["hospital", "police"],
    "fire":              ["hospital", "police"],
    "theft":             ["police"],
    "intrusion":         ["police"],
    "crowd_gathering":   ["police"],
    "animal":            ["police"],
    "patrol":            [],
    "normal":            [],
    "unknown_anomaly":   [],
}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    φ1, φ2 = radians(lat1), radians(lat2)
    dφ = radians(lat2 - lat1)
    dλ = radians(lng2 - lng1)
    a = sin(dφ / 2) ** 2 + cos(φ1) * cos(φ2) * sin(dλ / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


async def _query_overpass(lat: float, lng: float, amenity: str, radius_m: int = 10000) -> list[dict]:
    """Return list of OSM nodes for a given amenity near (lat, lng)."""
    query = f"""
[out:json][timeout:10];
(
  node["amenity"="{amenity}"](around:{radius_m},{lat},{lng});
  way["amenity"="{amenity}"](around:{radius_m},{lat},{lng});
);
out center 5;
"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                OVERPASS_URL,
                content=f"data={query}".encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
    except Exception as e:
        logger.warning("Overpass query failed for %s: %s", amenity, e)
        return []

    results = []
    for el in elements:
        node_lat = el.get("lat") or el.get("center", {}).get("lat")
        node_lng = el.get("lon") or el.get("center", {}).get("lon")
        if node_lat is None or node_lng is None:
            continue
        tags = el.get("tags", {})
        dist = _haversine_km(lat, lng, node_lat, node_lng)
        results.append({
            "name": tags.get("name") or tags.get("name:en") or f"Unnamed {amenity}",
            "amenity": amenity,
            "lat": node_lat,
            "lng": node_lng,
            "distance_km": round(dist, 3),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "address": tags.get("addr:full")
                       or f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip()
                       or None,
        })

    results.sort(key=lambda x: x["distance_km"])
    return results


async def get_emergency_contacts(
    incident_type: str,
    lat: float,
    lng: float,
) -> list[dict]:
    """
    Return the nearest emergency contact(s) for a given incident type.
    Each contact dict has: name, amenity, lat, lng, distance_km, phone, address.
    """
    services = INCIDENT_SERVICES.get(incident_type, [])
    if not services:
        return []

    import asyncio
    amenity_map = {"hospital": "hospital", "police": "police"}

    tasks = [_query_overpass(lat, lng, amenity_map[s]) for s in services]
    results_per_service = await asyncio.gather(*tasks)

    contacts = []
    for service, results in zip(services, results_per_service):
        if results:
            contacts.append(results[0])  # nearest only
        else:
            logger.warning("No %s found within 5km of %.4f, %.4f", service, lat, lng)

    return contacts
