"""Past exam PDFs -> structured history -> learned office profile.

    python history.py            # parse data/past/*.pdf, write data/history.json + data/profile.json, replay past sittings

Two seating formats are understood (the Sept "SEATING PLAN (dd.mm.yyyy)" table and the May
"Seating Arrangement Summary"), plus the B.Tech date sheet. Drop new semesters into data/past/ and re-run.
"""
import csv, io, json, re, statistics, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

PAST = Path(__file__).parent / "data" / "past"
OUT = Path(__file__).parent / "data"
ROOM = re.compile(r"^[A-Z]{2,3}\d?-[A-Z0-9]+$")
CODE = re.compile(r"[A-Z]{2}\d{4}")
ROLL = re.compile(r"^(\d{4})([A-Za-z]+)(\d{3})$")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def words(pdf):
    """[(page, x, y, text)] from pdftotext -tsv."""
    out = subprocess.run(["pdftotext", "-tsv", str(pdf), "-"], capture_output=True, text=True).stdout
    rows = csv.reader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE)
    next(rows, None)
    return [(int(r[1]), float(r[6]), float(r[7]), r[11]) for r in rows if len(r) > 11 and r[0] == "5" and r[11].strip()]


def expand(tokens):
    """['2026BTech001', 'to', '2026BTech025', '2026BTech570'] -> roll list. Ranges can include unregistered numbers."""
    out, i = [], 0
    while i < len(tokens):
        t = tokens[i].strip(",")
        if i + 2 < len(tokens) and tokens[i + 1] == "to":
            a, b = ROLL.match(t), ROLL.match(tokens[i + 2].strip(","))
            if a and b and a.group(1, 2) == b.group(1, 2):
                out += [f"{a[1]}{a[2]}{n:03d}" for n in range(int(a[3]), int(b[3]) + 1)]
                i += 3
                continue
        if ROLL.match(t):
            out.append(t)
        i += 1
    return out


def parse_table_plan(pdf):
    """Sept format: room label sits mid-cell, exam blocks around it. Assign blocks to rooms by y-position."""
    w = words(pdf)
    date = next(m[1] for *_, t in w for m in [re.search(r"\((\d\d\.\d\d\.\d{4})\)", t)] if m)
    hy, room_x = next((y, x) for p, x, y, t in w if p == 1 and t == "Room")       # column positions from the header row
    count_x = next(x for p, x, y, t in w if p == 1 and t == "Students") - 40
    head = [t for p, x, y, t in w if p == 1 and abs(y - hy) < 2]
    time = next(f"{a} {b}" for a, b in zip(head, head[1:]) if re.match(r"\d{1,2}:\d\d$", a) and b in ("AM", "PM"))
    sittings = []
    for page in sorted({p for p, *_ in w}):
        pw = sorted([(y, x, t) for p, x, y, t in w if p == page and (page > 1 or y > hy + 5)])
        rooms = [(y, t) for y, x, t in pw if ROOM.match(t) and x < room_x + 40]
        blocks = []                                      # one block per "X Sem: (CODE)" marker
        for y, x, t in pw:
            m = re.match(r"^\(([A-Z]{2}\d{4})\)$", t)
            if m:
                sem = next((ROMAN.get(t2) for y2, x2, t2 in pw if abs(y2 - y) < 2 and x2 < x and t2 in ROMAN), None)
                blocks.append({"exam": m[1], "sem": sem, "y0": y, "y1": y, "tokens": [], "count": None})
            elif blocks and x > room_x + 40:             # rolls/counts belong to the marker directly above them
                b = blocks[-1]
                if t.isdigit() and x > count_x:
                    b["count"] = int(t)
                elif ROLL.match(t.strip(",")) or t == "to":
                    b["tokens"].append(t); b["y1"] = max(b["y1"], y)
        if not rooms or not blocks:
            continue
        sittings.append((rooms, blocks))
    plan = defaultdict(list)
    for rooms, blocks in sittings:
        for (_, room), group in zip(rooms, partition(rooms, blocks)):
            for b in group:
                rolls = expand(b["tokens"])
                plan[room].append({"exam": b["exam"], "sem": b["sem"], "count": b["count"] or len(rolls), "rolls": rolls})
    return {"date": "-".join(reversed(date.split("."))), "time": time, "source": pdf.name, "rooms": dict(plan)}


