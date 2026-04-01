-- AeroGuard Platform — Seed Data
-- Run after schema.sql to populate demo cameras and drones.

-- ─── cameras ────────────────────────────────────────────────────────────────
INSERT INTO cameras (name, location_desc, lat, lng, stream_url, is_active) VALUES
    ('Gate A Magarpatta',    'Gate A, Magarpatta City, Pune',          18.5074, 73.9286, 'http://placeholder/stream/1', TRUE),
    ('Parking Amanora',      'Amanora Park Town Parking, Hadapsar',    18.5018, 73.9357, 'http://placeholder/stream/2', TRUE),
    ('Industrial Hadapsar',  'Industrial Estate, Hadapsar, Pune',      18.4965, 73.9406, 'http://placeholder/stream/3', TRUE),
    ('Residential Kharadi',  'Kharadi Residential Zone, Pune',         18.5513, 73.9413, 'http://placeholder/stream/4', TRUE);

-- ─── drones ─────────────────────────────────────────────────────────────────
INSERT INTO drones (name, lat, lng, home_lat, home_lng, battery_pct, status, speed_kmh, stream_url) VALUES
    ('Alpha-1', 18.5074, 73.9286, 18.5074, 73.9286, 92, 'available', 60, 'http://placeholder/drone-stream/1'),
    ('Beta-2',  18.5200, 73.9100, 18.5200, 73.9100, 78, 'available', 60, 'http://placeholder/drone-stream/2'),
    ('Gamma-3', 18.4900, 73.9450, 18.4900, 73.9450, 45, 'charging',  60, 'http://placeholder/drone-stream/3'),
    ('Delta-4', 18.5400, 73.9500, 18.5400, 73.9500, 88, 'available', 60, 'http://placeholder/drone-stream/4');
