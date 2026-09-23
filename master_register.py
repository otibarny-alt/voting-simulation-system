import os
import re

import psycopg
from psycopg.rows import dict_row


MASTER_REGISTER_DATABASE_URL = os.getenv("MASTER_REGISTER_DATABASE_URL", "").strip()
_SCHEMA_READY = False


def configured():
    return bool(MASTER_REGISTER_DATABASE_URL)


def connect():
    if not MASTER_REGISTER_DATABASE_URL:
        raise RuntimeError("MASTER_REGISTER_DATABASE_URL is not configured.")
    # Never let a temporary Render PostgreSQL outage hold an entire web page
    # open indefinitely. Administrative pages catch this bounded failure and
    # remain usable while showing the database warning.
    return psycopg.connect(
        MASTER_REGISTER_DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=2,
        options="-c statement_timeout=4000 -c lock_timeout=2000",
    )


def ensure_schema():
    global _SCHEMA_READY
    if not configured():
        return
    if _SCHEMA_READY:
        return
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS master_voters (
                    national_id TEXT PRIMARY KEY,
                    serial_no TEXT NOT NULL,
                    party_membership_number TEXT,
                    first_name TEXT,
                    middle_name TEXT,
                    surname TEXT,
                    full_name TEXT,
                    phone TEXT,
                    gender TEXT,
                    date_of_birth TEXT,
                    county TEXT,
                    constituency TEXT,
                    ward TEXT,
                    polling_station TEXT,
                    polling_station_code TEXT,
                    id_photo_ref TEXT,
                    passport_photo_ref TEXT,
                    source_submission_id TEXT,
                    source_updated_at TEXT,
                    import_batch_id UUID,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_master_voters_serial_ci ON master_voters (LOWER(serial_no))")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_master_voters_membership_ci ON master_voters (LOWER(party_membership_number)) WHERE NULLIF(party_membership_number, '') IS NOT NULL")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_master_voters_geo ON master_voters (LOWER(county), LOWER(constituency), LOWER(ward)) WHERE active")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_master_voters_station ON master_voters (LOWER(polling_station)) WHERE active")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_master_voters_station_code ON master_voters (polling_station_code) WHERE active")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voter_register_import_batches (
                    batch_id UUID PRIMARY KEY,
                    filename TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK (mode IN ('merge','replace')),
                    status TEXT NOT NULL DEFAULT 'STAGING',
                    staged_rows BIGINT NOT NULL DEFAULT 0,
                    valid_rows BIGINT NOT NULL DEFAULT 0,
                    rejected_rows BIGINT NOT NULL DEFAULT 0,
                    promoted_rows BIGINT NOT NULL DEFAULT 0,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    staged_at TIMESTAMPTZ,
                    promoted_at TIMESTAMPTZ,
                    notes TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voter_register_stage (
                    batch_id UUID NOT NULL REFERENCES voter_register_import_batches(batch_id) ON DELETE CASCADE,
                    row_number BIGINT NOT NULL,
                    national_id TEXT,
                    serial_no TEXT,
                    party_membership_number TEXT,
                    first_name TEXT,
                    middle_name TEXT,
                    surname TEXT,
                    full_name TEXT,
                    phone TEXT,
                    gender TEXT,
                    date_of_birth TEXT,
                    county TEXT,
                    constituency TEXT,
                    ward TEXT,
                    polling_station TEXT,
                    polling_station_code TEXT,
                    id_photo_ref TEXT,
                    passport_photo_ref TEXT,
                    source_submission_id TEXT,
                    source_updated_at TEXT,
                    validation_error TEXT,
                    PRIMARY KEY (batch_id, row_number)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_voter_stage_batch_serial ON voter_register_stage(batch_id, LOWER(serial_no))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_voter_stage_batch_national ON voter_register_stage(batch_id, national_id)")
        conn.commit()
    _SCHEMA_READY = True


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def lookup_by_serial(serial_no):
    if not configured() or not str(serial_no or "").strip():
        return None
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM master_voters WHERE active AND LOWER(serial_no)=LOWER(%s) LIMIT 1", (str(serial_no).strip(),))
            return cur.fetchone()


def serial_exists(serial_no):
    """Return True when a serial is already active or present in a valid staged row."""
    value = str(serial_no or "").strip()
    if not configured() or not value:
        return False
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM master_voters
                    WHERE LOWER(serial_no)=LOWER(%s)
                    UNION ALL
                    SELECT 1 FROM voter_register_stage
                    WHERE validation_error IS NULL AND LOWER(serial_no)=LOWER(%s)
                ) AS found
            """, (value, value))
            return bool(cur.fetchone()["found"])


def lookup_by_national_id(national_id):
    value = _digits(national_id)
    if not configured() or not value:
        return None
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM master_voters WHERE active AND national_id=%s LIMIT 1", (value,))
            return cur.fetchone()


def registered_total():
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM master_voters WHERE active")
            return int(cur.fetchone()["n"] or 0)


def registered_breakdown():
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT county, constituency, ward, COUNT(*) AS registered_voters
                           FROM master_voters WHERE active
                           GROUP BY county, constituency, ward
                           ORDER BY LOWER(county), LOWER(constituency), LOWER(ward)""")
            return list(cur.fetchall())


def registered_for_station(polling_station_code="", polling_station=""):
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            if str(polling_station_code or "").strip():
                cur.execute("SELECT COUNT(*) AS n FROM master_voters WHERE active AND polling_station_code=%s", (str(polling_station_code).strip(),))
                count = int(cur.fetchone()["n"] or 0)
                if count or not str(polling_station or "").strip():
                    return count
            cur.execute("SELECT COUNT(*) AS n FROM master_voters WHERE active AND LOWER(polling_station)=LOWER(%s)", (str(polling_station).strip(),))
            return int(cur.fetchone()["n"] or 0)
