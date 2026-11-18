"""python server.py  ->  http://localhost:8000"""
import base64, csv, io, json, re, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import scheduler

ROOT = Path(__file__).parent
ROOMS = ROOT / "rooms.json"
PLANS = ROOT / "data" / "plans"
PLAN_ID = re.compile(r"^[0-9a-z-]{6,40}$")


def plan_meta(p):
    r = p.get("result", {})
    met, d = r.get("metrics") or {}, r.get("diff") or {}
    return {k: p.get(k) for k in ("id", "name", "kind", "created", "parent", "approved")} | {
        "status": p.get("status", "draft"), "version": p.get("version", 1),
        "start": r.get("calendar", {}).get("start"), "end": r.get("calendar", {}).get("end"),
        "exams": r.get("stats", {}).get("exams"), "students": r.get("stats", {}).get("students"),
        "rooms": len({rid for v in r.get("seating", {}).values() for rid in v}), "ok": r.get("ok") and not r.get("violations"),
        "utilisation": (met.get("seats") or {}).get("utilisation"), "gini": (met.get("invigilation") or {}).get("gini"),
        "changes": r.get("changes"), "stability": d.get("stability"), "exams_moved": d.get("exams_moved")}


def load_plan(pid):
    f = PLANS / f"{pid}.json"
    return json.loads(f.read_text()) if PLAN_ID.match(pid or "") and f.exists() else None


HEADER_WORDS = re.compile(r"roll|subject|course|code|student|name", re.I)