def partition(rooms, blocks):
    """Split blocks (in order) into len(rooms) consecutive groups so each room label sits closest to its group's centre."""
    n, k, INF = len(blocks), len(rooms), float("inf")
    cost = lambda r, i, j: abs(rooms[r][0] - (blocks[i]["y0"] + blocks[j - 1]["y1"]) / 2)
    best = [[INF] * (n + 1) for _ in range(k + 1)]
    back = [[0] * (n + 1) for _ in range(k + 1)]
    best[0][0] = 0
    for r in range(1, k + 1):
        for j in range(r, n + 1):
            for i in range(r - 1, j):
                c = best[r - 1][i] + cost(r - 1, i, j)
                if c < best[r][j]:
                    best[r][j], back[r][j] = c, i
    cuts, j = [], n
    for r in range(k, 0, -1):
        cuts.append((back[r][j], j)); j = back[r][j]
    return [blocks[i:j] for i, j in reversed(cuts)]


def parse_summary_plan(pdf):
    """May format: 'Room No.: X' label mid-cell, 'CODE [ N STUDENTS ] : rolls' blocks. Same position-based assignment."""
    import datetime as dt
    text = subprocess.run(["pdftotext", "-raw", str(pdf), "-"], capture_output=True, text=True).stdout
    m = re.search(r"Date & Time : \w+, (\d+) (\w+) (\d{4}), (\d+:\d\d [AP]M)", text)
    date = dt.datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%d %B %Y").date().isoformat()
    w = words(pdf)
    plan = defaultdict(list)
    for page in sorted({p for p, *_ in w}):
        pw = sorted([(y, x, t) for p, x, y, t in w if p == page])
        rooms = [t for (y, x, t), (_, _, prev) in zip(pw[1:], pw) if prev == "No.:" and ROOM.match(t)]
        totals = [int(pw[i + 3][2]) for i in range(len(pw) - 3) if pw[i][2] == "TOTAL" and pw[i + 3][2].isdigit()]
        blocks = []
        for i, (y, x, t) in enumerate(pw):
            if CODE.fullmatch(t) and i + 2 < len(pw) and pw[i + 1][2] == "[" and pw[i + 2][2].isdigit():
                blocks.append({"exam": t, "count": int(pw[i + 2][2]), "tokens": []})
            elif blocks and (ROLL.match(t.strip(",")) or t == "to"):
                blocks[-1]["tokens"].append(t)
        if len(rooms) != len(totals):
            raise ValueError(f"page {page}: {len(rooms)} room labels but {len(totals)} totals")
        it = iter(blocks)                                 # each room's blocks must add up to its printed total
        for room, total in zip(rooms, totals):
            got = 0
            while got < total:
                b = next(it); got += b["count"]
                plan[room].append({"exam": b["exam"], "sem": None, "count": b["count"], "rolls": expand(b["tokens"])})
            if got != total:
                raise ValueError(f"{room}: blocks add to {got}, printed total {total}")
    return {"date": date, "time": m[4], "source": pdf.name, "rooms": dict(plan)}


def parse_datesheet(pdf):
    """Course codes -> (date, time) by nearest date/time cell on the same page."""
    w = words(pdf)
    out = {}
    for page in {p for p, *_ in w}:
        pw = [(x, y, t) for p, x, y, t in w if p == page]
        dates = [(y, t) for x, y, t in pw if re.match(r"\d\d\.\d\d\.\d{4}$", t)]
        times = [(y, f"{t} {n}") for (x, y, t), (_, _, n) in zip(pw, pw[1:]) if re.match(r"\d{1,2}:\d\d$", t) and n in ("AM", "PM")]
        if not dates:
            continue
        for x, y, t in pw:
            m = re.match(r"^([A-Z]{2}\d{4}):$", t)
            if m and m[1] not in out:
                d = min(dates, key=lambda d: abs(d[0] - y))[1]
                tm = min(times, key=lambda q: abs(q[0] - y))[1] if times else ""
                name = " ".join(t2 for x2, y2, t2 in pw if abs(y2 - y) < 2 and x < x2 < x + 160 and not re.match(r"\d", t2))
                out[m[1]] = {"date": "-".join(reversed(d.split("."))), "time": re.sub(r"^0", "", tm), "name": name}
    return out


