from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
DB = BASE / "database" / "procurement.db"
app = Flask(__name__)
app.secret_key = "college-project-secret"

def db():
    conn=sqlite3.connect(DB)
    conn.row_factory=sqlite3.Row
    return conn

def init_db():
    DB.parent.mkdir(exist_ok=True)
    conn=db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, role TEXT NOT NULL, department TEXT
    );
    CREATE TABLE IF NOT EXISTS requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      request_no TEXT, employee TEXT, department TEXT, laptop_model TEXT,
      justification TEXT, manager TEXT, approval_status TEXT DEFAULT 'Pending',
      procurement_status TEXT DEFAULT 'Not Started',
      delivery_location TEXT, created_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS procurement_tasks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      request_id INTEGER, assigned_to TEXT, status TEXT DEFAULT 'Open',
      created_at TEXT, completed_at TEXT
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0:
        conn.executemany("INSERT INTO users(name,role,department) VALUES(?,?,?)",[
            ("John","Employee","IT"),("Manager A","Manager","IT"),
            ("Procurement Team","Procurement","IT"),("Admin","Admin","IT")])
    conn.commit(); conn.close()

@app.route("/")
def index():
    conn=db()
    rows=conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", requests=rows, user=session.get("user"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        name=request.form["name"]
        conn=db(); u=conn.execute("SELECT * FROM users WHERE name=?",(name,)).fetchone(); conn.close()
        if u:
            session["user"]=u["name"]; session["role"]=u["role"]
            return redirect(url_for("index"))
        flash("User not found. Try John, Manager A, Procurement Team or Admin.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/request", methods=["GET","POST"])
def new_request():
    if request.method=="POST":
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn=db()
        cur=conn.execute("""INSERT INTO requests
        (request_no,employee,department,laptop_model,justification,manager,
         approval_status,procurement_status,delivery_location,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(
            "TEMP",request.form["employee"],request.form["department"],
            request.form["laptop_model"],request.form["justification"],
            request.form["manager"],"Pending","Not Started",
            request.form["delivery_location"],now,now))
        rid=cur.lastrowid
        conn.execute("UPDATE requests SET request_no=? WHERE id=?",(f"LAP{rid:04d}",rid))
        conn.commit(); conn.close()
        flash("Laptop request submitted. Manager approval is now pending.")
        return redirect(url_for("index"))
    return render_template("request.html")

@app.route("/approve/<int:rid>/<action>")
def approve(rid,action):
    conn=db(); row=conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
    if not row: conn.close(); return "Request not found",404
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if action=="approve":
        conn.execute("UPDATE requests SET approval_status='Approved', procurement_status='In Progress', updated_at=? WHERE id=?",(now,rid))
        conn.execute("INSERT INTO procurement_tasks(request_id,assigned_to,status,created_at) VALUES(?,?,?,?)",
                     (rid,"Procurement Team","Open",now))
        msg="Request approved and procurement task automatically created."
    else:
        conn.execute("UPDATE requests SET approval_status='Rejected', procurement_status='Closed', updated_at=? WHERE id=?",(now,rid))
        msg="Request rejected and workflow closed."
    conn.commit(); conn.close(); flash(msg); return redirect(url_for("index"))

@app.route("/complete/<int:rid>")
def complete(rid):
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn=db()
    conn.execute("UPDATE procurement_tasks SET status='Completed',completed_at=? WHERE request_id=? AND status='Open'",(now,rid))
    conn.execute("UPDATE requests SET procurement_status='Completed',updated_at=? WHERE id=?",(now,rid))
    conn.commit(); conn.close(); flash("Procurement completed. Requester notification generated."); return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    conn=db()
    stats={
      "total":conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
      "pending":conn.execute("SELECT COUNT(*) FROM requests WHERE approval_status='Pending'").fetchone()[0],
      "approved":conn.execute("SELECT COUNT(*) FROM requests WHERE approval_status='Approved'").fetchone()[0],
      "completed":conn.execute("SELECT COUNT(*) FROM requests WHERE procurement_status='Completed'").fetchone()[0],
    }
    conn.close(); return render_template("dashboard.html",stats=stats)

if __name__=="__main__":
    init_db()
    app.run(debug=True)
