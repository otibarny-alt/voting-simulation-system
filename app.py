import os, sqlite3, csv
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
 return c

def cfg():
 return [{"key":k,"title":t,"count":n,"candidates":[{"slot":i,"name":f"Candidate {i}"} for i in range(1,n+1)]} for k,t,n in ELECTIONS]


COUNTY_MAIN = os.getenv("COUNTY_MAIN_FILENAME", "county_main.csv")

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

@app.get("/")
def home(): return render_template("verify.html")

@app.post("/start")
def start():
 voter=request.form.get("voter_id","").strip()
 if not voter: return render_template("verify.html",error="Enter a demo voter ID.")
 session.clear(); session["voter_id"]=voter; session["choices"]={}
 session["geo"]={x:(request.form.get(x,"").strip() or d) for x,d in [
  ("county","Demo County"),("constituency","Demo Constituency"),("ward","Demo Ward"),
  ("poll_station","Demo Polling Station"),("stream","Stream 1")]}
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
 c.execute("DELETE FROM demo_votes WHERE voter_session=?",(voter,))
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
 c=con(); rows=c.execute("SELECT election,candidate,county,constituency,ward,poll_station,stream,COUNT(*) votes FROM demo_votes GROUP BY election,candidate,county,constituency,ward,poll_station,stream ORDER BY election,candidate").fetchall(); c.close()
 return render_template("tallies.html",rows=rows,elections=cfg())

@app.post("/reset-demo")
def reset():
 c=con(); c.execute("DELETE FROM demo_votes"); c.commit(); c.close(); session.clear()
 return redirect(url_for("home"))

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
