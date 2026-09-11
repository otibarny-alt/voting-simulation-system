# V23.23: member self-service registration and administrator approval portal.
import os, sqlite3, csv, json, re, hmac, secrets, hashlib, smtplib, threading, time, shutil, tempfile, copy
import requests
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from datetime import datetime, date, time as dt_time
from email.message import EmailMessage
from io import BytesIO, StringIO
from urllib.parse import urljoin
from xhtml2pdf import pisa
from zoneinfo import ZoneInfo
from itsdangerous import URLSafeSerializer, BadSignature
from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify, send_file
from markupsafe import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

app=Flask(__name__)
app.secret_key=os.getenv("FLASK_SECRET_KEY","training-only-change-me")
app.config["MAX_CONTENT_LENGTH"]=int(os.getenv("DATA_UPLOAD_MAX_MB","30") or 30)*1024*1024
DB=os.getenv("DEMO_DB_PATH","training_votes.db")
KENYA_TZ=ZoneInfo("Africa/Nairobi")
OFFICIAL_CLOSE_TIME="08:00"
SMTP_HOST=os.getenv("SMTP_HOST","").strip()
SMTP_PORT=int(os.getenv("SMTP_PORT","587") or 587)
SMTP_USERNAME=os.getenv("SMTP_USERNAME","").strip()
SMTP_PASSWORD=os.getenv("SMTP_PASSWORD","").strip()
SMTP_FROM_EMAIL=os.getenv("SMTP_FROM_EMAIL",SMTP_USERNAME).strip()
SMTP_FROM_NAME=os.getenv("SMTP_FROM_NAME","ODM Training Tally Reports").strip()
SMTP_USE_TLS=os.getenv("SMTP_USE_TLS","true").strip().lower() not in ("0","false","no")
SMTP_USE_SSL=os.getenv("SMTP_USE_SSL","false").strip().lower() in ("1","true","yes")

ELECTIONS=[
 ("president","President",10),("governor","Governor",6),("senator","Senator",6),
 ("woman_rep","Woman Rep",6),("mna","MNA",6),("mca","MCA",6)
]

def con():
 # Deployed training terminals can briefly overlap during reset/reopen. Give
 # SQLite time to finish the other request instead of returning a bare HTTP 500.
 c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=30000")
 c.execute('CREATE TABLE IF NOT EXISTS demo_votes(id INTEGER PRIMARY KEY AUTOINCREMENT,voter_session TEXT,election TEXT,candidate INTEGER,candidate_id TEXT,candidate_name TEXT,county TEXT,constituency TEXT,ward TEXT,poll_station TEXT,stream TEXT)')
 vote_cols={r[1] for r in c.execute("PRAGMA table_info(demo_votes)").fetchall()}
 if "candidate_id" not in vote_cols: c.execute("ALTER TABLE demo_votes ADD COLUMN candidate_id TEXT")
 if "candidate_name" not in vote_cols: c.execute("ALTER TABLE demo_votes ADD COLUMN candidate_name TEXT")
 if "dashboard_event_id" not in vote_cols: c.execute("ALTER TABLE demo_votes ADD COLUMN dashboard_event_id TEXT")
 if "dashboard_mirrored" not in vote_cols: c.execute("ALTER TABLE demo_votes ADD COLUMN dashboard_mirrored INTEGER DEFAULT 0")
 c.execute('CREATE INDEX IF NOT EXISTS idx_demo_votes_voter ON demo_votes(voter_session)')
 c.execute('CREATE INDEX IF NOT EXISTS idx_demo_votes_dashboard_mirrored ON demo_votes(dashboard_mirrored)')
 c.execute('''CREATE TABLE IF NOT EXISTS stream_sessions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,session_date TEXT NOT NULL,county TEXT,constituency TEXT,ward TEXT,
 poll_station TEXT,stream TEXT,opened_at TEXT,closed_at TEXT,opening_zero_votes INTEGER DEFAULT 0,
 opening_lat REAL, opening_lon REAL, opening_accuracy REAL,
 UNIQUE(session_date,poll_station,stream))''')
 cols={r[1] for r in c.execute("PRAGMA table_info(stream_sessions)").fetchall()}
 # CREATE TABLE IF NOT EXISTS does not upgrade an existing Render disk. V22.63+
 # writes opening_zero_votes during /stream/open, so old databases without that
 # column failed immediately after a terminal reset.
 stream_session_migrations={
  "closed_at":"TEXT",
  "poll_station_code":"TEXT",
  "opening_zero_votes":"INTEGER DEFAULT 0",
  "opening_lat":"REAL",
  "opening_lon":"REAL",
  "opening_accuracy":"REAL"
 }
 for column,declaration in stream_session_migrations.items():
  if column not in cols:
   c.execute(f"ALTER TABLE stream_sessions ADD COLUMN {column} {declaration}")
 # Persist schema upgrades even when the caller only performs a SELECT and
 # closes the connection (as stream_session() does before /stream/open).
 c.commit()
 return c

def cfg():
 return [{"key":k,"title":t,"count":n,"candidates":[]} for k,t,n in ELECTIONS]


COUNTY_MAIN = os.getenv("COUNTY_MAIN_FILENAME", "county_main.csv")
AGENTS_LOGIN = os.getenv("AGENTS_LOGIN_FILENAME", "agents_login.csv")
DATA_UPLOAD_DIR = os.getenv("DATA_UPLOAD_DIR", "").strip()
VOTING_OPEN_TIME = os.getenv("VOTING_OPEN_TIME", "").strip()
VOTING_CLOSE_TIME = os.getenv("VOTING_CLOSE_TIME", "").strip()
REPORT_HEADER_IMAGE_URL = os.getenv("REPORT_HEADER_IMAGE_URL", "/static/odm_report_header.png").strip()
KOBO_BASE_URL = os.getenv("KOBO_BASE_URL", "https://kf.kobotoolbox.org").rstrip("/")
MEMBERSHIP_ASSET_UID = os.getenv("MEMBERSHIP_ASSET_UID", "").strip()
KOBO_API_TOKEN = os.getenv("KOBO_API_TOKEN", "").strip()
MEMBERSHIP_CSV_FILENAME = os.getenv("MEMBERSHIP_CSV_FILENAME", "membership_registration.csv").strip()
MEMBERSHIP_CSV_CACHE_SECONDS = int(os.getenv("MEMBERSHIP_CSV_CACHE_SECONDS", "300") or 300)
_MEMBERSHIP_CSV_CACHE = {"loaded_at": 0.0, "rows": {}, "media": {}}
CANDIDATE_PORTAL_BASE_URL = os.getenv("CANDIDATE_PORTAL_BASE_URL", "").rstrip("/")
CANDIDATE_CATALOG_CACHE_SECONDS = max(1,int(os.getenv("CANDIDATE_CATALOG_CACHE_SECONDS","60") or 60))
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ELECTION_ID = os.getenv("ELECTION_ID", "ODM_INTERNAL_NOMINATIONS").strip()
ENTRANCE_APPROVAL_MINUTES = int(os.getenv("ENTRANCE_APPROVAL_MINUTES", "30") or 30)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
VOTER_VERIFICATION_BASE_URL = os.getenv("VOTER_VERIFICATION_BASE_URL", "https://odm-member-photo-verifier.onrender.com").strip().rstrip("/")


def managed_data_file(configured_name):
 """Resolve a CSV from persistent upload storage, seeding it from the build."""
 configured_name=str(configured_name or "").strip()
 packaged=configured_name if os.path.isabs(configured_name) else os.path.join(app.root_path,configured_name)
 if not DATA_UPLOAD_DIR:
  return packaged
 os.makedirs(DATA_UPLOAD_DIR,exist_ok=True)
 target=os.path.join(DATA_UPLOAD_DIR,os.path.basename(configured_name))
 if not os.path.exists(target) and os.path.isfile(packaged):
  shutil.copy2(packaged,target)
 return target

def repository_admin_logged_in():
 return bool(session.get("repository_admin"))


# V22.56: shared PostgreSQL connection pool + one-time schema initialization.
# Opening a fresh TLS connection to Render PostgreSQL for every repository query
# is expensive. Reusing a small pool makes repository navigation much faster.
PG_POOL = None
if DATABASE_URL:
 try:
  _pool_url = DATABASE_URL
  if _pool_url.startswith("postgres://"):
   _pool_url = "postgresql://" + _pool_url[len("postgres://"):]
  PG_POOL = ConnectionPool(
   conninfo=_pool_url,
   min_size=int(os.getenv("PG_POOL_MIN_SIZE", "2") or 2),
   max_size=int(os.getenv("PG_POOL_MAX_SIZE", "8") or 8),
   timeout=10,
   kwargs={"row_factory": dict_row},
   open=True
  )
  # Build the minimum pool connections during worker startup so the first
  # repository request does not pay the Render PostgreSQL/TLS connection cost.
  try:
   PG_POOL.wait(timeout=10)
  except Exception as exc:
   app.logger.warning("PostgreSQL pool warm-up did not complete: %s", exc)
 except Exception as exc:
  app.logger.warning("Could not start PostgreSQL connection pool: %s", exc)
  PG_POOL = None

_GLOBAL_DB_READY = False
_GLOBAL_DB_INIT_LOCK = threading.Lock()
_REPO_COUNTS_CACHE = {"at": 0.0, "value": {}}
_REPO_COUNTS_TTL = int(os.getenv("REPO_COUNTS_TTL_SECONDS", "120") or 120)
_REPO_FILTER_CACHE = {}
_REPO_FILTER_TTL = int(os.getenv("REPO_FILTER_TTL_SECONDS", "120") or 120)


def kenya_now():
 return datetime.now(KENYA_TZ)

def official_close_reached():
 now=kenya_now()
 close_t=dt_time(8,0)
 return now.time() >= close_t

def close_time_message():
 return "08:00 (8:00 AM) Africa/Nairobi"

_CANDIDATE_CATALOG_CACHE={}
_CANDIDATE_CATALOG_CACHE_LOCK=threading.Lock()

def candidate_portal_catalog(geo):
 cache_key=tuple(norm_key(geo.get(k,"")) for k in ("county","constituency","ward"))
 now=time.monotonic()
 cached=_CANDIDATE_CATALOG_CACHE.get(cache_key)
 if cached and now-cached[0] < CANDIDATE_CATALOG_CACHE_SECONDS:
  return copy.deepcopy(cached[1])
 if not CANDIDATE_PORTAL_BASE_URL:
  raise RuntimeError("Candidate Portal connection is not configured.")
 r=requests.get(
  f"{CANDIDATE_PORTAL_BASE_URL}/api/candidates",
  params={
   "county":geo.get("county",""),
   "constituency":geo.get("constituency",""),
   "ward":geo.get("ward","")
  },
  timeout=(4,10)
 )
 r.raise_for_status()
 payload=r.json()
 rows=payload.get("results",[]) if isinstance(payload,dict) else []
 catalog={k:[] for k,_,_ in ELECTIONS}
 position_aliases={
  "president":"president","presidential":"president",
  "governor":"governor","gubernatorial":"governor",
  "senator":"senator","senatorial":"senator",
  "woman_rep":"woman_rep","women_rep":"woman_rep",
  "woman_representative":"woman_rep","women_representative":"woman_rep",
  "mna":"mna","member_of_national_assembly":"mna",
  "member_national_assembly":"mna","national_assembly":"mna",
  "mca":"mca","member_of_county_assembly":"mca",
  "member_county_assembly":"mca","county_assembly":"mca"
 }
 for row in rows:
  raw_position=str(row.get("position","")).strip().lower()
  normalized_position=re.sub(r"[^a-z0-9]+","_",raw_position).strip("_")
  key=position_aliases.get(normalized_position,normalized_position)
  if key not in catalog:
   continue
  catalog[key].append({
   "candidate_id":str(row.get("candidate_id","")).strip(),
   "name":str(row.get("full_name","")).strip() or "Unnamed candidate",
   "membership_no":str(row.get("membership_no","")).strip(),
   "bio":str(row.get("bio","")).strip(),
   "photo_url":row.get("photo_url"),
   "county":str(row.get("county","")).strip(),
   "constituency":str(row.get("constituency","")).strip(),
   "ward":str(row.get("ward","")).strip()
  })
 for key in catalog:
  catalog[key].sort(key=lambda x:(x["name"].lower(),x["candidate_id"]))
  for idx,cand in enumerate(catalog[key],start=1):
   cand["slot"]=idx
 with _CANDIDATE_CATALOG_CACHE_LOCK:
  _CANDIDATE_CATALOG_CACHE[cache_key]=(time.monotonic(),copy.deepcopy(catalog))
 return catalog

def election_with_candidates(step,geo):
 e=cfg()[step]
 catalog=candidate_portal_catalog(geo)
 e["candidates"]=catalog.get(e["key"],[])
 e["count"]=len(e["candidates"])
 return e

def current_catalog_or_empty(geo):
 try:
  return candidate_portal_catalog(geo)
 except Exception:
  return {k:[] for k,_,_ in ELECTIONS}


def dashboard_candidate_catalog(election,candidate_totals,event_names=None,event_geo=None):
 """Merge every registered candidate with anonymous vote-event fallbacks.

 The candidate portal is authoritative for who is registered and for the
 electoral area in which a candidate may appear. Stored vote events remain a
 fallback so historical tallies are not hidden if the portal is temporarily
 unavailable or a registration later changes.
 """
 event_names=event_names or {}
 event_geo=event_geo or {}
 candidates_by_id={}
 # First request the complete catalogue. Also request each exact electoral area
 # present in vote events: some candidate services intentionally return local
 # positions only when their county/constituency/ward is supplied.
 catalogue_geographies=[{}]
 seen_geo=set()
 for geo in event_geo.values():
  scoped={k:str(geo.get(k,"") or "").strip() for k in ("county","constituency","ward")}
  marker=tuple(scoped[k].lower() for k in ("county","constituency","ward"))
  if any(marker) and marker not in seen_geo:
   seen_geo.add(marker)
   catalogue_geographies.append(scoped)

 catalogue_errors=[]
 for geo in catalogue_geographies:
  try:
   catalog=candidate_portal_catalog(geo)
   for cand in catalog.get(election,[]):
    cid=str(cand.get("candidate_id","") or "").strip()
    if not cid:
     continue
    existing=candidates_by_id.get(cid,{})
    candidates_by_id[cid]={
     "candidate_id":cid,
     "name":cand.get("name") or existing.get("name") or event_names.get(cid) or cid,
     "county":cand.get("county") or existing.get("county") or geo.get("county","") or "",
     "constituency":cand.get("constituency") or existing.get("constituency") or geo.get("constituency","") or "",
     "ward":cand.get("ward") or existing.get("ward") or geo.get("ward","") or "",
     "photo_url":cand.get("photo_url") or existing.get("photo_url"),
     "votes":int(candidate_totals.get(cid,0) or 0)
    }
  except Exception as exc:
   catalogue_errors.append(str(exc))
 if catalogue_errors and not candidates_by_id:
  app.logger.warning("Candidate catalogue unavailable for %s dashboard: %s",election,"; ".join(catalogue_errors))

 for cid in set(event_names) | set(candidate_totals):
  if not cid or cid=="__SKIP__":
   continue
  geo=event_geo.get(cid,{})
  existing=candidates_by_id.get(cid)
  if existing:
   # Fill any geographic fields omitted by the portal from the vote event.
   for field in ("county","constituency","ward"):
    if not existing.get(field) and geo.get(field):
     existing[field]=geo[field]
   continue
  candidates_by_id[cid]={
   "candidate_id":cid,
   "name":event_names.get(cid) or cid,
   "county":geo.get("county","") or "",
   "constituency":geo.get("constituency","") or "",
   "ward":geo.get("ward","") or "",
   "photo_url":None,
   "votes":int(candidate_totals.get(cid,0) or 0)
  }

 candidates=list(candidates_by_id.values())
 candidates.sort(key=lambda x:(-int(x.get("votes",0)),str(x.get("name","")).lower()))
 return candidates


def pg_url():
 url=DATABASE_URL
 if url.startswith("postgres://"):
  url="postgresql://"+url[len("postgres://"):]
 return url

def lock_db():
 if not DATABASE_URL:
  raise RuntimeError("DATABASE_URL is required for global device locking.")
 if PG_POOL is not None:
  return PG_POOL.connection()
 return psycopg.connect(pg_url(), row_factory=dict_row)

def init_global_lock_db():
 global _GLOBAL_DB_READY
 if not DATABASE_URL or _GLOBAL_DB_READY:
  return
 with _GLOBAL_DB_INIT_LOCK:
  if _GLOBAL_DB_READY:
   return
  with lock_db() as conn:
   with conn.cursor() as cur:
    cur.execute("""
     CREATE TABLE IF NOT EXISTS simulation_terminal_locks(
       session_date TEXT NOT NULL,
       poll_station TEXT NOT NULL,
       stream TEXT NOT NULL,
       county TEXT,
       constituency TEXT,
       ward TEXT,
       owner_token_hash TEXT NOT NULL,
       locked_at TEXT NOT NULL,
       released_at TEXT,
       closed_at TEXT,
       PRIMARY KEY(session_date,poll_station,stream)
     )
    """)
    cur.execute("ALTER TABLE simulation_terminal_locks ADD COLUMN IF NOT EXISTS closed_at TEXT")
    cur.execute("ALTER TABLE simulation_terminal_locks ADD COLUMN IF NOT EXISTS poll_station_code TEXT")
    cur.execute("""
     CREATE TABLE IF NOT EXISTS simulation_pdf_reports(
       id BIGSERIAL PRIMARY KEY,
       session_date TEXT NOT NULL,
       election TEXT NOT NULL,
       election_title TEXT NOT NULL,
       county TEXT, constituency TEXT, ward TEXT,
       poll_station TEXT NOT NULL, stream TEXT NOT NULL,
       closed_at TEXT, deposited_at TEXT NOT NULL,
       filename TEXT NOT NULL, pdf_data BYTEA NOT NULL,
       UNIQUE(session_date,election,poll_station,stream)
     )
    """)
    # Composite indexes are deliberately metadata-only: pdf_data is never part of an index.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election ON simulation_pdf_reports(election)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election_county ON simulation_pdf_reports(election,county)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election_constituency ON simulation_pdf_reports(election,constituency)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election_ward ON simulation_pdf_reports(election,ward)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election_poll_station ON simulation_pdf_reports(election,poll_station)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election_stream ON simulation_pdf_reports(election,stream)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_election_deposited ON simulation_pdf_reports(election,deposited_at DESC,id DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_pdf_geo ON simulation_pdf_reports(election,county,constituency,ward,poll_station,stream)")
    # Anonymous, simulation-only ballot events used by the separate live results dashboard.
    # No National ID, phone number or member identifier is stored here.
    cur.execute("""
     CREATE TABLE IF NOT EXISTS simulation_dashboard_vote_events(
       event_id TEXT PRIMARY KEY,
       session_date TEXT NOT NULL,
       election TEXT NOT NULL,
       candidate_id TEXT NOT NULL,
       candidate_name TEXT,
       county TEXT, constituency TEXT, ward TEXT,
       poll_station TEXT NOT NULL, stream TEXT NOT NULL,
       recorded_at TEXT NOT NULL
     )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_dash_events_date_election ON simulation_dashboard_vote_events(session_date,election)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sim_dash_events_geo ON simulation_dashboard_vote_events(session_date,election,county,constituency,ward,poll_station,stream)")
    cur.execute("""
     CREATE TABLE IF NOT EXISTS voter_admission_approvals(
       election_id TEXT NOT NULL,
       national_id TEXT NOT NULL,
       polling_station TEXT NOT NULL,
       approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
       approved_by TEXT NOT NULL,
       consumed_at TIMESTAMPTZ,
       consumed_station TEXT,
       consumed_stream TEXT,
       PRIMARY KEY(election_id,national_id)
     )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_voter_admission_station ON voter_admission_approvals(election_id,polling_station,approved_at DESC)")
    cur.execute("""
     CREATE TABLE IF NOT EXISTS voter_status(
       election_id TEXT NOT NULL,
       national_id TEXT NOT NULL,
       voted_at TIMESTAMPTZ,
       voted_at_station TEXT,
       verified_by TEXT,
       PRIMARY KEY(election_id,national_id)
     )
    """)
    cur.execute("""
     CREATE TABLE IF NOT EXISTS membership_change_requests(
       id BIGSERIAL PRIMARY KEY,
       national_id TEXT NOT NULL,
       request_type TEXT NOT NULL CHECK(request_type IN ('new','edit')),
       request_data JSONB NOT NULL,
       original_data JSONB,
       status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
       submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
       reviewed_at TIMESTAMPTZ,
       reviewed_by TEXT,
       rejection_reason TEXT
     )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_membership_requests_status_date ON membership_change_requests(status,submitted_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_membership_requests_national_id ON membership_change_requests(national_id,submitted_at DESC)")
   conn.commit()
  _GLOBAL_DB_READY = True

def token_hash(token):
 return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

def polling_location_label(poll_station,stream=""):
 station_label=re.sub(r"\s+"," ",re.sub(r"[_-]+"," ",str(poll_station or "").strip())).strip().upper()
 stream_label=re.sub(r"\s+"," ",re.sub(r"[_-]+"," ",str(stream or "").strip())).strip().upper()
 if station_label and stream_label.startswith(station_label+" "):
  stream_label=stream_label[len(station_label):].strip()
 parts=[]
 for label in (station_label,stream_label):
  if label and label not in parts:
   parts.append(label)
 return " — ".join(parts) or "THE RECORDED POLLING STATION / STREAM"

def already_voted_message(national_id,poll_station="",stream="",include_prefix=True):
 message=f"ID No {national_id} has already voted at {polling_location_label(poll_station,stream)} and cannot be admitted again."
 return f"VOTING NOT ALLOWED: {message}" if include_prefix else message

def entrance_approval_status(national_id,poll_station):
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    SELECT a.polling_station,a.approved_at,a.approved_by,a.consumed_at,
           a.consumed_station,a.consumed_stream,
           (a.approved_at >= NOW() - (%s * INTERVAL '1 minute')) AS approval_valid,
           v.voted_at,v.voted_at_station
    FROM voter_admission_approvals a
    LEFT JOIN voter_status v
      ON v.election_id=a.election_id AND v.national_id=a.national_id
    WHERE a.election_id=%s AND a.national_id=%s
   """,(ENTRANCE_APPROVAL_MINUTES,ELECTION_ID,national_id))
   row=cur.fetchone()
 if not row:
  return False,"Entrance approval not found. Return to the entrance verification official for positive identification.",None
 if row.get("voted_at"):
  voted_station=row.get("voted_at_station") or row.get("consumed_station") or row.get("polling_station")
  return False,already_voted_message(national_id,voted_station,row.get("consumed_stream"),include_prefix=False),None
 if row.get("consumed_at"):
  return False,"This entrance approval has already been used by a voting terminal.",None
 if not row.get("approval_valid"):
  return False,f"Entrance approval has expired. Ask the entrance official to verify the voter again (approval lasts {ENTRANCE_APPROVAL_MINUTES} minutes).",None
 if station_key(row.get("polling_station"))!=station_key(poll_station):
  return False,"Entrance approval was issued for a different polling station.",None
 approval={
  "national_id":str(national_id),
  "polling_station":str(row.get("polling_station") or ""),
  "approved_at":str(row.get("approved_at") or ""),
  "approved_by":str(row.get("approved_by") or "")
 }
 return True,"Entrance approval confirmed.",approval

def consume_entrance_approval(national_id,poll_station,stream):
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    SELECT polling_station,consumed_at,
           (approved_at >= NOW() - (%s * INTERVAL '1 minute')) AS approval_valid
    FROM voter_admission_approvals
    WHERE election_id=%s AND national_id=%s
    FOR UPDATE
   """,(ENTRANCE_APPROVAL_MINUTES,ELECTION_ID,national_id))
   row=cur.fetchone()
   if not row:
    return False,"Entrance approval not found."
   if row.get("consumed_at"):
    return False,"Entrance approval has already been used."
   if not row.get("approval_valid"):
    return False,"Entrance approval expired before ballot access. Return to the entrance official."
   if station_key(row.get("polling_station"))!=station_key(poll_station):
    return False,"Entrance approval belongs to a different polling station."
   cur.execute("""
    UPDATE voter_admission_approvals
    SET consumed_at=NOW(),consumed_station=%s,consumed_stream=%s
    WHERE election_id=%s AND national_id=%s AND consumed_at IS NULL
      AND approved_at >= NOW() - (%s * INTERVAL '1 minute')
    RETURNING consumed_at
   """,(poll_station,stream,ELECTION_ID,national_id,ENTRANCE_APPROVAL_MINUTES))
   changed=cur.fetchone()
  conn.commit()
 return (True,"Entrance approval consumed.") if changed else (False,"Entrance approval could not be claimed. Verify the voter again.")

def mark_shared_voter_voted(national_id,poll_station):
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    INSERT INTO voter_status(election_id,national_id,voted_at,voted_at_station,verified_by)
    VALUES(%s,%s,NOW(),%s,'SIMULATION_BALLOT')
    ON CONFLICT(election_id,national_id) DO UPDATE SET
      voted_at=COALESCE(voter_status.voted_at,EXCLUDED.voted_at),
      voted_at_station=COALESCE(voter_status.voted_at_station,EXCLUDED.voted_at_station),
      verified_by=COALESCE(voter_status.verified_by,EXCLUDED.verified_by)
   """,(ELECTION_ID,national_id,poll_station))
  conn.commit()

