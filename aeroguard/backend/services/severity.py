"""
Dynamic severity scoring for incidents.

severity = 0.40 * base_impact(incident_type)
         + 0.35 * risk_score
         + 0.15 * min(1.0, human_crowd / 20.0)
         + 0.10 * time_criticality (ramps over 10 min)

Severity is recomputed on every vision_service update and stored
in incidents.severity + a rolling severity_history table (last 5 rows).
"""
import logging
from datetime import datetime, timezone
from math import isfinite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type weights
# ---------------------------------------------------------------------------
TYPE_WEIGHTS: dict[str, float] = {
    "fire":             0.90,
    "accident":         0.85,
    "vehicle_collision":0.85,
    "fight":            0.80,
    "crowd_gathering":  0.75,
    "intrusion":        0.65,
    "theft":            0.50,
    "animal":           0.30,
    "patrol":           0.10,
    "normal":           0.10,
    "unknown_anomaly":  0.40,
}
DEFAULT_TYPE_WEIGHT = 0.50

CROWD_CAP       = 20.0   # crowd count normalised against this
TIME_RAMP_SECS  = 600.0  # severity reaches max time component after 10 min
REROUTE_THRESHOLD = 0.25 # minimum severity gap to justify rerouting


# ---------------------------------------------------------------------------
# Core formula
# ---------------------------------------------------------------------------

def compute_severity(
    incident_type: str,
    risk_score: float,
    human_crowd: int,
    created_at: datetime | None = None,
    crowd_score: float = 0.0,
) -> float:
    """Return a severity score in [0, 1]."""
    base_impact = TYPE_WEIGHTS.get(incident_type, DEFAULT_TYPE_WEIGHT)

    # Use crowd_score directly from Om's YOLO pipeline (already 0–1)
    # Fall back to human_crowd normalisation if crowd_score not available
    crowd_component = crowd_score if crowd_score > 0.0 else min(1.0, human_crowd / CROWD_CAP)

    if created_at is not None:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_secs = max(0.0, (now - created_at).total_seconds())
        time_criticality = min(1.0, age_secs / TIME_RAMP_SECS)
    else:
        time_criticality = 0.0

    severity = (
        0.40 * base_impact
        + 0.35 * risk_score
        + 0.15 * crowd_component
        + 0.10 * time_criticality
    )
    return round(min(1.0, max(0.0, severity if isfinite(severity) else 0.0)), 6)


# ---------------------------------------------------------------------------
# Trend helpers
# ---------------------------------------------------------------------------

def compute_trend(history: list[dict]) -> float:
    """
    Given a list of severity_history rows (sorted oldest→newest),
    return the trend as (latest - oldest) / elapsed_seconds.
    Positive = worsening, negative = stabilising.
    Returns 0.0 if fewer than 2 data points.
    """
    if len(history) < 2:
        return 0.0
    oldest = history[0]
    newest = history[-1]
    try:
        t0 = _parse_ts(oldest["recorded_at"])
        t1 = _parse_ts(newest["recorded_at"])
        dt = (t1 - t0).total_seconds()
        if dt < 1:
            return 0.0
        return round((newest["severity"] - oldest["severity"]) / dt, 8)
    except Exception:
        return 0.0


def _parse_ts(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def update_incident_severity(incident_id: str, incident: dict) -> float:
    """
    Recompute severity for an incident dict, persist it to incidents table,
    append a severity_history row, prune history to last 5 rows,
    and update severity_trend.

    Returns the new severity value.
    """
    from db.supabase import supabase

    created_at = None
    raw_ts = incident.get("created_at")
    if raw_ts:
        try:
            created_at = _parse_ts(raw_ts)
        except Exception:
            pass

    new_severity = compute_severity(
        incident_type=incident.get("incident_type", "normal"),
        risk_score=float(incident.get("risk_score", 0.0)),
        human_crowd=int(incident.get("human_crowd", 0)),
        created_at=created_at,
        crowd_score=float(incident.get("crowd_score", 0.0)),
    )

    # Append history row
    supabase.table("severity_history").insert({
        "incident_id": incident_id,
        "severity":    new_severity,
        "human_crowd": int(incident.get("human_crowd", 0)),
        "risk_score":  float(incident.get("risk_score", 0.0)),
    }).execute()

    # Fetch last 5 history rows for trend
    hist_resp = (
        supabase.table("severity_history")
        .select("*")
        .eq("incident_id", incident_id)
        .order("recorded_at", desc=False)
        .limit(5)
        .execute()
    )
    history = hist_resp.data or []
    trend = compute_trend(history)

    # Prune rows older than the last 5
    all_hist = (
        supabase.table("severity_history")
        .select("id, recorded_at")
        .eq("incident_id", incident_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    all_rows = all_hist.data or []
    if len(all_rows) > 5:
        ids_to_delete = [r["id"] for r in all_rows[5:]]
        supabase.table("severity_history").delete().in_("id", ids_to_delete).execute()

    # Update incident
    supabase.table("incidents").update({
        "severity":       new_severity,
        "severity_trend": trend,
    }).eq("id", incident_id).execute()

    logger.debug("Incident %s severity=%.4f trend=%.6f", incident_id, new_severity, trend)
    return new_severity
