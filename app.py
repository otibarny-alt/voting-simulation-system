import os, sqlite3, csv
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session

app=Flask(__name__)
app.secret_key=os.getenv("FLASK_SECRET_KEY","training-only-change-me")
DB=os.getenv("DEMO_DB_PATH","training_votes.db")

ELECTIONS=[
 ("president","President",10),("governor","Governor",6),("senator","Senator",6),
 ("woman_rep","Woman Rep",6),("mna","MNA",6),("mca","MCA",6)
]

def con():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS demo_votes(id INTEGER PRIMARY KEY AUTOINCREMENT,voter_session TEXT,election TEXT,candidate INTEGER,county TEXT,constituency TEXT,ward TEXT,poll_station TEXT,stream TEXT)')
 c.execute('CREATE INDEX IF NOT EXISTS idx_demo_votes_voter ON demo_votes(voter_session)')
 c.execute('''CREATE TABLE IF NOT EXISTS stream_sessions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,session_date TEXT NOT NULL,county TEXT,constituency TEXT,ward TEXT,
 poll_station TEXT,stream TEXT,opened_at TEXT,closed_at TEXT,opening_zero_votes INTEGER DEFAULT 0,
 UNIQUE(session_date,poll_station,stream))''')
 return c

def cfg():
 return [{"key":k,"title":t,"count":n,"candidates":[{"slot":i,"name":f"Candidate {i}"} for i in range(1,n+1)]} for k,t,n in ELECTIONS]


COUNTY_MAIN = os.getenv("COUNTY_MAIN_FILENAME", "county_main.csv")
AGENTS_LOGIN = os.getenv("AGENTS_LOGIN_FILENAME", "agents_login.csv")
VOTING_OPEN_TIME = os.getenv("VOTING_OPEN_TIME", "").strip()
VOTING_CLOSE_TIME = os.getenv("VOTING_CLOSE_TIME", "").strip()
REPORT_HEADER_IMAGE_URL = os.getenv("REPORT_HEADER_IMAGE_URL", "").strip()

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

@app.get("/stream-control")
def stream_control():
 ps=request.args.get("poll_station","").strip(); st=request.args.get("stream","").strip()
 row=stream_session(ps,st) if ps and st else None
 return render_template("stream_control.html",row=row,poll_station=ps,stream=st,
 open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
 report_header_image_url=REPORT_HEADER_IMAGE_URL)

@app.post("/stream/open")
def open_stream():
 f=request.form; ps=f.get("poll_station","").strip(); st=f.get("stream","").strip()
 c=con()
 precast=c.execute("SELECT COUNT(*) n FROM demo_votes WHERE poll_station=? AND stream=?",(ps,st)).fetchone()["n"]
 if precast:
  c.close()
  return render_template("stream_control.html",row=None,poll_station=ps,stream=st,
   open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
   report_header_image_url=REPORT_HEADER_IMAGE_URL,
   error=f"OPENING BLOCKED: {precast} simulated ballot records already exist in this stream.")
 now=datetime.now().astimezone().isoformat(timespec="seconds")
 c.execute("""INSERT OR IGNORE INTO stream_sessions
 (session_date,county,constituency,ward,poll_station,stream,opened_at,opening_zero_votes)
 VALUES(?,?,?,?,?,?,?,1)""",(today_iso(),f.get("county",""),f.get("constituency",""),f.get("ward",""),ps,st,now))
 c.commit(); c.close()
 return redirect(url_for("stream_control",poll_station=ps,stream=st))

@app.post("/stream/close")
def close_stream():
 ps=request.form.get("poll_station","").strip(); st=request.form.get("stream","").strip()
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
 return render_template("stream_report.html",row=row,votes=votes,open_time=VOTING_OPEN_TIME,close_time=VOTING_CLOSE_TIME,
  report_header_image_url=REPORT_HEADER_IMAGE_URL,
  open_ok=time_status(row["opened_at"],VOTING_OPEN_TIME),close_ok=time_status(row["closed_at"],VOTING_CLOSE_TIME))

@app.get("/")
def home(): return render_template("verify.html")

@app.post("/start")
def start():
 voter=request.form.get("voter_id","").strip()
 if not voter: return render_template("verify.html",error="Enter a demo voter ID.")
 previous=previous_vote(voter)
 if previous:
  station=previous["poll_station"] or "the recorded polling station"
  return render_template("verify.html",error=f"Voter ID {voter} has already voted at {station} polling station and cannot vote again.")
 geo={x:(request.form.get(x,"").strip() or d) for x,d in [
  ("county","Demo County"),("constituency","Demo Constituency"),("ward","Demo Ward"),
  ("poll_station","Demo Polling Station"),("stream","Stream 1")]}
 ss=stream_session(geo["poll_station"],geo["stream"])
 if not ss:
  return render_template("verify.html",error="Voting has not been opened for this stream. First verify zero pre-cast votes and open the stream.")
 if ss["closed_at"]:
  return render_template("verify.html",error="Voting for this stream has already been closed for today.")
 session.clear(); session["voter_id"]=voter; session["choices"]={}; session["geo"]=geo
 return redirect(url_for("ballot",step=0))