def global_lock_row(session_date,poll_station,stream):
 if not DATABASE_URL:
  return None
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    SELECT * FROM simulation_terminal_locks
    WHERE session_date=%s AND poll_station=%s AND stream=%s
    LIMIT 1
   """,(session_date,poll_station,stream))
   return cur.fetchone()

def claim_global_lock(lock_data, owner_token):
 """
 Atomically reserve one stream to one device for the day.
 Returns (True, row) when this device owns/claimed it; (False, row) when another device owns it.
 """
 if not DATABASE_URL:
  raise RuntimeError("Global device locking is not configured. Set DATABASE_URL to Render PostgreSQL.")
 init_global_lock_db()
 now=datetime.now().astimezone().isoformat(timespec="seconds")
 th=token_hash(owner_token)
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    INSERT INTO simulation_terminal_locks(
      session_date,poll_station,stream,county,constituency,ward,poll_station_code,owner_token_hash,locked_at,released_at
    ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)
    ON CONFLICT (session_date,poll_station,stream) DO NOTHING
   """,(
    lock_data["session_date"],lock_data["poll_station"],lock_data["stream"],
    lock_data.get("county",""),lock_data.get("constituency",""),lock_data.get("ward",""),
    lock_data.get("poll_station_code",""),th,now
   ))
   claimed=cur.rowcount==1
   cur.execute("""
    SELECT * FROM simulation_terminal_locks
    WHERE session_date=%s AND poll_station=%s AND stream=%s
    LIMIT 1
   """,(lock_data["session_date"],lock_data["poll_station"],lock_data["stream"]))
   row=cur.fetchone()
  conn.commit()
 if claimed:
  return True,row
 # A formally closed stream can never be reopened on the same election/session date.
 if row and row.get("closed_at"):
  return False,row

 # If an earlier record was explicitly released by the owning device, allow a fresh claim.
 if row and row.get("released_at"):
  with lock_db() as conn:
   with conn.cursor() as cur:
    cur.execute("""
     UPDATE simulation_terminal_locks
     SET county=%s,constituency=%s,ward=%s,poll_station_code=%s,owner_token_hash=%s,locked_at=%s,released_at=NULL
     WHERE session_date=%s AND poll_station=%s AND stream=%s AND released_at IS NOT NULL
    """,(
     lock_data.get("county",""),lock_data.get("constituency",""),lock_data.get("ward",""),
     lock_data.get("poll_station_code",""),th,now,lock_data["session_date"],lock_data["poll_station"],lock_data["stream"]
    ))
    reclaimed=cur.rowcount==1
    cur.execute("""
     SELECT * FROM simulation_terminal_locks
     WHERE session_date=%s AND poll_station=%s AND stream=%s
     LIMIT 1
    """,(lock_data["session_date"],lock_data["poll_station"],lock_data["stream"]))
    row=cur.fetchone()
   conn.commit()
  return reclaimed,row
 return bool(row and hmac.compare_digest(row.get("owner_token_hash",""),th)),row

def owns_global_lock(lock_data, owner_token):
 if not lock_data or not owner_token or not DATABASE_URL:
  return False
 row=global_lock_row(lock_data.get("session_date",""),lock_data.get("poll_station",""),lock_data.get("stream",""))
 if not row or row.get("released_at"):
  return False
 return hmac.compare_digest(row.get("owner_token_hash",""),token_hash(owner_token))

def mark_global_stream_closed(lock_data, owner_token):
 if not owns_global_lock(lock_data,owner_token):
  return False
 now=kenya_now().isoformat(timespec="seconds")
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    UPDATE simulation_terminal_locks
    SET closed_at=%s
    WHERE session_date=%s AND poll_station=%s AND stream=%s
      AND owner_token_hash=%s AND closed_at IS NULL
   """,(now,lock_data["session_date"],lock_data["poll_station"],lock_data["stream"],token_hash(owner_token)))
   ok=cur.rowcount==1
  conn.commit()
 return ok

def admin_reopen_global_stream(lock_data, owner_token):
 """
 Administrator-only override used to reopen a formally closed TRAINING stream.
 The new/current admin device becomes the lock owner, while all existing
 simulated votes remain intact.
 """
 if not DATABASE_URL or not lock_data or not owner_token:
  return False
 now=kenya_now().isoformat(timespec="seconds")
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    UPDATE simulation_terminal_locks
    SET owner_token_hash=%s, locked_at=%s, released_at=NULL, closed_at=NULL
    WHERE session_date=%s AND poll_station=%s AND stream=%s
      AND closed_at IS NOT NULL
   """,(
    token_hash(owner_token),now,lock_data["session_date"],
    lock_data["poll_station"],lock_data["stream"]
   ))
   ok=cur.rowcount==1
  conn.commit()
 return ok

def delete_repository_reports_for_stream(session_date,poll_station,stream):
 """Remove stale PDFs when a closed training stream is reopened.
 Fresh PDFs will be generated after the stream is closed again."""
 if not DATABASE_URL:
  return 0
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    DELETE FROM simulation_pdf_reports
    WHERE session_date=%s AND poll_station=%s AND stream=%s
   """,(session_date,poll_station,stream))
   n=cur.rowcount
  conn.commit()
 invalidate_repository_cache()
 return n

def release_global_lock(lock_data, owner_token):
 """
 Only the owning device can release its global lock.
 """
 if not owns_global_lock(lock_data,owner_token):
  return False
 now=datetime.now().astimezone().isoformat(timespec="seconds")
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    UPDATE simulation_terminal_locks
    SET released_at=%s
    WHERE session_date=%s AND poll_station=%s AND stream=%s
      AND owner_token_hash=%s AND released_at IS NULL
   """,(now,lock_data["session_date"],lock_data["poll_station"],lock_data["stream"],token_hash(owner_token)))
   ok=cur.rowcount==1
  conn.commit()
 return ok

# Create the lock table when the app starts. If PostgreSQL is temporarily unavailable,
# requests will fail closed when they attempt lock-sensitive actions.
try:
 init_global_lock_db()
except Exception as _lock_init_error:
 print("Global lock database initialization warning:",_lock_init_error)

TERMINAL_LOCK_COOKIE = "training_terminal_stream_lock"
TERMINAL_OWNER_COOKIE = "training_terminal_owner_token"
TERMINAL_ACTIVE_COOKIE = "training_terminal_active_stream"
TERMINAL_CLOSED_COOKIE = "training_terminal_closed_stream"
TERMINAL_LOCK_SALT = "training-terminal-stream-v22"

def terminal_serializer():
 return URLSafeSerializer(app.secret_key, salt=TERMINAL_LOCK_SALT)

def terminal_lock():
 raw=request.cookies.get(TERMINAL_LOCK_COOKIE,"")
 owner=request.cookies.get(TERMINAL_OWNER_COOKIE,"")
 if not raw or not owner:
  return None
 try:
  data=terminal_serializer().loads(raw)
  if isinstance(data,dict) and data.get("poll_station") and data.get("stream"):
   # A browser cookie alone is no longer sufficient. The central PostgreSQL
   # registry must confirm this exact device owns the stream.
   if owns_global_lock(data,owner):
    return data
 except (BadSignature,Exception):
  pass
 return None


def norm_key(v):
 return "_".join((v or "").strip().lower().replace("-", " ").split())

def agent_rows():
 try:
  with open(managed_data_file(AGENTS_LOGIN), encoding="utf-8-sig", errors="replace", newline="") as f:
   return list(csv.DictReader(f))
 except Exception:
  return []


_REGISTERED_TOTAL_CACHE={"signature":None,"value":0}
def authoritative_registered_total():
 """Sum the active agents register once; dashboard feeds reuse this exact value."""
 path=managed_data_file(AGENTS_LOGIN)
 try: signature=(path,os.path.getmtime(path),os.path.getsize(path))
 except OSError: return 0
 if _REGISTERED_TOTAL_CACHE.get("signature")==signature:
  return int(_REGISTERED_TOTAL_CACHE.get("value") or 0)
 total=sum(to_int(r.get("total_registered_voters",0)) for r in agent_rows())
 _REGISTERED_TOTAL_CACHE.update({"signature":signature,"value":total})
 return total

def to_int(v):
 try: return int(float(str(v or "0").replace(",","").strip()))
 except Exception: return 0

def registered_voter_index():
 by_stream={}
 for r in agent_rows():
  key=norm_key(r.get("poll_station_name",""))
  if key: by_stream[key]=to_int(r.get("total_registered_voters",0))
 return by_stream


def polling_register_code_key(value):
 """Normalize full or spreadsheet-scientific polling stream codes."""
 try:
  return f"{float(str(value or '').strip()):.5E}"
 except Exception:
  return ""


def registered_voters_for_stream(poll_station_code, stream):
 """Return the active stream's electorate from the agents polling register."""
 stream_key=norm_key(stream)
 station_code=re.sub(r"\D+","",str(poll_station_code or ""))
 suffix_match=re.search(r"(?:stream[_\s-]*)(\d+)\s*$",str(stream or ""),re.I)
 target_code=""
 if station_code and suffix_match:
  target_code=polling_register_code_key(station_code+f"{int(suffix_match.group(1)):02d}")

 name_matches=[]
 for r in agent_rows():
  if norm_key(r.get("poll_station_name",""))!=stream_key:
   continue
  registered=to_int(r.get("total_registered_voters",0))
  name_matches.append(registered)
  if target_code and polling_register_code_key(r.get("poll_station_code",""))==target_code:
   return registered

 # Legacy sessions may predate station-code capture. Use a name only when it is unique.
 if len(name_matches)==1:
  return name_matches[0]
 return 0

def hierarchy_rows():
 rows=[]
 try:
  with open(managed_data_file(COUNTY_MAIN), encoding="utf-8-sig", errors="replace", newline="") as f:
   rows=list(csv.DictReader(f))
 except Exception:
  pass
 return rows

# V22.73: build the county hierarchy once per Gunicorn worker and serve only
# the selected branch. This avoids sending all 46,000+ stream rows to the
# browser just to populate the first County dropdown.
_HIERARCHY_CACHE = None
_HIERARCHY_LOCK = threading.Lock()
_REGISTER_GEO_INDEX = None

def _hierarchy_cache():
 global _HIERARCHY_CACHE
 if _HIERARCHY_CACHE is not None:
  return _HIERARCHY_CACHE
 with _HIERARCHY_LOCK:
  if _HIERARCHY_CACHE is not None:
   return _HIERARCHY_CACHE
  rows=hierarchy_rows()
  counties=[]
  constituencies={}
  wards={}
  stations={}
  streams={}
  for r in rows:
   kind=(r.get("list_name") or "").strip()
   name=(r.get("name") or "").strip()
   if not name:
    continue
   item={"name":name,"label":(r.get("label") or name).strip()}
   if kind=="county":
    counties.append(item)
   elif kind=="constituency":
    key=norm_key(r.get("county_key",""))
    item["county_key"]=r.get("county_key","")
    constituencies.setdefault(key,[]).append(item)
   elif kind=="ward":
    key=norm_key(r.get("constituency_key",""))
    item["constituency_key"]=r.get("constituency_key","")
    wards.setdefault(key,[]).append(item)
   elif kind=="poll_station":
    key=norm_key(r.get("ward_key",""))
    item["ward_key"]=r.get("ward_key","")
    item["poll_station_code"]=r.get("poll_station_code","")
    stations.setdefault(key,[]).append(item)
   elif kind=="poll_station_stream":
    key=norm_key(r.get("poll_station_key",""))
    item["poll_station_key"]=r.get("poll_station_key","")
    streams.setdefault(key,[]).append(item)
  _HIERARCHY_CACHE={
   "counties":counties,
   "constituencies":constituencies,
   "wards":wards,
   "poll_stations":stations,
   "streams":streams,
  }
 return _HIERARCHY_CACHE

def hierarchy_payload():
 # Kept for backward compatibility with any older client that still requests
 # the complete hierarchy. The new stream-control page does not use it.
 h=_hierarchy_cache()
 return {
  "counties":h["counties"],
  "constituencies":[x for rows in h["constituencies"].values() for x in rows],
  "wards":[x for rows in h["wards"].values() for x in rows],
  "poll_stations":[x for rows in h["poll_stations"].values() for x in rows],
  "streams":[x for rows in h["streams"].values() for x in rows],
 }

@app.get("/api/hierarchy")
def api_hierarchy():
 h=_hierarchy_cache()
 level=(request.args.get("level") or "").strip().lower()
 parent=norm_key(request.args.get("parent") or "")
 if level=="counties":
  payload={"rows":h["counties"]}
 elif level=="constituencies":
  payload={"rows":h["constituencies"].get(parent,[])}
 elif level=="wards":
  payload={"rows":h["wards"].get(parent,[])}
 elif level in ("stations","poll_stations"):
  payload={"rows":h["poll_stations"].get(parent,[])}
 elif level=="streams":
  payload={"rows":h["streams"].get(parent,[])}
 else:
  payload=hierarchy_payload()
 resp=jsonify(payload)
 # county_main.csv changes only when a new build is deployed, so browser/proxy
 # caching is safe and makes repeated navigation virtually instant.
 resp.headers["Cache-Control"]="public, max-age=3600"
 return resp


def kobo_headers():
 return {"Authorization": f"Token {KOBO_API_TOKEN}"}

def field(row,*names):
 for n in names:
  v=row.get(n)
  if v not in (None,""):
   return str(v).strip()
 return ""

def station_key(v):
 return re.sub(r"[^a-z0-9]+","_",str(v or "").strip().lower()).strip("_")

def _lookup_member_kobo(national_id):
 if not MEMBERSHIP_ASSET_UID or not KOBO_API_TOKEN:
  raise RuntimeError("ODM membership connection is not configured.")
 url=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/data/"
 q={"basics/national_id_no":str(national_id)}
 r=requests.get(url,headers=kobo_headers(),params={"query":json.dumps(q)},timeout=25)
 r.raise_for_status()
 data=r.json()
 rows=data.get("results",data if isinstance(data,list) else [])
 if not rows:
  return None
 # Most recent matching submission if duplicates exist.
 rows=sorted(rows,key=lambda x:x.get("_id",0),reverse=True)
 return rows[0]

def _kobo_media_files():
 results=[]
 url=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/files/"
 while url:
  r=requests.get(url,headers=kobo_headers(),timeout=30)
  r.raise_for_status()
  payload=r.json()
  results.extend(payload.get("results",[]))
  url=payload.get("next")
 return results

def _load_membership_csv():
 now=time.time()
 if _MEMBERSHIP_CSV_CACHE["rows"] and now-_MEMBERSHIP_CSV_CACHE["loaded_at"]<MEMBERSHIP_CSV_CACHE_SECONDS:
  return _MEMBERSHIP_CSV_CACHE["rows"]
 content=None
 media={}
 media_error=None
 if MEMBERSHIP_ASSET_UID and KOBO_API_TOKEN:
  try:
   for item in _kobo_media_files():
    filename=str((item.get("metadata") or {}).get("filename") or "").strip()
    if filename:
     media[filename.replace("\\","/").split("/")[-1].lower()]=item
   csv_item=media.get(MEMBERSHIP_CSV_FILENAME.lower())
   if csv_item and csv_item.get("content"):
    r=requests.get(csv_item["content"],headers=kobo_headers(),timeout=60)
    r.raise_for_status()
    content=r.content
  except Exception as exc:
   media_error=exc
 if content is None:
  local_path=os.path.join(app.root_path,MEMBERSHIP_CSV_FILENAME)
  if os.path.isfile(local_path):
   with open(local_path,"rb") as source:
    content=source.read()
  elif media_error:
   raise RuntimeError(f"Unable to load {MEMBERSHIP_CSV_FILENAME} from Kobo media: {media_error}")
  else:
   return {}
 rows={}
 for raw in csv.DictReader(StringIO(content.decode("utf-8-sig",errors="replace"))):
  row={str(k or "").strip():("" if v is None else str(v).strip()) for k,v in raw.items()}
  national_id=re.sub(r"\D","",row.get("national_id_no",""))
  if national_id:
   rows[national_id]=row
 _MEMBERSHIP_CSV_CACHE.update(loaded_at=now,rows=rows,media=media)
 return rows

def _membership_csv_row(national_id):
 row=_load_membership_csv().get(re.sub(r"\D","",str(national_id or "")))
 if not row:
  return None
 return {
  "_id":"membership-csv:"+row.get("national_id_no",""),
  "_membership_source":MEMBERSHIP_CSV_FILENAME,
  "basics/national_id_no":row.get("national_id_no",""),
  "members_particulars/first_name":row.get("first_name",""),
  "members_particulars/other_names":row.get("middle_name",""),
  "members_particulars/surname":row.get("surname",""),
  "members_particulars/odm_membership_no":row.get("odm_membership_no",""),
  "electorals_units/selected_poll_station1":row.get("poll_station",""),
  "electorals_units/poll_station_label":row.get("poll_station",""),
  "basics/id_photo":row.get("member_id_photo",""),
  "basics/passport_photo":row.get("member_passport_photo",""),
 }

def lookup_member(national_id):
 """Prefer live Kobo and use membership_registration.csv as the fallback."""
 live_error=None
 try:
  row=_lookup_member_kobo(national_id)
  if row:
   return row
 except Exception as exc:
  live_error=exc
 row=_membership_csv_row(national_id)
 if row:
  return row
 if live_error:
  raise live_error
 return None

def member_view(row):
 first=field(row,"members_particulars/first_name","members_particulars/first_name1")
 other=field(row,"members_particulars/other_names","members_particulars/other_names1")
 surname=field(row,"members_particulars/surname","members_particulars/surname1")
 full=" ".join(x for x in (first,other,surname) if x).strip()
 return {
  "submission_id":row.get("_id"),
  "national_id":field(row,"basics/national_id_no"),
  "full_name":full or field(row,"stored_particulars_confirmed/full_name"),
  "membership_no":field(row,"members_particulars/odm_membership_no","stored_particulars_confirmed/odm_membership_no_confirmed"),
  "polling_station_key":field(
    row,
    "electorals_units/selected_poll_station1",
    "particulars_confirmation/selected_poll_station1_confirmation",
    "stored_particulars_confirmed/selected_poll_station1_calculation",
    "stored_particulars_confirmed/selected_poll_station1_confirmed"
  ),
  "polling_station_label":field(
    row,
    "electorals_units/poll_station_label",
    "electorals_units/selected_poll_station1"
  ),
  "id_photo_name":field(row,"basics/id_photo"),
  "passport_photo_name":field(row,"basics/passport_photo"),
 }

def submission_detail(submission_id):
 url=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/data/{submission_id}/"
 r=requests.get(url,headers=kobo_headers(),timeout=25)
 r.raise_for_status()
 return r.json()

def attachment_url(row,kind):
 field_name="basics/id_photo" if kind=="id" else "basics/passport_photo"
 wanted=field(row,field_name)
 atts=row.get("_attachments") or []
 # Prefer exact question xpath/field match.
 for a in atts:
  xpath=str(a.get("question_xpath") or a.get("question_name") or "")
  if field_name in xpath:
   return a.get("download_url") or a.get("url")
 # Fall back to matching stored filename.
 if wanted:
  for a in atts:
   fn=str(a.get("filename") or "")
   if fn==wanted or fn.endswith("/"+wanted):
    return a.get("download_url") or a.get("url")
 return None

def previous_vote(voter_id):
 c=con()
 row=c.execute("SELECT poll_station, stream FROM demo_votes WHERE voter_session=? LIMIT 1",(voter_id,)).fetchone()
 c.close()
 return row


def today_iso(): return kenya_now().date().isoformat()

def stream_session(poll_station,stream):
 c=con(); row=c.execute("SELECT * FROM stream_sessions WHERE session_date=? AND poll_station=? AND stream=?",
 (today_iso(),poll_station,stream)).fetchone(); c.close(); return row

def time_status(ts,expected):
 if not ts or not expected: return None
 try: return datetime.fromisoformat(ts).strftime("%H:%M")==expected
 except Exception: return None


def closed_stream_cookie():
 raw=request.cookies.get(TERMINAL_CLOSED_COOKIE,"")
 if not raw:
  return None
 try:
  data=terminal_serializer().loads(raw)
 except BadSignature:
  return None
 if not isinstance(data,dict):
  return None
 if not data.get("session_date") or not data.get("poll_station") or not data.get("stream"):
  return None
 return data

def terminal_active_after_reset(lock=None):
 if not lock:
  lock=terminal_lock()
 if not lock:
  return False
 raw=request.cookies.get(TERMINAL_ACTIVE_COOKIE,"")
 if not raw:
  return False
 try:
  active=terminal_serializer().loads(raw)
 except BadSignature:
  return False
 if not isinstance(active,dict):
  return False
 return all(
  str(active.get(k,""))==str(lock.get(k,""))
  for k in ("session_date","poll_station","stream")
 )

def locked_stream_vote_count(lock):
 if not lock:
  return 0
 c=con()
 n=c.execute(
  "SELECT COUNT(*) n FROM demo_votes WHERE poll_station=? AND stream=?",
  (lock.get("poll_station",""),lock.get("stream",""))
 ).fetchone()["n"]
 c.close()
 return n

def stream_distinct_voter_count(ref):
 # A completed simulated ballot writes one row per election. Count distinct
 # voter sessions so a stream with zero actual participants cannot produce
 # or deposit an empty tally PDF. SKIP choices still count as participation.
 if not ref:
  return 0
 station=str(ref.get("poll_station","") or "")
 stream=str(ref.get("stream","") or "")
 if not station or not stream:
  return 0
 c=con()
 try:
  row=c.execute(
   "SELECT COUNT(DISTINCT voter_session) n FROM demo_votes WHERE poll_station=? AND stream=?",
   (station,stream)
  ).fetchone()
  return int(row["n"] or 0) if row else 0
 finally:
  c.close()

@app.post("/terminal/reset")
def terminal_reset():
 lock=terminal_lock()
 if not lock:
  return render_template(
   "stream_control.html",row=None,poll_station="",stream="",
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="Terminal reset denied: this browser/device does not own a valid central stream lock."
  )

 votes=locked_stream_vote_count(lock)
 row=stream_session(lock.get("poll_station",""),lock.get("stream",""))
 can_reset=(votes==0) or (row and row["closed_at"])
 if not can_reset:
  return render_template(
   "stream_control.html",row=row,poll_station=lock.get("poll_station",""),
   stream=lock.get("stream",""),open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="Terminal reset blocked: simulated votes already exist in this open stream. Close the stream before changing station."
  )

 owner=request.cookies.get(TERMINAL_OWNER_COOKIE,"")
 if not release_global_lock(lock,owner):
  return render_template(
   "stream_control.html",row=row,poll_station=lock.get("poll_station",""),
   stream=lock.get("stream",""),open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="Terminal reset denied: only the device that originally locked this stream can release it."
  )

 session.clear()
 session["awaiting_new_stream_after_reset"]=True
 session["terminal_reset_completed"]=True
 resp=redirect(url_for("stream_control"))
 resp.delete_cookie(TERMINAL_LOCK_COOKIE)
 resp.delete_cookie(TERMINAL_OWNER_COOKIE)
 resp.delete_cookie(TERMINAL_ACTIVE_COOKIE)
 resp.delete_cookie(TERMINAL_CLOSED_COOKIE)
 return resp

