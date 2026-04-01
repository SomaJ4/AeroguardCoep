import os
import httpx
import logging

logger = logging.getLogger(__name__)

ORS_BASE = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"


async def fetch_route(
    from_lat: float, from_lng: float,
    to_lat: float, to_lng: float,
) -> dict | None:
    """
    Fetch a route from ORS between two coordinates.
    Returns GeoJSON FeatureCollection or None on failure.
    """
    api_key = os.environ.get("ORS_API_KEY", "")
    if not api_key:
        logger.warning("ORS_API_KEY not set, skipping route fetch")
        return None

    body = {
        "coordinates": [
            [from_lng, from_lat],  # ORS uses [lng, lat]
            [to_lng, to_lat],
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                ORS_BASE,
                json=body,
                headers={"Authorization": api_key, "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("ORS returned %s: %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.exception("ORS route fetch failed, using straight line fallback")
    return None


def straight_line_geojson(
    from_lat: float, from_lng: float,
    to_lat: float, to_lng: float,
) -> dict:
    """Fallback: straight line between two points as GeoJSON."""
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [from_lng, from_lat],
                    [to_lng, to_lat],
                ]
            },
            "properties": {"fallback": True}
        }]
    }