def read_table(name, raw):
    """Any spreadsheet the office is likely to have -> list of rows (header first). CSV in any common encoding/separator, or .xlsx."""
    low = name.lower()
    if low.endswith(".xls"):
        raise ValueError("Old .xls files can't be read. In Excel use File > Save As and pick .xlsx or CSV.")
    if low.endswith((".xlsx", ".xlsm")):
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
        rows = [["" if v is None else str(v).strip() for v in r] for r in ws.iter_rows(values_only=True)]
    else:
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = raw.decode("utf-16")
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1252", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        raise ValueError("The file is empty.")
    start = next((i for i, r in enumerate(rows[:20]) if sum(bool(HEADER_WORDS.search(c)) for c in r) >= 2), 0)   # skip title rows
    rows = rows[start:]
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/rooms":
            self.send(200, json.loads(ROOMS.read_text()) if ROOMS.exists() else [])
        elif self.path == "/api/vocab":
            self.send(200, scheduler.VOCAB)
        elif self.path == "/api/plans":                 # dashboard: saved plans, newest first
            PLANS.mkdir(parents=True, exist_ok=True)
            plans = [plan_meta(json.loads(f.read_text())) for f in PLANS.glob("*.json")]
            self.send(200, sorted(plans, key=lambda x: x["created"] or "", reverse=True))
        elif self.path.startswith("/api/plans/"):
            plan = load_plan(self.path.rsplit("/", 1)[1])
            self.send(200, plan) if plan else self.send(404, {"error": "plan not found"})
        elif self.path.startswith("/samples/"):                # sample files for trying the system
            f = (ROOT / "samples" / Path(self.path).name)
            if f.is_file():
                ctype = {".csv": "text/csv; charset=utf-8", ".txt": "text/plain; charset=utf-8"}.get(f.suffix, "application/octet-stream")
                self.send(200, f.read_bytes(), ctype)
            else:
                self.send(404, {"error": "no such sample"})
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/rooms":
                if not all(isinstance(r.get("id"), str) and isinstance(r.get("layout"), str) for r in body):
                    return self.send(400, {"error": "each room needs id and layout"})
                ROOMS.write_text(json.dumps(body, indent=1))
                self.send(200, {"saved": len(body)})
            elif self.path == "/api/interpret":
                import rule_model
                if body.get("plan_id"):                    # rescheduling: read rules against the saved plan's own data
                    plan = load_plan(body["plan_id"])
                    if not plan:
                        return self.send(404, {"error": "plan not found"})
                    inp = plan["result"].get("inputs") or scheduler._inputs_from_result(plan)
                    body.update(enrollment=inp["enrollment"], rooms=inp["rooms"], calendar=inp["calendar"])
                exams, _ = scheduler.load_enrollment(body["enrollment"])
                self.send(200, rule_model.interpret(body["text"], exams, body["rooms"], body["calendar"]))
            elif self.path == "/api/plans":                # save a finished plan for the dashboard
                import datetime as dt
                now = dt.datetime.now()
                pid = now.strftime("%Y%m%d-%H%M%S") + "-" + format(now.microsecond, "06d")[:3]
                parent = load_plan(body.get("parent")) if body.get("parent") else None
                plan = {"id": pid, "name": str(body.get("name") or (parent or {}).get("name") or "Exam plan")[:120],
                        "kind": body.get("kind", (parent or {}).get("kind", "")), "created": now.isoformat(timespec="seconds"),
                        "result": body["result"], "rules": body.get("rules", (parent or {}).get("rules", [])), "status": "draft",
                        "parent": parent and parent["id"], "version": (parent or {}).get("version", 0) + 1}
                PLANS.mkdir(parents=True, exist_ok=True)
                (PLANS / f"{pid}.json").write_text(json.dumps(plan))
                self.send(200, plan_meta(plan))
            elif self.path == "/api/table":                # uploaded spreadsheet -> rows, for preview and column choice
                rows = read_table(body["name"], base64.b64decode(body["data"]))
                self.send(200, {"columns": rows[0], "rows": rows[1:]})
            elif self.path == "/api/summary":              # what the page needs to build pickers and tick boxes
                exams, students = scheduler.load_enrollment(body["enrollment"])
                prof = ROOT / "data" / "profile.json"
                learned = []
                if prof.exists():
                    import history
                    learned = history.profile_constraints(json.loads(prof.read_text()), exams, (body.get("calendar") or {}).get("start"))
                self.send(200, {
                    "students": len(students),
                    "exams": [{"code": c, "name": e["name"], "size": len(e["students"]), "semester": e.get("semester"), "kind": e.get("kind")}
                              for c, e in sorted(exams.items())],
                    "max_per_student": max((len(s["exams"]) for s in students.values()), default=0),
                    "learned": learned})
            elif self.path == "/api/import":               # Word seat maps / past PDFs dropped on the Rooms page
                import history
                saved = []
                for f in body["files"]:
                    name = Path(f["name"]).name
                    if Path(name).suffix.lower() not in (".docx", ".pdf"):
                        return self.send(400, {"error": f"{name}: only .docx and .pdf files are accepted"})
                    history.PAST.mkdir(parents=True, exist_ok=True)
                    (history.PAST / name).write_bytes(base64.b64decode(f["data"]))
                    saved.append(name)
                _, _, notes = history.rebuild(log=lambda *_: None)
                self.send(200, {"saved": saved, "notes": notes, "rooms": json.loads(ROOMS.read_text())})
            elif self.path == "/api/corrections":           # admin-reviewed rules become training data
                with open(ROOT / "corrections.jsonl", "a") as f:
                    for c in body:
                        f.write(json.dumps({"text": c["text"], "rules": c["rules"]}) + "\n")
                self.send(200, {"saved": len(body)})
            elif self.path == "/api/reschedule":           # repair a saved plan with the fewest changes
                plan = load_plan(body.get("plan_id"))
                if not plan:
                    return self.send(404, {"error": "plan not found"})
                self.send(200, scheduler.reschedule(plan, body.get("changes", []), body.get("freeze_before") or None,
                                                    int(body.get("time_limit", 60)), log=lambda *_: None))
            elif re.fullmatch(r"/api/plans/[0-9a-z-]+/(approve|unapprove)", self.path):   # admin approval gates publishing
                _, _, _, pid, act = self.path.split("/")
                plan = load_plan(pid)
                if not plan:
                    return self.send(404, {"error": "plan not found"})
                if act == "approve" and (not plan["result"].get("ok") or plan["result"].get("violations")):
                    return self.send(400, {"error": "A plan with problems can't be approved."})
                import datetime as dt
                plan["status"] = "approved" if act == "approve" else "draft"
                plan["approved"] = dt.datetime.now().isoformat(timespec="seconds") if act == "approve" else None
                (PLANS / f"{pid}.json").write_text(json.dumps(plan))
                self.send(200, plan_meta(plan))
            elif self.path == "/api/solve":
                prof = ROOT / "data" / "profile.json"
                profile = json.loads(prof.read_text()) if body.get("use_profile", True) and prof.exists() else None
                self.send(200, scheduler.run(body["enrollment"], body["rooms"], body["constraints"], body["calendar"],
                                             body.get("invigilators", ""), int(body.get("time_limit", 60)), profile=profile))
            else:
                self.send(404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            self.send(400, {"error": f"{type(e).__name__}: {e}"})


def _delete(self):
    pid = self.path.rsplit("/", 1)[1]
    f = PLANS / f"{pid}.json"
    if self.path.startswith("/api/plans/") and PLAN_ID.match(pid) and f.exists():
        f.unlink(); self.send(200, {"deleted": pid})
    else:
        self.send(404, {"error": "plan not found"})


Handler.do_DELETE = _delete


if __name__ == "__main__":
    print("http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
