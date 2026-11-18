"""Clicks through the real page in headless Chromium. Needs `python server.py` running.
    python test_ui.py            # screenshots go to ui_shots/
rooms.json is backed up and restored, and plans the test saves are deleted again.
"""
import glob, json, os, random, shutil, tempfile, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
import test_scenarios as ts

URL = "http://127.0.0.1:8000/"
ROOT = Path(__file__).parent
SHOTS = ROOT / "ui_shots"


def chromium(p):
    try:
        return p.chromium.launch()
    except Exception:                                     # browser revision mismatch: use any cached Chromium
        exe = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))[-1]
        return p.chromium.launch(executable_path=exe)


def plan_ids():
    return {p["id"] for p in json.load(urllib.request.urlopen(URL + "api/plans"))}


def cleanup(before):
    for pid in plan_ids() - before:
        urllib.request.urlopen(urllib.request.Request(f"{URL}api/plans/{pid}", method="DELETE"))


def page(p, errors, width=1280):
    b = chromium(p)
    pg = b.new_page(viewport={"width": width, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and "status of 400" not in m.text and errors.append(m.text))   # 400 = a refused file, shown to the user
    pg.on("dialog", lambda d: d.accept())
    pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.goto(URL + "#/plan/1"); pg.reload()
    return b, pg


def main():
    SHOTS.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "rooms.json", tmp / "rooms.json")
    before = plan_ids()
    enr, _, codes = ts.uni(random.Random(7), students=80, exams=6, cohorts=2)
    (tmp / "enroll.csv").write_text(enr)
    (tmp / "LAB-9.csv").write_text("S,S,,S,S\nS,x,,S,S\nS,S,,S,S\n")
    errors = []
    try:
        with sync_playwright() as p:
            b, pg = page(p, errors)

            # 1 exam & students: type, upload, pick courses
            pg.check("input[name=kind][value=midsem]", force=True)
            assert "Mid-sem" in pg.input_value("#planName") and "Mid-sem defaults" in pg.inner_text("#kindNote")
            pg.check("input[name=kind][value=endsem]", force=True)
            pg.fill("#planName", "UI test plan")
            pg.set_input_files("#enrollFile", str(tmp / "enroll.csv"))
            pg.wait_for_selector("#enrollInfo .note.ok")
            assert "80" in pg.inner_text("#enrollStats")
            assert not pg.is_hidden("#pickCard")
            pg.uncheck(f'[data-course="{codes[5]}"]')                         # leave one course out of this plan
            assert "5</b> of 6" in pg.inner_html("#pickInfo")
            pg.screenshot(path=str(SHOTS / "1-students.png"), full_page=True)

            # 2 rooms
            pg.click("text=Next: rooms")
            placeholders = sum(1 for r in json.loads((ROOT / "rooms.json").read_text()) if r.get("placeholder"))
            assert pg.locator(".room .pill.warn").count() == placeholders
            pg.click("#roomsReal")
            assert pg.locator(".room.off").count() == placeholders
            pg.screenshot(path=str(SHOTS / "2-rooms.png"), full_page=True)
            pg.set_input_files("#layoutFiles", str(tmp / "LAB-9.csv"))
            pg.wait_for_selector("#roomEdit #rid")
            assert pg.locator("#rid").input_value() == "LAB-9"
            n = pg.locator(".room").count()
            pg.locator("#roomEdit .seat:not(.gap):not(.x)").first.click()
            assert pg.locator("#roomEdit .seat.x").count() == 2
            pg.click("#delRoom")
            pg.wait_for_function(f"document.querySelectorAll('.room').length === {n - 1}")

            # 3 dates & rules
            pg.click("text=Next: dates & rules")
            pg.fill("#calStart", "2027-01-04"); pg.fill("#calEnd", "2027-01-15"); pg.dispatch_event("#calEnd", "change")
            assert "10</b> exam days" in pg.inner_html("#periodInfo"), pg.inner_html("#periodInfo")
            pg.fill("#holDate", "2027-01-06"); pg.click("#addHol")
            assert "9</b> exam days" in pg.inner_html("#periodInfo")
            assert pg.is_checked("#r_gap")                                         # end-sem preset
            pg.check("#r_b2b")
            pg.select_option("#newType", "fix_exam")
            pg.select_option("#nf_exam", codes[0]); pg.fill("#nf_date", "2027-01-05"); pg.select_option("#nf_slot", "1")
            pg.click("#addSpecific")
            assert codes[0] in pg.inner_text("#specificList")
            assert pg.locator(f'#nf_exam option[value="{codes[5]}"]').count() == 0  # excluded course isn't offered
            pg.click("#englishBox summary")
            pg.fill("#english", f"{codes[2]} before {codes[4]}\nserve tea in every room")
            pg.click("#interpret")
            pg.wait_for_function("document.querySelector('#interpretMsg').textContent.startsWith('Found')", timeout=240000)
            assert pg.locator("#englishList .added.bad").count() == 1
            pg.screenshot(path=str(SHOTS / "3-rules.png"), full_page=True)
            pg.click("#jsonBox summary"); pg.fill("#timeLimit", "15")
            pg.wait_for_function("document.querySelector('#rulesJson').value.includes('room_use')")

            pg.click("#solve")
            pg.wait_for_selector("#resultBox h1", timeout=240000)
            txt = pg.inner_text("#resultBox")
            assert "Every rule checked" in txt and "Saved to dashboard" in txt, txt[:600]

            # 4 results
            sched = pg.inner_text("#tabBody")
            assert codes[0] in sched and codes[5] not in sched                   # only selected courses scheduled
            assert "Wed, Jan 6" not in sched and "Mon, Jan 4" in sched, sched[:900]   # holiday free, first day used
            pg.screenshot(path=str(SHOTS / "4-schedule.png"), full_page=True)
            with pg.expect_download() as d:
                pg.click("#dlSchedule")
            assert "Course code" in Path(d.value.path()).read_text(encoding="utf-8-sig")
            pg.click(".tabs button[data-t=seating]")
            painted = pg.locator("#roomCards .cs b").count()
            assert painted > 0 and "TEACHER" in pg.inner_text("#roomCards")
            first = pg.locator("#roomCards .cs b").first.inner_text()
            pg.fill("#seatFind", first)
            assert pg.locator("#roomCards .cs.hit").count() == 1
            pg.screenshot(path=str(SHOTS / "5-seating.png"), full_page=True)
            with pg.expect_download() as d:
                pg.click("#dlSeating")
            assert Path(d.value.path()).read_text(encoding="utf-8-sig").count("\n") > 50
            pg.evaluate("window.print = () => { window.__printed = document.querySelector('#printArea').innerText.length }")
            pg.click("#printSeating")
            assert pg.evaluate("window.__printed") > 100 and pg.locator("#printArea .cs b").count() > 0
            pg.click(".tabs button[data-t=student]")
            roll = next(l.split(",")[1] for l in enr.splitlines()[1:] if l.split(",")[3] != codes[5])
            pg.fill("#rollq", roll)
            assert "seat" in pg.inner_text("#rollOut").lower()
            pg.locator("#rollOut [data-show]").first.click()
            assert pg.locator("#roomCards .cs.hit").count() == 1

            # dashboard: the plan is saved, opens again, survives a reload
            pg.click(".mainnav a[data-page=dashboard]")
            pg.wait_for_selector(".plan.current")
            assert "UI test plan" in pg.inner_text(".plan.current") and "End-sem" in pg.inner_text(".plan.current")
            pg.screenshot(path=str(SHOTS / "6-dashboard.png"), full_page=True)
            pg.reload(); pg.wait_for_selector(".plan.current")
            pg.locator("#dashActs [data-open]").click()
            pg.wait_for_selector("#resultBox h1")
            assert "UI test plan" in pg.inner_text("#resultBox h1")

            # room view
            pg.click(".mainnav a[data-page=roomview]")
            pg.wait_for_selector("#rvBody .roomcard")
            assert pg.locator("#rvBody .rvlist button").count() >= 1 and pg.locator("#rvBody .cs b").count() > 0
            pg.locator("#rvBody .rvlist button").last.click()
            pg.wait_for_selector("#rvBody .roomcard")
            pg.screenshot(path=str(SHOTS / "7-roomview.png"), full_page=True)
            pg.evaluate("window.print = () => { window.__printed = document.querySelector('#printArea').innerText.length }")
            pg.click("#rvPrint")
            assert pg.evaluate("window.__printed") > 50

            # settings survive a reload
            pg.goto(URL + "#/plan/3"); pg.reload()
            assert pg.is_checked("#r_b2b") and pg.input_value("#calStart") == "2027-01-04" and codes[0] in pg.inner_text("#specificList")

            # phone width: nothing scrolls sideways
            pg.set_viewport_size({"width": 390, "height": 844})
            for h in ("#/dashboard", "#/plan/1", "#/plan/2", "#/plan/3", "#/plan/4", "#/rooms"):
                pg.goto(URL + h); pg.wait_for_timeout(300)
                assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"{h} scrolls sideways on a phone"
            pg.screenshot(path=str(SHOTS / "8-phone.png"))
            b.close()
    finally:
        shutil.copy(tmp / "rooms.json", ROOT / "rooms.json")
        cleanup(before)
    assert not errors, errors
    print("ui ok: dashboard, wizard, course selection, exam type, saved plans, room view;", painted, "students drawn in one session")


