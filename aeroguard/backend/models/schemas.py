from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


# Camera
class CameraCreate(BaseModel):
    name: str
    location_desc: str | None = None
    lat: float
    lng: float
    stream_url: str | None = None
    is_active: bool = True


class CameraUpdate(BaseModel):
    name: str | None = None
    location_desc: str | None = None
    lat: float | None = None
    lng: float | None = None
    stream_url: str | None = None
    is_active: bool | None = None


class CameraOut(BaseModel):
    id: str
    name: str
    location_desc: str | None = None
    lat: float
    lng: float
    stream_url: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


# Incident
class IncidentCreate(BaseModel):
    camera_id: str
    incident_type: Literal["fire", "theft", "accident", "intrusion", "patrol", "animal"]
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    lat: float
    lng: float
    snapshot_url: str | None = None


class IncidentOut(BaseModel):
    id: str
    camera_id: str
    incident_type: str
    risk_score: float
    confidence: float
    risk_level: str
    lat: float
    lng: float
    snapshot_url: str | None = None
    status: str
    human_crowd: int = 0
    severity: float | None = None
    severity_trend: float | None = None
    created_at: datetime | None = None


# Drone
class DroneOut(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    home_lat: float
    home_lng: float
    battery_pct: float
    status: Literal["available", "en_route", "on_scene", "charging"]
    speed_kmh: float
    stream_url: str | None = None
    created_at: datetime | None = None


# Dispatch
class DispatchRequest(BaseModel):
    incident_id: str
    drone_id: str | None = None


class DispatchOut(BaseModel):
    dispatch_log_id: str
    drone_id: str
    incident_id: str
    eta_seconds: int
    route_geojson: dict | None


# Monitoring
class MonitoringStart(BaseModel):
    camera_id: str


class MonitoringStop(BaseModel):
    session_id: str


class MonitoringSessionOut(BaseModel):
    id: str
    camera_id: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None


# Shared
class StatusUpdate(BaseModel):
    status: str


# Vision Service integration models

class AnalyzeResult(BaseModel):
    """Result returned by the Vision Service POST /analyze endpoint."""
    id: str
    camera_id: str
    incident_type: Literal[
        "fire", "theft", "accident", "intrusion", "patrol", "animal",
        "vehicle_collision", "unknown_anomaly", "normal", "crowd_gathering"
    ]
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    lat: float
    lng: float
    snapshot_url: Optional[str] = None
    human_crowd: Optional[int] = 0
    crowd_score: Optional[float] = 0.0        # Om's YOLO crowd signal (0.0–1.0)
    # Optional enriched fields from Om's new parallel pipeline
    decision_source: Optional[str] = None
    autoencoder_score_raw: Optional[float] = None
    autoencoder_score_calibrated: Optional[float] = None
    risk_band: Optional[str] = None
    classifier_raw_label: Optional[str] = None
    classifier_mapped_label: Optional[str] = None
    classifier_confidence: Optional[float] = None
    classifier_accepted: Optional[bool] = None

    class Config:
        extra = "ignore"


class BatchResultItem(BaseModel):
    """Per-video outcome in a batch analysis response."""
    camera_id: str
    url: str  # Supabase public URL
    status: Literal["success", "failed"]
    result: Optional[AnalyzeResult] = None  # present when status == "success"
    error: Optional[str] = None             # present when status == "failed"


class BatchResult(BaseModel):
    """Aggregated response for POST /upload/videos."""
    items: list[BatchResultItem]