@app.get("/stream-control")
def stream_control():
 current_lock=terminal_lock()
 ps=request.args.get("poll_station","").strip()
 st=request.args.get("stream","").strip()

 # When arriving from the voter-verification screen the URL may not contain
 # station/stream query parameters. Use the authoritative device lock instead.
 if current_lock:
  if not ps:
   ps=current_lock.get("poll_station","")
  if not st:
   st=current_lock.get("stream","")

 row=stream_session(ps,st) if ps and st else None
 owns_current=bool(
  current_lock and row
  and current_lock.get("poll_station")==row["poll_station"]
  and current_lock.get("stream")==row["stream"]
 )

 return render_template(
  "stream_control.html",
  row=row,poll_station=ps,stream=st,
  open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
  report_header_image_url=REPORT_HEADER_IMAGE_URL,
  post_reset_new_stream_locked=bool(session.get("post_reset_new_stream_locked")),
  reset_required=bool(current_lock and not terminal_active_after_reset(current_lock)),
  can_close_now=official_close_reached(),
  official_close_time=close_time_message(),
  owns_current_stream=owns_current,
  stream_admin_logged_in=repository_admin_logged_in(),
  reopened_notice=session.pop("stream_reopened_notice","")
 )

@app.post("/stream/admin-reopen")
def admin_reopen_stream():
 if not repository_admin_logged_in():
  ps=(request.form.get("poll_station") or "").strip()
  st=(request.form.get("stream") or "").strip()
  nxt=url_for("stream_control",poll_station=ps,stream=st)
  return redirect(url_for("repository_admin_login",next=nxt))

 ps=(request.form.get("poll_station") or "").strip()
 st=(request.form.get("stream") or "").strip()
 if not ps or not st:
  return redirect(url_for("stream_control"))

 row=stream_session(ps,st)
 central=global_lock_row(today_iso(),ps,st) if DATABASE_URL else None
 if not row or not row["closed_at"] or not central or not central.get("closed_at"):
  return render_template(
   "stream_control.html",row=row,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="ADMIN REOPEN BLOCKED: this stream is not recorded as formally closed in both the local and central training records.",
   can_close_now=official_close_reached(),official_close_time=close_time_message(),
   owns_current_stream=False,stream_admin_logged_in=True
  )

 owner_token=request.cookies.get(TERMINAL_OWNER_COOKIE,"") or secrets.token_urlsafe(32)
 lock_data={
  "session_date":today_iso(),
  "county":central.get("county") or row["county"] or "",
  "constituency":central.get("constituency") or row["constituency"] or "",
  "ward":central.get("ward") or row["ward"] or "",
  "poll_station":ps,"stream":st,
  "poll_station_code":central.get("poll_station_code") or row["poll_station_code"] or ""
 }
 try:
  if not admin_reopen_global_stream(lock_data,owner_token):
   raise RuntimeError("central closed-stream record could not be reopened")
 except Exception as exc:
  return render_template(
   "stream_control.html",row=row,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"ADMIN REOPEN FAILED: {exc}",
   can_close_now=False,official_close_time=close_time_message(),
   owns_current_stream=False,stream_admin_logged_in=True
  )

 # Preserve every existing simulated vote; only reopen the stream status.
 c=con()
 c.execute("UPDATE stream_sessions SET closed_at=NULL WHERE id=?",(row["id"],))
 c.commit(); c.close()

 # PDFs generated at the earlier close are now stale because additional voters
 # may participate. Remove only this stream's repository copies; the final close
 # will generate fresh reports containing the complete totals.
 try:
  delete_repository_reports_for_stream(today_iso(),ps,st)
 except Exception as exc:
  app.logger.warning("Could not remove stale repository PDFs during reopen: %s",exc)

 session["stream_reopened_notice"]="ADMIN REOPEN COMPLETE: this training stream is open again. Existing votes were preserved and new eligible voters may continue."
 session.pop("post_reset_new_stream_locked",None)
 session.pop("awaiting_new_stream_after_reset",None)
 session.pop("terminal_reset_completed",None)

 resp=redirect(url_for("stream_control",poll_station=ps,stream=st))
 resp.set_cookie(TERMINAL_LOCK_COOKIE,terminal_serializer().dumps(lock_data),
                 httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
 resp.set_cookie(TERMINAL_OWNER_COOKIE,owner_token,
                 httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
 resp.set_cookie(TERMINAL_ACTIVE_COOKIE,terminal_serializer().dumps({
   "session_date":today_iso(),"poll_station":ps,"stream":st
  }),httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
 resp.delete_cookie(TERMINAL_CLOSED_COOKIE)
 return resp

@app.post("/stream/open")
def open_stream():
 f=request.form; ps=f.get("poll_station","").strip(); st=f.get("stream","").strip()

 if not ps or not st:
  return render_template(
   "stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="OPENING BLOCKED: select a polling station and stream, then try again."
  ),400

 # A formally closed stream can only be reopened through the authenticated administrator override.
 try:
  previous_session=stream_session(ps,st)
 except Exception as exc:
  app.logger.exception("Could not read local stream state for %s / %s",ps,st)
  return render_template(
   "stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING TEMPORARILY UNAVAILABLE: the terminal stream database did not respond. Wait a few seconds and retry. {exc}"
  ),503
 if previous_session and previous_session["closed_at"]:
  return render_template(
   "stream_control.html",row=previous_session,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="REOPENING BLOCKED: this voting stream is formally closed. An administrator must use the Admin Reopen control.",
   can_close_now=official_close_reached(),official_close_time=close_time_message()
  )

 try:
  central_existing=global_lock_row(today_iso(),ps,st) if DATABASE_URL else None
 except Exception as exc:
  app.logger.exception("Could not read central lock state for %s / %s",ps,st)
  return render_template(
   "stream_control.html",row=previous_session,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING TEMPORARILY UNAVAILABLE: the central lock service did not respond. No stream was opened or reset. Wait a few seconds and retry. {exc}"
  ),503
 if central_existing and central_existing.get("closed_at"):
  return render_template(
   "stream_control.html",row=previous_session,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="REOPENING BLOCKED: this voting stream is formally closed. An administrator must use the Admin Reopen control.",
   can_close_now=official_close_reached(),official_close_time=close_time_message()
  )

 # If this device already owns a valid lock, do not allow it to silently move to another stream.
 existing_local=terminal_lock()
 if existing_local and (existing_local.get("poll_station")!=ps or existing_local.get("stream")!=st):
  return render_template(
   "stream_control.html",
   row=stream_session(existing_local.get("poll_station",""),existing_local.get("stream","")),
   poll_station=existing_local.get("poll_station",""),stream=existing_local.get("stream",""),
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="This device is already centrally locked to another polling-station stream. Use the owner-device reset procedure first."
  )

 c=None
 try:
  c=con()
  precast=c.execute("SELECT COUNT(*) n FROM demo_votes WHERE poll_station=? AND stream=?",(ps,st)).fetchone()["n"]
 except Exception as exc:
  app.logger.exception("Could not complete pre-cast check for %s / %s",ps,st)
  return render_template(
   "stream_control.html",row=previous_session,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING TEMPORARILY UNAVAILABLE: the zero-vote check could not be completed. No stream was opened or reset. Wait a few seconds and retry. {exc}"
  ),503
 finally:
  if c is not None:c.close()
 if precast:
  return render_template("stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING BLOCKED: {precast} simulated ballot records already exist in this stream.")
 lock_data={"county":f.get("county","").strip(),"constituency":f.get("constituency","").strip(),
            "ward":f.get("ward","").strip(),"poll_station":ps,"stream":st,
            "poll_station_code":f.get("poll_station_code","").strip(),"session_date":today_iso()}
 owner_token=request.cookies.get(TERMINAL_OWNER_COOKIE,"") or secrets.token_urlsafe(32)

 try:
  claimed,central_row=claim_global_lock(lock_data,owner_token)
 except Exception as exc:
  return render_template(
   "stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING BLOCKED: central device-lock database unavailable. {exc}"
  )

 if not claimed:
  locked_at=(central_row or {}).get("locked_at","")
  return render_template(
   "stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING BLOCKED: {ps} / {st} is already locked to another device. Lock time: {locked_at or 'recorded centrally'}. This device cannot unlock or take over that stream."
  )

 now=kenya_now().isoformat(timespec="seconds")
 try: opening_lat=float(f.get("opening_lat","")) if f.get("opening_lat","") else None
 except: opening_lat=None
 try: opening_lon=float(f.get("opening_lon","")) if f.get("opening_lon","") else None
 except: opening_lon=None
 try: opening_accuracy=float(f.get("opening_accuracy","")) if f.get("opening_accuracy","") else None
 except: opening_accuracy=None

 c=None
 try:
  c=con()
  c.execute("""INSERT OR IGNORE INTO stream_sessions
  (session_date,county,constituency,ward,poll_station,stream,poll_station_code,opened_at,opening_zero_votes,opening_lat,opening_lon,opening_accuracy)
  VALUES(?,?,?,?,?,?,?,?,1,?,?,?)""",(today_iso(),f.get("county",""),f.get("constituency",""),f.get("ward",""),ps,st,f.get("poll_station_code",""),now,opening_lat,opening_lon,opening_accuracy))
  c.commit()
 except Exception:
  if c is not None:
   try: c.rollback()
   except Exception: pass
  # Do not strand a central lock when the local stream record could not be
  # created. Releasing it lets the same terminal safely retry the operation.
  try:
   release_global_lock(lock_data,owner_token)
  except Exception as release_exc:
   app.logger.warning("Could not release central lock after local open failure: %s",release_exc)
  app.logger.exception("Local stream creation failed for %s / %s",ps,st)
  return render_template(
   "stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="OPENING FAILED: the terminal database could not create this stream. The central lock was released; please select the stream and try again."
  )
 finally:
  if c is not None:
   c.close()

 activated_after_reset=bool(
  session.pop("awaiting_new_stream_after_reset",False)
  and session.get("terminal_reset_completed")
 )
 if activated_after_reset:
  session["post_reset_new_stream_locked"]=True
 else:
  session.pop("post_reset_new_stream_locked",None)

 resp=redirect(url_for("stream_control",poll_station=ps,stream=st))
 resp.set_cookie(TERMINAL_LOCK_COOKIE,terminal_serializer().dumps(lock_data),
                 httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
 resp.set_cookie(TERMINAL_OWNER_COOKIE,owner_token,
                 httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
 # Every successful opening activates this stream on the owning device. Earlier
 # builds wrote this cookie only after a terminal reset, so a first-time GPS
 # opening was immediately treated as inactive and the Training Ballot link was
 # omitted on the redirected control page.
 resp.set_cookie(
  TERMINAL_ACTIVE_COOKIE,
  terminal_serializer().dumps({
   "session_date":lock_data["session_date"],
   "poll_station":lock_data["poll_station"],
   "stream":lock_data["stream"]
  }),
  httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400
 )
 return resp

@app.post("/stream/close")
def close_stream():
 ps=request.form.get("poll_station","").strip(); st=request.form.get("stream","").strip()
 lock=terminal_lock()

 if not lock or lock.get("poll_station")!=ps or lock.get("stream")!=st:
  return render_template(
   "stream_control.html",row=stream_session(ps,st),poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="Close denied: only the device that owns the central lock for this polling-station stream can close it.",
   can_close_now=official_close_reached(),official_close_time=close_time_message()
  )

 row=stream_session(ps,st)
 if not row:
  return redirect(url_for("stream_control",poll_station=ps,stream=st))

 if row["closed_at"]:
  return render_template(
   "stream_control.html",row=row,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="This voting stream is formally closed. An administrator must use the Admin Reopen control.",
   can_close_now=False,official_close_time=close_time_message()
  )

 # TESTING: official closing is temporarily fixed at 08:00 East Africa Time.
 if not official_close_reached():
  return render_template(
   "stream_control.html",row=row,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"CLOSING BLOCKED: voting cannot be closed before {close_time_message()}.",
   can_close_now=False,official_close_time=close_time_message()
  )

 owner=request.cookies.get(TERMINAL_OWNER_COOKIE,"")
 if not mark_global_stream_closed(lock,owner):
  return render_template(
   "stream_control.html",row=row,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error="Closing blocked: the central lock could not be marked permanently closed.",
   can_close_now=True,official_close_time=close_time_message()
  )

 now=kenya_now().isoformat(timespec="seconds")
 c=con()
 c.execute("UPDATE stream_sessions SET closed_at=? WHERE id=? AND closed_at IS NULL",(now,row["id"]))
 c.commit(); c.close()

 # Once closed, voting stops unless an authenticated administrator explicitly reopens this training stream.
 # Preserve a signed read-only reference so the closed stream's tally dashboard
 # remains available for opening, viewing and printing.
 resp=redirect(url_for("tallies"))
 resp.delete_cookie(TERMINAL_ACTIVE_COOKIE)
 resp.set_cookie(
  TERMINAL_CLOSED_COOKIE,
  terminal_serializer().dumps({
   "session_date":lock.get("session_date",today_iso()),
   "poll_station":ps,
   "stream":st,
   "poll_station_code":lock.get("poll_station_code","")
  }),
  httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400
 )
 return resp

@app.get("/stream/report")
def stream_report():
 ps=request.args.get("poll_station","").strip(); st=request.args.get("stream","").strip()
 row=stream_session(ps,st)
 if not row:return redirect(url_for("stream_control",poll_station=ps,stream=st))
 c=con(); votes=c.execute("SELECT COUNT(DISTINCT voter_session) n FROM demo_votes WHERE poll_station=? AND stream=?",(ps,st)).fetchone()["n"]; c.close()

 geo={
  "county":row["county"] or "",
  "constituency":row["constituency"] or "",
  "ward":row["ward"] or "",
  "poll_station":row["poll_station"] or "",
  "stream":row["stream"] or ""
 }

 candidate_error=""
 try:
  catalog=candidate_portal_catalog(geo)
 except Exception as exc:
  catalog={k:[] for k,_,_ in ELECTIONS}
  candidate_error=f"Registered candidate names could not be loaded from the Candidate Registration Portal: {exc}"

 position_rows=[
  {"key":"president","title":"President","candidates":catalog.get("president",[])},
  {"key":"governor","title":"Governor","candidates":catalog.get("governor",[])},
  {"key":"senator","title":"Senator","candidates":catalog.get("senator",[])},
  {"key":"woman_rep","title":"Woman Representative","candidates":catalog.get("woman_rep",[])},
  {"key":"mna","title":"MNA","candidates":catalog.get("mna",[])},
  {"key":"mca","title":"MCA","candidates":catalog.get("mca",[])}
 ]

 return render_template("stream_report.html",row=row,
  open_time=VOTING_OPEN_TIME,
  report_header_image_url=REPORT_HEADER_IMAGE_URL,
  open_ok=time_status(row["opened_at"],VOTING_OPEN_TIME),
  position_rows=position_rows,
  candidate_error=candidate_error)

def voting_stream_ready():
 lock=terminal_lock()
 if not lock or lock.get("session_date")!=today_iso():
  return False,None,None
 row=stream_session(lock.get("poll_station",""),lock.get("stream",""))
 if not row or not row["opened_at"] or row["closed_at"]:
  return False,lock,row
 # A previous/stale device lock is not active for voter entry.
 # It becomes active only after this device resets and opens a new stream.
 # The activation is stored in a signed cookie, not the voter session.
 if not terminal_active_after_reset(lock):
  return False,lock,row
 return True,lock,row

@app.get("/")
def home():
 session.pop("post_reset_new_stream_locked",None)
 ready,lock,row=voting_stream_ready()
 return render_template("verify.html",stream_ready=ready,stream_row=row)

@app.post("/start")
def start():
 ready,lock,ss=voting_stream_ready()
 if not ready:
  return render_template(
   "verify.html",
   stream_ready=False,
   stream_row=ss,
   error="Voter ID entry is blocked until this computer has been assigned to an opened voting stream and the pre-opening report has been generated."
  )

 voter=request.form.get("voter_id","").strip()
 if not voter:
  return render_template("verify.html",stream_ready=True,stream_row=ss,error="Enter a demo voter ID.")

 previous=previous_vote(voter)
 if previous:
  return render_template("verify.html",error=already_voted_message(voter,previous["poll_station"],previous["stream"]))

 geo={k:lock.get(k,"") for k in ("county","constituency","ward","poll_station","stream")}

 try:
  entrance_ok,entrance_message,entrance_approval=entrance_approval_status(voter,geo.get("poll_station",""))
 except Exception as e:
  return render_template("verify.html",stream_ready=True,stream_row=ss,error=f"Unable to check entrance approval: {e}")
 if not entrance_ok:
  return render_template("verify.html",stream_ready=True,stream_row=ss,error=f"VOTING NOT ALLOWED: {entrance_message}")

 try:
  row=lookup_member(voter)
 except Exception as e:
  return render_template("verify.html",error=f"Unable to verify voter from the membership lookup sources: {e}")

 if not row:
  return render_template("verify.html",error=f"National ID {voter} was not found in Kobo submissions or membership_registration.csv.")

 member=member_view(row)

 membership_station = member.get("polling_station_key") or member.get("polling_station_label") or ""
 locked_station = geo.get("poll_station","")
 station_match = bool(membership_station and locked_station and station_key(membership_station)==station_key(locked_station))

 session.clear()
 session["pending_voter_id"]=voter
 session["membership_submission_id"]=member["submission_id"]
 session["membership_verified"]=True
 session["membership_station_match"]=station_match
 session["membership_station"]=membership_station
 session["entrance_approval_checked"]=True
 session["entrance_approval"]=entrance_approval
 session["geo"]=geo
 return render_template("member_verify.html",member=member,geo=geo,station_match=station_match,entrance_approval_confirmed=True,entrance_approval=entrance_approval)

@app.post("/membership/confirm")
def confirm_member():
 if not session.get("membership_verified") or not session.get("pending_voter_id"):
  return redirect(url_for("home"))
 if not session.get("membership_station_match"):
  geo=session.get("geo",{})
  voter=session.get("pending_voter_id")
  try:
   row=lookup_member(voter)
   member=member_view(row) if row else {}
  except Exception:
   member={}
  return render_template(
   "member_verify.html",
   member=member,
   geo=geo,
   station_match=False,
   error="VOTING NOT ALLOWED: the polling station recorded in the ODM Membership Registration Database does not match this terminal's locked polling station."
  )
 voter=session.get("pending_voter_id")
 previous=previous_vote(voter)
 if previous:
  session.clear()
  return render_template("verify.html",error=already_voted_message(voter,previous["poll_station"],previous["stream"]))
 geo=session.get("geo",{})
 lock=terminal_lock()
 if not lock or any(geo.get(k,"")!=lock.get(k,"") for k in ("county","constituency","ward","poll_station","stream")):
  session.clear()
  return render_template("verify.html",error="Terminal stream verification changed. Restart voter verification.")
 ss=stream_session(geo.get("poll_station",""),geo.get("stream",""))
 if not ss or ss["closed_at"]:
  session.clear()
  return render_template("verify.html",error="This stream is not open for simulated voting.")
 if not session.get("entrance_approval_checked") or not session.get("entrance_approval"):
  session.clear()
  return render_template("verify.html",error="Entrance approval was not checked. Restart voter verification.")
 try:
  approval_claimed,approval_message=consume_entrance_approval(voter,geo.get("poll_station",""),geo.get("stream",""))
 except Exception as e:
  return render_template("verify.html",stream_ready=True,stream_row=ss,error=f"Unable to claim entrance approval: {e}")
 if not approval_claimed:
  session.clear()
  return render_template("verify.html",error=f"VOTING NOT ALLOWED: {approval_message}")
 session["voter_id"]=voter
 session["entrance_approval_consumed"]=True
 session["choices"]={}
 session.pop("pending_voter_id",None)
 return redirect(url_for("ballot",step=0))

@app.post("/membership/cancel")
def cancel_member():
 keep_geo=session.get("geo")
 session.clear()
 return redirect(url_for("home"))

@app.get("/membership-photo/<submission_id>/<kind>")
def membership_photo(submission_id,kind):
 if kind not in ("id","passport"):
  return Response(status=404)
 if str(session.get("membership_submission_id"))!=str(submission_id):
  return Response(status=403)
 try:
  if str(submission_id).startswith("membership-csv:"):
   national_id=str(submission_id).split(":",1)[1]
   row=_membership_csv_row(national_id) or {}
   filename=field(row,"basics/id_photo" if kind=="id" else "basics/passport_photo")
   item=_MEMBERSHIP_CSV_CACHE["media"].get(filename.replace("\\","/").split("/")[-1].lower()) if filename else None
   media=item.get("content") if item else None
  else:
   row=submission_detail(submission_id)
   media=attachment_url(row,kind)
  if not media:
   return Response(status=404)
  r=requests.get(media,headers=kobo_headers(),timeout=25,stream=True)
  r.raise_for_status()
  return Response(r.iter_content(chunk_size=65536),
                  content_type=r.headers.get("Content-Type","image/jpeg"))
 except Exception:
  return Response(status=404)

@app.route("/ballot/<int:step>",methods=["GET","POST"])
def ballot(step):
 if "voter_id" not in session:return redirect(url_for("home"))
 structure=cfg()
 if step<0 or step>=len(structure):return redirect(url_for("review"))
 geo=session.get("geo",{})
 try:
  e=election_with_candidates(step,geo)
 except Exception:
  e=structure[step]
  return render_template(
   "ballot.html",e=e,step=step,total=len(structure),
   error="Candidate data could not be loaded from the Candidate Registration Portal. Check the portal connection and try again.",
   selected=None
  )
 if request.method=="POST":
  action=str(request.form.get("action","choose")).strip().lower()
  choices=dict(session.get("choices",{}))

  # SKIP must be processed even when this electoral area has no registered
  # candidates. Previously the no-candidates GET render happened before the
  # POST handler, so the final MCA skip could never advance to Review/Submit.
  if action=="skip":
   choices[e["key"]]={
    "candidate_id":"__SKIP__",
    "candidate_name":"SKIPPED",
    "membership_no":"",
    "slot":0,
    "skipped":True
   }
   session["choices"]=choices
   return redirect(url_for("ballot",step=step+1)) if step+1<len(structure) else redirect(url_for("review"))

  selected_id=str(request.form.get("candidate","")).strip()
  selected=next((x for x in e["candidates"] if x["candidate_id"]==selected_id),None)
  if not selected:
   return render_template("ballot.html",e=e,step=step,total=len(structure),error="Choose one registered candidate or use the SKIP button.",selected=None)
  choices[e["key"]]={
   "candidate_id":selected["candidate_id"],
   "candidate_name":selected["name"],
   "membership_no":selected.get("membership_no",""),
   "slot":selected["slot"],
   "skipped":False
  }
  session["choices"]=choices
  return redirect(url_for("ballot",step=step+1)) if step+1<len(structure) else redirect(url_for("review"))

 if not e["candidates"]:
  return render_template(
   "ballot.html",e=e,step=step,total=len(structure),
   error=f"No active {e['title']} candidates are registered for this electoral area.",
   selected=None
  )

 saved=session.get("choices",{}).get(e["key"],{})
 selected_id=saved.get("candidate_id") if isinstance(saved,dict) and not saved.get("skipped") else None
 return render_template("ballot.html",e=e,step=step,total=len(structure),selected=selected_id,
                        previously_skipped=bool(isinstance(saved,dict) and saved.get("skipped")))

@app.get("/review")
def review():
 if "voter_id" not in session:return redirect(url_for("home"))
 choices=session.get("choices",{})
 geo=session.get("geo",{})
 # Re-load the selected candidates so the review screen can show their photos
 # and other visual identity information.
 try:
  catalog=candidate_portal_catalog(geo)
 except Exception:
  catalog={k:[] for k,_,_ in ELECTIONS}

 review_choices={}
 for e in cfg():
  picked=choices.get(e["key"])
  if not isinstance(picked,dict):
   continue
  item=dict(picked)
  if picked.get("skipped") or picked.get("candidate_id")=="__SKIP__":
   item["skipped"]=True
   item["photo_url"]=None
  else:
   current=next(
    (c for c in catalog.get(e["key"],[]) if c.get("candidate_id")==picked.get("candidate_id")),
    None
   )
   if current:
    item["photo_url"]=current.get("photo_url")
   item["skipped"]=False
  review_choices[e["key"]]=item

 return render_template(
  "review.html",
  elections=cfg(),
  choices=review_choices,
  geo=geo,
  voter_id=session.get("voter_id","")
 )

@app.post("/cast")
def cast():
 if "voter_id" not in session:return redirect(url_for("home"))
 choices=session.get("choices",{})
 if len(choices)!=6:return redirect(url_for("review"))
 c=con(); voter=session["voter_id"]; geo=session["geo"]
 existing=c.execute("SELECT poll_station, stream FROM demo_votes WHERE voter_session=? LIMIT 1",(voter,)).fetchone()
 if existing:
  c.close()
  session.clear()
  return render_template("verify.html",error=already_voted_message(voter,existing["poll_station"],existing["stream"]))
 for e in cfg():
  picked=choices.get(e["key"])
  if not isinstance(picked,dict) or not picked.get("candidate_id"):
   c.close()
   return redirect(url_for("review"))
  c.execute("""INSERT INTO demo_votes(
   voter_session,election,candidate,candidate_id,candidate_name,county,constituency,ward,poll_station,stream
  ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
   (voter,e["key"],picked.get("slot",0),picked.get("candidate_id",""),picked.get("candidate_name",""),
    geo["county"],geo["constituency"],geo["ward"],geo["poll_station"],geo["stream"]))
 c.commit(); c.close()
 try:
  mark_shared_voter_voted(voter,geo.get("poll_station",""))
 except Exception as exc:
  app.logger.error("Could not update shared voter-status record after ballot cast: %s",exc)
 try:
  sync_unmirrored_votes_to_dashboard()
  try:
   _GOV_DASHBOARD_CACHE["payload"]=None
   _SEN_DASHBOARD_CACHE["payload"]=None
   _PRES_DASHBOARD_CACHE["payload"]=None
   _WOMAN_REP_DASHBOARD_CACHE["payload"]=None
   _MNA_DASHBOARD_CACHE["payload"]=None
   _MCA_DASHBOARD_CACHE["payload"]=None
  except Exception:
   pass
 except Exception as exc:
  app.logger.warning("Dashboard mirror sync deferred: %s",exc)
 session["completed"]=True
 return redirect(url_for("complete"))



def sync_unmirrored_votes_to_dashboard():
 """
 Mirror completed simulation ballot rows into PostgreSQL for the read-only live dashboard.
 The mirror is anonymous: it stores only election/candidate/geography plus a random event id.
 Event IDs make retries idempotent, so a temporary database error cannot double-count a row.
 """
 if not DATABASE_URL:
  return 0
 init_global_lock_db()
 c=con()
 rows=c.execute("""
  SELECT id,election,candidate_id,candidate_name,county,constituency,ward,poll_station,stream,dashboard_event_id
  FROM demo_votes
  WHERE COALESCE(dashboard_mirrored,0)=0
  ORDER BY id
 """).fetchall()
 if not rows:
  c.close()
  return 0
 prepared=[]
 now=kenya_now().isoformat(timespec="seconds")
 session_date=today_iso()
 try:
  for r in rows:
   event_id=(r["dashboard_event_id"] or "").strip() or secrets.token_hex(24)
   if not r["dashboard_event_id"]:
    c.execute("UPDATE demo_votes SET dashboard_event_id=? WHERE id=?",(event_id,r["id"]))
   prepared.append((
    event_id,session_date,r["election"] or "",r["candidate_id"] or "",r["candidate_name"] or "",
    r["county"] or "",r["constituency"] or "",r["ward"] or "",r["poll_station"] or "",r["stream"] or "",now,r["id"]
   ))
  c.commit()
  with lock_db() as conn:
   with conn.cursor() as cur:
    for row in prepared:
     cur.execute("""
      INSERT INTO simulation_dashboard_vote_events(
       event_id,session_date,election,candidate_id,candidate_name,county,constituency,ward,poll_station,stream,recorded_at
      ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(event_id) DO NOTHING
     """,row[:-1])
   conn.commit()
  c.executemany("UPDATE demo_votes SET dashboard_mirrored=1 WHERE id=?",[(row[-1],) for row in prepared])
  c.commit()
  return len(prepared)
 finally:
  c.close()


def dashboard_election_aliases(election):
 """Return canonical and legacy keys used by earlier training-ballot builds."""
 if election=="woman_rep":
  return (
   "woman_rep","women_rep","woman-rep","women-rep",
   "womanrep","womenrep",
   "woman-representative","women-representative",
   "woman_representative","women_representative",
   "woman representative","women representative",
   "woman rep","women rep"
  )
 return (election,)


def _persistent_dashboard_snapshot(election):
 """Return anonymous dashboard aggregates for an election, with safe fallback behavior.

 If the PostgreSQL mirror is temporarily unavailable or contains no rows while the local
 SQLite ballot store still has votes, return None so the API uses the local fallback.
 If today's mirror is empty after a deploy/date rollover, use the most recent mirrored
 simulation date for that election so previously mirrored training results remain visible.
 """
 if not DATABASE_URL:
  return None
 init_global_lock_db()
 try:
  c=con()
  aliases=dashboard_election_aliases(election)
  marks=','.join('?' for _ in aliases)
  pending=c.execute(f"SELECT 1 FROM demo_votes WHERE LOWER(election) IN ({marks}) AND COALESCE(dashboard_mirrored,0)=0 LIMIT 1",aliases).fetchone()
  local_count=int(c.execute(f"SELECT COUNT(*) FROM demo_votes WHERE LOWER(election) IN ({marks})",aliases).fetchone()[0] or 0)
  c.close()
  if pending:
   sync_unmirrored_votes_to_dashboard()
 except Exception as exc:
  app.logger.warning("%s dashboard mirror sync failed; using local fallback: %s", election, exc)
  return None

 session_date=today_iso()
 try:
  with lock_db() as conn:
   with conn.cursor() as cur:
    cur.execute("""
     SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
     FROM simulation_dashboard_vote_events
     WHERE session_date=%s AND LOWER(election) = ANY(%s)
     GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
     ORDER BY county,constituency,ward,poll_station,stream,candidate_name
    """,(session_date,list(aliases)))
    rows=cur.fetchall()

    # If PostgreSQL is empty but this worker still has local votes, never mask them.
    if not rows and local_count>0:
     return None

    # Across Render deploys the local SQLite file can be fresh/empty while the durable
    # anonymous mirror still has the user's most recent training session. Use that session.
    if not rows:
     cur.execute("SELECT MAX(session_date) AS d FROM simulation_dashboard_vote_events WHERE LOWER(election) = ANY(%s)",(list(aliases),))
     latest=cur.fetchone()
     latest_date=(latest.get("d") if latest else None) if hasattr(latest,'get') else (latest[0] if latest else None)
     if latest_date:
      session_date=str(latest_date)
      cur.execute("""
       SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
       FROM simulation_dashboard_vote_events
       WHERE session_date=%s AND LOWER(election) = ANY(%s)
       GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
       ORDER BY county,constituency,ward,poll_station,stream,candidate_name
      """,(session_date,list(aliases)))
      rows=cur.fetchall()

    cur.execute("""
     SELECT session_date,county,constituency,ward,poll_station,stream,locked_at,released_at,closed_at
     FROM simulation_terminal_locks
     WHERE session_date=%s
     ORDER BY COALESCE(closed_at,locked_at) DESC
    """,(session_date,))
    locks=cur.fetchall()
  return rows,locks
 except Exception as exc:
  app.logger.warning("%s persistent dashboard read failed; using local fallback: %s", election, exc)
  return None


def persistent_presidential_dashboard_snapshot():
 return _persistent_dashboard_snapshot("president")


def persistent_gubernatorial_dashboard_snapshot():
 return _persistent_dashboard_snapshot("governor")


def persistent_senatorial_dashboard_snapshot():
 return _persistent_dashboard_snapshot("senator")


def persistent_mna_dashboard_snapshot():
 return _persistent_dashboard_snapshot("mna")


def persistent_mca_dashboard_snapshot():
 return _persistent_dashboard_snapshot("mca")


def persistent_woman_rep_dashboard_snapshot():
 return _persistent_dashboard_snapshot("woman_rep")

def dashboard_api_authorized():
 supplied=request.headers.get("X-Dashboard-Key","")
 return bool(DASHBOARD_API_KEY and supplied and hmac.compare_digest(supplied,DASHBOARD_API_KEY))

# Very short cache for the gubernatorial feed. This prevents several dashboard browser
# requests from repeating the same PostgreSQL aggregation at the same moment.
_GOV_DASHBOARD_CACHE={"at":0.0,"payload":None}
_GOV_DASHBOARD_CACHE_LOCK=threading.Lock()
GOV_DASHBOARD_CACHE_SECONDS=max(1,int(os.getenv("GOV_DASHBOARD_CACHE_SECONDS","3")))

_PRES_DASHBOARD_CACHE={"at":0.0,"payload":None}
_PRES_DASHBOARD_CACHE_LOCK=threading.Lock()
PRES_DASHBOARD_CACHE_SECONDS=max(1,int(os.getenv("PRES_DASHBOARD_CACHE_SECONDS","3")))

_SEN_DASHBOARD_CACHE={"at":0.0,"payload":None}
_SEN_DASHBOARD_CACHE_LOCK=threading.Lock()
SEN_DASHBOARD_CACHE_SECONDS=max(1,int(os.getenv("SEN_DASHBOARD_CACHE_SECONDS","3")))

_WOMAN_REP_DASHBOARD_CACHE={"at":0.0,"payload":None}
_WOMAN_REP_DASHBOARD_CACHE_LOCK=threading.Lock()
WOMAN_REP_DASHBOARD_CACHE_SECONDS=max(1,int(os.getenv("WOMAN_REP_DASHBOARD_CACHE_SECONDS","3")))

_MNA_DASHBOARD_CACHE={"at":0.0,"payload":None}
_MNA_DASHBOARD_CACHE_LOCK=threading.Lock()
MNA_DASHBOARD_CACHE_SECONDS=max(1,int(os.getenv("MNA_DASHBOARD_CACHE_SECONDS","3")))

_MCA_DASHBOARD_CACHE={"at":0.0,"payload":None}
_MCA_DASHBOARD_CACHE_LOCK=threading.Lock()
MCA_DASHBOARD_CACHE_SECONDS=max(1,int(os.getenv("MCA_DASHBOARD_CACHE_SECONDS","3")))


def _build_woman_rep_dashboard_payload():
 """Aggregate the anonymous Woman Representative simulation vote feed."""
 try:
  persistent=persistent_woman_rep_dashboard_snapshot()
 except Exception as exc:
  app.logger.warning("Persistent woman_rep dashboard snapshot unavailable; using local fallback: %s",exc)
  persistent=None

 if persistent is not None:
  rows,lock_rows=persistent
  sessions=[]
  for r in lock_rows:
   opened_at=(r.get("locked_at") or "") if not r.get("released_at") or r.get("closed_at") else ""
   sessions.append({
    "session_date":r.get("session_date") or "",
    "county":r.get("county") or "",
    "constituency":r.get("constituency") or "",
    "ward":r.get("ward") or "",
    "poll_station":r.get("poll_station") or "",
    "stream":r.get("stream") or "",
    "opened_at":opened_at,
    "closed_at":r.get("closed_at") or ""
   })
 else:
  c=con()
  aliases=dashboard_election_aliases("woman_rep")
  marks=','.join('?' for _ in aliases)
  rows=c.execute(f"""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes
   WHERE LOWER(election) IN ({marks})
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
   ORDER BY county,constituency,ward,poll_station,stream,candidate_name
  """,aliases).fetchall()
  sessions=c.execute("""
   SELECT session_date,county,constituency,ward,poll_station,stream,opened_at,closed_at
   FROM stream_sessions
   ORDER BY COALESCE(closed_at,opened_at) DESC
  """).fetchall()
  c.close()

 streams={}
 candidate_totals={}
 candidate_counties={}
 skipped_total=0
 participants_total=0

 for r in rows:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  county=(r["county"] or "").strip()
  key=(county,(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  item=streams.setdefault(key,{
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "candidate_votes":{},
   "candidate_names":{},
   "candidate_counties":{},
   "candidate_selections":0,
   "skipped":0,
   "participants":0
  })
  cid=(r["candidate_id"] or "").strip()
  n=int(r["n"] or 0)
  if cid=="__SKIP__":
   item["skipped"]+=n
   skipped_total+=n
  else:
   item["candidate_votes"][cid]=item["candidate_votes"].get(cid,0)+n
   item["candidate_names"][cid]=(r["candidate_name"] or cid)
   item["candidate_counties"][cid]=county
   item["candidate_selections"]+=n
   candidate_totals[cid]=candidate_totals.get(cid,0)+n
   if county:
    candidate_counties[cid]=county
  item["participants"]+=n
  participants_total+=n

 session_map={}
 for r in sessions:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  session_map[key]={
   "session_date":r["session_date"] or "",
   "opened_at":r["opened_at"] or "",
   "closed_at":r["closed_at"] or ""
  }
  if key not in streams:
   streams[key]={
    "county":r["county"] or "",
    "constituency":r["constituency"] or "",
    "ward":r["ward"] or "",
    "poll_station":r["poll_station"] or "",
    "stream":stream_name,
    "candidate_votes":{},"candidate_names":{},"candidate_counties":{},
    "candidate_selections":0,"skipped":0,"participants":0
   }

 for key,item in streams.items():
  sess=session_map.get(key,{})
  item["opened_at"]=sess.get("opened_at","")
  item["closed_at"]=sess.get("closed_at","")
  item["session_date"]=sess.get("session_date","")
  item["status"]="CLOSED" if item["closed_at"] else ("OPEN" if item["opened_at"] else "NOT STARTED")

 names={}
 for item in streams.values():
  names.update(item.get("candidate_names",{}))
 event_geo={cid:{"county":candidate_counties.get(cid,"")} for cid in set(names) | set(candidate_totals)}
 candidates=dashboard_candidate_catalog("woman_rep",candidate_totals,names,event_geo)

 return {
  "source":"training_simulation",
  "simulation_only":True,
  "election":"woman_rep",
  "candidates":candidates,
  "streams":list(streams.values()),
  "totals":{
   "registered_voters":authoritative_registered_total(),
   "candidate_selections":sum(candidate_totals.values()),
   "skipped":skipped_total,
   "participants":participants_total
  }
 }


@app.get("/api/dashboard/women-representative")
@app.get("/api/dashboard/woman-representative")
@app.get("/api/dashboard/women-rep")
@app.get("/api/dashboard/woman-rep")
def api_dashboard_woman_rep():
 """Read-only aggregate feed for the Women Representative Simulation Results Dashboard."""
 if not dashboard_api_authorized():
  return jsonify({"error":"Unauthorized"}),401
 now_ts=time.time()
 cached=_WOMAN_REP_DASHBOARD_CACHE.get("payload")
 if cached is not None and now_ts-float(_WOMAN_REP_DASHBOARD_CACHE.get("at") or 0)<WOMAN_REP_DASHBOARD_CACHE_SECONDS:
  return jsonify(cached)
 payload=_build_woman_rep_dashboard_payload()
 with _WOMAN_REP_DASHBOARD_CACHE_LOCK:
  _WOMAN_REP_DASHBOARD_CACHE["payload"]=payload
  _WOMAN_REP_DASHBOARD_CACHE["at"]=time.time()
 return jsonify(payload)

@app.get("/api/dashboard/president")
def api_dashboard_president():
 """
 Read-only aggregate feed for the separate Presidential Simulation Results Dashboard.
 No voter National IDs are returned.
 """
 if not dashboard_api_authorized():
  return jsonify({"error":"Unauthorized"}),401

 now_ts=time.time()
 cached=_PRES_DASHBOARD_CACHE.get("payload")
 if cached is not None and now_ts-float(_PRES_DASHBOARD_CACHE.get("at") or 0)<PRES_DASHBOARD_CACHE_SECONDS:
  return jsonify(cached)

 # Prefer the persistent anonymous PostgreSQL mirror so dashboard totals survive
 # Render deploys/restarts and reflect the current simulation across workers/devices.
 try:
  persistent=persistent_presidential_dashboard_snapshot()
 except Exception as exc:
  app.logger.warning("Persistent dashboard snapshot unavailable; using local fallback: %s",exc)
  persistent=None

 if persistent is not None:
  rows,lock_rows=persistent
  sessions=[]
  for r in lock_rows:
   # A released, unclosed lock is not an active opened stream.
   opened_at=(r.get("locked_at") or "") if not r.get("released_at") or r.get("closed_at") else ""
   sessions.append({
    "session_date":r.get("session_date") or "",
    "county":r.get("county") or "",
    "constituency":r.get("constituency") or "",
    "ward":r.get("ward") or "",
    "poll_station":r.get("poll_station") or "",
    "stream":r.get("stream") or "",
    "opened_at":opened_at,
    "closed_at":r.get("closed_at") or ""
   })
 else:
  c=con()
  rows=c.execute("""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes
   WHERE election='president'
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
   ORDER BY county,constituency,ward,poll_station,stream,candidate_name
  """).fetchall()
  sessions=c.execute("""
   SELECT session_date,county,constituency,ward,poll_station,stream,opened_at,closed_at
   FROM stream_sessions
   ORDER BY COALESCE(closed_at,opened_at) DESC
  """).fetchall()
  c.close()

 streams={}
 candidate_totals={}
 skipped_total=0
 participants_total=0

 for r in rows:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  # Use the full geographic identity. Stream names are not globally unique in county_main.csv.
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  item=streams.setdefault(key,{
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "candidate_votes":{},
   "candidate_names":{},
   "candidate_selections":0,
   "skipped":0,
   "participants":0
  })
  cid=(r["candidate_id"] or "").strip()
  n=int(r["n"] or 0)
  if cid=="__SKIP__":
   item["skipped"]+=n
   skipped_total+=n
  else:
   item["candidate_votes"][cid]=item["candidate_votes"].get(cid,0)+n
   item["candidate_names"][cid]=(r["candidate_name"] or cid)
   item["candidate_selections"]+=n
   candidate_totals[cid]=candidate_totals.get(cid,0)+n
  item["participants"]+=n
  participants_total+=n

 # Add stream status/times without exposing individual voter records.
 session_map={}
 for r in sessions:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  session_map[key]={
   "session_date":r["session_date"] or "",
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "opened_at":r["opened_at"] or "",
   "closed_at":r["closed_at"] or ""
  }
  if key not in streams:
   streams[key]={
    "county":r["county"] or "",
    "constituency":r["constituency"] or "",
    "ward":r["ward"] or "",
    "poll_station":r["poll_station"] or "",
    "stream":stream_name,
    "candidate_votes":{},
    "candidate_names":{},
    "candidate_selections":0,
    "skipped":0,
    "participants":0
   }

 for key,item in streams.items():
  sess=session_map.get(key,{})
  item["opened_at"]=sess.get("opened_at","")
  item["closed_at"]=sess.get("closed_at","")
  item["session_date"]=sess.get("session_date","")
  item["status"]="CLOSED" if item["closed_at"] else ("OPEN" if item["opened_at"] else "NOT STARTED")

 # Merge the current national catalogue with names actually present in stored vote
 # events. This preserves zero-vote catalogue candidates without hiding votes when a
 # candidate ID was renamed, replaced or temporarily absent from the live catalogue.
 seen_names={}
 for item in streams.values():
  seen_names.update(item.get("candidate_names",{}))
 candidates=dashboard_candidate_catalog("president",candidate_totals,seen_names)

 payload={
  "source":"training_simulation",
  "simulation_only":True,
  "election":"president",
  "candidates":candidates,
  "streams":list(streams.values()),
  "totals":{
   "registered_voters":authoritative_registered_total(),
   "candidate_selections":sum(candidate_totals.values()),
   "skipped":skipped_total,
   "participants":participants_total
  }
 }
 with _PRES_DASHBOARD_CACHE_LOCK:
  _PRES_DASHBOARD_CACHE["payload"]=payload
  _PRES_DASHBOARD_CACHE["at"]=time.time()
 return jsonify(payload)
@app.get("/api/dashboard/governor")
def api_dashboard_governor():
 """
 Read-only aggregate feed for the separate Gubernatorial Simulation Results Dashboard.
 No voter National IDs are returned.
 """
 if not dashboard_api_authorized():
  return jsonify({"error":"Unauthorized"}),401

 now_ts=time.time()
 cached=_GOV_DASHBOARD_CACHE.get("payload")
 if cached is not None and now_ts-float(_GOV_DASHBOARD_CACHE.get("at") or 0)<GOV_DASHBOARD_CACHE_SECONDS:
  return jsonify(cached)

 # Prefer the persistent anonymous PostgreSQL mirror so dashboard totals survive
 # Render deploys/restarts and reflect the current simulation across workers/devices.
 try:
  persistent=persistent_gubernatorial_dashboard_snapshot()
 except Exception as exc:
  app.logger.warning("Persistent dashboard snapshot unavailable; using local fallback: %s",exc)
  persistent=None

 if persistent is not None:
  rows,lock_rows=persistent
  sessions=[]
  for r in lock_rows:
   # A released, unclosed lock is not an active opened stream.
   opened_at=(r.get("locked_at") or "") if not r.get("released_at") or r.get("closed_at") else ""
   sessions.append({
    "session_date":r.get("session_date") or "",
    "county":r.get("county") or "",
    "constituency":r.get("constituency") or "",
    "ward":r.get("ward") or "",
    "poll_station":r.get("poll_station") or "",
    "stream":r.get("stream") or "",
    "opened_at":opened_at,
    "closed_at":r.get("closed_at") or ""
   })
 else:
  c=con()
  rows=c.execute("""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes
   WHERE election='governor'
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
   ORDER BY county,constituency,ward,poll_station,stream,candidate_name
  """).fetchall()
  sessions=c.execute("""
   SELECT session_date,county,constituency,ward,poll_station,stream,opened_at,closed_at
   FROM stream_sessions
   ORDER BY COALESCE(closed_at,opened_at) DESC
  """).fetchall()
  c.close()

 streams={}
 candidate_totals={}
 skipped_total=0
 participants_total=0

 for r in rows:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  # Use the full geographic identity. Stream names are not globally unique in county_main.csv.
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  item=streams.setdefault(key,{
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "candidate_votes":{},
   "candidate_names":{},
   "candidate_selections":0,
   "skipped":0,
   "participants":0
  })
  cid=(r["candidate_id"] or "").strip()
  n=int(r["n"] or 0)
  if cid=="__SKIP__":
   item["skipped"]+=n
   skipped_total+=n
  else:
   item["candidate_votes"][cid]=item["candidate_votes"].get(cid,0)+n
   item["candidate_names"][cid]=(r["candidate_name"] or cid)
   item["candidate_selections"]+=n
   candidate_totals[cid]=candidate_totals.get(cid,0)+n
  item["participants"]+=n
  participants_total+=n

 # Add stream status/times without exposing individual voter records.
 session_map={}
 for r in sessions:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  session_map[key]={
   "session_date":r["session_date"] or "",
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "opened_at":r["opened_at"] or "",
   "closed_at":r["closed_at"] or ""
  }
  if key not in streams:
   streams[key]={
    "county":r["county"] or "",
    "constituency":r["constituency"] or "",
    "ward":r["ward"] or "",
    "poll_station":r["poll_station"] or "",
    "stream":stream_name,
    "candidate_votes":{},
    "candidate_names":{},
    "candidate_selections":0,
    "skipped":0,
    "participants":0
   }

 for key,item in streams.items():
  sess=session_map.get(key,{})
  item["opened_at"]=sess.get("opened_at","")
  item["closed_at"]=sess.get("closed_at","")
  item["session_date"]=sess.get("session_date","")
  item["status"]="CLOSED" if item["closed_at"] else ("OPEN" if item["opened_at"] else "NOT STARTED")

 # Merge all registered county candidates, including those with zero votes,
 # with names retained in anonymous vote events.
 names={}
 candidate_counties={}
 for item in streams.values():
  names.update(item.get("candidate_names",{}))
  for cid in item.get("candidate_names",{}):
   candidate_counties[cid]=item.get("county","") or candidate_counties.get(cid,"")
 event_geo={cid:{"county":candidate_counties.get(cid,"")} for cid in set(names) | set(candidate_totals)}
 candidates=dashboard_candidate_catalog("governor",candidate_totals,names,event_geo)

 payload={
  "source":"training_simulation",
  "simulation_only":True,
  "election":"governor",
  "candidates":candidates,
  "streams":list(streams.values()),
  "totals":{
   "registered_voters":authoritative_registered_total(),
   "candidate_selections":sum(candidate_totals.values()),
   "skipped":skipped_total,
   "participants":participants_total
  }
 }
 with _GOV_DASHBOARD_CACHE_LOCK:
  _GOV_DASHBOARD_CACHE["payload"]=payload
  _GOV_DASHBOARD_CACHE["at"]=time.time()
 return jsonify(payload)


@app.get("/api/dashboard/senator")
def api_dashboard_senator():
 """
 Read-only aggregate feed for the separate Senatorial Simulation Results Dashboard.
 No voter National IDs are returned.
 """
 if not dashboard_api_authorized():
  return jsonify({"error":"Unauthorized"}),401

 now_ts=time.time()
 cached=_SEN_DASHBOARD_CACHE.get("payload")
 if cached is not None and now_ts-float(_SEN_DASHBOARD_CACHE.get("at") or 0)<SEN_DASHBOARD_CACHE_SECONDS:
  return jsonify(cached)

 # Prefer the persistent anonymous PostgreSQL mirror so dashboard totals survive
 # Render deploys/restarts and reflect the current simulation across workers/devices.
 try:
  persistent=persistent_senatorial_dashboard_snapshot()
 except Exception as exc:
  app.logger.warning("Persistent dashboard snapshot unavailable; using local fallback: %s",exc)
  persistent=None

 if persistent is not None:
  rows,lock_rows=persistent
  sessions=[]
  for r in lock_rows:
   # A released, unclosed lock is not an active opened stream.
   opened_at=(r.get("locked_at") or "") if not r.get("released_at") or r.get("closed_at") else ""
   sessions.append({
    "session_date":r.get("session_date") or "",
    "county":r.get("county") or "",
    "constituency":r.get("constituency") or "",
    "ward":r.get("ward") or "",
    "poll_station":r.get("poll_station") or "",
    "stream":r.get("stream") or "",
    "opened_at":opened_at,
    "closed_at":r.get("closed_at") or ""
   })
 else:
  c=con()
  rows=c.execute("""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes
   WHERE election='senator'
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
   ORDER BY county,constituency,ward,poll_station,stream,candidate_name
  """).fetchall()
  sessions=c.execute("""
   SELECT session_date,county,constituency,ward,poll_station,stream,opened_at,closed_at
   FROM stream_sessions
   ORDER BY COALESCE(closed_at,opened_at) DESC
  """).fetchall()
  c.close()

 streams={}
 candidate_totals={}
 skipped_total=0
 participants_total=0

 for r in rows:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  # Use the full geographic identity. Stream names are not globally unique in county_main.csv.
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  item=streams.setdefault(key,{
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "candidate_votes":{},
   "candidate_names":{},
   "candidate_selections":0,
   "skipped":0,
   "participants":0
  })
  cid=(r["candidate_id"] or "").strip()
  n=int(r["n"] or 0)
  if cid=="__SKIP__":
   item["skipped"]+=n
   skipped_total+=n
  else:
   item["candidate_votes"][cid]=item["candidate_votes"].get(cid,0)+n
   item["candidate_names"][cid]=(r["candidate_name"] or cid)
   item["candidate_selections"]+=n
   candidate_totals[cid]=candidate_totals.get(cid,0)+n
  item["participants"]+=n
  participants_total+=n

 # Add stream status/times without exposing individual voter records.
 session_map={}
 for r in sessions:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  session_map[key]={
   "session_date":r["session_date"] or "",
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":stream_name,
   "opened_at":r["opened_at"] or "",
   "closed_at":r["closed_at"] or ""
  }
  if key not in streams:
   streams[key]={
    "county":r["county"] or "",
    "constituency":r["constituency"] or "",
    "ward":r["ward"] or "",
    "poll_station":r["poll_station"] or "",
    "stream":stream_name,
    "candidate_votes":{},
    "candidate_names":{},
    "candidate_selections":0,
    "skipped":0,
    "participants":0
   }

 for key,item in streams.items():
  sess=session_map.get(key,{})
  item["opened_at"]=sess.get("opened_at","")
  item["closed_at"]=sess.get("closed_at","")
  item["session_date"]=sess.get("session_date","")
  item["status"]="CLOSED" if item["closed_at"] else ("OPEN" if item["opened_at"] else "NOT STARTED")

 # Merge all registered county candidates, including those with zero votes,
 # with names retained in anonymous vote events.
 names={}
 candidate_counties={}
 for item in streams.values():
  names.update(item.get("candidate_names",{}))
  for cid in item.get("candidate_names",{}):
   candidate_counties[cid]=item.get("county","") or candidate_counties.get(cid,"")
 event_geo={cid:{"county":candidate_counties.get(cid,"")} for cid in set(names) | set(candidate_totals)}
 candidates=dashboard_candidate_catalog("senator",candidate_totals,names,event_geo)

 payload={
  "source":"training_simulation",
  "simulation_only":True,
  "election":"senator",
  "candidates":candidates,
  "streams":list(streams.values()),
  "totals":{
   "registered_voters":authoritative_registered_total(),
   "candidate_selections":sum(candidate_totals.values()),
   "skipped":skipped_total,
   "participants":participants_total
  }
 }
 with _SEN_DASHBOARD_CACHE_LOCK:
  _SEN_DASHBOARD_CACHE["payload"]=payload
  _SEN_DASHBOARD_CACHE["at"]=time.time()
 return jsonify(payload)


def _build_mna_dashboard_payload():
 """Aggregate the anonymous Member of National Assembly simulation vote feed."""
 try:
  persistent=persistent_mna_dashboard_snapshot()
 except Exception as exc:
  app.logger.warning("Persistent MNA dashboard snapshot unavailable; using local fallback: %s",exc)
  persistent=None

 if persistent is not None:
  rows,lock_rows=persistent
  sessions=[]
  for r in lock_rows:
   opened_at=(r.get("locked_at") or "") if not r.get("released_at") or r.get("closed_at") else ""
   sessions.append({
    "session_date":r.get("session_date") or "","county":r.get("county") or "",
    "constituency":r.get("constituency") or "","ward":r.get("ward") or "",
    "poll_station":r.get("poll_station") or "","stream":r.get("stream") or "",
    "opened_at":opened_at,"closed_at":r.get("closed_at") or ""
   })
 else:
  c=con()
  rows=c.execute("""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes WHERE election='mna'
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
   ORDER BY county,constituency,ward,poll_station,stream,candidate_name
  """).fetchall()
  sessions=c.execute("""
   SELECT session_date,county,constituency,ward,poll_station,stream,opened_at,closed_at
   FROM stream_sessions ORDER BY COALESCE(closed_at,opened_at) DESC
  """).fetchall()
  c.close()

 streams={}
 candidate_totals={}
 candidate_counties={}
 candidate_constituencies={}
 skipped_total=0
 participants_total=0
 for r in rows:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  county=(r["county"] or "").strip()
  constituency=(r["constituency"] or "").strip()
  key=(county,constituency,(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  item=streams.setdefault(key,{
   "county":county,"constituency":constituency,"ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "","stream":stream_name,
   "candidate_votes":{},"candidate_names":{},"candidate_counties":{},
   "candidate_constituencies":{},"candidate_selections":0,"skipped":0,"participants":0
  })
  cid=(r["candidate_id"] or "").strip()
  n=int(r["n"] or 0)
  if cid=="__SKIP__":
   item["skipped"]+=n
   skipped_total+=n
  else:
   item["candidate_votes"][cid]=item["candidate_votes"].get(cid,0)+n
   item["candidate_names"][cid]=(r["candidate_name"] or cid)
   item["candidate_counties"][cid]=county
   item["candidate_constituencies"][cid]=constituency
   item["candidate_selections"]+=n
   candidate_totals[cid]=candidate_totals.get(cid,0)+n
   if county: candidate_counties[cid]=county
   if constituency: candidate_constituencies[cid]=constituency
  item["participants"]+=n
  participants_total+=n

 session_map={}
 for r in sessions:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:
   continue
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),
       (r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  session_map[key]={"session_date":r["session_date"] or "","opened_at":r["opened_at"] or "","closed_at":r["closed_at"] or ""}
  if key not in streams:
   streams[key]={
    "county":r["county"] or "","constituency":r["constituency"] or "","ward":r["ward"] or "",
    "poll_station":r["poll_station"] or "","stream":stream_name,
    "candidate_votes":{},"candidate_names":{},"candidate_counties":{},"candidate_constituencies":{},
    "candidate_selections":0,"skipped":0,"participants":0
   }
 for key,item in streams.items():
  sess=session_map.get(key,{})
  item["opened_at"]=sess.get("opened_at","")
  item["closed_at"]=sess.get("closed_at","")
  item["session_date"]=sess.get("session_date","")
  item["status"]="CLOSED" if item["closed_at"] else ("OPEN" if item["opened_at"] else "NOT STARTED")

 names={}
 for item in streams.values():
  names.update(item.get("candidate_names",{}))
 event_geo={cid:{"county":candidate_counties.get(cid,""),"constituency":candidate_constituencies.get(cid,"")} for cid in set(names) | set(candidate_totals)}
 candidates=dashboard_candidate_catalog("mna",candidate_totals,names,event_geo)
 return {
  "source":"training_simulation","simulation_only":True,"election":"mna",
  "candidates":candidates,"streams":list(streams.values()),
  "totals":{"registered_voters":authoritative_registered_total(),"candidate_selections":sum(candidate_totals.values()),"skipped":skipped_total,"participants":participants_total}
 }


@app.get("/api/dashboard/mna")
@app.get("/api/dashboard/member-national-assembly")
def api_dashboard_mna():
 """Read-only MNA aggregate feed; returns no voter identifiers."""
 if not dashboard_api_authorized():
  return jsonify({"error":"Unauthorized"}),401
 now_ts=time.time()
 cached=_MNA_DASHBOARD_CACHE.get("payload")
 if cached is not None and now_ts-float(_MNA_DASHBOARD_CACHE.get("at") or 0)<MNA_DASHBOARD_CACHE_SECONDS:
  return jsonify(cached)
 payload=_build_mna_dashboard_payload()
 with _MNA_DASHBOARD_CACHE_LOCK:
  _MNA_DASHBOARD_CACHE["payload"]=payload
  _MNA_DASHBOARD_CACHE["at"]=time.time()
 return jsonify(payload)


def _build_mca_dashboard_payload():
 """Aggregate anonymous MCA votes and retain each candidate's registered ward."""
 try:
  persistent=persistent_mca_dashboard_snapshot()
 except Exception as exc:
  app.logger.warning("Persistent MCA dashboard snapshot unavailable; using local fallback: %s",exc)
  persistent=None

 if persistent is not None:
  rows,lock_rows=persistent
  sessions=[]
  for r in lock_rows:
   opened_at=(r.get("locked_at") or "") if not r.get("released_at") or r.get("closed_at") else ""
   sessions.append({
    "session_date":r.get("session_date") or "","county":r.get("county") or "",
    "constituency":r.get("constituency") or "","ward":r.get("ward") or "",
    "poll_station":r.get("poll_station") or "","stream":r.get("stream") or "",
    "opened_at":opened_at,"closed_at":r.get("closed_at") or ""
   })
 else:
  c=con()
  rows=c.execute("""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes WHERE election='mca'
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
   ORDER BY county,constituency,ward,poll_station,stream,candidate_name
  """).fetchall()
  sessions=c.execute("""
   SELECT session_date,county,constituency,ward,poll_station,stream,opened_at,closed_at
   FROM stream_sessions ORDER BY COALESCE(closed_at,opened_at) DESC
  """).fetchall()
  c.close()

 streams={};candidate_totals={};candidate_counties={};candidate_constituencies={};candidate_wards={}
 skipped_total=0;participants_total=0
 for r in rows:
  stream_name=(r["stream"] or "").strip()
  if not stream_name: continue
  county=(r["county"] or "").strip();constituency=(r["constituency"] or "").strip();ward=(r["ward"] or "").strip()
  key=(county,constituency,ward,(r["poll_station"] or "").strip(),stream_name)
  item=streams.setdefault(key,{
   "county":county,"constituency":constituency,"ward":ward,
   "poll_station":r["poll_station"] or "","stream":stream_name,
   "candidate_votes":{},"candidate_names":{},"candidate_counties":{},
   "candidate_constituencies":{},"candidate_wards":{},
   "candidate_selections":0,"skipped":0,"participants":0
  })
  cid=(r["candidate_id"] or "").strip();n=int(r["n"] or 0)
  if cid=="__SKIP__":
   item["skipped"]+=n;skipped_total+=n
  else:
   item["candidate_votes"][cid]=item["candidate_votes"].get(cid,0)+n
   item["candidate_names"][cid]=(r["candidate_name"] or cid)
   item["candidate_counties"][cid]=county
   item["candidate_constituencies"][cid]=constituency
   item["candidate_wards"][cid]=ward
   item["candidate_selections"]+=n
   candidate_totals[cid]=candidate_totals.get(cid,0)+n
   if county:candidate_counties[cid]=county
   if constituency:candidate_constituencies[cid]=constituency
   if ward:candidate_wards[cid]=ward
  item["participants"]+=n;participants_total+=n

 session_map={}
 for r in sessions:
  stream_name=(r["stream"] or "").strip()
  if not stream_name:continue
  key=((r["county"] or "").strip(),(r["constituency"] or "").strip(),(r["ward"] or "").strip(),(r["poll_station"] or "").strip(),stream_name)
  session_map[key]={"session_date":r["session_date"] or "","opened_at":r["opened_at"] or "","closed_at":r["closed_at"] or ""}
  if key not in streams:
   streams[key]={"county":r["county"] or "","constituency":r["constituency"] or "","ward":r["ward"] or "","poll_station":r["poll_station"] or "","stream":stream_name,"candidate_votes":{},"candidate_names":{},"candidate_counties":{},"candidate_constituencies":{},"candidate_wards":{},"candidate_selections":0,"skipped":0,"participants":0}
 for key,item in streams.items():
  sess=session_map.get(key,{})
  item["opened_at"]=sess.get("opened_at","");item["closed_at"]=sess.get("closed_at","");item["session_date"]=sess.get("session_date","")
  item["status"]="CLOSED" if item["closed_at"] else ("OPEN" if item["opened_at"] else "NOT STARTED")

 names={}
 for item in streams.values():names.update(item.get("candidate_names",{}))
 event_geo={cid:{"county":candidate_counties.get(cid,""),"constituency":candidate_constituencies.get(cid,""),"ward":candidate_wards.get(cid,"")} for cid in set(names) | set(candidate_totals)}
 candidates=dashboard_candidate_catalog("mca",candidate_totals,names,event_geo)
 return {"source":"training_simulation","simulation_only":True,"election":"mca","candidates":candidates,"streams":list(streams.values()),"totals":{"registered_voters":authoritative_registered_total(),"candidate_selections":sum(candidate_totals.values()),"skipped":skipped_total,"participants":participants_total}}


@app.get("/api/dashboard/mca")
@app.get("/api/dashboard/member-county-assembly")
def api_dashboard_mca():
 """Read-only MCA aggregate feed; returns no voter identifiers."""
 if not dashboard_api_authorized():return jsonify({"error":"Unauthorized"}),401
 now_ts=time.time();cached=_MCA_DASHBOARD_CACHE.get("payload")
 if cached is not None and now_ts-float(_MCA_DASHBOARD_CACHE.get("at") or 0)<MCA_DASHBOARD_CACHE_SECONDS:return jsonify(cached)
 payload=_build_mca_dashboard_payload()
 with _MCA_DASHBOARD_CACHE_LOCK:
  _MCA_DASHBOARD_CACHE["payload"]=payload;_MCA_DASHBOARD_CACHE["at"]=time.time()
 return jsonify(payload)


@app.get("/complete")
def complete():
 if not session.get("completed"):return redirect(url_for("home"))
 return render_template("complete.html",geo=session["geo"])

def tallies_available():
 lock=terminal_lock()
 if lock:
  row=stream_session(lock.get("poll_station",""),lock.get("stream",""))
  if row and row["closed_at"]:
   return True,lock,row

 closed_ref=closed_stream_cookie()
 if closed_ref and closed_ref.get("session_date")==today_iso():
  row=stream_session(closed_ref.get("poll_station",""),closed_ref.get("stream",""))
  if row and row["closed_at"]:
   return True,closed_ref,row

 return False,lock,None

@app.get("/tallies")
def tallies():
 available,lock,row=tallies_available()
 if not available:
  return render_template(
   "tallies_locked.html",
   terminal_lock=lock,
   stream_row=row,
   official_close_time="08:00 (8:00 AM)"
  ),403

 # Do not generate or display any tally/general report for a closed stream
 # that recorded no completed simulated voter session. This check happens
 # before candidate lookups, tally aggregation, GPS work or PDF deposition.
 report_ref=lock or closed_stream_cookie() or {}
 if stream_distinct_voter_count(report_ref) <= 0:
  return render_template(
   "no_voting_report.html",
   poll_station=report_ref.get("poll_station", ""),
   stream=report_ref.get("stream", ""),
   report_header_image_url=REPORT_HEADER_IMAGE_URL
  ),409

 report_poll_station=str(report_ref.get("poll_station","") or "").strip()
 report_stream=str(report_ref.get("stream","") or "").strip()
 report_station_code=str(report_ref.get("poll_station_code","") or "").strip()
 if not report_station_code and row is not None:
  try: report_station_code=str(row["poll_station_code"] or "").strip()
  except Exception: pass
 c=con()
 vote_rows=c.execute("""SELECT election,candidate,candidate_id,candidate_name,COUNT(*) votes
 FROM demo_votes
 WHERE poll_station=? AND stream=?
 GROUP BY election,candidate,candidate_id,candidate_name
 ORDER BY election,candidate_name,candidate""",(report_poll_station,report_stream)).fetchall()
 geo_rows=c.execute("""SELECT election,poll_station,stream,
 COUNT(DISTINCT voter_session) participation,
 COUNT(DISTINCT CASE WHEN candidate_id='__SKIP__' THEN voter_session END) skipped
 FROM demo_votes
 WHERE poll_station=? AND stream=?
 GROUP BY election,poll_station,stream
 ORDER BY election,poll_station,stream""",(report_poll_station,report_stream)).fetchall()
 c.close()

 vote_map={}
 legacy_vote_map={}
 vote_name_map={}
 for r in vote_rows:
  cid=(r["candidate_id"] or "").strip()
  if cid=="__SKIP__":
   continue
  if cid:
   vote_map[(r["election"],cid)]=vote_map.get((r["election"],cid),0)+int(r["votes"])
   vote_name_map[(r["election"],cid)]=(r["candidate_name"] or cid)
  else:
   try: legacy_slot=int(r["candidate"])
   except: legacy_slot=0
   legacy_vote_map[(r["election"],legacy_slot)]=legacy_vote_map.get((r["election"],legacy_slot),0)+int(r["votes"])
 # Every registered-voter calculation below comes from this one polling-register
 # lookup, resolved by station code plus stream identity.
 authoritative_registered=registered_voters_for_stream(report_station_code,report_stream)
 hp=hierarchy_payload()
 stream_to_station={norm_key(x["name"]):norm_key(x.get("poll_station_key","")) for x in hp["streams"]}
 station_labels={norm_key(x["name"]):x.get("label") or x["name"] for x in hp["poll_stations"]}
 stream_labels={norm_key(x["name"]):x.get("label") or x["name"] for x in hp["streams"]}

 geo_by_election={}
 for r in geo_rows: geo_by_election.setdefault(r["election"],[]).append(r)

 tally_sections=[]
 available,tally_ref,closed_row=tallies_available()
 tally_geo=tally_ref or {}
 catalog=current_catalog_or_empty(tally_geo)

 for e in cfg():
  candidates=[]
  seen=set()
  for cand in catalog.get(e["key"],[]):
   cid=cand["candidate_id"]
   seen.add(cid)
   candidates.append({
    "slot":cand["slot"],"candidate_id":cid,"name":cand["name"],
    "membership_no":cand.get("membership_no",""),
    "photo_url":cand.get("photo_url"),
    "votes":vote_map.get((e["key"],cid),0)
   })
  for (ek,cid),votes in vote_map.items():
   if ek==e["key"] and cid not in seen:
    candidates.append({
     "slot":999999,"candidate_id":cid,
     "name":vote_name_map.get((ek,cid),cid),
     "membership_no":"","photo_url":None,"votes":votes
    })
  for (ek,slot),votes in legacy_vote_map.items():
   if ek==e["key"]:
    candidates.append({
     "slot":slot,"candidate_id":f"LEGACY-{slot}",
     "name":f"Legacy Candidate {slot}",
     "membership_no":"","photo_url":None,"votes":votes
    })
  candidates.sort(key=lambda x:(-x["votes"],x["name"].lower()))
  previous_votes=None; previous_rank=0
  for position,cand in enumerate(candidates,start=1):
   if previous_votes is None or cand["votes"]!=previous_votes: previous_rank=position
   cand["rank"]=previous_rank; previous_votes=cand["votes"]

  stream_summary=[]; station_acc={}; election_cast=0; election_skipped=0; election_participation=0
  stream_registered_total=authoritative_registered
  for r in geo_by_election.get(e["key"],[]):
   sk=norm_key(r["stream"]); pk=norm_key(r["poll_station"]) or stream_to_station.get(sk,"")
   participation=int(r["participation"] or 0)
   skipped=int(r["skipped"] or 0)
   cast=max(0,participation-skipped)
   registered=authoritative_registered
   election_cast+=cast
   election_skipped+=skipped
   election_participation+=participation
   stream_summary.append({
    "name":stream_labels.get(sk,(r["stream"] or "").replace("_"," ").title()),
    "votes_cast":cast,
    "skipped":skipped,
    "participation":participation,
    "registered":registered,
    "not_cast":max(0,registered-participation)
   })
   st=station_acc.setdefault(pk,{
    "name":station_labels.get(pk,(r["poll_station"] or "").replace("_"," ").title()),
    "votes_cast":0,"skipped":0,"participation":0,"registered":0
   })
   st["votes_cast"]+=cast
   st["skipped"]+=skipped
   st["participation"]+=participation

  # This certificate is for one active stream. Its electorate is identical for
  # President, Governor, Senator, Woman Representative, MNA and MCA.
  if not stream_summary:
   sk=norm_key(report_stream)
   stream_summary.append({
    "name":stream_labels.get(sk,report_stream.replace("_"," ").title()),
    "votes_cast":0,"skipped":0,"participation":0,
    "registered":authoritative_registered,"not_cast":authoritative_registered
   })
  if not station_acc:
   pk=norm_key(report_poll_station)
   station_acc[pk]={
    "name":report_poll_station.replace("_"," ").title(),
    "votes_cast":0,"skipped":0,"participation":0,"registered":authoritative_registered
   }

  for pk,st in station_acc.items():
   st["streams_count"]=1
   st["registered"]=authoritative_registered
   st["not_cast"]=max(0,st["registered"]-st["participation"])

  station_summary=sorted(station_acc.values(),key=lambda x:x["name"])
  stream_summary.sort(key=lambda x:x["name"])
  station_registered_total=sum(x["registered"] for x in station_summary)

  skip_rate=(100.0*election_skipped/stream_registered_total) if stream_registered_total else 0.0
  tally_sections.append({"key":e["key"],"title":e["title"],"candidates":candidates,
   "total_votes_cast":election_cast,
   "total_skipped":election_skipped,
   "total_participation":election_participation,
   "skip_rate":skip_rate,
   "stream_registered_total":stream_registered_total,
   "station_registered_total":station_registered_total,
   "total_not_cast":max(0,stream_registered_total-election_participation),
   "streams":stream_summary,"stations":station_summary})

 return render_template("tallies.html",sections=tally_sections)


def render_tally_pdf(report_html, ref=None):
 ref=ref or {}
 report_html=re.sub(r'<button\b[^>]*>.*?</button>','',report_html,flags=re.I|re.S)
 report_html=re.sub(r'(src=["\'])(/[^"\']+)(["\'])',lambda m:m.group(1)+urljoin(request.host_url,m.group(2))+m.group(3),report_html,flags=re.I)
 css="""
 @page { size: A4; margin: 7mm; }
 body{font-family:Helvetica,Arial,sans-serif;color:#111;font-size:9pt;line-height:1.12}
 h1,h2,h3,h4,p{margin-top:0} h2{font-size:15pt;margin:0 0 5px 0} h3{font-size:11pt;margin:4px 0} h4{font-size:9.5pt;margin:3px 0}
 table{width:100%;border-collapse:collapse;margin:4px 0} th,td{border:1px solid #aaa;padding:3px 4px;text-align:left;vertical-align:middle;line-height:1.08}
 img{max-width:76px;height:auto}.print-report-header img{max-width:100%;width:100%;height:auto}
 .tally-candidate-photo,.cert-candidate-photo{max-width:56px;max-height:64px}
 .tally-actions,.no-print,.gps-help{display:none}.report-generation-meta,.summary-box{border:1px solid #bbb;padding:4px;margin:3px 0}
 .report-meta-grid,.summary-grid{display:block}.report-meta-grid div,.summary-box{margin:1px 0}.signature-space{height:26px}
 .participation,.agent-certification,.officer-certification,.signature-section{margin-top:6px!important;padding-top:4px!important}
 .signature-table th,.signature-table td,.agent-sign-table th,.agent-sign-table td{padding:2px 3px!important}
 """
 pdf_header_html=""
 try:
  header_path=os.path.join(app.root_path,"static","odm_report_header.png")
  if os.path.isfile(header_path):
   import base64
   with open(header_path,"rb") as f: header_b64=base64.b64encode(f.read()).decode("ascii")
   pdf_header_html='<div class="pdf-odm-header"><img src="data:image/png;base64,'+header_b64+'" alt="ODM Report Header"></div>'
  elif REPORT_HEADER_IMAGE_URL:
   u=REPORT_HEADER_IMAGE_URL
   if u.startswith("/"):u=urljoin(request.host_url,u)
   pdf_header_html='<div class="pdf-odm-header"><img src="'+u+'" alt="ODM Report Header"></div>'
 except Exception as exc: app.logger.warning("Could not prepare repository PDF header: %s",exc)
 geo_ident='<table border="1" cellspacing="0" cellpadding="3" width="100%" style="border:1px solid #777;margin:0 0 5px 0;font-size:9pt;line-height:1.05"><tr><td colspan="2" align="center" style="background:#f2f2f2;font-weight:bold;font-size:9.5pt;padding:3px"><b>REPORT LOCATION IDENTIFICATION</b></td></tr><tr><td width="50%"><b>County:</b> '+str(escape(ref.get('county','') or '—'))+'</td><td width="50%"><b>Constituency:</b> '+str(escape(ref.get('constituency','') or '—'))+'</td></tr><tr><td><b>Ward:</b> '+str(escape(ref.get('ward','') or '—'))+'</td><td><b>Polling Station Stream:</b> '+str(escape(ref.get('poll_station','') or '—'))+' — '+str(escape(ref.get('stream','') or '—'))+'</td></tr></table>'
 html='<!doctype html><html><head><meta charset="utf-8"><style>'+css+' .pdf-odm-header{text-align:center;margin:0 0 4px}.pdf-odm-header img{width:100%;height:auto}.pdf-stream-ident{border:1px solid #9a9a9a;background:#f7f7f7;padding:7px 9px;margin:0 0 10px;font-size:10.5pt;line-height:1.35}.pdf-stream-ident .pdf-ident-title{text-align:center;font-weight:700;font-size:11pt;margin:0 0 5px}.pdf-stream-ident table{width:100%;border-collapse:collapse;margin:0}.pdf-stream-ident td{width:50%;border:1px solid #c5c5c5;padding:5px 7px;vertical-align:top}</style></head><body>'+pdf_header_html+geo_ident+'<div style="font-weight:700;color:#9b0000;margin-bottom:5px;font-size:9pt">TRAINING / SIMULATION ONLY — no official vote was cast.</div>'+report_html+'</body></html>'
 buf=BytesIO(); result=pisa.CreatePDF(html,dest=buf,encoding="utf-8",path=request.host_url)
 if result.err: raise RuntimeError("PDF rendering failed")
 return buf.getvalue()

def repository_counts(force=False):
 if not DATABASE_URL:return {}
 init_global_lock_db()
 now=time.monotonic()
 if not force and _REPO_COUNTS_CACHE.get("value") and (now-_REPO_COUNTS_CACHE.get("at",0.0)) < _REPO_COUNTS_TTL:
  return dict(_REPO_COUNTS_CACHE["value"])
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("SELECT election,COUNT(*) AS report_count FROM simulation_pdf_reports GROUP BY election")
   value={r['election']:int(r['report_count']) for r in cur.fetchall()}
 _REPO_COUNTS_CACHE["value"]=value
 _REPO_COUNTS_CACHE["at"]=now
 return dict(value)

def invalidate_repository_cache():
 _REPO_COUNTS_CACHE["value"]={}
 _REPO_COUNTS_CACHE["at"]=0.0
 _REPO_FILTER_CACHE.clear()

def repository_filter_sets(election,filters):
 """Return cascading dropdown values with a short in-process cache."""
 key=(election,filters.get("county","") or "",filters.get("constituency","") or "",filters.get("ward","") or "",filters.get("poll_station","") or "")
 now=time.monotonic()
 cached=_REPO_FILTER_CACHE.get(key)
 if cached and (now-cached[0]) < _REPO_FILTER_TTL:
  return {k:list(v) for k,v in cached[1].items()}
 result={"counties":[],"constituencies":[],"wards":[],"stations":[],"streams":[]}
 specs=[
  ("counties","county",{}),
  ("constituencies","constituency",{"county":filters.get("county","")}),
  ("wards","ward",{"county":filters.get("county",""),"constituency":filters.get("constituency","")}),
  ("stations","poll_station",{"county":filters.get("county",""),"constituency":filters.get("constituency",""),"ward":filters.get("ward","")}),
  ("streams","stream",{"county":filters.get("county",""),"constituency":filters.get("constituency",""),"ward":filters.get("ward",""),"poll_station":filters.get("poll_station","")}),
 ]
 with lock_db() as conn:
  with conn.cursor() as cur:
   for out_key,column,parents in specs:
    if column!='county':
     parent={'constituency':'county','ward':'constituency','poll_station':'ward','stream':'poll_station'}[column]
     if not filters.get(parent):
      continue
    where=['election=%s']; params=[election]
    for pkey,val in parents.items():
     if val:
      where.append(f"{pkey}=%s"); params.append(val)
    sql=f"SELECT DISTINCT {column} AS value FROM simulation_pdf_reports WHERE {' AND '.join(where)} AND COALESCE({column},'')<>'' ORDER BY {column}"
    cur.execute(sql,params)
    result[out_key]=[r['value'] for r in cur.fetchall()]
 _REPO_FILTER_CACHE[key]=(now,{k:list(v) for k,v in result.items()})
 return result

def repository_category_rows(election,filters,page=1,per_page=50):
 where=['election=%s']; params=[election]
 for key in ('county','constituency','ward','poll_station','stream'):
  val=(filters.get(key) or '').strip()
  if val:
   where.append(f"{key}=%s"); params.append(val)
 offset=(page-1)*per_page
 base=' AND '.join(where)
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute(f"SELECT COUNT(*) AS n FROM simulation_pdf_reports WHERE {base}",params)
   total=int(cur.fetchone()['n'])
   cur.execute(f"""SELECT id,session_date,election,election_title,county,constituency,ward,poll_station,stream,closed_at,deposited_at,filename
    FROM simulation_pdf_reports WHERE {base}
    ORDER BY deposited_at DESC,id DESC LIMIT %s OFFSET %s""",params+[per_page,offset])
   rows=cur.fetchall()
 return rows,total

@app.post("/report-repository/deposit")
def deposit_report():
 available,ref,row=tallies_available()
 if not available:return jsonify({"ok":False,"error":"Reports can be deposited only after formal stream closing."}),403
 if not DATABASE_URL:return jsonify({"ok":False,"error":"Central repository requires DATABASE_URL (shared PostgreSQL)."}),503
 data=request.get_json(silent=True) or {}; election=str(data.get("election","")).strip().lower(); report_html=str(data.get("report_html","")).strip()
 allowed={k:t for k,t,_ in ELECTIONS}
 if election not in allowed or not report_html:return jsonify({"ok":False,"error":"Invalid report."}),400
 # Never create an empty repository report. A formally closed stream must
 # also have at least one completed simulated voter session.
 participants=stream_distinct_voter_count(ref)
 if participants < 1:
  return jsonify({
   "ok":False,
   "no_votes":True,
   "error":"No report generated: this polling-station stream recorded no simulated voters."
  }),409
 title=allowed[election]
 safe=lambda v: re.sub(r'[^A-Za-z0-9_-]+','_',str(v or '')).strip('_') or 'unknown'
 filename=f"{safe(title)}_Tally_{safe(ref.get('poll_station'))}_{safe(ref.get('stream'))}.pdf"
 now=kenya_now().isoformat(timespec='seconds'); init_global_lock_db()
 # Critical speed path: if this stream/category PDF already exists, do NOT run
 # xhtml2pdf again. Tally pages may be revisited many times after closing.
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""SELECT id, filename FROM simulation_pdf_reports
                  WHERE session_date=%s AND election=%s AND poll_station=%s AND stream=%s
                  LIMIT 1""",
               (ref.get('session_date',today_iso()),election,ref.get('poll_station',''),ref.get('stream','')))
   existing=cur.fetchone()
 if existing:
  return jsonify({"ok":True,"filename":existing.get('filename') or filename,"already_exists":True})
 # Generate the PDF only for a genuinely missing repository item.
 pdf=render_tally_pdf(report_html,ref)
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""INSERT INTO simulation_pdf_reports(session_date,election,election_title,county,constituency,ward,poll_station,stream,closed_at,deposited_at,filename,pdf_data)
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT(session_date,election,poll_station,stream) DO UPDATE SET election_title=EXCLUDED.election_title,county=EXCLUDED.county,constituency=EXCLUDED.constituency,ward=EXCLUDED.ward,closed_at=EXCLUDED.closed_at,deposited_at=EXCLUDED.deposited_at,filename=EXCLUDED.filename,pdf_data=EXCLUDED.pdf_data""",
    (ref.get('session_date',today_iso()),election,title,ref.get('county',''),ref.get('constituency',''),ref.get('ward',''),ref.get('poll_station',''),ref.get('stream',''),row['closed_at'] if row else '',now,filename,psycopg.Binary(pdf)))
  conn.commit()
 invalidate_repository_cache()
 return jsonify({"ok":True,"filename":filename})

@app.route("/report-repository/admin-login", methods=["GET","POST"])
def repository_admin_login():
 error=""
 if request.method=="POST":
  username=(request.form.get("username") or "").strip()
  password=request.form.get("password") or ""
  if not ADMIN_USERNAME or not ADMIN_PASSWORD:
   error="Administrator login is not configured on the server."
  elif hmac.compare_digest(username,ADMIN_USERNAME) and hmac.compare_digest(password,ADMIN_PASSWORD):
   session["repository_admin"]=True
   next_url=(request.args.get("next") or "").strip()
   if not next_url.startswith("/") or next_url.startswith("//"):
    next_url=url_for("report_repository")
   return redirect(next_url)
  else:
   error="Invalid administrator username or password."
 next_url=(request.args.get("next") or "").strip()
 if not next_url.startswith("/") or next_url.startswith("//"):
  next_url=url_for("report_repository")
 return render_template("repository_admin_login.html",error=error,next_url=next_url)


DATA_FILE_SPECS={
 "county_main":{
  "label":"County hierarchy",
  "configured":lambda:COUNTY_MAIN,
  "required":{"list_name","name","label"},
 },
 "agents_login":{
  "label":"Agents and registered voters",
  "configured":lambda:AGENTS_LOGIN,
  "required":{"agent_id_no","poll_station_code","poll_station_name","total_registered_voters"},
 },
}

MEMBERSHIP_CSV_REQUIRED={
 "national_id_no","phone_no","odm_membership_no","first_name","middle_name",
 "surname","county","constituency","ward","poll_station","poll_station_code",
 "member_id_photo","member_passport_photo"
}

MEMBERSHIP_SELF_SERVICE_FIELDS=(
 "phone_no","odm_membership_no","first_name","middle_name","surname",
 "county","constituency","ward","poll_station","poll_station_code",
)

def clean_national_id(value):
 return re.sub(r"\D","",str(value or ""))

def clean_phone(value):
 digits=re.sub(r"\D","",str(value or ""))
 if digits.startswith("254") and len(digits)==12:
  digits="0"+digits[3:]
 elif len(digits)==9:
  digits="0"+digits
 return digits

def membership_request_row(row):
 if not row:
  return None
 item=dict(row)
 for key in ("request_data","original_data"):
  value=item.get(key)
  if isinstance(value,str):
   try:item[key]=json.loads(value)
   except Exception:item[key]={}
  elif value is None:item[key]={}
 return item

def latest_membership_request(national_id):
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""SELECT * FROM membership_change_requests
                  WHERE national_id=%s ORDER BY submitted_at DESC,id DESC LIMIT 1""",
               (clean_national_id(national_id),))
   return membership_request_row(cur.fetchone())

def membership_csv_source_bytes():
 media=current_membership_csv_media()
 if media and media.get("content"):
  response=requests.get(media["content"],headers=kobo_headers(),timeout=90)
  response.raise_for_status()
  return response.content
 local_path=os.path.join(app.root_path,MEMBERSHIP_CSV_FILENAME)
 if os.path.isfile(local_path):
  with open(local_path,"rb") as source:
   return source.read()
 raise RuntimeError(f"{MEMBERSHIP_CSV_FILENAME} is missing from Kobo media and no packaged fallback exists.")

def approve_membership_request(request_id,reviewer):
 """Apply one pending request to the authoritative CSV and mark it approved."""
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("SELECT pg_advisory_xact_lock(hashtext('membership-registration-csv-update'))")
   cur.execute("SELECT * FROM membership_change_requests WHERE id=%s FOR UPDATE",(request_id,))
   request_row=membership_request_row(cur.fetchone())
   if not request_row:
    raise ValueError("Membership request was not found.")
   if request_row["status"]!="pending":
    raise ValueError("This membership request has already been reviewed.")
   raw=membership_csv_source_bytes()
   text=raw.decode("utf-8-sig",errors="replace")
   reader=csv.DictReader(StringIO(text))
   headers=list(reader.fieldnames or [])
   missing=MEMBERSHIP_CSV_REQUIRED-set(headers)
   if missing:
    raise ValueError("Current membership CSV is missing required columns: "+", ".join(sorted(missing)))
   rows=[]; matched=False; national_id=request_row["national_id"]
   updates=request_row.get("request_data") or {}
   for source_row in reader:
    row={key:("" if value is None else str(value)) for key,value in source_row.items()}
    if clean_national_id(row.get("national_id_no"))==national_id:
     if request_row["request_type"]=="new":
      raise ValueError("This National ID was added to the membership CSV while the request was pending.")
     for key in MEMBERSHIP_SELF_SERVICE_FIELDS:
      row[key]=str(updates.get(key,"")).strip()
     row["national_id_no"]=national_id
     matched=True
    rows.append(row)
   if request_row["request_type"]=="edit" and not matched:
    raise ValueError("The member record to be edited is no longer present in the membership CSV.")
   if request_row["request_type"]=="new":
    new_row={header:"" for header in headers}
    new_row["national_id_no"]=national_id
    for key in MEMBERSHIP_SELF_SERVICE_FIELDS:
     new_row[key]=str(updates.get(key,"")).strip()
    rows.append(new_row)
   output=StringIO(newline="")
   writer=csv.DictWriter(output,fieldnames=headers,extrasaction="ignore")
   writer.writeheader(); writer.writerows(rows)
   fd,temp_path=tempfile.mkstemp(prefix="membership-approved-",suffix=".csv")
   os.close(fd)
   try:
    with open(temp_path,"wb") as target:
     target.write(output.getvalue().encode("utf-8-sig"))
    validate_membership_csv(temp_path)
    replace_kobo_membership_csv(temp_path)
   finally:
    if os.path.exists(temp_path):os.unlink(temp_path)
   cur.execute("""UPDATE membership_change_requests
                  SET status='approved',reviewed_at=NOW(),reviewed_by=%s,rejection_reason=NULL
                  WHERE id=%s""",(reviewer,request_id))
  conn.commit()
 _MEMBERSHIP_CSV_CACHE.update(loaded_at=0.0,rows={},media={})

def kobo_membership_media_files():
 if not MEMBERSHIP_ASSET_UID or not KOBO_API_TOKEN:
  raise RuntimeError("MEMBERSHIP_ASSET_UID and KOBO_API_TOKEN must be configured.")
 results=[]
 url=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/files/"
 while url:
  response=requests.get(url,headers=kobo_headers(),timeout=30)
  response.raise_for_status()
  payload=response.json()
  results.extend(payload.get("results",[]))
  url=payload.get("next")
 return results

def current_membership_csv_media():
 matches=[]
 for item in kobo_membership_media_files():
  filename=str((item.get("metadata") or {}).get("filename") or "").strip()
  if filename.lower()==MEMBERSHIP_CSV_FILENAME.lower():
   matches.append(item)
 if not matches:
  return None
 return sorted(matches,key=lambda item:str(item.get("date_created") or item.get("uid") or ""),reverse=True)[0]

def normalize_uploaded_csv_utf8(path):
 """Decode common spreadsheet CSV encodings and rewrite as UTF-8 with BOM."""
 with open(path,"rb") as source:
  raw=source.read()
 if not raw:
  raise ValueError("The uploaded CSV is empty.")
 if b"\x00" in raw:
  raise ValueError("The uploaded file appears to be binary, not a CSV text file.")
 decoded=None; source_encoding=None
 for encoding in ("utf-8-sig","utf-8","cp1252","iso-8859-1"):
  try:
   decoded=raw.decode(encoding,errors="strict")
   source_encoding=encoding
   break
  except UnicodeDecodeError:
   continue
 if decoded is None:
  raise ValueError("The CSV text encoding could not be recognized. Save it as UTF-8 CSV and try again.")
 # Kobo and the application receive one predictable encoding regardless of
 # whether Excel exported UTF-8, Windows-1252 or Latin-1 source bytes.
 with open(path,"wb") as target:
  target.write(decoded.encode("utf-8-sig"))
 return source_encoding

def validate_membership_csv(path):
 with open(path,encoding="utf-8-sig",errors="strict",newline="") as source:
  reader=csv.DictReader(source)
  headers=set(reader.fieldnames or [])
  missing=MEMBERSHIP_CSV_REQUIRED-headers
  if missing:
   raise ValueError("Missing required columns: "+", ".join(sorted(missing)))
  rows=0; ids=set()
  for row in reader:
   rows+=1
   national_id=re.sub(r"\D","",str(row.get("national_id_no") or ""))
   if not re.fullmatch(r"\d{7,8}",national_id):
    raise ValueError(f"Row {rows + 1} has an invalid National ID.")
   if national_id in ids:
    raise ValueError(f"Duplicate National ID found at row {rows + 1}.")
   ids.add(national_id)
  if rows<1:
   raise ValueError("The uploaded CSV contains no data rows.")
 return rows

def replace_kobo_membership_csv(path):
 old_files=[]
 for item in kobo_membership_media_files():
  filename=str((item.get("metadata") or {}).get("filename") or "").strip()
  if filename.lower()==MEMBERSHIP_CSV_FILENAME.lower():
   old_files.append(item)
 endpoint=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/files/"
 upload_endpoint=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/files.json"

 def error_detail(response):
  try:
   payload=response.json()
   detail=json.dumps(payload,ensure_ascii=False) if payload else ""
  except Exception:
   detail=""
  if not detail:
   detail=(response.text or "").strip()
  detail=re.sub(r"\s+"," ",detail)[:800]
  return f"HTTP {response.status_code}: {detail}" if detail else f"HTTP {response.status_code}"

 # Kobo reserves form-media filenames and rejects a second file with the same
 # name. Retain the current bytes for rollback, remove only matching copies,
 # and then upload the already validated replacement.
 rollback_bytes=None
 if old_files:
  current=sorted(old_files,key=lambda item:str(item.get("date_created") or item.get("uid") or ""),reverse=True)[0]
  content_url=str(current.get("content") or "").strip()
  if not content_url:
   current_uid=str(current.get("uid") or "")
   content_url=f"{endpoint}{current_uid}/content/"
  backup_response=requests.get(content_url,headers=kobo_headers(),timeout=90)
  if not backup_response.ok:
   raise RuntimeError("Could not back up the current Kobo membership CSV before replacement: "+error_detail(backup_response))
  rollback_bytes=backup_response.content

 for item in old_files:
  uid=str(item.get("uid") or "")
  if not uid:
   continue
  delete_response=requests.delete(f"{endpoint}{uid}/",headers=kobo_headers(),timeout=30)
  if delete_response.status_code not in (200,202,204,404):
   raise RuntimeError("Kobo could not remove the previous membership CSV: "+error_detail(delete_response))

 try:
  with open(path,"rb") as source:
   response=requests.post(
    upload_endpoint,headers=kobo_headers(),data={
     "file_type":"form_media",
     "description":"ODM membership registration fallback CSV",
     "metadata":json.dumps({"filename":MEMBERSHIP_CSV_FILENAME}),
    },
    files={"content":(MEMBERSHIP_CSV_FILENAME,source,"text/csv")},timeout=90
   )
  if not response.ok:
   raise RuntimeError(error_detail(response))
 except Exception as upload_exc:
  rollback_note=""
  if rollback_bytes is not None:
   restore_response=requests.post(
    upload_endpoint,headers=kobo_headers(),data={
     "file_type":"form_media",
     "description":"ODM membership registration fallback CSV (restored backup)",
     "metadata":json.dumps({"filename":MEMBERSHIP_CSV_FILENAME}),
    },
    files={"content":(MEMBERSHIP_CSV_FILENAME,BytesIO(rollback_bytes),"text/csv")},timeout=90
   )
   rollback_note=" The previous Kobo file was restored." if restore_response.ok else " WARNING: Kobo also rejected restoration of the previous file: "+error_detail(restore_response)
  raise RuntimeError("Kobo rejected the replacement upload at "+upload_endpoint+": "+str(upload_exc)+rollback_note) from upload_exc

 _MEMBERSHIP_CSV_CACHE.update(loaded_at=0.0,rows={},media={})
 return []

def _all_kobo_membership_submissions():
 if not MEMBERSHIP_ASSET_UID or not KOBO_API_TOKEN:
  raise RuntimeError("MEMBERSHIP_ASSET_UID and KOBO_API_TOKEN must be configured.")
 rows=[]; url=f"{KOBO_BASE_URL}/api/v2/assets/{MEMBERSHIP_ASSET_UID}/data/?limit=1000"
 while url:
  response=requests.get(url,headers=kobo_headers(),timeout=60); response.raise_for_status()
  payload=response.json(); rows.extend(payload.get("results",[])); url=payload.get("next")
 return rows

def _register_member_from_kobo(row):
 first=field(row,"members_particulars/first_name","members_particulars/first_name1","basics/first_name","first_name")
 middle=field(row,"members_particulars/other_names","members_particulars/other_names1","members_particulars/middle_name","middle_name")
 surname=field(row,"members_particulars/surname","members_particulars/surname1","basics/surname","surname")
 full_name=" ".join(value for value in (first,middle,surname) if value).strip() or field(row,"stored_particulars_confirmed/full_name","full_name","name")
 return {"member_id":field(row,"basics/national_id_no","national_id_no"),"full_name":full_name,
  "odm_registration_no":field(row,"members_particulars/odm_membership_no","stored_particulars_confirmed/odm_membership_no_confirmed","odm_membership_no"),
  "county":field(row,"electorals_units/county","electorals_units/selected_county","electorals_units/selected_county1","electorals_units/county_name","particulars_confirmation/selected_county1_confirmation","stored_particulars_confirmed/selected_county1_confirmed","county"),
  "constituency":field(row,"electorals_units/constituency","electorals_units/selected_constituency","electorals_units/selected_constituency1","particulars_confirmation/selected_constituency1_confirmation","stored_particulars_confirmed/selected_constituency1_confirmed","constituency"),
  "ward":field(row,"electorals_units/ward","electorals_units/selected_ward","electorals_units/selected_ward1","particulars_confirmation/selected_ward1_confirmation","stored_particulars_confirmed/selected_ward1_confirmed","ward"),
  "polling_station":field(row,"electorals_units/poll_station_label","electorals_units/selected_poll_station1","stored_particulars_confirmed/selected_poll_station1_confirmed","poll_station"),
  "submission_time":str(row.get("_submission_time") or ""),"source":"Kobo submission"}

def _register_member_from_csv(row):
 return {"member_id":str(row.get("national_id_no") or "").strip(),
  "full_name":" ".join(str(row.get(key) or "").strip() for key in ("first_name","middle_name","surname") if str(row.get(key) or "").strip()),
  "odm_registration_no":str(row.get("odm_membership_no") or "").strip(),"county":str(row.get("county") or "").strip(),
  "constituency":str(row.get("constituency") or "").strip(),"ward":str(row.get("ward") or "").strip(),
  "polling_station":str(row.get("poll_station") or "").strip(),"submission_time":"","source":MEMBERSHIP_CSV_FILENAME}

def _enrich_register_geography(member):
 """Fill/canonicalize a member's electoral labels from county_main.csv."""
 index=_register_geography_index()
 def first(kind,value,parent_key="",parent_field=""):
  candidates=index[kind].get(station_key(value),[])
  if parent_key and parent_field:
   narrowed=[row for row in candidates if norm_key(row.get(parent_field))==norm_key(parent_key)]
   if narrowed: candidates=narrowed
  return candidates[0] if candidates else None
 county=first("counties",member.get("county"))
 constituency=first("constituencies",member.get("constituency"),(county or {}).get("name"),"county_key")
 ward=first("wards",member.get("ward"),(constituency or {}).get("name"),"constituency_key")
 station=first("stations",member.get("polling_station"),(ward or {}).get("name"),"ward_key")
 if not ward and station: ward=first("wards",station.get("ward_key"))
 if not constituency and ward: constituency=first("constituencies",ward.get("constituency_key"))
 if not county and constituency: county=first("counties",constituency.get("county_key"))
 if county: member["county"]=county.get("label") or member.get("county","")
 if constituency: member["constituency"]=constituency.get("label") or member.get("constituency","")
 if ward: member["ward"]=ward.get("label") or member.get("ward","")
 if station: member["polling_station"]=station.get("label") or member.get("polling_station","")
 return member

def _register_geography_index():
 """Build the register's hierarchy lookups once per worker, not once per voter."""
 global _REGISTER_GEO_INDEX
 if _REGISTER_GEO_INDEX is not None: return _REGISTER_GEO_INDEX
 hierarchy=_hierarchy_cache()
 index={"counties":{},"constituencies":{},"wards":{},"stations":{}}
 sources={
  "counties":hierarchy["counties"],
  "constituencies":[row for rows in hierarchy["constituencies"].values() for row in rows],
  "wards":[row for rows in hierarchy["wards"].values() for row in rows],
  "stations":[row for rows in hierarchy["poll_stations"].values() for row in rows],
 }
 for kind,rows in sources.items():
  for row in rows:
   for alias in {station_key(row.get("name")),station_key(row.get("label"))}:
    if alias: index[kind].setdefault(alias,[]).append(row)
 _REGISTER_GEO_INDEX=index
 return index

def combined_voters_register():
 """Merge both sources by National ID; the newest live Kobo record wins."""
 kobo_rows=_all_kobo_membership_submissions(); newest={}
 for raw in kobo_rows:
  member=_register_member_from_kobo(raw); member_id=re.sub(r"\D","",member["member_id"])
  if not member_id: continue
  member["member_id"]=member_id; existing=newest.get(member_id)
  if not existing or member["submission_time"]>=existing["submission_time"]: newest[member_id]=member
 csv_rows=_load_membership_csv(); csv_added=0; csv_fields_filled=0
 for member_id,raw in csv_rows.items():
  csv_member=_register_member_from_csv(raw)
  if member_id not in newest: newest[member_id]=csv_member; csv_added+=1
  else:
   for key in ("full_name","odm_registration_no","county","constituency","ward","polling_station"):
    if not str(newest[member_id].get(key) or "").strip() and str(csv_member.get(key) or "").strip():
     newest[member_id][key]=csv_member[key]; csv_fields_filled+=1
 members=[_enrich_register_geography(member) for member in newest.values()]
 members.sort(key=lambda member:(station_key(member.get("county")),station_key(member.get("constituency")),station_key(member.get("ward")),station_key(member.get("polling_station")),station_key(member.get("full_name")),member.get("member_id","")))
 return members,{"kobo_submissions":len(kobo_rows),"csv_records":len(csv_rows),"csv_added":csv_added,"csv_fields_filled":csv_fields_filled,"unique_members":len(members)}

def _register_filters():
 return {key:(request.args.get(key) or "").strip() for key in ("county","constituency","ward","polling_station")}

def _register_hierarchy_options(filters):
 """Return the county_main.csv branch matching the current register filters."""
 hierarchy=_hierarchy_cache()
 def chosen(rows,value):
  wanted=station_key(value)
  return next((row for row in rows if wanted and wanted in (station_key(row.get("name")),station_key(row.get("label")))),None)
 counties=hierarchy["counties"]
 county=chosen(counties,filters.get("county"))
 constituencies=hierarchy["constituencies"].get(norm_key((county or {}).get("name","")),[]) if county else []
 constituency=chosen(constituencies,filters.get("constituency"))
 wards=hierarchy["wards"].get(norm_key((constituency or {}).get("name","")),[]) if constituency else []
 ward=chosen(wards,filters.get("ward"))
 stations=hierarchy["poll_stations"].get(norm_key((ward or {}).get("name","")),[]) if ward else []
 return {"counties":counties,"constituencies":constituencies,"wards":wards,"stations":stations}

def _filter_register(members,filters):
 return [member for member in members if all(not filters.get(key) or station_key(member.get(key))==station_key(filters[key]) for key in filters)]

def _register_station_groups(members):
 groups=[]
 for member in members:
  key=tuple(member.get(k,"") for k in ("county","constituency","ward","polling_station"))
  if not groups or groups[-1][0]!=key: groups.append((key,[]))
  groups[-1][1].append(member)
 return groups

def _safe_register_filename(filters,extension):
 area=next((filters[key] for key in ("polling_station","ward","constituency","county") if filters.get(key)),"National")
 area=re.sub(r"[^A-Za-z0-9_-]+","_",area).strip("_") or "National"
 return f"Voters_Register_{area}.{extension}"

WINNERS_REPORT_ELECTIONS=(
 ("president","President",()),
 ("governor","Governor",("county",)),
 ("senator","Senator",("county",)),
 ("woman_rep","Women Representative",("county",)),
 ("mna","Member of National Assembly",("county","constituency")),
 ("mca","Member of County Assembly",("county","constituency","ward")),
)

def _winner_source_rows(election):
 """Read the same durable anonymous tallies used by the results dashboards."""
 persistent=_persistent_dashboard_snapshot(election)
 if persistent is not None: return persistent[0]
 aliases=dashboard_election_aliases(election); marks=','.join('?' for _ in aliases)
 c=con()
 try:
  return c.execute(f"""
   SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,COUNT(*) AS n
   FROM demo_votes WHERE LOWER(election) IN ({marks})
   GROUP BY county,constituency,ward,poll_station,stream,candidate_id,candidate_name
  """,aliases).fetchall()
 finally: c.close()

def _winner_area_label(area_fields,area):
 if not area_fields: return "National"
 values=[str(area.get(field) or "").strip() for field in area_fields]
 return " / ".join(value or f"{field.replace('_',' ').title()} not specified" for field,value in zip(area_fields,values))

def winners_and_runners_up_report(filters=None):
 filters=filters or {}
 sections=[]
 try: registered_catalog=candidate_portal_catalog({})
 except Exception as exc:
  app.logger.warning("Candidate catalogue unavailable for winners report; using stored vote candidates: %s",exc)
  registered_catalog={key:[] for key,_,_ in ELECTIONS}
 for election,title,area_fields in WINNERS_REPORT_ELECTIONS:
  county_filter=(filters.get(f"{election}_county") or "").strip() if election in ("mna","mca") else ""
  contests={}
  for row in _winner_source_rows(election):
   cid=str(row["candidate_id"] or "").strip()
   if not cid or cid=="__SKIP__": continue
   area={field:str(row[field] or "").strip() for field in area_fields}
   if county_filter and station_key(area.get("county"))!=station_key(county_filter): continue
   area_key=tuple(station_key(area[field]) for field in area_fields)
   contest=contests.setdefault(area_key,{"area":area,"candidates":{}})
   candidate=contest["candidates"].setdefault(cid,{"candidate_id":cid,"name":str(row["candidate_name"] or cid).strip(),"votes":0})
   candidate["votes"]+=int(row["n"] or 0)
   if str(row["candidate_name"] or "").strip(): candidate["name"]=str(row["candidate_name"]).strip()
  for candidate in registered_catalog.get(election,[]):
   cid=str(candidate.get("candidate_id") or "").strip()
   if not cid: continue
   area={field:str(candidate.get(field) or "").strip() for field in area_fields}
   if area_fields and any(not area[field] for field in area_fields): continue
   if county_filter and station_key(area.get("county"))!=station_key(county_filter): continue
   area_key=tuple(station_key(area[field]) for field in area_fields)
   contest=contests.setdefault(area_key,{"area":area,"candidates":{}})
   contest["candidates"].setdefault(cid,{"candidate_id":cid,"name":str(candidate.get("name") or cid).strip(),"votes":0})
  results=[]
  for contest in contests.values():
   candidates=sorted(contest["candidates"].values(),key=lambda item:(-item["votes"],station_key(item["name"]),item["candidate_id"]))
   total=sum(item["votes"] for item in candidates)
   if total==0:
    leaders=[{**item,"rank":0,"result":"No result","share":0.0} for item in candidates[:2]]
    results.append({"area":contest["area"],"area_label":_winner_area_label(area_fields,contest["area"]),"total_votes":0,"leaders":leaders})
    continue
   distinct_votes=sorted({item["votes"] for item in candidates},reverse=True)
   rank_for_votes={votes:index+1 for index,votes in enumerate(distinct_votes)}
   rank_counts={rank:sum(1 for item in candidates if rank_for_votes[item["votes"]]==rank) for rank in (1,2)}
   leaders=[]
   for item in candidates:
    rank=rank_for_votes[item["votes"]]
    if rank>2: continue
    result=("Joint winner" if rank_counts.get(1,0)>1 else "Winner") if rank==1 else ("Joint runner-up" if rank_counts.get(2,0)>1 else "Runner-up")
    leaders.append({**item,"rank":rank,"result":result,"share":round((item["votes"]*100/total),2) if total else 0.0})
   results.append({"area":contest["area"],"area_label":_winner_area_label(area_fields,contest["area"]),"total_votes":total,"leaders":leaders})
  results.sort(key=lambda item:tuple(station_key(item["area"].get(field)) for field in area_fields))
  sections.append({"election":election,"title":title,"contests":results,"contest_count":len(results),"county_filter":county_filter})
 return sections

def _register_pdf(members,filters):
 output=BytesIO(); page_width,_=landscape(A4); styles=getSampleStyleSheet()
 title_style=ParagraphStyle("RegisterTitle",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=16,leading=19,alignment=TA_CENTER,textColor=colors.HexColor("#14213d"),spaceAfter=6)
 station_style=ParagraphStyle("Station",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=12,leading=15,textColor=colors.HexColor("#111111"),spaceAfter=5)
 small=ParagraphStyle("Small",parent=styles["BodyText"],fontName="Helvetica",fontSize=7.2,leading=8.5)
 header=ParagraphStyle("Header",parent=small,fontName="Helvetica-Bold",textColor=colors.white,alignment=TA_CENTER)
 def footer(canvas,doc):
  canvas.saveState(); canvas.setFont("Helvetica",7); canvas.setFillColor(colors.HexColor("#555555")); canvas.drawString(12*mm,8*mm,"ODM Voters Register - Election Officials' Physical Verification Copy"); canvas.drawRightString(page_width-12*mm,8*mm,f"Page {doc.page}"); canvas.restoreState()
 doc=SimpleDocTemplate(output,pagesize=landscape(A4),rightMargin=10*mm,leftMargin=10*mm,topMargin=10*mm,bottomMargin=13*mm,title="ODM Voters Register")
 story=[]; groups=_register_station_groups(members)
 for index,(area,station_members) in enumerate(groups):
  county,constituency,ward,polling_station=area
  story.extend([Paragraph("ODM VOTERS REGISTER",title_style),Paragraph(f"Polling Station: {escape(polling_station or 'Not specified')}",station_style),Paragraph(f"County: {escape(county or 'Not specified')} &nbsp;&nbsp; Constituency: {escape(constituency or 'Not specified')} &nbsp;&nbsp; Ward: {escape(ward or 'Not specified')} &nbsp;&nbsp; Registered members: {len(station_members):,}",small),Spacer(1,4*mm)])
  data=[[Paragraph(value,header) for value in ("No.","Member ID","Full name","ODM registration no.","County","Constituency","Ward","Polling station","Checked")]]
  for number,member in enumerate(station_members,1):
   values=(str(number),member["member_id"],member["full_name"],member["odm_registration_no"],member["county"],member["constituency"],member["ward"],member["polling_station"],"")
   data.append([Paragraph(escape(str(value or "")),small) for value in values])
  table=Table(data,colWidths=[10*mm,22*mm,43*mm,30*mm,24*mm,31*mm,29*mm,50*mm,16*mm],repeatRows=1,hAlign="LEFT")
  table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#ef7d00")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#9a9a9a")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f5f7fa")])]))
  story.append(table)
  if index<len(groups)-1: story.append(PageBreak())
 if not groups: story=[Paragraph("ODM VOTERS REGISTER",title_style),Paragraph("No members matched the selected filters.",styles["BodyText"])]
 doc.build(story,onFirstPage=footer,onLaterPages=footer); return output.getvalue()


def validate_admin_csv(path,file_type):
 spec=DATA_FILE_SPECS[file_type]
 with open(path,encoding="utf-8-sig",errors="strict",newline="") as f:
  reader=csv.DictReader(f)
  headers=set(reader.fieldnames or [])
  missing=spec["required"]-headers
  if missing:
   raise ValueError("Missing required columns: "+", ".join(sorted(missing)))
  rows=0; kinds=set()
  for row in reader:
   rows+=1
   if file_type=="county_main":
    kinds.add((row.get("list_name") or "").strip())
   elif rows<=200 and str(row.get("total_registered_voters") or "").strip():
    if to_int(row.get("total_registered_voters"))<0:
     raise ValueError("Registered-voter totals cannot be negative.")
  if rows<1:
   raise ValueError("The uploaded CSV contains no data rows.")
  if file_type=="county_main" and not {"county","constituency","ward","poll_station","poll_station_stream"}.issubset(kinds):
   raise ValueError("County hierarchy must contain county, constituency, ward, poll_station and poll_station_stream rows.")
 return rows


@app.route("/admin/data-files",methods=["GET","POST"])
def admin_data_files():
 global _HIERARCHY_CACHE,_REGISTER_GEO_INDEX
 if not repository_admin_logged_in():
  return redirect(url_for("repository_admin_login",next=url_for("admin_data_files")))

 token=session.get("data_files_csrf")
 if not token:
  token=secrets.token_urlsafe(32)
  session["data_files_csrf"]=token

 if request.method=="POST":
  supplied=request.form.get("csrf_token","")
  if not supplied or not hmac.compare_digest(supplied,token):
   session["data_files_error"]="Security token expired. Reload the page and try again."
   return redirect(url_for("admin_data_files"))
  file_type=(request.form.get("file_type") or "").strip()
  spec=DATA_FILE_SPECS.get(file_type)
  upload=request.files.get("csv_file")
  is_membership=file_type=="membership_registration"
  if (not spec and not is_membership) or not upload or not upload.filename:
   session["data_files_error"]="Select the CSV file to upload."
   return redirect(url_for("admin_data_files"))
  if not upload.filename.lower().endswith(".csv"):
   session["data_files_error"]="Only .csv files are accepted."
   return redirect(url_for("admin_data_files"))

  if is_membership:
   fd,temp_path=tempfile.mkstemp(prefix="membership-upload-",suffix=".csv")
   os.close(fd)
   try:
    upload.save(temp_path)
    source_encoding=normalize_uploaded_csv_utf8(temp_path)
    rows=validate_membership_csv(temp_path)
    delete_failures=replace_kobo_membership_csv(temp_path)
    if delete_failures:
     session["data_files_message"]=f"Membership Registration CSV uploaded to Kobo ({rows:,} rows; normalized from {source_encoding} to UTF-8). Kobo retained {len(delete_failures)} older copy/copies that could not be removed."
    else:
     session["data_files_message"]=f"Membership Registration CSV replaced in Kobo media successfully ({rows:,} rows; normalized from {source_encoding} to UTF-8)."
   except Exception as exc:
    session["data_files_error"]=f"Membership CSV upload rejected: {exc}"
   finally:
    if os.path.exists(temp_path):
     os.unlink(temp_path)
   return redirect(url_for("admin_data_files"))

  target=managed_data_file(spec["configured"]())
  os.makedirs(os.path.dirname(target),exist_ok=True)
  fd,temp_path=tempfile.mkstemp(prefix="data-upload-",suffix=".csv",dir=os.path.dirname(target))
  os.close(fd)
  try:
   upload.save(temp_path)
   normalize_uploaded_csv_utf8(temp_path)
   rows=validate_admin_csv(temp_path,file_type)
   backup_root=os.path.join(DATA_UPLOAD_DIR or app.root_path,"data_backups")
   os.makedirs(backup_root,exist_ok=True)
   if os.path.isfile(target):
    stamp=kenya_now().strftime("%Y%m%d-%H%M%S-%f")
    shutil.copy2(target,os.path.join(backup_root,f"{os.path.basename(target)}.{stamp}.bak"))
   os.replace(temp_path,target)
   if file_type=="county_main":
    with _HIERARCHY_LOCK:
     _HIERARCHY_CACHE=None
     _REGISTER_GEO_INDEX=None
   session["data_files_message"]=f"{spec['label']} CSV replaced successfully ({rows:,} rows)."
  except Exception as exc:
   if os.path.exists(temp_path):
    os.unlink(temp_path)
   session["data_files_error"]=f"Upload rejected: {exc}"
  return redirect(url_for("admin_data_files"))

 files=[]
 for key,spec in DATA_FILE_SPECS.items():
  path=managed_data_file(spec["configured"]())
  files.append({
   "key":key,"label":spec["label"],"filename":os.path.basename(path),
   "size":os.path.getsize(path) if os.path.isfile(path) else 0,
   "modified":datetime.fromtimestamp(os.path.getmtime(path),KENYA_TZ).isoformat(timespec="seconds") if os.path.isfile(path) else "Missing"
  })
 try:
  membership_media=current_membership_csv_media()
  metadata=(membership_media or {}).get("metadata") or {}
  files.append({
   "key":"membership_registration","label":"Membership Registration (Kobo media)",
   "filename":metadata.get("filename") or MEMBERSHIP_CSV_FILENAME,
   "size":int(metadata.get("size") or 0),
   "modified":membership_media.get("date_created") if membership_media else "Missing from Kobo media",
   "remote":True,
  })
 except Exception as exc:
  files.append({
   "key":"membership_registration","label":"Membership Registration (Kobo media)",
   "filename":MEMBERSHIP_CSV_FILENAME,"size":0,
   "modified":"Unable to read Kobo media: "+str(exc),"remote":True,
  })
 return render_template(
 "admin_data_files.html",files=files,csrf_token=token,
  message=session.pop("data_files_message",None),error=session.pop("data_files_error",None),
  persistent=bool(DATA_UPLOAD_DIR),voter_verification_base_url=VOTER_VERIFICATION_BASE_URL,
  candidate_portal_base_url=CANDIDATE_PORTAL_BASE_URL
 )


@app.route("/membership",methods=["GET","POST"])
def membership_portal():
 """Public entry point for private membership status and change requests."""
 error=None
 if request.method=="POST":
  national_id=clean_national_id(request.form.get("national_id"))
  phone=clean_phone(request.form.get("phone"))
  if not re.fullmatch(r"\d{7,8}",national_id):
   error="Enter a valid 7- or 8-digit National ID number."
  elif not re.fullmatch(r"0\d{9}",phone):
   error="Enter a valid registered phone number."
  else:
   try:
    csv_row=_load_membership_csv().get(national_id)
    latest=latest_membership_request(national_id)
    expected_phone=clean_phone((csv_row or {}).get("phone_no"))
    if not csv_row and latest:
     expected_phone=clean_phone((latest.get("request_data") or {}).get("phone_no"))
    if expected_phone and not hmac.compare_digest(phone,expected_phone):
     error="The National ID and phone number do not match the membership record."
    else:
     session["membership_member_id"]=national_id
     session["membership_member_phone"]=phone
     session["membership_member_existing"]=bool(csv_row)
     session["membership_csrf"]=secrets.token_urlsafe(32)
     return redirect(url_for("membership_application"))
   except Exception as exc:
    app.logger.exception("Membership portal lookup failed")
    error=f"Membership lookup is temporarily unavailable: {exc}"
 return render_template("membership_portal.html",error=error)


@app.route("/membership/application",methods=["GET","POST"])
def membership_application():
 national_id=clean_national_id(session.get("membership_member_id"))
 if not national_id:
  return redirect(url_for("membership_portal"))
 try:
  current=_load_membership_csv().get(national_id)
  latest=latest_membership_request(national_id)
 except Exception as exc:
  return render_template("membership_application.html",national_id=national_id,current={},values={},latest=None,csrf_token=session.get("membership_csrf",""),error=str(exc),message=None),502
 token=session.get("membership_csrf") or secrets.token_urlsafe(32)
 session["membership_csrf"]=token
 message=session.pop("membership_message",None); error=None
 pending=bool(latest and latest.get("status")=="pending")
 values=dict(current or {})
 if latest and not current and latest.get("request_data"):
  values.update(latest["request_data"])
 values.setdefault("phone_no",session.get("membership_member_phone",""))
 if request.method=="POST":
  supplied=request.form.get("csrf_token","")
  if not supplied or not hmac.compare_digest(supplied,token):
   error="Security token expired. Reload the page and try again."
  elif pending:
   error="Your previous request is still pending administrator review."
  else:
   submitted={key:str(request.form.get(key) or "").strip() for key in MEMBERSHIP_SELF_SERVICE_FIELDS}
   submitted["phone_no"]=clean_phone(submitted["phone_no"])
   values.update(submitted)
   required_labels={
    "phone_no":"Phone number","odm_membership_no":"ODM registration number",
    "first_name":"First name","surname":"Surname","county":"County",
    "constituency":"Constituency","ward":"Ward","poll_station":"Polling station",
   }
   missing=[label for key,label in required_labels.items() if not submitted.get(key)]
   if missing:
    error="Complete the following fields: "+", ".join(missing)+"."
   elif not re.fullmatch(r"0\d{9}",submitted["phone_no"]):
    error="Enter a valid phone number."
   else:
    request_type="edit" if current else "new"
    init_global_lock_db()
    with lock_db() as conn:
     with conn.cursor() as cur:
      cur.execute("""INSERT INTO membership_change_requests
       (national_id,request_type,request_data,original_data,status)
       VALUES(%s,%s,%s::jsonb,%s::jsonb,'pending')""",
       (national_id,request_type,json.dumps(submitted),json.dumps(current or {})))
     conn.commit()
    session["membership_message"]="Your membership request was submitted and is pending administrator approval."
    return redirect(url_for("membership_application"))
 return render_template("membership_application.html",national_id=national_id,current=current or {},values=values,latest=latest,csrf_token=token,error=error,message=message)


@app.post("/membership/logout")
def membership_logout():
 for key in ("membership_member_id","membership_member_phone","membership_member_existing","membership_csrf","membership_message"):
  session.pop(key,None)
 return redirect(url_for("membership_portal"))


@app.route("/admin/membership-requests",methods=["GET","POST"])
def admin_membership_requests():
 if not repository_admin_logged_in():
  return redirect(url_for("repository_admin_login",next=request.path))
 token=session.get("membership_admin_csrf") or secrets.token_urlsafe(32)
 session["membership_admin_csrf"]=token
 message=session.pop("membership_admin_message",None); error=session.pop("membership_admin_error",None)
 if request.method=="POST":
  supplied=request.form.get("csrf_token","")
  if not supplied or not hmac.compare_digest(supplied,token):
   session["membership_admin_error"]="Security token expired. Reload the page and try again."
   return redirect(url_for("admin_membership_requests"))
  try:
   request_id=int(request.form.get("request_id") or 0)
   decision=(request.form.get("decision") or "").strip().lower()
   if decision=="approve":
    approve_membership_request(request_id,ADMIN_USERNAME or "administrator")
    session["membership_admin_message"]="Membership request approved and the Kobo CSV was updated."
   elif decision=="reject":
    reason=(request.form.get("rejection_reason") or "").strip()
    if not reason:raise ValueError("Enter a reason for rejection.")
    init_global_lock_db()
    with lock_db() as conn:
     with conn.cursor() as cur:
      cur.execute("""UPDATE membership_change_requests SET status='rejected',reviewed_at=NOW(),
                     reviewed_by=%s,rejection_reason=%s WHERE id=%s AND status='pending'""",
                  (ADMIN_USERNAME or "administrator",reason,request_id))
      if cur.rowcount!=1:raise ValueError("The request was not found or was already reviewed.")
     conn.commit()
    session["membership_admin_message"]="Membership request rejected."
   else:raise ValueError("Choose Approve or Reject.")
  except Exception as exc:
   app.logger.exception("Membership request review failed")
   session["membership_admin_error"]=str(exc)
  return redirect(url_for("admin_membership_requests",status=request.args.get("status","pending")))
 status=(request.args.get("status") or "pending").strip().lower()
 if status not in ("pending","approved","rejected","all"):status="pending"
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   if status=="all":
    cur.execute("SELECT * FROM membership_change_requests ORDER BY submitted_at DESC,id DESC LIMIT 500")
   else:
    cur.execute("SELECT * FROM membership_change_requests WHERE status=%s ORDER BY submitted_at DESC,id DESC LIMIT 500",(status,))
   rows=[membership_request_row(row) for row in cur.fetchall()]
 return render_template("admin_membership_requests.html",rows=rows,status=status,csrf_token=token,message=message,error=error)


@app.get("/admin/data-files/download/<file_type>")
def download_admin_data_file(file_type):
 if not repository_admin_logged_in():
  return redirect(url_for("repository_admin_login",next=request.path))
 spec=DATA_FILE_SPECS.get((file_type or "").strip())
 if (file_type or "").strip()=="membership_registration":
  try:
   media=current_membership_csv_media()
   if not media or not media.get("content"):
    return Response("membership_registration.csv is missing from Kobo media.",status=404,mimetype="text/plain")
   upstream=requests.get(media["content"],headers=kobo_headers(),timeout=60)
   upstream.raise_for_status()
   return Response(upstream.content,mimetype="text/csv; charset=utf-8",headers={
    "Content-Disposition":f'attachment; filename="{MEMBERSHIP_CSV_FILENAME}"',
    "Cache-Control":"no-store",
   })
  except Exception as exc:
   return Response(f"Unable to download membership CSV from Kobo: {exc}",status=502,mimetype="text/plain")
 if not spec:
  return Response("Unknown data file.",status=404,mimetype="text/plain")
 path=managed_data_file(spec["configured"]())
 if not os.path.isfile(path):
  return Response("Current data file is missing.",status=404,mimetype="text/plain")
 return send_file(path,mimetype="text/csv; charset=utf-8",as_attachment=True,
                  download_name=os.path.basename(path),conditional=True)

@app.get("/admin/user-manual")
def admin_user_manual():
 if not repository_admin_logged_in():
  return redirect(url_for("repository_admin_login",next=request.path))
 return render_template("admin_user_manual.html")

@app.get("/admin/user-manual/download")
def download_admin_user_manual():
 if not repository_admin_logged_in():
  return redirect(url_for("repository_admin_login",next=request.path))
 path=os.path.join(app.root_path,"static","manuals","ODM_2027_Nomination_System_User_Manual_V1.docx")
 if not os.path.isfile(path):
  return Response("User manual is unavailable on this deployment.",status=404,mimetype="text/plain")
 return send_file(path,
  mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  as_attachment=True,download_name="ODM_2027_Nomination_System_User_Manual_V1.docx",conditional=True)

@app.get("/admin/voters-register")
def admin_voters_register():
 if not repository_admin_logged_in(): return redirect(url_for("repository_admin_login",next=request.full_path))
 filters=_register_filters()
 try:
  members,stats=combined_voters_register(); members=_filter_register(members,filters); groups=_register_station_groups(members)
  return render_template("admin_voters_register.html",groups=groups,filters=filters,options=_register_hierarchy_options(filters),stats=stats,total=len(members),error=None)
 except Exception as exc:
  return render_template("admin_voters_register.html",groups=[],filters=filters,options=_register_hierarchy_options(filters),stats={},total=0,error=str(exc)),502

@app.get("/admin/voters-register.csv")
def download_voters_register_csv():
 if not repository_admin_logged_in(): return redirect(url_for("repository_admin_login",next=request.full_path))
 filters=_register_filters()
 try:
  members,_=combined_voters_register(); members=_filter_register(members,filters); output=StringIO(newline="")
  columns=["member_id","full_name","odm_registration_no","county","constituency","ward","polling_station"]
  writer=csv.DictWriter(output,fieldnames=columns); writer.writeheader()
  for member in members: writer.writerow({key:member.get(key,"") for key in columns})
  return Response("\ufeff"+output.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{_safe_register_filename(filters,"csv")}"',"Cache-Control":"no-store"})
 except Exception as exc: return Response(f"Unable to generate voters register: {exc}",status=502,mimetype="text/plain")

@app.get("/admin/voters-register.pdf")
def download_voters_register_pdf():
 if not repository_admin_logged_in(): return redirect(url_for("repository_admin_login",next=request.full_path))
 filters=_register_filters()
 try:
  members,_=combined_voters_register(); members=_filter_register(members,filters); pdf=_register_pdf(members,filters)
  return send_file(BytesIO(pdf),mimetype="application/pdf",as_attachment=True,download_name=_safe_register_filename(filters,"pdf"),max_age=0)
 except Exception as exc: return Response(f"Unable to generate voters register: {exc}",status=502,mimetype="text/plain")

@app.get("/admin/winners-runners-up")
def admin_winners_runners_up():
 if not repository_admin_logged_in(): return redirect(url_for("repository_admin_login",next=request.full_path))
 filters={key:(request.args.get(key) or "").strip() for key in ("mna_county","mca_county")}
 counties=_hierarchy_cache()["counties"]
 try:
  sections=winners_and_runners_up_report(filters)
  return render_template("admin_winners_runners_up.html",sections=sections,filters=filters,counties=counties,error=None,generated_at=kenya_now().strftime("%d %B %Y, %H:%M"))
 except Exception as exc:
  app.logger.exception("Unable to generate winners and runners-up report")
  return render_template("admin_winners_runners_up.html",sections=[],filters=filters,counties=counties,error=str(exc),generated_at=kenya_now().strftime("%d %B %Y, %H:%M")),502

@app.get("/admin/winners-runners-up.csv")
def download_winners_runners_up_csv():
 if not repository_admin_logged_in(): return redirect(url_for("repository_admin_login",next=request.full_path))
 filters={key:(request.args.get(key) or "").strip() for key in ("mna_county","mca_county")}
 try:
  output=StringIO(newline=""); columns=["category","elective_area","position","candidate_id","candidate_name","votes","vote_share_percent","total_valid_votes"]
  writer=csv.DictWriter(output,fieldnames=columns);writer.writeheader()
  for section in winners_and_runners_up_report(filters):
   for contest in section["contests"]:
    for leader in contest["leaders"]:
     writer.writerow({"category":section["title"],"elective_area":contest["area_label"],"position":leader["result"],"candidate_id":leader["candidate_id"],"candidate_name":leader["name"],"votes":leader["votes"],"vote_share_percent":f'{leader["share"]:.2f}',"total_valid_votes":contest["total_votes"]})
  return Response("\ufeff"+output.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":'attachment; filename="Winners_and_Runners_Up.csv"',"Cache-Control":"no-store"})
 except Exception as exc: return Response(f"Unable to generate winners report: {exc}",status=502,mimetype="text/plain")

@app.post("/report-repository/admin-logout")
def repository_admin_logout():
 session.pop("repository_admin",None)
 return redirect(url_for("report_repository"))

@app.get("/report-repository")
def report_repository():
 order=[('president','Presidential Reports'),('governor','Gubernatorial Reports'),('senator','Senatorial Reports'),('woman_rep','Women Rep Reports'),('mna','MNA Reports'),('mca','MCA Reports')]
 counts={}; error=''
 if not DATABASE_URL:
  error='Central repository requires DATABASE_URL (shared PostgreSQL).'
 else:
  try:
   counts=repository_counts()
  except Exception:
   app.logger.exception('Report repository summary could not be loaded')
   error='The report database is temporarily unavailable. The repository link is working; please retry shortly or check the Render database connection.'
 groups=[{'key':k,'title':title,'count':counts.get(k,0)} for k,title in order]
 resp=app.make_response(render_template('report_repository.html',groups=groups,total_reports=sum(g['count'] for g in groups),error=error,is_admin=repository_admin_logged_in()))
 resp.headers['Cache-Control']='private, max-age=15'
 return resp

@app.get("/report-repository/<election>")
def report_repository_category(election):
 allowed={k:t for k,t,_ in ELECTIONS}
 if election not in allowed:return Response('Report category not found',status=404)
 if not DATABASE_URL:return Response('Repository unavailable',status=503)
 filters={k:(request.args.get(k,'') or '').strip() for k in ('county','constituency','ward','poll_station','stream')}
 try: page=max(1,int(request.args.get('page','1')))
 except Exception: page=1
 per_page=50
 error=''; rows=[]; total=0; pages=1; filter_sets={'counties':[],'constituencies':[],'wards':[],'stations':[],'streams':[]}
 try:
  init_global_lock_db()
  rows,total=repository_category_rows(election,filters,page,per_page)
  pages=max(1,(total+per_page-1)//per_page)
  if page>pages:
   page=pages; rows,total=repository_category_rows(election,filters,page,per_page)
  filter_sets=repository_filter_sets(election,filters)
 except Exception:
  app.logger.exception('Report repository category could not be loaded: %s',election)
  error='The report database is temporarily unavailable. Please retry shortly or check the Render database connection.'
 report_tabs=[('president','President'),('governor','Gubernatorial'),('senator','Senatorial'),('woman_rep','Women Rep'),('mna','MNA'),('mca','MCA')]
 resp=app.make_response(render_template('report_repository_category.html',election=election,title=allowed[election]+' Reports',report_tabs=report_tabs,rows=rows,total=total,page=page,pages=pages,per_page=per_page,filters=filters,counties=filter_sets['counties'],constituencies=filter_sets['constituencies'],wards=filter_sets['wards'],stations=filter_sets['stations'],streams=filter_sets['streams'],is_admin=repository_admin_logged_in(),error=error))
 resp.headers['Cache-Control']='private, max-age=10'
 return resp

@app.post("/report-repository/delete/<int:report_id>")
def repository_delete(report_id):
 if not repository_admin_logged_in():
  return Response('Administrator login required to delete repository reports.',status=403)
 if not DATABASE_URL:return Response('Repository unavailable',status=503)
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute('SELECT id,election,filename FROM simulation_pdf_reports WHERE id=%s',(report_id,)); r=cur.fetchone()
   if not r:return Response('Report not found',status=404)
   cur.execute('DELETE FROM simulation_pdf_reports WHERE id=%s',(report_id,))
  conn.commit()
 invalidate_repository_cache()
 election=(r.get('election') or '').strip()
 if election in {k for k,_,_ in ELECTIONS}:
  return redirect(url_for('report_repository_category',election=election))
 return redirect(url_for('report_repository'))

@app.get("/report-repository/pdf/<int:report_id>")
def repository_pdf(report_id):
 if not DATABASE_URL:return Response('Repository unavailable',status=503)
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute('SELECT filename,pdf_data FROM simulation_pdf_reports WHERE id=%s',(report_id,)); r=cur.fetchone()
 if not r:return Response('Report not found',status=404)
 data=bytes(r['pdf_data'])
 resp=Response(data,mimetype='application/pdf',headers={'Content-Disposition':f'inline; filename="{r["filename"]}"','Content-Length':str(len(data)),'Cache-Control':'private, max-age=3600'})
 return resp

@app.get("/report-repository/download/<int:report_id>")
def repository_download(report_id):
 if not DATABASE_URL:return Response('Repository unavailable',status=503)
 init_global_lock_db()
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute('SELECT filename,pdf_data FROM simulation_pdf_reports WHERE id=%s',(report_id,)); r=cur.fetchone()
 if not r:return Response('Report not found',status=404)
 data=bytes(r['pdf_data'])
 resp=Response(data,mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="{r["filename"]}"','Content-Length':str(len(data)),'Cache-Control':'private, max-age=3600'})
 return resp

@app.post("/email-tally")
def email_tally():
 available,lock,row=tallies_available()
 if not available:
  return jsonify({"ok":False,"error":"Tally reports are available only after the voting stream has been officially closed."}),403
 data=request.get_json(silent=True) or {}
 recipient=str(data.get("email","")).strip()
 election=str(data.get("election","")).strip().lower()
 report_html=str(data.get("report_html","")).strip()
 allowed={k:t for k,t,_ in ELECTIONS}
 if election not in allowed:
  return jsonify({"ok":False,"error":"Invalid tally report."}),400
 ref=lock or closed_stream_cookie() or {}
 if stream_distinct_voter_count(ref) < 1:
  return jsonify({
   "ok":False,
   "no_votes":True,
   "error":"No report generated: this polling-station stream recorded no simulated voters."
  }),409
 if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",recipient):
  return jsonify({"ok":False,"error":"Enter a valid email address."}),400
 if not report_html:
  return jsonify({"ok":False,"error":"The report content is empty."}),400
 if not SMTP_HOST or not SMTP_FROM_EMAIL:
  return jsonify({"ok":False,"error":"Email is not configured on the server. Set the SMTP environment variables in Render."}),503
 report_html=re.sub(r'<button\b[^>]*>.*?</button>','',report_html,flags=re.I|re.S)
 # Make relative image URLs absolute so the PDF renderer can fetch report branding/photos.
 report_html=re.sub(
  r'(src=["\'])(/[^"\']+)(["\'])',
  lambda m: m.group(1)+urljoin(request.host_url,m.group(2))+m.group(3),
  report_html, flags=re.I
 )
 safe_title=allowed[election]
 station=ref.get("poll_station","")
 stream=ref.get("stream","")
 subject=f"{safe_title} Tally Report - {station} - {stream}"
 css="""
 @page { size: A4; margin: 7mm; }
 body{font-family:Helvetica,Arial,sans-serif;color:#111;font-size:9pt;line-height:1.12}
 h1,h2,h3,h4,p{margin-top:0} h2{font-size:15pt;margin:0 0 5px 0} h3{font-size:11pt;margin:4px 0} h4{font-size:9.5pt;margin:3px 0}
 table{width:100%;border-collapse:collapse;margin:4px 0} th,td{border:1px solid #aaa;padding:3px 4px;text-align:left;vertical-align:middle;line-height:1.08}
 img{max-width:76px;height:auto}.print-report-header img{max-width:100%;width:100%;height:auto}
 .tally-candidate-photo,.cert-candidate-photo{max-width:56px;max-height:64px}
 .tally-actions,.no-print,.gps-help{display:none}.report-generation-meta,.summary-box{border:1px solid #bbb;padding:4px;margin:3px 0}
 .report-meta-grid,.summary-grid{display:block}.report-meta-grid div,.summary-box{margin:1px 0}.signature-space{height:26px}
 .participation,.agent-certification,.officer-certification,.signature-section{margin-top:6px!important;padding-top:4px!important}
 .signature-table th,.signature-table td,.agent-sign-table th,.agent-sign-table td{padding:2px 3px!important}
 """
 # The browser tally page has a global ODM report header outside each individual tally section.
 # report_html contains only the selected section, so explicitly add the bundled ODM header to the PDF.
 pdf_header_html=""
 try:
  header_path=os.path.join(app.root_path,"static","odm_report_header.png")
  if os.path.isfile(header_path):
   import base64
   with open(header_path,"rb") as header_file:
    header_b64=base64.b64encode(header_file.read()).decode("ascii")
   pdf_header_html='<div class="pdf-odm-header"><img src="data:image/png;base64,'+header_b64+'" alt="ODM Report Header"></div>'
  elif REPORT_HEADER_IMAGE_URL:
   header_url=REPORT_HEADER_IMAGE_URL
   if header_url.startswith("/"):
    header_url=urljoin(request.host_url,header_url)
   pdf_header_html='<div class="pdf-odm-header"><img src="'+header_url+'" alt="ODM Report Header"></div>'
 except Exception as exc:
  app.logger.warning("Could not prepare ODM PDF header: %s",exc)

 geo_ident='<table border="1" cellspacing="0" cellpadding="3" width="100%" style="border:1px solid #777;margin:0 0 5px 0;font-size:9pt;line-height:1.05"><tr><td colspan="2" align="center" style="background:#f2f2f2;font-weight:bold;font-size:9.5pt;padding:3px"><b>REPORT LOCATION IDENTIFICATION</b></td></tr><tr><td width="50%"><b>County:</b> '+str(escape(ref.get('county','') or '—'))+'</td><td width="50%"><b>Constituency:</b> '+str(escape(ref.get('constituency','') or '—'))+'</td></tr><tr><td><b>Ward:</b> '+str(escape(ref.get('ward','') or '—'))+'</td><td><b>Polling Station Stream:</b> '+str(escape(ref.get('poll_station','') or '—'))+' — '+str(escape(ref.get('stream','') or '—'))+'</td></tr></table>'
 html='<!doctype html><html><head><meta charset="utf-8"><style>'+css+' .pdf-odm-header{text-align:center;margin:0 0 4px 0}.pdf-odm-header img{width:100%;max-width:100%;height:auto}.pdf-stream-ident{border:1px solid #9a9a9a;background:#f7f7f7;padding:7px 9px;margin:0 0 10px;font-size:10.5pt;line-height:1.35}.pdf-stream-ident .pdf-ident-title{text-align:center;font-weight:700;font-size:11pt;margin:0 0 5px}.pdf-stream-ident table{width:100%;border-collapse:collapse;margin:0}.pdf-stream-ident td{width:50%;border:1px solid #c5c5c5;padding:5px 7px;vertical-align:top}</style></head><body>'+pdf_header_html+geo_ident+'<div style="font-weight:700;color:#9b0000;margin-bottom:5px;font-size:9pt">TRAINING / SIMULATION ONLY — no official vote was cast.</div>'+report_html+'</body></html>' 

 # Create an A4 PDF attachment from this specific tally report.
 pdf_buffer=BytesIO()
 pdf_result=pisa.CreatePDF(html, dest=pdf_buffer, encoding="utf-8", path=request.host_url)
 if pdf_result.err:
  app.logger.error("Tally PDF generation failed with %s rendering errors", pdf_result.err)
  return jsonify({"ok":False,"error":"The tally report could not be converted to PDF. Check the Render logs for PDF rendering details."}),500
 pdf_bytes=pdf_buffer.getvalue()
 safe_station=re.sub(r'[^A-Za-z0-9_-]+','_',station or 'polling_station').strip('_')
 safe_stream=re.sub(r'[^A-Za-z0-9_-]+','_',stream or 'stream').strip('_')
 safe_report=re.sub(r'[^A-Za-z0-9_-]+','_',safe_title).strip('_')
 pdf_filename=f"{safe_report}_Tally_{safe_station}_{safe_stream}.pdf"

 msg=EmailMessage()
 msg["Subject"]=subject
 msg["From"]=f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
 msg["To"]=recipient
 msg.set_content(f"{safe_title} training/simulation tally report for {station} / {stream}. The printable PDF report is attached to this email.")
 msg.add_alternative('<p><b>'+safe_title+'</b> training/simulation tally report for '+station+' / '+stream+'.</p><p>The printable PDF report is attached to this email for easy download and printing.</p><p><b>TRAINING / SIMULATION ONLY — no official vote was cast.</b></p>',subtype="html")
 msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)
 try:
  smtp_cls=smtplib.SMTP_SSL if SMTP_USE_SSL else smtplib.SMTP
  with smtp_cls(SMTP_HOST,SMTP_PORT,timeout=25) as server:
   if not SMTP_USE_SSL and SMTP_USE_TLS:
    server.ehlo()
    server.starttls()
    server.ehlo()
   if SMTP_USERNAME:
    server.login(SMTP_USERNAME,SMTP_PASSWORD)
   server.send_message(msg)
 except smtplib.SMTPAuthenticationError as exc:
  app.logger.exception("Tally email authentication failed")
  return jsonify({"ok":False,"error":"SMTP authentication failed. For Gmail, use the full Gmail address as SMTP_USERNAME and a 16-character Google App Password as SMTP_PASSWORD."}),502
 except smtplib.SMTPConnectError as exc:
  app.logger.exception("Tally email connection failed")
  return jsonify({"ok":False,"error":f"Could not connect to SMTP server {SMTP_HOST}:{SMTP_PORT}. Check SMTP_HOST, SMTP_PORT and SSL/TLS settings."}),502
 except (TimeoutError, OSError) as exc:
  app.logger.exception("Tally email network/timeout failure")
  return jsonify({"ok":False,"error":f"SMTP connection timed out or was blocked while connecting to {SMTP_HOST}:{SMTP_PORT}."}),502
 except smtplib.SMTPException as exc:
  app.logger.exception("Tally email SMTP failure")
  return jsonify({"ok":False,"error":f"SMTP server rejected the message: {exc.__class__.__name__}. Check the Render logs for details."}),502
 except Exception as exc:
  app.logger.exception("Tally email failed")
  return jsonify({"ok":False,"error":f"Email could not be sent ({exc.__class__.__name__}). Check the SMTP settings and Render logs."}),502
 return jsonify({"ok":True,"message":f"{safe_title} tally report PDF emailed to {recipient}."})

@app.post("/reset-demo")
def reset():
 c=con(); c.execute("DELETE FROM demo_votes"); c.commit(); c.close(); session.clear()
 return redirect(url_for("home"))


@app.context_processor
def inject_report_branding():
 lock=terminal_lock()
 ready=False
 row=None
 if lock:
  row=stream_session(lock.get("poll_station",""),lock.get("stream",""))
  ready=bool(
   row and row["opened_at"] and not row["closed_at"]
   and lock.get("session_date")==today_iso()
   and terminal_active_after_reset(lock)
  )
 closed_ref=closed_stream_cookie()
 closed_row=None
 if closed_ref and closed_ref.get("session_date")==today_iso():
  closed_row=stream_session(closed_ref.get("poll_station",""),closed_ref.get("stream",""))

 return {
  "report_header_image_url": REPORT_HEADER_IMAGE_URL,
  "terminal_lock": lock,
  "terminal_lock_vote_count": locked_stream_vote_count(lock) if lock else 0,
  "stream_ready": ready,
  "stream_row": row or closed_row,
  "closed_stream_row": closed_row,
  "reset_required": bool(lock and not terminal_active_after_reset(lock)),
  "stream_admin_logged_in": repository_admin_logged_in()
 }

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
