-- AeroGuard Platform — Database Schema
-- Run this against a fresh Supabase project to create all required tables.

-- ─── cameras ────────────────────────────────────────────────────────────────
CREATE TABLE cameras (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    location_desc TEXT,
    lat           DOUBLE PRECISION NOT NULL,
    lng           DOUBLE PRECISION NOT NULL,
    stream_url    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── drones ─────────────────────────────────────────────────────────────────
CREATE TABLE drones (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    home_lat    DOUBLE PRECISION NOT NULL,
    home_lng    DOUBLE PRECISION NOT NULL,
    battery_pct DOUBLE PRECISION NOT NULL
                    CHECK (battery_pct >= 0 AND battery_pct <= 100),
    status      TEXT NOT NULL DEFAULT 'available'
                    CHECK (status IN ('available', 'en_route', 'on_scene', 'charging')),
    speed_kmh   DOUBLE PRECISION NOT NULL DEFAULT 60,
    stream_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── incidents ──────────────────────────────────────────────────────────────
CREATE TABLE incidents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id     UUID REFERENCES cameras(id),
    incident_type TEXT NOT NULL
                      CHECK (incident_type IN ('fire', 'theft', 'accident', 'intrusion', 'patrol', 'animal')),
    risk_score    DOUBLE PRECISION NOT NULL
                      CHECK (risk_score >= 0 AND risk_score <= 1),
    confidence    DOUBLE PRECISION NOT NULL
                      CHECK (confidence >= 0 AND confidence <= 1),
    risk_level    TEXT CHECK (risk_level IN ('low', 'medium', 'high')),
    lat           DOUBLE PRECISION NOT NULL,
    lng           DOUBLE PRECISION NOT NULL,
    snapshot_url  TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open', 'resolved', 'acknowledged')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── dispatch_logs ──────────────────────────────────────────────────────────
CREATE TABLE dispatch_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id   UUID NOT NULL REFERENCES incidents(id),
    drone_id      UUID NOT NULL REFERENCES drones(id),
    dispatched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    arrived_at    TIMESTAMPTZ,
    eta_seconds   INTEGER NOT NULL,
    route_geojson JSONB
);

-- ─── monitoring_sessions ────────────────────────────────────────────────────
CREATE TABLE monitoring_sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id  UUID NOT NULL REFERENCES cameras(id),
    status     TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'stopped')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at   TIMESTAMPTZ
);

-- ─── Supabase Realtime ──────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
ALTER PUBLICATION supabase_realtime ADD TABLE drones;
ALTER PUBLICATION supabase_realtime ADD TABLE dispatch_logs;