ROLL_ANY = re.compile(r"\d{2,4}[A-Za-z]+\d{3}|\bto\b")


def norm_roll(r):
    m = re.match(r"^(\d{2,4})([A-Za-z]+)(\d{3})$", r)
    return f"{'20' + m[1] if len(m[1]) == 2 else m[1]}{m[2]}{m[3]}" if m else r


def _text(el):
    return "".join(x.text or "" for x in el.iter() if x.tag.endswith("}t"))


def parse_docx(path):
    """Word seat maps: heading paragraphs ('... (CS1134) rolls ... Room No.: EB1-101'), then a table whose cells are seats.
    Returns raw tables; build_docx() decides aisles using every file together."""
    import docx
    from docx.table import Table
    d = docx.Document(str(path))
    header, out = "", {"date": None, "time": None, "source": Path(path).name, "tables": {}}

    for el in d.element.body.iterchildren():
        if el.tag.endswith("}p"):
            t = _text(el).strip()
            header += " " + t
            m = re.search(r"Date:\s*(\d\d)\.(\d\d)\.(\d{4})", t)
            if m: out["date"] = f"{m[3]}-{m[2]}-{m[1]}"
            m = re.search(r"Time:\s*0?(\d{1,2}:\d\d)\s*([AP]M)", t)
            if m: out["time"] = f"{m[1]} {m[2]}"
            continue
        if not el.tag.endswith("}tbl"):
            continue
        ids = re.findall(r"Room No\.?\s*:?\s*([A-Z]{2,3}\d?-[A-Z0-9]+)", header)
        segs = re.split(r"\(([A-Z]{2}\d{4})\)", header)
        header = ""
        if not ids:
            continue
        roll_exam = {}
        for code, txt in zip(segs[1::2], segs[2::2]):
            for r in expand([norm_roll(t) for t in ROLL_ANY.findall(txt)]):
                roll_exam.setdefault(r, code)
        rows, above = Table(el, d).rows, set()
        hdr = _cells(rows[0], above)
        out["tables"][ids[-1]] = {"header": hdr, "rows": [_cells(r, above) for r in rows[1:]][::-1],   # front row first
                                  "roll_exam": roll_exam}
    return out


VCONT = "\x00below"                                       # lower half of a vertically merged (tall) seat


def _cells(row, above):
    """Unique cells of a row as [grid_start, grid_end, text]. python-docx returns the top cell again for the lower part
    of a vertical merge, so a cell already seen in an earlier row is marked as the lower half of a tall seat."""
    cells, last = [], None
    for gi, c in enumerate(row.cells):
        if c._tc is last:
            cells[-1][1] = gi
            continue
        last = c._tc
        cells.append([gi, gi, VCONT if c._tc in above else c.text.strip()])
    above.update(c._tc for c in row.cells)
    return cells


