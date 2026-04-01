-- Run this in Supabase SQL editor to add the alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id),
    risk_level  TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    message     TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Realtime so dashboard receives alerts instantly
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
