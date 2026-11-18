-- Migration: Emergency Notifications
-- Stores a record every time AeroGuard contacts emergency services for an incident.

CREATE TABLE IF NOT EXISTS emergency_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    amenity         TEXT NOT NULL,          -- 'hospital' or 'police'
    facility_name   TEXT NOT NULL,
    facility_lat    DOUBLE PRECISION,
    facility_lng    DOUBLE PRECISION,
    distance_km     DOUBLE PRECISION,
    phone           TEXT,
    sms_sent        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emergency_notifications_incident
    ON emergency_notifications (incident_id, created_at DESC);

ALTER PUBLICATION supabase_realtime ADD TABLE emergency_notifications;