def build_docx(docs):
    """Aisle = column labelled 'Passage', or with no bench number where no file ever seated anyone."""
    used, header = defaultdict(set), {}
    for d in docs:
        for rid, t in d["tables"].items():
            header.setdefault(rid, t["header"])
            for row in t["rows"]:
                for g0, g1, txt in row:
                    if txt and txt != VCONT and txt.lower() != "passage":
                        used[rid] |= set(range(g0, g1 + 1))
    aisle = {}
    for rid, hdr in header.items():
        aisle[rid] = {g for g0, g1, txt in hdr for g in range(g0, g1 + 1)
                      if txt.lower() == "passage" or (not txt and g not in used[rid])}
    layouts, sittings = {}, []
    for d in docs:
        plan, maps = {}, {}
        for rid, t in d["tables"].items():
            lines, seats = [], []
            for row in t["rows"]:
                ch = [" "] * (max((c[1] for c in row), default=0) + 1)
                for g0, g1, txt in row:
                    if txt == VCONT or txt.lower() == "passage" or set(range(g0, g1 + 1)) <= aisle[rid]:
                        continue
                    ch[g0] = "S"
                    for g in range(g0 + 1, g1 + 1):
                        ch[g] = "-"
                    r = norm_roll(txt) if txt else None
                    seats.append((r, t["roll_exam"].get(r, "?")) if r else None)
                lines.append("".join(ch).rstrip())
            layouts.setdefault(rid, "\n".join(lines))
            if any(seats):
                maps[rid] = seats
                plan[rid] = [{"exam": e, "sem": None, "count": n, "rolls": sorted(r for r, x in filter(None, seats) if x == e)}
                             for e, n in Counter(x for _, x in filter(None, seats)).items()]
        if plan:
            sittings.append({"date": d["date"], "time": d["time"], "source": d["source"], "rooms": plan, "seatmaps": maps})
    return sittings, layouts


def parse_all(folder=PAST):
    docs, datesheet = [], {}
    for f in sorted(folder.glob("*.docx")):
        try:
            docs.append(parse_docx(f))
        except Exception as e:                            # one bad file must not stop the rest
            print(f"failed: {f.name}: {e}")
    sittings, layouts = build_docx(docs)
    for pdf in sorted(folder.glob("*.pdf")):
        head = subprocess.run(["pdftotext", "-l", "1", str(pdf), "-"], capture_output=True, text=True).stdout
        try:
            if "Date Sheet" in head:
                datesheet.update(parse_datesheet(pdf))
            elif "SEATING PLAN (" in head:
                sittings.append(parse_table_plan(pdf))
            elif "Date & Time :" in head:
                sittings.append(parse_summary_plan(pdf))
            else:
                print(f"skipped (no readable text or unknown format): {pdf.name}")
        except Exception as e:                            # one bad PDF must not stop the rest
            print(f"failed: {pdf.name}: {e}")
    return {"sittings": sittings, "datesheet": datesheet, "layouts": layouts}


# ---------------- learning ----------------

def cohort(rolls):
    """Admission-year batch of an exam, e.g. '2026BTech' (majority of its students)."""
    c = Counter(m[1] + m[2] for r in rolls for m in [ROLL.match(r)] if m)
    return c.most_common(1)[0][0] if c else None


def semester_at(roll_cohort, date):
    """'2025BTech' sitting on 2026-09-21 -> semester 3 (odd term Jul-Dec, even term Jan-Jun)."""
    if not roll_cohort or not date:
        return None
    y, m = int(date[:4]), int(date[5:7])
    year = y - int(roll_cohort[:4]) + (1 if m >= 7 else 0)
    return 2 * year - (1 if m >= 7 else 0) if year >= 1 else None