def uploads():
    """Every kind of enrollment file the office might have, plus the sample button and clear errors."""
    tmp = Path(tempfile.mkdtemp())
    (tmp / "odd.csv").write_text("Name,ID,Paper\nAmit,2026BTech001,AS1108\nRiya,2026BTech002,AS1108\nRiya,2026BTech002,CS1139\n")
    (tmp / "old.xls").write_bytes(b"\xd0\xcf\x11\xe0not really excel")
    errors = []
    with sync_playwright() as p:
        b, pg = page(p, errors)
        stats = lambda: pg.inner_text("#enrollInfo")

        def upload(path):
            pg.evaluate("document.querySelector('#enrollInfo').innerHTML = ''")
            pg.set_input_files("#enrollFile", str(path))
            pg.wait_for_selector("#enrollInfo .note", timeout=60000)

        upload(ROOT / "End Term Date Sheet Draft.csv")
        assert "1,201" in stats() and "72" in stats(), stats()
        assert pg.locator("#enrollTable tbody tr").count() == 500
        pg.fill("#enrollTable .search", "2025BBA002")
        assert 0 < pg.locator("#enrollTable tbody tr").count() < 20
        pg.fill("#enrollTable .search", "")
        sem1 = pg.locator("[data-sem='1']")
        sem1.uncheck()                                                     # whole semester out
        assert "1,201" not in pg.inner_text("#enrollStats")
        sem1.check()
        pg.screenshot(path=str(SHOTS / "0-upload-preview.png"), full_page=True)
        for f in ("enrollment_sample.xlsx", "enrollment_semicolon_windows.csv", "enrollment_sample.csv"):
            upload(ROOT / "samples" / f)
            assert "260" in stats() and "15" in stats(), (f, stats())
        upload(tmp / "odd.csv")
        assert "loaded" in stats() and "2" in stats(), stats()
        pg.select_option("#map_roll", "")
        pg.wait_for_selector("#enrollInfo .note.warn")
        pg.select_option("#map_roll", "1")
        pg.wait_for_selector("#enrollInfo .note.ok")
        upload(tmp / "old.xls")
        assert "Save As" in stats(), stats()
        pg.evaluate("document.querySelector('#enrollInfo').innerHTML = ''")
        pg.click("#trySample")
        pg.wait_for_selector("#enrollInfo .note.ok")
        pg.wait_for_selector("#invigInfo .note.ok")
        assert "260" in stats() and "18 invigilators" in pg.inner_text("#invigInfo")
        pg.goto((ROOT / "index.html").as_uri())
        assert pg.is_visible("#fileWarning")
        b.close()
    assert not errors, errors
    print("uploads ok: end-term CSV, Excel, Windows ;-CSV, unusual headings, semester filter, old .xls message, sample button, file:// warning")


