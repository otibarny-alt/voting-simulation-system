import os
import re

import psycopg
from psycopg.rows import dict_row


MASTER_REGISTER_DATABASE_URL = os.getenv("MASTER_REGISTER_DATABASE_URL", "").strip()
_SCHEMA_READY = False


def configured():
    return bool(MASTER_REGISTER_DATABASE_URL)


def connect(statement_timeout_ms=4000, lock_timeout_ms=2000):
    if not MASTER_REGISTER_DATABASE_URL:
        raise RuntimeError("MASTER_REGISTER_DATABASE_URL is not configured.")
    # Never let a temporary Render PostgreSQL outage hold an entire web page
    # open indefinitely. Administrative pages catch this bounded failure and
    # remain usable while showing the database warning.
    return psycopg.connect(
        MASTER_REGISTER_DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=2,
        options=f"-c statement_timeout={int(statement_timeout_ms)} -c lock_timeout={int(lock_timeout_ms)}",
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


def phone_owner(phone, exclude_national_id=""):
    """Return the active member using a normalized Kenyan phone number."""
    value = _digits(phone)
    if value.startswith("254") and len(value) == 12:
        value = "0" + value[3:]
    elif len(value) == 9:
        value = "0" + value
    excluded = _digits(exclude_national_id)
    if not configured() or not value:
        return None
    ensure_schema()
    local = value[1:] if value.startswith("0") and len(value) == 10 else value
    variants = list(dict.fromkeys((value, local, "254" + local, "+254" + local)))
    # This is the only unavoidable whole-register phone comparison when the
    # imported database has no phone index. Give it a bounded maintenance-style
    # window instead of the four-second public lookup limit.
    with connect(statement_timeout_ms=30000, lock_timeout_ms=5000) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT national_id FROM master_voters WHERE active AND national_id<>%s "
                "AND phone=ANY(%s) LIMIT 1",
                (excluded, variants),
            )
            row = cur.fetchone()
            return row.get("national_id") if row else None


def apply_membership_change(national_id, request_type, updates, request_id=None):
    """Apply an approved self-service membership request to the master register."""
    ensure_schema()
    national_id = _digits(national_id)
    request_type = str(request_type or "").strip().lower()
    updates = dict(updates or {})
    if not national_id:
        raise ValueError("The membership request has no valid National ID.")
    if request_type not in ("new", "edit"):
        raise ValueError("Unsupported membership request type.")
    source_ref = f"membership-request:{request_id}" if request_id is not None else "membership-request"
    mapping = {
        "serial_no": "serial_no",
        "odm_membership_no": "party_membership_number",
        "first_name": "first_name",
        "middle_name": "middle_name",
        "surname": "surname",
        "phone_no": "phone",
        "county": "county",
        "constituency": "constituency",
        "ward": "ward",
        "poll_station": "polling_station",
        "poll_station_code": "polling_station_code",
        "member_id_photo": "id_photo_ref",
        "member_passport_photo": "passport_photo_ref",
    }
    with connect(statement_timeout_ms=30000, lock_timeout_ms=5000) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM master_voters WHERE national_id=%s FOR UPDATE", (national_id,))
            existing = cur.fetchone()
            if request_type == "edit" and not existing:
                raise ValueError("The member record to be edited is no longer present in the master voters register.")
            if request_type == "new" and existing and existing.get("source_submission_id") != source_ref:
                raise ValueError("This National ID is already present in the master voters register.")
            values = dict(existing or {})
            for request_key, database_key in mapping.items():
                if request_key in updates:
                    values[database_key] = str(updates.get(request_key) or "").strip()
            if request_type == "new" and not str(values.get("serial_no") or "").strip():
                raise ValueError("This new membership request has no generated serial number.")
            if not str(values.get("party_membership_number") or "").strip():
                values["party_membership_number"] = "ODM" + national_id
            values["full_name"] = " ".join(
                str(values.get(key) or "").strip()
                for key in ("first_name", "middle_name", "surname")
                if str(values.get(key) or "").strip()
            )
            columns = (
                "serial_no", "party_membership_number", "first_name", "middle_name", "surname",
                "full_name", "phone", "gender", "date_of_birth", "county", "constituency",
                "ward", "polling_station", "polling_station_code", "id_photo_ref", "passport_photo_ref",
            )
            params = [national_id] + [str(values.get(column) or "").strip() for column in columns] + [source_ref]
            cur.execute(f"""
                INSERT INTO master_voters
                    (national_id,{','.join(columns)},source_submission_id,source_updated_at,active,updated_at)
                VALUES (%s,{','.join(['%s'] * len(columns))},%s,NOW()::text,TRUE,NOW())
                ON CONFLICT (national_id) DO UPDATE SET
                    {','.join(f'{column}=EXCLUDED.{column}' for column in columns)},
                    source_submission_id=EXCLUDED.source_submission_id,
                    source_updated_at=EXCLUDED.source_updated_at,
                    active=TRUE,updated_at=NOW()
            """, params)
        conn.commit()


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


def _register_where(filters=None):
    filters = filters or {}
    clauses = ["active"]
    params = []
    columns = {
        "county": "county", "constituency": "constituency", "ward": "ward",
        "polling_station": "polling_station",
    }
    for key, column in columns.items():
        value = str(filters.get(key) or "").strip()
        if value:
            clauses.append(f"LOWER({column})=LOWER(%s)")
            params.append(value)
    return " AND ".join(clauses), params


def voters_register_count(filters=None):
    """Count active voters for the selected register geography."""
    ensure_schema()
    where, params = _register_where(filters)
    with connect(statement_timeout_ms=30000) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM master_voters WHERE {where}", params)
            return int(cur.fetchone()["n"] or 0)


def voters_register_rows(filters=None, limit=None):
    """Return active register rows without consulting Kobo or the fallback CSV."""
    ensure_schema()
    where, params = _register_where(filters)
    sql = f"""SELECT national_id AS member_id, serial_no,
                     CONCAT_WS(' ',first_name,middle_name,surname) AS full_name,
                     party_membership_number AS odm_registration_no,
                     county,constituency,ward,polling_station
              FROM master_voters WHERE {where}
              ORDER BY LOWER(county),LOWER(constituency),LOWER(ward),
                       LOWER(polling_station),
                       CASE WHEN national_id ~ '^[0-9]+$' THEN national_id::numeric END,
                       national_id"""
    if limit is not None:
        sql += " LIMIT %s"
        params = [*params, int(limit)]
    with connect(statement_timeout_ms=120000) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def iter_voters_register_rows(filters=None):
    """Stream a complete filtered register without holding it in web-worker memory."""
    ensure_schema()
    where, params = _register_where(filters)
    sql = f"""SELECT national_id AS member_id, serial_no,
                     CONCAT_WS(' ',first_name,middle_name,surname) AS full_name,
                     party_membership_number AS odm_registration_no,
                     county,constituency,ward,polling_station
              FROM master_voters WHERE {where}
              ORDER BY LOWER(county),LOWER(constituency),LOWER(ward),
                       LOWER(polling_station),
                       CASE WHEN national_id ~ '^[0-9]+$' THEN national_id::numeric END,
                       national_id"""
    with connect(statement_timeout_ms=0) as conn:
        with conn.cursor(name="voters_register_export") as cur:
            cur.itersize = 10000
            cur.execute(sql, params)
            for row in cur:
                yield dict(row)


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