def learn(h):
    """Office profile estimated from past sittings + date sheets. Feeds the solver as defaults and soft preferences."""
    cap, mix, per_room_exams, fill = defaultdict(list), [], [], []
    exam_cohort = {}
    for s in h["sittings"]:
        for room, segs in s["rooms"].items():
            n = sum(x["count"] for x in segs)
            cap[room].append(n)
            per_room_exams.append(len(segs))
            mix.append(len(segs) > 1)
            for x in segs:
                exam_cohort.setdefault(x["exam"], cohort(x["rolls"]))
    # slot habit per semester, from every sitting and date sheet (morning = slot 1)
    slot_by_sem, seen = defaultdict(Counter), set()
    events = [(x["exam"], st["date"], st["time"], cohort(x["rolls"])) for st in h["sittings"] for segs in st["rooms"].values() for x in segs]
    events += [(code, d["date"], d["time"], exam_cohort.get(code)) for code, d in h["datesheet"].items()]
    for code, date, time, coh in events:
        sem = semester_at(coh, date)
        if sem and (code, date) not in seen:
            seen.add((code, date)); slot_by_sem[sem][1 if "AM" in (time or "") else 2] += 1
    room_cap = {r: max(v) for r, v in cap.items()}
    # seat level, from Word seat maps: how the office spaces students
    import scheduler
    side = {"mixed": [0, 0], "single": [0, 0]}; front = [0, 0]; fills = []
    for st in h["sittings"]:
        for rid, seats in st.get("seatmaps", {}).items():
            lay = scheduler.parse_layout({"layout": h["layouts"][rid]})
            if len(lay) != len(seats):
                continue
            kind = "mixed" if len({x[1] for x in seats if x}) > 1 else "single"
            for a, b in scheduler.adjacent_pairs(lay, ["side"]):
                if seats[a] and seats[b]:
                    side[kind][0] += seats[a][1] == seats[b][1]; side[kind][1] += 1
            for a, b in scheduler.adjacent_pairs(lay, ["front"]):
                if seats[a] and seats[b]:
                    front[0] += seats[a][1] == seats[b][1]; front[1] += 1
            fills.append(sum(1 for x in seats if x) / len(seats))
    rate = lambda v: round(v[0] / v[1], 2) if v[1] else None
    return {
        "room_capacity": room_cap,                                    # most students the office ever put in each room
        "max_exams_per_room": max(per_room_exams, default=3),
        "typical_exams_per_room": statistics.median(per_room_exams) if per_room_exams else 2,
        "mixed_room_share": round(sum(mix) / len(mix), 2) if mix else None,
        "semester_slot": {str(k): max(v, key=v.get) for k, v in sorted(slot_by_sem.items())},
        "semester_slot_confidence": {str(k): round(max(v.values()) / sum(v.values()), 2) for k, v in sorted(slot_by_sem.items())},
        "semester_slot_evidence": {str(k): sum(v.values()) for k, v in sorted(slot_by_sem.items())},
        "same_exam_side_by_side": {"mixed_rooms": rate(side["mixed"]), "single_exam_rooms": rate(side["single"])},
        "same_exam_front_back": rate(front),
        "seat_fill": {"median": round(statistics.median(fills), 2), "max": round(max(fills), 2)} if fills else None,
        "exam_cohort": exam_cohort,
        "data": {"sittings": len(h["sittings"]), "datesheet_courses": len(h["datesheet"]),
                 "room_observations": sum(len(v) for v in cap.values())},
    }


def profile_constraints(profile, exams, start=None):
    """Turn the learned profile into solver rules for the exams in this run. All soft, except the room-mix cap."""
    cons = [{"id": "learned-mix", "type": "max_exams_per_room", "params": {"n": profile["max_exams_per_room"]},
             "text": f"learned: the office never mixed more than {profile['max_exams_per_room']} exams in a room"}]
    by_slot, sems_in = defaultdict(list), defaultdict(set)
    for e, x in exams.items():
        sem = str(x.get("semester") or semester_at(cohort(x["students"]), start) or "")
        if sem in profile.get("semester_slot", {}) and profile["semester_slot_confidence"][sem] >= 0.75 \
                and profile["semester_slot_evidence"][sem] >= 3:
            by_slot[profile["semester_slot"][sem]].append(e); sems_in[profile["semester_slot"][sem]].add(int(sem))
    for slot, ex in sorted(by_slot.items()):
        cons.append({"id": f"learned-slot{slot}", "type": "prefer_slot", "params": {"exams": sorted(ex), "slot": slot, "weight": 1},
                     "text": f"learned: semester {', '.join(map(str, sorted(sems_in[slot])))} exams usually sit in the "
                             f"{'morning' if slot == 1 else 'afternoon'} ({len(ex)} exams)"})
    if (profile.get("same_exam_side_by_side") or {}).get("single_exam_rooms", 0) >= 0.5:
        cons.append({"id": "learned-adjacent", "type": "adjacent_when_needed", "params": {},
                     "text": "learned: when an exam is too big to space out, the office seats it side by side"})
    return cons


