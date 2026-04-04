"""
Geometry utilities for no-fly zone avoidance routing.

All coordinates are (lat, lng) tuples throughout this module.
"""
from math import sqrt
from haversine import haversine, Unit


# ---------------------------------------------------------------------------
# Primitive geometry
# ---------------------------------------------------------------------------

def direction(p1: tuple, p2: tuple, p3: tuple) -> float:
    """
    Cross product of vectors p1→p2 and p1→p3.
    Positive = p3 is to the left of p1→p2.
    Negative = p3 is to the right.
    Zero     = collinear.
    """
    return (
        (p2[0] - p1[0]) * (p3[1] - p1[1])
        - (p2[1] - p1[1]) * (p3[0] - p1[0])
    )


def segments_intersect(p1: tuple, p2: tuple, p3: tuple, p4: tuple) -> bool:
    """
    True if segment p1→p2 properly intersects segment p3→p4.
    Uses the direction / cross-product test.
    """
    d1 = direction(p3, p4, p1)
    d2 = direction(p3, p4, p2)
    d3 = direction(p1, p2, p3)
    d4 = direction(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def point_in_polygon(point: tuple, polygon: list[tuple]) -> bool:
    """
    Ray-casting algorithm.
    Cast a horizontal ray rightward from point and count polygon edge crossings.
    Odd count → inside (True).  Even count → outside (False).
    """
    lat, lng = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lng) != (yj > lng)) and (lat < (xj - xi) * (lng - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def path_intersects_polygon(start: tuple, end: tuple, polygon: list[tuple]) -> bool:
    """
    True if the straight-line segment start→end crosses any edge of polygon.
    """
    n = len(polygon)
    for i in range(n):
        edge_a = polygon[i]
        edge_b = polygon[(i + 1) % n]
        if segments_intersect(start, end, edge_a, edge_b):
            return True
    return False


# ---------------------------------------------------------------------------
# Waypoint finding
# ---------------------------------------------------------------------------

def _polygon_centroid(polygon: list[tuple]) -> tuple:
    lat = sum(p[0] for p in polygon) / len(polygon)
    lng = sum(p[1] for p in polygon) / len(polygon)
    return (lat, lng)


def _push_away(vertex: tuple, centroid: tuple, buffer: float = 0.0005) -> tuple:
    """Push vertex slightly away from centroid to add a safety buffer."""
    dlat = vertex[0] - centroid[0]
    dlng = vertex[1] - centroid[1]
    mag = sqrt(dlat ** 2 + dlng ** 2) or 1e-9
    return (vertex[0] + buffer * dlat / mag, vertex[1] + buffer * dlng / mag)


def find_best_waypoints(
    start: tuple, end: tuple, polygon: list[tuple]
) -> list[tuple]:
    """
    Find the shortest 2-waypoint detour around polygon.

    For every pair of polygon vertices (W1, W2):
      - Check that start→W1, W1→W2, and W2→end are all collision-free.
      - Compute total detour distance.
    Return the pair with minimum total distance, pushed slightly away from
    the polygon centroid for safety.

    Falls back to a single-vertex detour if no 2-vertex path is found,
    and finally returns [start, end] unchanged if nothing works.
    """
    centroid = _polygon_centroid(polygon)
    n = len(polygon)
    best_dist = float("inf")
    best_pair: list[tuple] = []

    for i in range(n):
        w1 = _push_away(polygon[i], centroid)
        for j in range(n):
            if i == j:
                continue
            w2 = _push_away(polygon[j], centroid)
            # All three legs must be clear
            if (
                not path_intersects_polygon(start, w1, polygon)
                and not path_intersects_polygon(w1, w2, polygon)
                and not path_intersects_polygon(w2, end, polygon)
            ):
                dist = (
                    haversine(start, w1, unit=Unit.KILOMETERS)
                    + haversine(w1, w2, unit=Unit.KILOMETERS)
                    + haversine(w2, end, unit=Unit.KILOMETERS)
                )
                if dist < best_dist:
                    best_dist = dist
                    best_pair = [w1, w2]

    if best_pair:
        return best_pair

    # Fallback: single vertex detour
    best_single_dist = float("inf")
    best_single: tuple | None = None
    for i in range(n):
        w = _push_away(polygon[i], centroid)
        if (
            not path_intersects_polygon(start, w, polygon)
            and not path_intersects_polygon(w, end, polygon)
        ):
            dist = (
                haversine(start, w, unit=Unit.KILOMETERS)
                + haversine(w, end, unit=Unit.KILOMETERS)
            )
            if dist < best_single_dist:
                best_single_dist = dist
                best_single = w

    if best_single:
        return [best_single]

    # Last resort: return no waypoints (straight line, caller handles it)
    return []


# ---------------------------------------------------------------------------
# Path smoothing
# ---------------------------------------------------------------------------

def smooth_path(waypoints: list[tuple], no_fly_polygons: list[list[tuple]]) -> list[tuple]:
    """
    Remove redundant intermediate waypoints.

    For each consecutive triple (W1, W2, W3):
      If W1→W3 is clear of all no-fly polygons, remove W2 and restart.
    Returns the simplified waypoint list.
    """
    path = list(waypoints)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(path) - 2:
            w1, w3 = path[i], path[i + 2]
            clear = all(
                not path_intersects_polygon(w1, w3, poly)
                for poly in no_fly_polygons
            )
            if clear:
                path.pop(i + 1)
                changed = True
            else:
                i += 1
    return path


# ---------------------------------------------------------------------------
# Main routing
# ---------------------------------------------------------------------------

def compute_route(
    start: tuple,
    end: tuple,
    no_fly_zones: list[dict],
) -> tuple[list[tuple], float]:
    """
    Compute a collision-free route from start to end avoiding all active
    no-fly zones.

    no_fly_zones: list of dicts with key "polygon" → list of {lat, lng} dicts.

    Returns (waypoints, total_distance_km).
    """
    # Convert polygon dicts to (lat, lng) tuples
    polygons: list[list[tuple]] = []
    for zone in no_fly_zones:
        poly = [(p["lat"], p["lng"]) for p in zone["polygon"]]
        polygons.append(poly)

    path: list[tuple] = [start, end]

    # Iteratively resolve intersections
    max_iterations = 20
    for _ in range(max_iterations):
        resolved = True
        new_path: list[tuple] = [path[0]]
        for idx in range(len(path) - 1):
            seg_start = path[idx]
            seg_end = path[idx + 1]
            inserted = False
            for poly in polygons:
                if path_intersects_polygon(seg_start, seg_end, poly):
                    waypoints = find_best_waypoints(seg_start, seg_end, poly)
                    new_path.extend(waypoints)
                    resolved = False
                    inserted = True
                    break
            new_path.append(seg_end)
            if inserted:
                break  # restart with updated path
        path = new_path
        if resolved:
            break

    path = smooth_path(path, polygons)

    distance_km = sum(
        haversine(path[i], path[i + 1], unit=Unit.KILOMETERS)
        for i in range(len(path) - 1)
    )
    return path, distance_km
