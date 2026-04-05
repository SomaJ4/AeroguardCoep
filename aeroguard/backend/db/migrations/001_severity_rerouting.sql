-- Migration: Dynamic Severity Scoring + Rerouting
-- Run against your Supabase project SQL editor.

-- ─── incidents: new columns ─────────────────────────────────────────────────
ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS human_crowd      INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS severity         DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS severity_trend   DOUBLE PRECISION DEFAULT 0;

-- Allow 'abandoned' as a valid incident status
ALTER TABLE incidents
    DROP CONSTRAINT IF EXISTS incidents_status_check;
ALTER TABLE incidents
    ADD CONSTRAINT incidents_status_check
    CHECK (status IN ('open', 'resolved', 'acknowledged', 'abandoned'));

-- ─── severity_history ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS severity_history (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id  UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    severity     DOUBLE PRECISION NOT NULL,
    human_crowd  INTEGER NOT NULL DEFAULT 0,
    risk_score   DOUBLE PRECISION NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_severity_history_incident
    ON severity_history (incident_id, recorded_at DESC);

-- ─── dispatch_logs: rerouting tracking ──────────────────────────────────────
ALTER TABLE dispatch_logs
    ADD COLUMN IF NOT EXISTS rerouted_from_incident_id UUID REFERENCES incidents(id),
    ADD COLUMN IF NOT EXISTS abandoned_incident_id     UUID REFERENCES incidents(id);

-- ─── Realtime ────────────────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE severity_history;

-- crowd_score from Om's YOLO pipeline
ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS crowd_score DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- Allow crowd_gathering as a valid incident type
ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_incident_type_check;
ALTER TABLE incidents ADD CONSTRAINT incidents_incident_type_check
    CHECK (incident_type IN (
        'fire', 'theft', 'accident', 'intrusion', 'patrol', 'animal',
        'crowd_gathering'
    ));