def rescheduling():
    """Reschedule page: repair a saved plan, save it as v2, approve it; dashboard shows figures and lineage."""
    before = plan_ids()
    enr, rooms, codes = ts.uni(random.Random(7), students=120, exams=8, cohorts=2, rooms=5)
    post = lambda path, body: json.load(urllib.request.urlopen(urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})))
    r = post("api/solve", {"enrollment": enr, "rooms": rooms, "constraints": [], "calendar": ts.CAL, "time_limit": 10, "use_profile": False,
                           "invigilators": "name,unavailable\n" + "\n".join(f"P{k}," for k in range(8))})
    meta = post("api/plans", {"name": "Reschedule test", "kind": "endsem", "result": dict(r, calendar=ts.CAL)})
    errors = []
    try:
        with sync_playwright() as p:
            b, pg = page(p, errors)
            pg.evaluate(f"localStorage.setItem('ep.currentPlan', JSON.stringify('{meta['id']}'))")
            pg.goto(URL + "#/reschedule"); pg.reload()
            pg.wait_for_selector(f"#rsPlan option[value='{meta['id']}']", state="attached")
            pg.select_option("#rsType", "move"); pg.select_option("#rsForm [data-f=exam]", codes[0]); pg.click("#rsAdd")
            assert "Move " + codes[0] in pg.inner_text("#rsList")
            pg.click("#rsRun"); pg.wait_for_selector("#rsOut .card", timeout=120000)
            out = pg.inner_text("#rsOut")
            assert "Every rule re-checked" in out and codes[0] in out and "Exams moved" in out, out[:500]
            pg.screenshot(path=str(SHOTS / "9-reschedule.png"), full_page=True)
            # swap two exams, no reason given: both trade sessions, or the clash is named
            pg.click("#rsList [data-rsx]")
            pg.select_option("#rsType", "swap"); pg.select_option("#rsForm [data-f=exam]", codes[0]); pg.select_option("#rsForm [data-f=exam2]", codes[1]); pg.click("#rsAdd")
            assert pg.locator("#rsList .added").count() == 2
            pg.click("#rsRun"); pg.wait_for_function("document.querySelector('#rsOut').innerText.length > 0", timeout=120000)
            out = pg.inner_text("#rsOut")
            assert ("Exams moved" in out and codes[0] in out and codes[1] in out) or "can't be absorbed" in out, out[:500]
            pg.click("#rsList [data-rsx]"); pg.click("#rsList [data-rsx]")
            pg.select_option("#rsType", "move"); pg.select_option("#rsForm [data-f=exam]", codes[0]); pg.click("#rsAdd")
            pg.click("#rsRun"); pg.wait_for_selector("#rsOut .card", timeout=120000)
            pg.click("#rsSave"); pg.wait_for_selector("#resultBox h1")
            assert "What this reschedule changed" in pg.inner_text("#resultBox") and "v2" in pg.inner_text("#resultBox")
            pg.click(".mainnav a[data-page=dashboard]"); pg.wait_for_selector("#dashKpis .kpi")
            cur = pg.inner_text(".plan.current")
            assert "v2" in cur and "Rescheduled from v1" in cur, cur
            assert pg.locator("#dashSheet .ex").count() > 0
            pg.click("#dashActs [data-appr]"); pg.wait_for_selector(".plan.current .pill.ok >> text=Approved")
            assert "Approved" in pg.inner_text("#planBand")
            assert pg.locator("#dashSheet .ex").count() > 0
            b.close()
    finally:
        cleanup(before)
    assert not errors, errors
    print("reschedule ok: minimal repair, diff shown, saved as v2 with lineage, approval")


if __name__ == "__main__":
    uploads()
    main()
    rescheduling()