@app.route("/ballot/<int:step>",methods=["GET","POST"])
def ballot(step):
 if "voter_id" not in session:return redirect(url_for("home"))
 c=cfg()
 if step<0 or step>=len(c):return redirect(url_for("review"))
 e=c[step]
 if request.method=="POST":
  try: choice=int(request.form.get("candidate","0"))
  except: choice=0
  if not 1<=choice<=e["count"]:
   return render_template("ballot.html",e=e,step=step,total=len(c),error="Choose one candidate.")
  choices=dict(session.get("choices",{})); choices[e["key"]]=choice; session["choices"]=choices
  return redirect(url_for("ballot",step=step+1)) if step+1<len(c) else redirect(url_for("review"))
 return render_template("ballot.html",e=e,step=step,total=len(c),selected=session.get("choices",{}).get(e["key"]))

@app.get("/review")
def review():
 if "voter_id" not in session:return redirect(url_for("home"))
 return render_template("review.html",elections=cfg(),choices=session.get("choices",{}),geo=session.get("geo",{}),voter_id=session.get("voter_id",""))

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
  c.execute("INSERT INTO demo_votes(voter_session,election,candidate,county,constituency,ward,poll_station,stream) VALUES(?,?,?,?,?,?,?,?)",
   (voter,e["key"],choices[e["key"]],geo["county"],geo["constituency"],geo["ward"],geo["poll_station"],geo["stream"]))
 c.commit(); c.close(); session["completed"]=True
 return redirect(url_for("complete"))

@app.get("/complete")
def complete():
 if not session.get("completed"):return redirect(url_for("home"))
 return render_template("complete.html",geo=session["geo"])

@app.get("/tallies")
def tallies():
 c=con()
 vote_rows=c.execute("SELECT election,candidate,COUNT(*) votes FROM demo_votes GROUP BY election,candidate ORDER BY election,candidate").fetchall()
 geo_rows=c.execute("SELECT election,poll_station,stream,COUNT(DISTINCT voter_session) votes_cast FROM demo_votes GROUP BY election,poll_station,stream ORDER BY election,poll_station,stream").fetchall()
 c.close()

 vote_map={(r["election"],int(r["candidate"])):int(r["votes"]) for r in vote_rows}
 reg_index=registered_voter_index()
 hp=hierarchy_payload()
 stream_to_station={norm_key(x["name"]):norm_key(x.get("poll_station_key","")) for x in hp["streams"]}
 station_labels={norm_key(x["name"]):x.get("label") or x["name"] for x in hp["poll_stations"]}
 stream_labels={norm_key(x["name"]):x.get("label") or x["name"] for x in hp["streams"]}

 geo_by_election={}
 for r in geo_rows: geo_by_election.setdefault(r["election"],[]).append(r)

 tally_sections=[]
 for e in cfg():
  candidates=[{"slot":cand["slot"],"name":cand["name"],"votes":vote_map.get((e["key"],cand["slot"]),0)} for cand in e["candidates"]]
  candidates.sort(key=lambda x:(-x["votes"],x["slot"]))
  previous_votes=None; previous_rank=0
  for position,cand in enumerate(candidates,start=1):
   if previous_votes is None or cand["votes"]!=previous_votes: previous_rank=position
   cand["rank"]=previous_rank; previous_votes=cand["votes"]

  stream_summary=[]; station_acc={}; election_cast=0; stream_registered_total=0
  for r in geo_by_election.get(e["key"],[]):
   sk=norm_key(r["stream"]); pk=norm_key(r["poll_station"]) or stream_to_station.get(sk,"")
   cast=int(r["votes_cast"] or 0); registered=reg_index.get(sk,0)
   election_cast+=cast; stream_registered_total+=registered
   stream_summary.append({"name":stream_labels.get(sk,(r["stream"] or "").replace("_"," ").title()),
                          "votes_cast":cast,"registered":registered,"not_cast":max(0,registered-cast)})
   st=station_acc.setdefault(pk,{"name":station_labels.get(pk,(r["poll_station"] or "").replace("_"," ").title()),
                                "votes_cast":0,"registered":0})
   st["votes_cast"]+=cast

  # A station's registered total includes every stream assigned to that station.
  for pk,st in station_acc.items():
   station_streams=[sk for sk,parent in stream_to_station.items() if parent==pk]
   st["streams_count"]=len(station_streams)
   st["registered"]=sum(reg_index.get(sk,0) for sk in station_streams)
   st["not_cast"]=max(0,st["registered"]-st["votes_cast"])

  station_summary=sorted(station_acc.values(),key=lambda x:x["name"])
  stream_summary.sort(key=lambda x:x["name"])
  station_registered_total=sum(x["registered"] for x in station_summary)

  tally_sections.append({"key":e["key"],"title":e["title"],"candidates":candidates,
   "total_votes_cast":election_cast,"stream_registered_total":stream_registered_total,
   "station_registered_total":station_registered_total,
   "total_not_cast":max(0,stream_registered_total-election_cast),
   "streams":stream_summary,"stations":station_summary})

 return render_template("tallies.html",sections=tally_sections)

@app.post("/reset-demo")
def reset():
 c=con(); c.execute("DELETE FROM demo_votes"); c.commit(); c.close(); session.clear()
 return redirect(url_for("home"))


@app.context_processor
def inject_report_branding():
 return {"report_header_image_url": REPORT_HEADER_IMAGE_URL}

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
