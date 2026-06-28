-- AIS Vessel Notifications — Supabase / PostgreSQL schema
-- Run this once in your Supabase SQL editor or via the CLI.

-- ---------------------------------------------------------------
-- vessels: one row per unique MMSI, updated when we learn more
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vessels (
    mmsi            BIGINT PRIMARY KEY,
    name            TEXT,
    imo             BIGINT,
    callsign        TEXT,
    ship_type       INTEGER,
    ship_type_label TEXT,
    length_m        NUMERIC(8, 2),
    width_m         NUMERIC(8, 2),
    draught         NUMERIC(8, 2),
    destination     TEXT,
    eta             TEXT,
    flag_country    TEXT,
    flag_emoji      TEXT,
    photo_url       TEXT,
    info            JSONB NOT NULL DEFAULT '{}'::JSONB,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_enriched   TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vessels_name ON vessels (name);
CREATE INDEX IF NOT EXISTS idx_vessels_ship_type ON vessels (ship_type);

-- Automatically keep updated_at current
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_vessels_updated_at ON vessels;
CREATE TRIGGER trg_vessels_updated_at
    BEFORE UPDATE ON vessels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ---------------------------------------------------------------
-- sightings: one row per processed AIS observation
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sightings (
    id          BIGSERIAL PRIMARY KEY,
    mmsi        BIGINT NOT NULL REFERENCES vessels (mmsi) ON DELETE CASCADE,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lat         NUMERIC(10, 7),
    lon         NUMERIC(10, 7),
    sog         NUMERIC(6, 2),   -- knots
    cog         NUMERIC(6, 2),   -- degrees
    heading     SMALLINT,
    nav_status  SMALLINT,
    direction   TEXT CHECK (direction IN ('Arriving', 'Departing')),
    source      TEXT NOT NULL DEFAULT 'unknown',
    raw         TEXT
);

-- Migration: add direction column to an existing sightings table
-- Run this once if the table already exists:
-- ALTER TABLE sightings
--     ADD COLUMN IF NOT EXISTS direction TEXT CHECK (direction IN ('Arriving', 'Departing'));

-- Fast lookup of latest sighting per vessel (used by dedup + notifications)
CREATE INDEX IF NOT EXISTS idx_sightings_mmsi_ts  ON sightings (mmsi, ts DESC);
-- Used by daily/weekly stats aggregations
CREATE INDEX IF NOT EXISTS idx_sightings_ts       ON sightings (ts DESC);
-- Used by stats ship-type breakdown (join with vessels)
CREATE INDEX IF NOT EXISTS idx_sightings_ts_mmsi  ON sightings (ts, mmsi);

-- ---------------------------------------------------------------
-- stats_summary: aggregated counts for a time window.
-- Returns a single JSON object so only one round trip is needed.
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION stats_summary(p_since TIMESTAMPTZ, p_until TIMESTAMPTZ)
RETURNS TABLE(
    total_sightings  BIGINT,
    unique_vessels   BIGINT,
    hourly_counts    JSONB,
    type_breakdown   JSONB,
    top_vessels      JSONB
) LANGUAGE sql STABLE AS $$
    SELECT
        COUNT(*)::BIGINT AS total_sightings,
        COUNT(DISTINCT s.mmsi)::BIGINT AS unique_vessels,

        -- hourly counts as [{hour: H, count: N}, ...]
        COALESCE(
            (SELECT jsonb_agg(jsonb_build_object('hour', h, 'count', cnt) ORDER BY h)
             FROM (
                 SELECT EXTRACT(HOUR FROM s2.ts AT TIME ZONE 'UTC')::INT AS h,
                        COUNT(*) AS cnt
                 FROM sightings s2
                 WHERE s2.ts >= p_since AND s2.ts <= p_until
                 GROUP BY h
             ) hc),
            '[]'::JSONB
        ) AS hourly_counts,

        -- type breakdown as [{ship_type_label: "Cargo", count: N}, ...]
        COALESCE(
            (SELECT jsonb_agg(jsonb_build_object('ship_type_label', COALESCE(tc.ship_type_label, 'Unknown'), 'count', tc.cnt) ORDER BY tc.cnt DESC)
             FROM (
                 SELECT v2.ship_type_label, COUNT(*) AS cnt
                 FROM sightings s2
                 LEFT JOIN vessels v2 ON v2.mmsi = s2.mmsi
                 WHERE s2.ts >= p_since AND s2.ts <= p_until
                 GROUP BY v2.ship_type_label
             ) tc),
            '[]'::JSONB
        ) AS type_breakdown,

        -- top 10 vessels by sighting count
        COALESCE(
            (SELECT jsonb_agg(jsonb_build_object('name', COALESCE(v3.name, 'MMSI ' || vc.mmsi::TEXT), 'mmsi', vc.mmsi, 'count', vc.cnt) ORDER BY vc.cnt DESC)
             FROM (
                 SELECT s3.mmsi, COUNT(*) AS cnt
                 FROM sightings s3
                 WHERE s3.ts >= p_since AND s3.ts <= p_until
                 GROUP BY s3.mmsi
                 ORDER BY cnt DESC
                 LIMIT 10
             ) vc
             LEFT JOIN vessels v3 ON v3.mmsi = vc.mmsi),
            '[]'::JSONB
        ) AS top_vessels

    FROM sightings s
    WHERE s.ts >= p_since AND s.ts <= p_until;
$$;

-- ---------------------------------------------------------------
-- daily_sighting_counts: per-day row counts for a date range.
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION daily_sighting_counts(p_since TIMESTAMPTZ, p_until TIMESTAMPTZ)
RETURNS TABLE(day_iso TEXT, count BIGINT) LANGUAGE sql STABLE AS $$
    SELECT
        to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS day_iso,
        COUNT(*)::BIGINT AS count
    FROM sightings
    WHERE ts >= p_since AND ts <= p_until
    GROUP BY day_iso
    ORDER BY day_iso;
$$;
