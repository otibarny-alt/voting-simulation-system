import os, sqlite3, csv, json, re, hmac, secrets, hashlib
import requests
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, date
from itsdangerous import URLSafeSerializer, BadSignature
from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify

app=Flask(__name__)
app.secret_key=os.getenv("FLASK_SECRET_KEY","training-only-change-me")
DB=os.getenv("DEMO_DB_PATH","training_votes.db")

ELECTIONS=[
 ("president","President",10),("governor","Governor",6),("senator","Senator",6),
 ("woman_rep","Woman Rep",6),("mna","MNA",6),("mca","MCA",6)
]

def con():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS demo_votes(id INTEGER PRIMARY KEY AUTOINCREMENT,voter_session TEXT,election TEXT,candidate INTEGER,candidate_id TEXT,candidate_name TEXT,county TEXT,constituency TEXT,ward TEXT,poll_station TEXT,stream TEXT)')
 vote_cols={r[1] for r in c.execute("PRAGMA table_info(demo_votes)").fetchall()}
 if "candidate_id" not in vote_cols: c.execute("ALTER TABLE demo_votes ADD COLUMN candidate_id TEXT")
 if "candidate_name" not in vote_cols: c.execute("ALTER TABLE demo_votes ADD COLUMN candidate_name TEXT")
 c.execute('CREATE INDEX IF NOT EXISTS idx_demo_votes_voter ON demo_votes(voter_session)')
 c.execute('''CREATE TABLE IF NOT EXISTS stream_sessions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,session_date TEXT NOT NULL,county TEXT,constituency TEXT,ward TEXT,
 poll_station TEXT,stream TEXT,opened_at TEXT,closed_at TEXT,opening_zero_votes INTEGER DEFAULT 0,
 opening_lat REAL, opening_lon REAL, opening_accuracy REAL,
 UNIQUE(session_date,poll_station,stream))''')
 cols={r[1] for r in c.execute("PRAGMA table_info(stream_sessions)").fetchall()}
 if "opening_lat" not in cols: c.execute("ALTER TABLE stream_sessions ADD COLUMN opening_lat REAL")
 if "opening_lon" not in cols: c.execute("ALTER TABLE stream_sessions ADD COLUMN opening_lon REAL")
 if "opening_accuracy" not in cols: c.execute("ALTER TABLE stream_sessions ADD COLUMN opening_accuracy REAL")
 return c

def cfg():
 return [{"key":k,"title":t,"count":n,"candidates":[]} for k,t,n in ELECTIONS]


COUNTY_MAIN = os.getenv("COUNTY_MAIN_FILENAME", "county_main.csv")
AGENTS_LOGIN = os.getenv("AGENTS_LOGIN_FILENAME", "agents_login.csv")
VOTING_OPEN_TIME = os.getenv("VOTING_OPEN_TIME", "").strip()
VOTING_CLOSE_TIME = os.getenv("VOTING_CLOSE_TIME", "").strip()
REPORT_HEADER_IMAGE_URL = os.getenv("REPORT_HEADER_IMAGE_URL", "/static/odm_report_header.png").strip()
KOBO_BASE_URL = os.getenv("KOBO_BASE_URL", "https://kf.kobotoolbox.org").rstrip("/")
MEMBERSHIP_ASSET_UID = os.getenv("MEMBERSHIP_ASSET_UID", "").strip()
KOBO_API_TOKEN = os.getenv("KOBO_API_TOKEN", "").strip()
CANDIDATE_PORTAL_BASE_URL = os.getenv("CANDIDATE_PORTAL_BASE_URL", "").rstrip("/")
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def candidate_portal_catalog(geo):
 if not CANDIDATE_PORTAL_BASE_URL:
  raise RuntimeError("Candidate Portal connection is not configured.")
 r=requests.get(
  f"{CANDIDATE_PORTAL_BASE_URL}/api/candidates",
  params={
   "county":geo.get("county",""),
   "constituency":geo.get("constituency",""),
   "ward":geo.get("ward","")
  },
  timeout=20
 )
 r.raise_for_status()
 payload=r.json()
 rows=payload.get("results",[]) if isinstance(payload,dict) else []
 catalog={k:[] for k,_,_ in ELECTIONS}
 for row in rows:
  key=str(row.get("position","")).strip().lower()
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


