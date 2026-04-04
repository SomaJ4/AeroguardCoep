"""
Seed no-fly zones from OpenStreetMap Overpass API for Pune.

Queries real polygon data for hospitals, stadiums, industrial areas,
universities, aerodromes, and military zones, then inserts them into
the no_fly_zones table in Supabase.

Usage:
    cd aeroguard/backend
    python scripts/seed_no_fly_zones.py
"""
import json
import sys
import os
import time
import requests

# Add backend root to path so db/supabase imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from db.supabase import supabase

# Pune bounding box: south, west, north, east
BBOX = "18.40,73.75,18.65,74.05"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# OSM tags to query → reason label
QUERIES = [
    ("amenity", "hospital",    "hospital"),
    ("amenity", "clinic",      "hospital"),
    ("leisure", "stadium",     "stadium"),
    ("leisure", "sports_centre", "stadium"),
    ("landuse", "industrial",  "industrial"),
    ("landuse", "military",    "military"),
    ("aeroway", "aerodrome",   "airport"),
    ("amenity", "university",  "university"),
    ("amenity", "college",     "university"),
]

def build_query(key: str, value: str) -> str:
    return f"""
[out:json][timeout:30];
(
  way["{key}"="{value}"]({BBOX});
  relation["{key}"="{value}"]({BBOX});
);
out body;
>;
out skel qt;
"""

def fetch_elements(key: str, value: str) -> list[dict]:
    query = build_query(key, value)
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=40)
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except Exception as e:
        print(f"  Warning: failed to fetch {key}={value}: {e}")
        return []

def extract_polygons(elements: list[dict]) -> list[tuple[str, list[dict]]]:
    """
    Extract (name, polygon) pairs from OSM elements.
    Builds node lookup then traces way geometry.
    """
    nodes = {e["id"]: e for e in elements if e["type"] == "node"}
    results = []

    for el in elements:
        if el["type"] != "way":
            continue
        nd_refs = el.get("nodes", [])
        if len(nd_refs) < 4:  # need at least a triangle + closing point
            continue

        coords = []
        for nid in nd_refs:
            node = nodes.get(nid)
            if node:
                coords.append({"lat": node["lat"], "lng": node["lon"]})

        if len(coords) < 4:
            continue

        name = el.get("tags", {}).get("name") or el.get("tags", {}).get("name:en") or ""
        results.append((name, coords))

    return results

def main():
    print("Fetching no-fly zone data from OpenStreetMap for Pune...")
    print(f"Bounding box: {BBOX}\n")

    zones_to_insert = []
    seen_names = set()

    for key, value, reason in QUERIES:
        print(f"Querying {key}={value} ({reason})...")
        elements = fetch_elements(key, value)
        polygons = extract_polygons(elements)
        print(f"  Found {len(polygons)} polygons")

        for name, polygon in polygons:
            # Skip duplicates by name+reason
            dedup_key = f"{name}_{reason}"
            if dedup_key in seen_names:
                continue
            seen_names.add(dedup_key)

            display_name = name if name else f"Unnamed {reason.title()}"
            zones_to_insert.append({
                "name": display_name,
                "reason": reason,
                "polygon": polygon,
                "is_active": True,
            })

        time.sleep(1)  # be polite to Overpass API

    if not zones_to_insert:
        print("\nNo zones found. Check your internet connection or try again.")
        sys.exit(1)

    print(f"\nInserting {len(zones_to_insert)} no-fly zones into Supabase...")

    # Clear existing zones first
    supabase.table("no_fly_zones").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("Cleared existing no-fly zones.")

    # Insert in batches of 50
    batch_size = 50
    inserted = 0
    for i in range(0, len(zones_to_insert), batch_size):
        batch = zones_to_insert[i:i + batch_size]
        supabase.table("no_fly_zones").insert(batch).execute()
        inserted += len(batch)
        print(f"  Inserted {inserted}/{len(zones_to_insert)}...")

    print(f"\nDone! {inserted} no-fly zones seeded for Pune.")
    print("Breakdown:")
    for reason in set(z["reason"] for z in zones_to_insert):
        count = sum(1 for z in zones_to_insert if z["reason"] == reason)
        print(f"  {reason}: {count}")

if __name__ == "__main__":
    main()