def replay(h, rooms, log=print):
    """Re-seat each past sitting with our solver (same exams, same counts) and compare with what the office did."""
    import scheduler as s
    ids = {r["id"] for r in rooms}
    rows = []
    for st in h["sittings"]:
        exams = {}
        for room, segs in st["rooms"].items():
            for x in segs:
                exams.setdefault(x["exam"], {"name": x["exam"], "students": set()})
                exams[x["exam"]]["students"] |= {f"{x['exam']}-{room}-{i}" for i in range(x["count"])}
        if not set(st["rooms"]) <= ids:
            log(f"{st['date']} {st['time']}: skipped, rooms missing from rooms.json: {sorted(set(st['rooms']) - ids)}")
            continue
        use = [r for r in rooms if r["id"] in st["rooms"]]
        caps = s.room_capacity(use, [{"date": st["date"], "slot": 1}], [])[0]
        allow = [{"type": "allow_adjacent", "params": {"exams": [e for e in exams if len(exams[e]["students"]) > sum(r["spaced"] for r in caps.values())]}}]
        need, have = sum(len(x["students"]) for x in exams.values()), sum(r["usable"] for r in caps.values())
        if need > have:
            log(f"{st['date']} {st['time']}: {need} students but the current drawings of those rooms hold {have}; skipped")
            continue
        seated = s.seat_slot(sorted(exams), exams, caps, allow, time_limit=20)
        ours = len(seated) if seated else None
        rows.append((st["date"], st["time"], sum(len(x["students"]) for x in exams.values()), len(st["rooms"]), ours))
        log(f"{st['date']} {st['time']}: {rows[-1][2]} students, office used {rows[-1][3]} rooms, solver used {ours or 'FAILED'}")
    return rows


def update_rooms(h, profile, path):
    """Real layouts from the Word seat maps go into rooms.json. Returns rooms whose drawing is smaller than past use."""
    rooms = json.loads(path.read_text()) if path.exists() else []
    by = {r["id"]: r for r in rooms}
    import scheduler
    for rid, lay in h["layouts"].items():
        r = by.setdefault(rid, {"id": rid, "building": rid.split("-")[0]})
        if r.get("placeholder", True) or r.get("source") == "Word seat map":   # never overwrite a hand-drawn layout
            r["layout"], r["placeholder"], r["source"] = lay, False, "Word seat map"
    if not any(r in rooms for r in by.values()):
        pass
    rooms = list(by.values())
    path.write_text(json.dumps(rooms, indent=1))
    return [(r["id"], len(scheduler.parse_layout(r)), profile["room_capacity"][r["id"]]) for r in rooms
            if r["id"] in profile["room_capacity"] and len(scheduler.parse_layout(r)) < profile["room_capacity"][r["id"]]]


def rebuild(log=print):
    """Re-read data/past/, relearn the profile, install real layouts. Returns plain-language findings."""
    h = parse_all()
    OUT.mkdir(exist_ok=True)
    (OUT / "history.json").write_text(json.dumps(h, indent=1))
    p = learn(h)
    (OUT / "profile.json").write_text(json.dumps(p, indent=1))
    notes = [f"Read {len(h['sittings'])} past sittings, {len(h['datesheet'])} date-sheet courses and {len(h['layouts'])} room layouts."]
    for st in h["sittings"]:                              # data problems in the office's own files
        for rid, seats in st.get("seatmaps", {}).items():
            for roll, n in Counter(x[0] for x in seats if x).items():
                if n > 1:
                    notes.append(f"{st['source']}, room {rid}: {roll} appears in {n} seats.")
    for rid, seats, seen in update_rooms(h, p, Path(__file__).parent / "rooms.json"):
        notes.append(f"{rid}: the drawing has {seats} seats, but a past plan seated {seen} students there. Check the drawing.")
    return h, p, notes


if __name__ == "__main__":
    h, p, notes = rebuild()
    print(json.dumps({k: v for k, v in p.items() if k not in ("exam_cohort", "room_capacity")}, indent=1))
    print("\n".join(notes))
    if "--replay" in sys.argv:
        replay(h, json.load(open(Path(__file__).parent / "rooms.json")))