def pg_url():
 url=DATABASE_URL
 if url.startswith("postgres://"):
  url="postgresql://"+url[len("postgres://"):]
 return url

def lock_db():
 if not DATABASE_URL:
  raise RuntimeError("DATABASE_URL is required for global device locking.")
 return psycopg.connect(pg_url(), row_factory=dict_row)

def init_global_lock_db():
 if not DATABASE_URL:
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
      PRIMARY KEY(session_date,poll_station,stream)
    )
   """)
  conn.commit()

def token_hash(token):
 return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

def global_lock_row(session_date,poll_station,stream):
 if not DATABASE_URL:
  return None
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
 now=datetime.now().astimezone().isoformat(timespec="seconds")
 th=token_hash(owner_token)
 with lock_db() as conn:
  with conn.cursor() as cur:
   cur.execute("""
    INSERT INTO simulation_terminal_locks(
      session_date,poll_station,stream,county,constituency,ward,owner_token_hash,locked_at,released_at
    ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NULL)
    ON CONFLICT (session_date,poll_station,stream) DO NOTHING
   """,(
    lock_data["session_date"],lock_data["poll_station"],lock_data["stream"],
    lock_data.get("county",""),lock_data.get("constituency",""),lock_data.get("ward",""),
    th,now
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
 # If an earlier record was explicitly released by the owning device, allow a fresh claim.
 if row and row.get("released_at"):
  with lock_db() as conn:
   with conn.cursor() as cur:
    cur.execute("""
     UPDATE simulation_terminal_locks
     SET county=%s,constituency=%s,ward=%s,owner_token_hash=%s,locked_at=%s,released_at=NULL
     WHERE session_date=%s AND poll_station=%s AND stream=%s AND released_at IS NOT NULL
    """,(
     lock_data.get("county",""),lock_data.get("constituency",""),lock_data.get("ward",""),
     th,now,lock_data["session_date"],lock_data["poll_station"],lock_data["stream"]
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
  with open(AGENTS_LOGIN, encoding="utf-8-sig", errors="replace", newline="") as f:
   return list(csv.DictReader(f))
 except Exception:
  return []

def to_int(v):
 try: return int(float(str(v or "0").replace(",","").strip()))
 except Exception: return 0

def registered_voter_index():
 by_stream={}
 for r in agent_rows():
  key=norm_key(r.get("poll_station_name",""))
  if key: by_stream[key]=to_int(r.get("total_registered_voters",0))
 return by_stream

def hierarchy_rows():
 rows=[]
 try:
  with open(COUNTY_MAIN, encoding="utf-8", errors="replace", newline="") as f:
   rows=list(csv.DictReader(f))
 except Exception:
  pass
 return rows

def hierarchy_payload():
 rows=hierarchy_rows()
 return {
  "counties":[{"name":r["name"],"label":r.get("label") or r["name"]} for r in rows if r.get("list_name")=="county"],
  "constituencies":[{"name":r["name"],"label":r.get("label") or r["name"],"county_key":r.get("county_key","")} for r in rows if r.get("list_name")=="constituency"],
  "wards":[{"name":r["name"],"label":r.get("label") or r["name"],"constituency_key":r.get("constituency_key","")} for r in rows if r.get("list_name")=="ward"],
  "poll_stations":[{"name":r["name"],"label":r.get("label") or r["name"],"ward_key":r.get("ward_key",""),"poll_station_code":r.get("poll_station_code","")} for r in rows if r.get("list_name")=="poll_station"],
  "streams":[{"name":r["name"],"label":r.get("label") or r["name"],"poll_station_key":r.get("poll_station_key","")} for r in rows if r.get("list_name")=="poll_station_stream"]
 }

@app.get("/api/hierarchy")
def api_hierarchy():
 from flask import jsonify
 return jsonify(hierarchy_payload())


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

def lookup_member(national_id):
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


def today_iso(): return date.today().isoformat()

def stream_session(poll_station,stream):
 c=con(); row=c.execute("SELECT * FROM stream_sessions WHERE session_date=? AND poll_station=? AND stream=?",
 (today_iso(),poll_station,stream)).fetchone(); c.close(); return row

def time_status(ts,expected):
 if not ts or not expected: return None
 try: return datetime.fromisoformat(ts).strftime("%H:%M")==expected
 except Exception: return None


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
 return resp

@app.get("/stream-control")
def stream_control():
 ps=request.args.get("poll_station","").strip(); st=request.args.get("stream","").strip()
 row=stream_session(ps,st) if ps and st else None
 current_lock=terminal_lock()
 return render_template(
  "stream_control.html",
  row=row,poll_station=ps,stream=st,
  open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
  report_header_image_url=REPORT_HEADER_IMAGE_URL,
  post_reset_new_stream_locked=bool(session.get("post_reset_new_stream_locked")),
  reset_required=bool(current_lock and not session.get("active_stream_after_reset"))
 )

@app.post("/stream/open")
def open_stream():
 f=request.form; ps=f.get("poll_station","").strip(); st=f.get("stream","").strip()

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

 c=con()
 precast=c.execute("SELECT COUNT(*) n FROM demo_votes WHERE poll_station=? AND stream=?",(ps,st)).fetchone()["n"]
 if precast:
  c.close()
  return render_template("stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING BLOCKED: {precast} simulated ballot records already exist in this stream.")
 c.close()

 lock_data={"county":f.get("county","").strip(),"constituency":f.get("constituency","").strip(),
            "ward":f.get("ward","").strip(),"poll_station":ps,"stream":st,"session_date":today_iso()}
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

 now=datetime.now().astimezone().isoformat(timespec="seconds")
 try: opening_lat=float(f.get("opening_lat","")) if f.get("opening_lat","") else None
 except: opening_lat=None
 try: opening_lon=float(f.get("opening_lon","")) if f.get("opening_lon","") else None
 except: opening_lon=None
 try: opening_accuracy=float(f.get("opening_accuracy","")) if f.get("opening_accuracy","") else None
 except: opening_accuracy=None

 c=con()
 c.execute("""INSERT OR IGNORE INTO stream_sessions
 (session_date,county,constituency,ward,poll_station,stream,opened_at,opening_zero_votes,opening_lat,opening_lon,opening_accuracy)
 VALUES(?,?,?,?,?,?,?,1,?,?,?)""",(today_iso(),f.get("county",""),f.get("constituency",""),f.get("ward",""),ps,st,now,opening_lat,opening_lon,opening_accuracy))
 c.commit(); c.close()

 if session.pop("awaiting_new_stream_after_reset",False) and session.get("terminal_reset_completed"):
  session["post_reset_new_stream_locked"]=True
  session["active_stream_after_reset"]=True
 else:
  session.pop("post_reset_new_stream_locked",None)
  session.pop("active_stream_after_reset",None)

 resp=redirect(url_for("stream_control",poll_station=ps,stream=st))
 resp.set_cookie(TERMINAL_LOCK_COOKIE,terminal_serializer().dumps(lock_data),
                 httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
 resp.set_cookie(TERMINAL_OWNER_COOKIE,owner_token,
                 httponly=True,samesite="Lax",secure=request.is_secure,max_age=86400)
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
   error="Close denied: only the device that owns the central lock for this polling-station stream can close it."
  )
 row=stream_session(ps,st)
 if row and not row["closed_at"]:
  c=con(); now=datetime.now().astimezone().isoformat(timespec="seconds")
  c.execute("UPDATE stream_sessions SET closed_at=? WHERE id=?",(now,row["id"])); c.commit(); c.close()
 return redirect(url_for("stream_control",poll_station=ps,stream=st))

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
 # The operator must first reset the terminal, then open a new stream.
 if not session.get("active_stream_after_reset"):
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
  station=previous["poll_station"] or "the recorded polling station"
  return render_template("verify.html",error=f"Voter ID {voter} has already voted at {station} polling station and cannot vote again.")

 geo={k:lock.get(k,"") for k in ("county","constituency","ward","poll_station","stream")}

 try:
  row=lookup_member(voter)
 except Exception as e:
  return render_template("verify.html",error=f"Unable to verify voter from ODM Membership Portal: {e}")

 if not row:
  return render_template("verify.html",error=f"National ID {voter} was not found in the ODM Membership Registration Database.")

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
 session["geo"]=geo
 return render_template("member_verify.html",member=member,geo=geo,station_match=station_match)

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
  station=previous["poll_station"] or "the recorded polling station"
  session.clear()
  return render_template("verify.html",error=f"Voter ID {voter} has already voted at {station} polling station and cannot vote again.")
 geo=session.get("geo",{})
 lock=terminal_lock()
 if not lock or any(geo.get(k,"")!=lock.get(k,"") for k in ("county","constituency","ward","poll_station","stream")):
  session.clear()
  return render_template("verify.html",error="Terminal stream verification changed. Restart voter verification.")
 ss=stream_session(geo.get("poll_station",""),geo.get("stream",""))
 if not ss or ss["closed_at"]:
  session.clear()
  return render_template("verify.html",error="This stream is not open for simulated voting.")
 session["voter_id"]=voter
 session["choices"]={}
 session.pop("pending_voter_id",None)
 return redirect(url_for("ballot",step=0))

@app.post("/membership/cancel")
def cancel_member():
 keep_geo=session.get("geo")
 session.clear()
 return redirect(url_for("home"))

@app.get("/membership-photo/<int:submission_id>/<kind>")
def membership_photo(submission_id,kind):
 if kind not in ("id","passport"):
  return Response(status=404)
 if session.get("membership_submission_id")!=submission_id:
  return Response(status=403)
 try:
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
 if not e["candidates"]:
  return render_template(
   "ballot.html",e=e,step=step,total=len(structure),
   error=f"No active {e['title']} candidates are registered for this electoral area.",
   selected=None
  )

 if request.method=="POST":
  action=str(request.form.get("action","choose")).strip().lower()
  choices=dict(session.get("choices",{}))

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
  station=existing["poll_station"] or "the recorded polling station"
  c.close()
  session.clear()
  return render_template("verify.html",error=f"Voter ID {voter} has already voted at {station} polling station and cannot vote again.")
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
 c.commit(); c.close(); session["completed"]=True
 return redirect(url_for("complete"))


def dashboard_api_authorized():
 supplied=request.headers.get("X-Dashboard-Key","")
 return bool(DASHBOARD_API_KEY and supplied and hmac.compare_digest(supplied,DASHBOARD_API_KEY))

@app.get("/api/dashboard/president")
def api_dashboard_president():
 """
 Read-only aggregate feed for the separate Presidential Simulation Results Dashboard.
 No voter National IDs are returned.
 """
 if not dashboard_api_authorized():
  return jsonify({"error":"Unauthorized"}),401

 c=con()
 rows=c.execute("""
  SELECT county,constituency,ward,poll_station,stream,candidate_id,candidate_name,
         COUNT(*) AS n
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
  key=(r["stream"] or "").strip()
  if not key:
   continue
  item=streams.setdefault(key,{
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":key,
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
  key=(r["stream"] or "").strip()
  if not key:
   continue
  session_map[key]={
   "session_date":r["session_date"] or "",
   "county":r["county"] or "",
   "constituency":r["constituency"] or "",
   "ward":r["ward"] or "",
   "poll_station":r["poll_station"] or "",
   "stream":key,
   "opened_at":r["opened_at"] or "",
   "closed_at":r["closed_at"] or ""
  }
  if key not in streams:
   streams[key]={
    "county":r["county"] or "",
    "constituency":r["constituency"] or "",
    "ward":r["ward"] or "",
    "poll_station":r["poll_station"] or "",
    "stream":key,
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

 # Pull the current national presidential candidate list so zero-vote candidates are visible.
 candidates=[]
 try:
  catalog=candidate_portal_catalog({})
  for cand in catalog.get("president",[]):
   cid=cand.get("candidate_id","")
   candidates.append({
    "candidate_id":cid,
    "name":cand.get("name",""),
    "photo_url":cand.get("photo_url"),
    "votes":candidate_totals.get(cid,0)
   })
 except Exception:
  # Fallback to candidates seen in recorded simulation data.
  names={}
  for item in streams.values():
   names.update(item.get("candidate_names",{}))
  for cid,name in names.items():
   candidates.append({"candidate_id":cid,"name":name,"photo_url":None,"votes":candidate_totals.get(cid,0)})

 candidates.sort(key=lambda x:(-int(x.get("votes",0)),str(x.get("name","")).lower()))

 return jsonify({
  "source":"training_simulation",
  "simulation_only":True,
  "election":"president",
  "candidates":candidates,
  "streams":list(streams.values()),
  "totals":{
   "candidate_selections":sum(candidate_totals.values()),
   "skipped":skipped_total,
   "participants":participants_total
  }
 })


@app.get("/complete")
def complete():
 if not session.get("completed"):return redirect(url_for("home"))
 return render_template("complete.html",geo=session["geo"])

@app.get("/tallies")
def tallies():
 c=con()
 vote_rows=c.execute("""SELECT election,candidate,candidate_id,candidate_name,COUNT(*) votes
 FROM demo_votes
 GROUP BY election,candidate,candidate_id,candidate_name
 ORDER BY election,candidate_name,candidate""").fetchall()
 geo_rows=c.execute("""SELECT election,poll_station,stream,
 COUNT(DISTINCT voter_session) participation,
 COUNT(DISTINCT CASE WHEN candidate_id='__SKIP__' THEN voter_session END) skipped
 FROM demo_votes
 GROUP BY election,poll_station,stream
 ORDER BY election,poll_station,stream""").fetchall()
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
 reg_index=registered_voter_index()
 hp=hierarchy_payload()
 stream_to_station={norm_key(x["name"]):norm_key(x.get("poll_station_key","")) for x in hp["streams"]}
 station_labels={norm_key(x["name"]):x.get("label") or x["name"] for x in hp["poll_stations"]}
 stream_labels={norm_key(x["name"]):x.get("label") or x["name"] for x in hp["streams"]}

 geo_by_election={}
 for r in geo_rows: geo_by_election.setdefault(r["election"],[]).append(r)

 tally_sections=[]
 lock=terminal_lock()
 tally_geo=lock or {}
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
    "votes":vote_map.get((e["key"],cid),0)
   })
  for (ek,cid),votes in vote_map.items():
   if ek==e["key"] and cid not in seen:
    candidates.append({
     "slot":999999,"candidate_id":cid,
     "name":vote_name_map.get((ek,cid),cid),
     "membership_no":"","votes":votes
    })
  for (ek,slot),votes in legacy_vote_map.items():
   if ek==e["key"]:
    candidates.append({
     "slot":slot,"candidate_id":f"LEGACY-{slot}",
     "name":f"Legacy Candidate {slot}",
     "membership_no":"","votes":votes
    })
  candidates.sort(key=lambda x:(-x["votes"],x["name"].lower()))
  previous_votes=None; previous_rank=0
  for position,cand in enumerate(candidates,start=1):
   if previous_votes is None or cand["votes"]!=previous_votes: previous_rank=position
   cand["rank"]=previous_rank; previous_votes=cand["votes"]

  stream_summary=[]; station_acc={}; election_cast=0; election_skipped=0; election_participation=0; stream_registered_total=0
  for r in geo_by_election.get(e["key"],[]):
   sk=norm_key(r["stream"]); pk=norm_key(r["poll_station"]) or stream_to_station.get(sk,"")
   participation=int(r["participation"] or 0)
   skipped=int(r["skipped"] or 0)
   cast=max(0,participation-skipped)
   registered=reg_index.get(sk,0)
   election_cast+=cast
   election_skipped+=skipped
   election_participation+=participation
   stream_registered_total+=registered
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

  # A station's registered total includes every stream assigned to that station.
  for pk,st in station_acc.items():
   station_streams=[sk for sk,parent in stream_to_station.items() if parent==pk]
   st["streams_count"]=len(station_streams)
   st["registered"]=sum(reg_index.get(sk,0) for sk in station_streams)
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
   and session.get("active_stream_after_reset")
  )
 return {
  "report_header_image_url": REPORT_HEADER_IMAGE_URL,
  "terminal_lock": lock,
  "terminal_lock_vote_count": locked_stream_vote_count(lock) if lock else 0,
  "stream_ready": ready,
  "stream_row": row,
  "reset_required": bool(lock and not session.get("active_stream_after_reset"))
 }

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
