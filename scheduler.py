"""Exam timetabling + seating.

Stage 1  exam -> slot          CP-SAT over the whole period (so day 15 is as good as day 1)
Stage 2  students -> seats     CP-SAT per slot, on each room's drawn layout
If stage 2 can't seat a slot, that exam combination is banned and stage 1 re-runs.
validate() re-checks every hard rule on the final output, independently of the solvers.
"""
import csv, io, math, re, datetime as dt
from collections import Counter, defaultdict
from ortools.sat.python import cp_model

# Every constraint the solver understands. The LLM maps English onto these; anything else is "unsupported".
VOCAB = {
    "max_exams_per_day":  "n:int  - a student sits at most n exams per day (default 2)",
    "no_back_to_back":    "hard:bool - no student has exams in consecutive slots of the same day",
    "min_gap_days":       "days:int, hard:bool, exams?:[code] - a student's exams are at least `days` working days apart (only among `exams` if given)",
    "holiday":            "dates:[YYYY-MM-DD] - no exams on these dates",
    "day_slots":          "date:YYYY-MM-DD, slots:int - this date has only this many slots",
    "fix_exam":           "exam:code, date?:YYYY-MM-DD, slot?:int(1-based within day) - exam must be on this date/slot",
    "forbid_exam":        "exam:code, date?:YYYY-MM-DD, slot?:int - exam must NOT be on this date/slot",
    "same_slot":          "exams:[code] - these exams run at the same time (common paper)",
    "different_day":      "exams:[code] - these exams are all on different days",
    "order":              "first:code, then:code - `first` is held in an earlier slot than `then`",
    "prefer_early":       "exams?:[code], largest?:int, weight?:int - soft: schedule these (or the `largest` N exams) early",
    "prefer_late":        "exams?:[code], weight?:int - soft: schedule these late",
    "prefer_slot":        "exams:[code], slot:int, weight?:int - soft: hold these exams in this slot of the day (1 = morning)",
    "max_exams_per_room": "n:int - at most n different exams share one room in a slot",
    "room_use":           "mode:spread|compact - spread students over all selected rooms, or fill as few rooms as possible",
    "adjacent_when_needed": "(no params) - exams too big to space out may sit side by side instead of failing",
    "room_unavailable":   "room:id, date?:YYYY-MM-DD, slot?:int - room cannot be used then",
    "room_fill":          "max_fraction:float, room?:id - use at most this fraction of a room's seats (all rooms if no room)",
    "seat_spacing":       "directions:[side|front] - same-exam students may not sit next to each other in these directions (default [side])",
    "allow_adjacent":     "exams:[code] - these exams may sit side by side with themselves",
    "exam_rooms":         "exam:code, rooms:[id] - exam may only use these rooms",
    "student_rooms":      "students:[roll], rooms:[id] - these students must sit in these rooms (accessibility etc.)",
    "invigilation":       "per_students:int, min_per_room:int, max_per_day:int - invigilator staffing rule",
}
SOFT_TYPES = {"prefer_early", "prefer_late"}


# ---------------- data ----------------

def load_enrollment(text):
    """CSV with (at least) roll number + subject code columns. Same code across programs = one common paper."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    cols = {h.lower().strip(): h for h in reader.fieldnames or []}
    pick = lambda *keys: next((cols[c] for k in keys for c in cols if k in c), None)
    roll, code = pick("roll"), pick("subject code", "course code", "code")
    sname, stud = pick("subject name", "course name"), pick("student name")
    sem_col, kind_col = pick("semester", "session"), pick("subject type", "course type")
    if not roll or not code:
        raise ValueError(f"Enrollment CSV needs roll-number and subject-code columns; got {reader.fieldnames}")
    exams, students = {}, {}
    for r in reader:
        rn, c = r[roll].strip(), r[code].strip()
        if not rn or not c:
            continue
        e = exams.setdefault(c, {"name": (r.get(sname) or c).strip(), "students": set(), "_sem": Counter(), "_kind": Counter()})
        e["students"].add(rn)
        sem = re.search(r"(\d+)\s*$", (r.get(sem_col) or "").strip()) if sem_col else None
        if sem: e["_sem"][int(sem[1])] += 1
        if kind_col and r.get(kind_col, "").strip(): e["_kind"][r[kind_col].strip()] += 1
        students.setdefault(rn, {"name": (r.get(stud) or "").strip(), "exams": set()})["exams"].add(c)
    for e in exams.values():                              # an exam's semester/type = what most of its students say
        e["semester"] = e.pop("_sem").most_common(1)[0][0] if e["_sem"] else None
        e["kind"] = e.pop("_kind").most_common(1)[0][0] if e["_kind"] else None
    return exams, students


def parse_layout(room):
    """Layout = text grid, one line per row, front row first. 'S' usable seat, 'x' seat left empty,
    '-' widens the seat to its left by one column (benches of different widths), anything else = aisle/gap."""
    seats = []
    for r, line in enumerate(room["layout"].splitlines()):
        n, cur = 0, None
        for c, ch in enumerate(line):
            if ch == "-" and cur is not None:
                cur["end"] = c
                continue
            cur = None
            if ch in "Sx":
                n += 1
                cur = {"row": r, "col": c, "end": c, "label": f"R{r + 1}-{n}"}
                if ch == "S":
                    seats.append(cur)
    return seats


def adjacent_pairs(seats, directions):
    """Side neighbours touch in the same row; front/back neighbours overlap in consecutive rows."""
    rows = defaultdict(list)
    for i, s in enumerate(seats):
        rows[s["row"]].append(i)
    start = {(s["row"], s["col"]): i for i, s in enumerate(seats)}
    pairs = []
    if "side" in directions:
        pairs += [(i, start[(s["row"], s["end"] + 1)]) for i, s in enumerate(seats) if (s["row"], s["end"] + 1) in start]
    if "front" in directions:
        for r, idx in rows.items():
            pairs += [(i, j) for i in idx for j in rows.get(r + 1, [])
                      if seats[i]["col"] <= seats[j]["end"] and seats[j]["col"] <= seats[i]["end"]]
    return pairs


def spaced_capacity(n_seats, pairs):
    # ponytail: greedy independent set; exact on rows (paths), close on grids. Stage-2 cuts catch the gap.
    taken, banned = 0, set()
    nbr = defaultdict(set)
    for a, b in pairs:
        nbr[a].add(b); nbr[b].add(a)
    for i in range(n_seats):
        if i not in banned:
            taken += 1; banned |= nbr[i]
    return taken


def build_slots(cal, cons):
    holidays = set(cal.get("holidays", []))
    overrides = {}
    for c in cons:
        if c["type"] == "holiday":
            holidays |= set(c["params"].get("dates", []))
        if c["type"] == "day_slots":
            overrides[c["params"]["date"]] = int(c["params"]["slots"])
    times = cal.get("slot_times") or []
    per_day = int(cal.get("slots_per_day", 2))
    excl = set(cal.get("exclude_weekdays", [5, 6]))
    d, end, slots, day = dt.date.fromisoformat(cal["start"]), dt.date.fromisoformat(cal["end"]), [], 0
    while d <= end:
        iso = d.isoformat()
        n = overrides.get(iso, per_day)
        if d.weekday() not in excl and iso not in holidays and n > 0:
            for i in range(n):
                slots.append({"id": len(slots), "date": iso, "day": day, "slot": i + 1,
                              "time": times[i] if i < len(times) else f"Slot {i + 1}"})
            day += 1
        d += dt.timedelta(days=1)
    return slots


def check_constraints(cons, exams, rooms):
    """Reject anything the solver can't honour, loudly. Returns (usable constraints, problems)."""
    ok, problems, room_ids = [], [], {r["id"] for r in rooms}
    for c in cons:
        t, p = c.get("type"), c.get("params", {})
        if t not in VOCAB:
            problems.append(f"[{c.get('id')}] not supported: {c.get('text') or t} ({p.get('reason', 'no matching rule type')})")
            continue
        codes = p.get("exams", []) + [p[k] for k in ("exam", "first", "then") if k in p]
        rms = p.get("rooms", []) + ([p["room"]] if "room" in p else [])
        bad = [x for x in codes if x not in exams] + [x for x in rms if x not in room_ids]
        if bad:
            problems.append(f"[{c.get('id')}] unknown exam/room {bad}: {c.get('text', '')}")
            continue
        ok.append(c)
    return ok, problems


# ---------------- stage 1: timetable ----------------

EMPTY_SEAT_WEIGHT = 3      # per seat left empty only because a paper sits alone in its session


def solve_timetable(exams, students, slots, rooms, cons, cuts=(), time_limit=60, diagnose=False):
    m = cp_model.CpModel()
    E, T = sorted(exams), range(len(slots))
    size = {e: len(exams[e]["students"]) for e in E}
    x = {(e, t): m.NewBoolVar(f"{e}@{t}") for e in E for t in T}
    for e in E:
        m.AddExactlyOne(x[e, t] for t in T)

    days = defaultdict(list)
    for t in T:
        days[slots[t]["day"]].append(t)
    on_day = lambda e, d: sum(x[e, t] for t in days[d])
    groups = Counter(frozenset(s["exams"]) for s in students.values() if len(s["exams"]) > 1)
    for g in groups:                                   # core rule: one exam per student per slot
        for t in T:
            m.AddAtMostOne(x[e, t] for e in g)

    lits, obj = {}, []
    def lit(c):                                        # one switch per user rule -> lets us name conflicts
        lits[c["id"]] = m.NewBoolVar(c["id"])
        return lits[c["id"]]

    by_type = defaultdict(list)
    for c in cons:
        by_type[c["type"]].append(c)
    day_limits = [(int(c["params"]["n"]), lit(c)) for c in by_type["max_exams_per_day"]] or [(2, None)]

    for g, n in groups.items():
        for d in days:
            s = sum(on_day(e, d) for e in g)
            for k, l in day_limits:
                if len(g) > k:
                    (m.Add(s <= k).OnlyEnforceIf(l) if l is not None else m.Add(s <= k))
            over = m.NewIntVar(0, len(g), "")          # soft: spread a student's exams out
            m.Add(over >= s - 1)
            obj.append(5 * n * over)

    for c in by_type["no_back_to_back"]:
        hard, l = c["params"].get("hard", True), lit(c)
        for g, n in groups.items():
            for d, ts in days.items():
                for t1, t2 in zip(ts, ts[1:]):
                    s = sum(x[e, t1] + x[e, t2] for e in g)
                    if hard:
                        m.Add(s <= 1).OnlyEnforceIf(l)
                    else:
                        v = m.NewBoolVar(""); m.Add(s <= 1 + v); obj.append(5 * n * v)

    for c in by_type["min_gap_days"]:
        k, hard, l = int(c["params"]["days"]), c["params"].get("hard", True), lit(c)
        only = set(c["params"].get("exams") or E)
        dlist = sorted(days)
        for g, n in groups.items():
            gg = [e for e in g if e in only]
            if len(gg) < 2:
                continue
            for i in range(len(dlist)):
                s = sum(on_day(e, d) for e in gg for d in dlist[i:i + k])
                if hard:
                    m.Add(s <= 1).OnlyEnforceIf(l)
                else:
                    v = m.NewIntVar(0, len(gg), ""); m.Add(s <= 1 + v); obj.append(5 * n * v)

    match = lambda p, t: (not p.get("date") or slots[t]["date"] == p["date"]) and (not p.get("slot") or slots[t]["slot"] == int(p["slot"]))
    for c in by_type["fix_exam"]:
        m.Add(sum(x[c["params"]["exam"], t] for t in T if match(c["params"], t)) == 1).OnlyEnforceIf(lit(c))
    for c in by_type["forbid_exam"]:
        m.Add(sum(x[c["params"]["exam"], t] for t in T if match(c["params"], t)) == 0).OnlyEnforceIf(lit(c))
    for c in by_type["same_slot"]:
        l, ex = lit(c), c["params"]["exams"]
        for a, b in zip(ex, ex[1:]):
            for t in T:
                m.Add(x[a, t] == x[b, t]).OnlyEnforceIf(l)
    for c in by_type["different_day"]:
        l = lit(c)
        for d in days:
            m.Add(sum(on_day(e, d) for e in c["params"]["exams"]) <= 1).OnlyEnforceIf(l)
    pos = lambda e: sum(t * x[e, t] for t in T)
    for c in by_type["order"]:
        m.Add(pos(c["params"]["first"]) < pos(c["params"]["then"])).OnlyEnforceIf(lit(c))
    for c in by_type["prefer_early"] + by_type["prefer_late"]:
        p, w = c["params"], int(c["params"].get("weight", 1))
        ex = p.get("exams") or sorted(E, key=size.get, reverse=True)[:int(p.get("largest", 5))]
        for e in ex:
            obj.append(w * size[e] * (pos(e) if c["type"] == "prefer_early" else len(slots) - 1 - pos(e)))

    for c in by_type["prefer_slot"]:
        w, sl = int(c["params"].get("weight", 1)), int(c["params"]["slot"])
        for e in c["params"]["exams"]:
            obj.append(w * size[e] * sum(x[e, t] for t in T if slots[t]["slot"] != sl))

    # capacity, using the same room model stage 2 uses
    caps = room_capacity(rooms, slots, cons)
    allow_adj = {e for c in by_type["allow_adjacent"] for e in c["params"]["exams"]}
    exam_rooms = {c["params"]["exam"]: set(c["params"]["rooms"]) for c in by_type["exam_rooms"]}
    for t in T:
        m.Add(sum(size[e] * x[e, t] for e in E) <= sum(r["usable"] for r in caps[t].values()))
        for e in E:
            rs = [r for rid, r in caps[t].items() if e not in exam_rooms or rid in exam_rooms[e]]
            if size[e] > sum(r["usable" if e in allow_adj else "spaced"] for r in rs):
                m.Add(x[e, t] == 0)
        for S in cuts:
            m.Add(sum(x[e, t] for e in S) <= len(S) - 1)

    # Rooms filled completely. Same-exam students may not sit side by side, so an exam alone in a session
    # needs about usable/spaced times its size in seats, and the gaps stay empty unless other exams in the
    # same session fill them (the office's plans mix papers in every room). Penalise those empty seats so big
    # exams share sessions with other papers instead of sitting alone in half-empty rooms.
    for t in T:
        u, sp = sum(r["usable"] for r in caps[t].values()), sum(r["spaced"] for r in caps[t].values())
        if not sp or u <= sp:
            continue
        load = sum(size[e] * x[e, t] for e in E)
        empty = m.NewIntVar(0, u, f"empty{t}")
        for e in E:
            if e not in allow_adj and size[e] * u > 2 * sp * 10:   # skip tiny papers; they never force rooms open
                m.Add(empty >= (size[e] * u) // sp - load).OnlyEnforceIf(x[e, t])
        obj.append(EMPTY_SEAT_WEIGHT * empty)

    if diagnose:
        m.AddAssumptions(list(lits.values()))
    else:
        for l in lits.values():
            m.Add(l == 1)
    # use the whole period: no student-day doubling (above), fewer exams on consecutive days per student,
    # and the busiest day as light as possible, so exams spread from the first selected day to the last
    dl = sorted(days)
    for g, n in groups.items():
        for d1, d2 in zip(dl, dl[1:]):
            c = m.NewBoolVar("")
            m.Add(sum(on_day(e, d1) + on_day(e, d2) for e in g) <= 1 + len(g) * c)
            obj.append(n * c)
    for d in {dl[0], dl[-1]}:                            # the period starts on the first selected day and ends on the last
        used_d = m.NewBoolVar("")
        m.Add(sum(on_day(e, d) for e in E) >= 1).OnlyEnforceIf(used_d)
        obj.append(sum(size.values()) * used_d.Not())
    busiest = m.NewIntVar(0, sum(size.values()), "busiest")
    for d in dl:
        m.Add(sum(size[e] * on_day(e, d) for e in E) <= busiest)
    obj.append(busiest)
    m.Minimize(sum(obj))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 1 if diagnose else 8
    status = solver.Solve(m)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {e: next(t for t in T if solver.Value(x[e, t])) for e in E}, solver.StatusName(status)
    if status == cp_model.INFEASIBLE and diagnose:
        core = solver.SufficientAssumptionsForInfeasibility()
        names = {l.Index(): k for k, l in lits.items()}
        return None, [names[i] for i in core if i in names]
    return None, solver.StatusName(status)


SWITCHED = {"no_back_to_back", "min_gap_days", "fix_exam", "forbid_exam", "same_slot", "different_day", "order", "max_exams_per_day"}


def minimal_core(core, exams, students, slots, rooms, cons, cuts):
    """Drop rules from the conflict one at a time while it stays impossible, so admins only see the rules that matter."""
    for k in list(core):
        trial = [x for x in core if x != k]
        sub = [c for c in cons if c["type"] not in SWITCHED or c["id"] in trial]
        _, status = solve_timetable(exams, students, slots, rooms, sub, cuts, time_limit=10)
        if status == "INFEASIBLE":
            core = trial
    return core


def room_capacity(rooms, slots, cons):
    """Per slot: {room_id: {seats, pairs, usable, spaced}} after unavailability, fill limits, spacing rule."""
    dirs = next((c["params"]["directions"] for c in cons if c["type"] == "seat_spacing"), ["side"])
    fill_all = min([c["params"]["max_fraction"] for c in cons if c["type"] == "room_fill" and not c["params"].get("room")] or [1.0])
    fill = {c["params"]["room"]: c["params"]["max_fraction"] for c in cons if c["type"] == "room_fill" and c["params"].get("room")}
    base = {}
    for r in rooms:
        seats = parse_layout(r)
        pairs = adjacent_pairs(seats, dirs)
        usable = math.floor(len(seats) * min(fill_all, fill.get(r["id"], 1.0)))
        base[r["id"]] = {"seats": seats, "pairs": pairs, "usable": usable,
                         "spaced": min(usable, spaced_capacity(len(seats), pairs))}
    out = []
    for s in slots:
        blocked = {c["params"]["room"] for c in cons if c["type"] == "room_unavailable"
                   and (not c["params"].get("date") or c["params"]["date"] == s["date"])
                   and (not c["params"].get("slot") or int(c["params"]["slot"]) == s["slot"])}
        out.append({k: v for k, v in base.items() if k not in blocked})
    return out


# ---------------- stage 2: seating ----------------

def student_room_rules(cons):
    """roll -> rooms allowed by *every* student_rooms rule naming that student (empty set = contradiction)."""
    allowed = {}
    for c in cons:
        if c["type"] == "student_rooms":
            for r in c["params"]["students"]:
                allowed[r] = allowed.get(r, set(c["params"]["rooms"])) & set(c["params"]["rooms"])
    return allowed


def seat_slot(codes, exams, caps, cons, time_limit=6, workers=8):
    """Returns {room_id: [(seat_idx, roll, exam)]} or None if this exam mix can't be seated.
    Two small problems instead of one big one: (1) how many students of each exam go in each room,
    (2) which seats they take inside each room. Falls back to the all-at-once model if (2) can't follow (1)."""
    alloc = allocate_rooms(codes, exams, caps, cons, workers)
    if alloc is not None:
        allow_adj = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
        placed = {}
        for rid, counts in alloc.items():
            placed[rid] = place_in_room(caps[rid], counts, allow_adj)
            if placed[rid] is None:
                break
        else:
            out = assign_rolls(placed, codes, exams, caps, cons)
            if out is not None:
                return out
    return _seat_joint(codes, exams, caps, cons, time_limit, workers)


def allocate_rooms(codes, exams, caps, cons, workers=8):
    """{room: {exam: how many}}. Both modes use the fewest rooms; compact fills them one after another, spread evenly."""
    m = cp_model.CpModel()
    allow_adj = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
    exam_rooms = {c["params"]["exam"]: set(c["params"]["rooms"]) for c in cons if c["type"] == "exam_rooms"}
    mix = min([int(c["params"]["n"]) for c in cons if c["type"] == "max_exams_per_room"] or [len(codes)])
    mode = next((c["params"].get("mode") for c in cons if c["type"] == "room_use"), "compact")
    size = {e: len(exams[e]["students"]) for e in codes}
    order = sorted(caps, key=lambda r: (-caps[r]["usable"], r))      # fill the biggest rooms first
    n, b, y, load = {}, {}, {}, {}
    for rid in order:
        r = caps[rid]
        y[rid] = m.NewBoolVar(rid)
        for e in codes:
            if e in exam_rooms and rid not in exam_rooms[e]:
                continue
            top = min(size[e], r["usable"] if e in allow_adj else r["spaced"])
            n[rid, e] = m.NewIntVar(0, top, ""); b[rid, e] = m.NewBoolVar("")
            m.Add(n[rid, e] <= top * b[rid, e]); m.Add(n[rid, e] >= b[rid, e]); m.AddImplication(b[rid, e], y[rid])
        load[rid] = sum(v for (q, _), v in n.items() if q == rid)
        m.Add(load[rid] <= r["usable"] * y[rid])
        m.Add(sum(v for (q, _), v in b.items() if q == rid) <= mix)
    for e in codes:
        m.Add(sum(v for (_, q), v in n.items() if q == e) == size[e])
    groups = defaultdict(int)                                # pinned students need seats in their rooms
    for roll, rms in student_room_rules(cons).items():
        for e in codes:
            if roll in exams[e]["students"]:
                groups[e, frozenset(rms)] += 1
    for (e, rms), k in groups.items():
        m.Add(sum(v for (q, f), v in n.items() if f == e and q in rms) >= k)
    splits = sum(b.values())
    # Both modes open the FEWEST rooms first (never a handful of students in every selected room).
    # spread: then share students evenly over those rooms; compact: fill them one after another.
    if mode == "spread":
        fill = m.NewIntVar(0, 100, "fill")
        for rid in order:
            if caps[rid]["usable"]:
                m.Add(100 * load[rid] <= fill * caps[rid]["usable"])
        m.Minimize(1_000_000 * sum(y.values()) + 1000 * fill + splits)
    else:                                                    # empty seats only in the last room opened
        slack = sum((len(order) - k) * (caps[rid]["usable"] * y[rid] - load[rid]) for k, rid in enumerate(order))
        m.Minimize(1_000_000 * sum(y.values()) + 20 * splits + slack)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_workers = workers
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    out = defaultdict(dict)
    for (rid, e), v in n.items():
        if solver.Value(v):
            out[rid][e] = solver.Value(v)
    return dict(out)


def place_in_room(room, counts, allow_adj):
    """Seats for given counts in one room: same exam never adjacent (unless allowed), front rows first."""
    m = cp_model.CpModel()
    seats = room["seats"]
    z = {(i, e): m.NewBoolVar("") for i in range(len(seats)) for e in counts}
    for i in range(len(seats)):
        m.AddAtMostOne(z[i, e] for e in counts)
    for e, k in counts.items():
        m.Add(sum(z[i, e] for i in range(len(seats))) == k)
        if e not in allow_adj:
            for a, c in room["pairs"]:
                m.AddBoolOr([z[a, e].Not(), z[c, e].Not()])
    m.Minimize(sum(seats[i]["row"] * v for (i, e), v in z.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.num_workers = 1
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [(i, e) for (i, e), v in z.items() if solver.Value(v)]


def assign_rolls(placed, codes, exams, caps, cons):
    """Students onto the placed seats: pinned students in their rooms first, everyone else in roll-number order,
    room by room and front to back, so each room gets a continuous roll range like the office's plans."""
    allowed = student_room_rules(cons)
    key = lambda rid, i: (rid, caps[rid]["seats"][i]["row"], caps[rid]["seats"][i]["col"])
    out = defaultdict(list)
    for e in codes:
        free = sorted(((rid, i) for rid, ps in placed.items() for i, q in ps if q == e), key=lambda t: key(*t))
        for roll in sorted(exams[e]["students"] & set(allowed)):
            k = next((k for k, (rid, _) in enumerate(free) if rid in allowed[roll]), None)
            if k is None:
                return None
            rid, i = free.pop(k); out[rid].append((i, roll, e))
        rest = sorted(r for r in exams[e]["students"] if r not in allowed)
        if len(rest) != len(free):
            return None
        for (rid, i), roll in zip(free, rest):
            out[rid].append((i, roll, e))
    return out


def _seat_joint(codes, exams, caps, cons, time_limit=6, workers=8):
    """All rooms and seats in one model (slower; used when the two-step method can't lay a room out)."""
    m = cp_model.CpModel()
    allow_adj = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
    exam_rooms = {c["params"]["exam"]: set(c["params"]["rooms"]) for c in cons if c["type"] == "exam_rooms"}
    allowed = student_room_rules(cons)
    mix = min([int(c["params"]["n"]) for c in cons if c["type"] == "max_exams_per_room"] or [len(codes)])
    z, used, cost, front = {}, [], [], []
    by_room, by_exam, by_seat, room_used = defaultdict(list), defaultdict(list), defaultdict(list), {}
    for rid, r in caps.items():
        y = m.NewBoolVar(rid); used.append(y); in_room = []; room_used[rid] = y
        for e in codes:
            if e in exam_rooms and rid not in exam_rooms[e]:
                continue
            w = m.NewBoolVar("")                          # exam e uses room rid
            for i in range(len(r["seats"])):
                z[rid, i, e] = v = m.NewBoolVar("")
                m.AddImplication(v, w)
                front.append(r["seats"][i]["row"] * v)
                by_room[rid].append(v); by_exam[e].append(v); by_seat[rid, i].append(v)
            m.AddImplication(w, y); cost.append(w); in_room.append(w)
            if e not in allow_adj:
                for a, b in r["pairs"]:
                    m.AddBoolOr([z[rid, a, e].Not(), z[rid, b, e].Not()])
        m.Add(sum(in_room) <= mix)
        m.Add(sum(by_room[rid]) <= r["usable"])
    for vs in by_seat.values():
        m.AddAtMostOne(vs)
    for e in codes:
        m.Add(sum(by_exam[e]) == len(exams[e]["students"]))
    # pinned students: an explicit seat each, inside rooms every rule allows (few students, so exact is cheap)
    pin = {}
    for e in codes:
        for roll in sorted(exams[e]["students"] & set(allowed)):
            opts = [(rid, i) for (rid, i, q) in z if q == e and rid in allowed[roll]]
            if not opts:
                return None
            vs = []
            for rid, i in opts:
                pin[roll, e, rid, i] = v = m.NewBoolVar("")
                m.AddImplication(v, z[rid, i, e]); vs.append(v)
            m.AddExactlyOne(vs)
    seat_pins = defaultdict(list)
    for (roll, e, rid, i), v in pin.items():
        seat_pins[rid, i].append(v)
    for vs in seat_pins.values():
        m.AddAtMostOne(vs)
    mode = next((c["params"].get("mode") for c in cons if c["type"] == "room_use"), "compact")   # default: fill rooms completely
    if mode == "spread":                                  # fewest rooms first, then the lowest max fill % among them
        fill = m.NewIntVar(0, 100, "fill")
        for rid, r in caps.items():
            if r["usable"]:
                m.Add(100 * sum(by_room[rid]) <= fill * r["usable"])
        main = 1_000_000 * sum(used) + 1000 * fill + sum(cost)
    else:
        main = 1000 * sum(used) + sum(cost)             # fewer rooms (invigilators) always beats fewer paper splits
    m.Minimize(100000 * main + sum(front))               # then fill rooms from the front row backwards
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    status = solver.Solve(m)
    if status == cp_model.UNKNOWN:                       # ran out of time without any seating: try harder before giving up
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    out = defaultdict(list)
    for e in codes:
        taken = {(rid, i) for (roll, q, rid, i), v in pin.items() if q == e and solver.Value(v)}
        for (roll, q, rid, i), v in pin.items():
            if q == e and solver.Value(v):
                out[rid].append((i, roll, e))
        seats = sorted((rid, i) for (rid, i, q), v in z.items() if q == e and solver.Value(v) and (rid, i) not in taken)
        rest = sorted(r for r in exams[e]["students"] if r not in allowed)
        for (rid, i), roll in zip(seats, rest):           # everyone else in roll-number order, like the office does
            out[rid].append((i, roll, e))
    return out


def seat_all(by_slot, exams, caps, cons):
    """Slots are independent; CP-SAT releases the GIL while solving, so threads run them truly in parallel."""
    import os
    from concurrent.futures import ThreadPoolExecutor
    threads = max(1, (os.cpu_count() or 2) // 2)
    job = lambda t: (t, seat_slot(by_slot[t], exams, caps[t], cons, workers=2))
    with ThreadPoolExecutor(threads) as pool:
        return list(pool.map(job, list(by_slot)))


def rooms_needed(sizes, cap, allow_adj):
    """Lower bound on rooms for one session: enough seats for everyone, and enough spaced seats for each exam."""
    def k(n, key):
        got = 0
        for i, v in enumerate(sorted((r[key] for r in cap.values()), reverse=True)):
            if got >= n:
                return i
            got += v
        return len(cap) if got >= n else len(cap) + 1
    return max([k(sum(sizes.values()), "usable")] + [k(n, "spaced") for e, n in sizes.items() if e not in allow_adj])


def extra_rooms(result, caps, cons):
    """Sessions that opened more rooms than their students need, when no rule restricts which rooms may be used.
    This is the 'rooms left mostly empty' mistake; it must stay empty (tests assert it)."""
    if any(c["type"] in ("exam_rooms", "student_rooms", "max_exams_per_room") for c in cons):
        return []
    allow = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
    out = []
    for s in result["slots"]:
        rs = result["seating"].get(str(s["id"]), {})
        if rs:
            need = rooms_needed(Counter(x["exam"] for v in rs.values() for x in v), caps[s["id"]], allow)
            if len(rs) > need + 1:                       # +1: spacing inside mixed rooms can cost one room
                out.append(f"{s['date']} {s['time']}: {len(rs)} rooms used, about {need} would hold everyone")
    return out


def room_checks(result, caps, cons):
    """Plain-language findings about room use, shown with every plan."""
    dirs = next((c["params"].get("directions") for c in cons if c["type"] == "seat_spacing"), ["side"])
    allow = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
    tight, single, low, other = [], [], [], []
    for s in result["slots"]:
        rs = result["seating"].get(str(s["id"]), {})
        if not rs:
            continue
        cap = caps[s["id"]]
        n, seats = sum(len(v) for v in rs.values()), sum(r["usable"] for r in cap.values())
        when = f"{s['date']} {s['time']}"
        if seats and n > 0.9 * seats:
            tight.append(f"{when}: {n} students for {seats} seats in the selected rooms ({round(100 * n / seats)}%)")
        part = [(rid, len(v), cap[rid]["usable"], {x["exam"] for x in v}) for rid, v in rs.items() if len(v) < 0.9 * cap[rid]["usable"]]
        spaced = [p for p in part if len(p[3]) == 1 and dirs and not p[3] & allow and p[1] >= 0.8 * cap[p[0]]["spaced"]]
        if spaced:
            single.append(f"{when}: {', '.join(f'{rid} ({k}/{t}, {next(iter(ex))})' for rid, k, t, ex in spaced)}")
        rest = [p for p in part if p not in spaced]
        if len(rest) == 1 and rest[0][1] < 0.5 * rest[0][2]:
            rid, k, t, _ = rest[0]
            low.append(f"{when}, {rid}: {k} of {t} seats (the last room opened for this session)")
        elif len(rest) > 1:
            other.append(f"{when}: {', '.join(f'{rid} ({k}/{t})' for rid, k, t, _ in rest)}")
    out = []
    extra = extra_rooms(result, caps, cons)
    if extra:
        out.append({"level": "warn", "title": "Sessions using more rooms than needed (rooms left mostly empty)", "items": extra})
    if tight:
        out.append({"level": "warn", "title": "Sessions using almost every selected seat (little spare room)", "items": tight})
    if single:
        out.append({"level": "info", "title": "Rooms not completely full because everyone in them writes the same paper. Same-paper students "
                    "may not sit side by side, so some seats stay empty. To fill them, add a rule letting that exam sit side by side, "
                    "or untick “Keep students of the same exam apart”", "items": single})
    spread = next((c["params"].get("mode") for c in cons if c["type"] == "room_use"), "compact") == "spread"
    if other and not spread:                             # spread mode shares students evenly on purpose
        out.append({"level": "warn", "title": "Sessions with more than one partly-filled room (rules such as room limits or pinned students forced this)", "items": other})
    if low:
        out.append({"level": "info", "title": "Last room of the session less than half full", "items": low})
    return out


def assign_invigilators(seating, slots, invigilators, cons):
    rule = next((c["params"] for c in cons if c["type"] == "invigilation"), {})
    per, low, per_day = int(rule.get("per_students", 30)), int(rule.get("min_per_room", 1)), int(rule.get("max_per_day", 2))
    if not invigilators:
        return {}, ["No invigilator list uploaded, so no invigilation duties were assigned."]
    load, day_load, out, warn = Counter(), Counter(), {}, []
    for s in slots:
        busy = set()
        for rid, seats in seating.get(s["id"], {}).items():
            need, got = max(low, math.ceil(len(seats) / per)), []
            # ponytail: greedy least-loaded; swap for a CP model if fairness complaints come in
            for p in sorted(invigilators, key=lambda p: load[p["name"]]):
                if len(got) == need:
                    break
                if p["name"] in busy or s["date"] in p["unavailable"] or day_load[p["name"], s["date"]] >= per_day:
                    continue
                got.append(p["name"]); busy.add(p["name"]); load[p["name"]] += 1; day_load[p["name"], s["date"]] += 1
            if len(got) < need:
                warn.append(f"{s['date']} slot {s['slot']} room {rid}: needs {need} invigilators, only {len(got)} available")
            out[f"{s['id']}|{rid}"] = got
    return out, warn


def load_invigilators(text):
    if not text.strip():
        return []
    rows = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    return [{"name": r.get("name", "").strip(), "unavailable": {d.strip() for d in (r.get("unavailable") or "").split(";") if d.strip()}}
            for r in rows if r.get("name", "").strip()]


# ---------------- independent check ----------------

def validate(result, exams, students, rooms, cons):
    errs = []
    slot_of = {e: s["id"] for s in result["slots"] for e in s["exams"]}
    day_of = {s["id"]: s["date"] for s in result["slots"]}
    max_day = min([int(c["params"]["n"]) for c in cons if c["type"] == "max_exams_per_day"] or [2])
    missing = set(exams) - set(slot_of)
    if missing:
        errs.append(f"exams never scheduled: {sorted(missing)}")
    for roll, st in students.items():
        ss = [slot_of[e] for e in st["exams"] if e in slot_of]
        if len(ss) != len(set(ss)):
            errs.append(f"{roll} has two exams in one slot")
        if max(Counter(day_of[s] for s in ss).values(), default=0) > max_day:
            errs.append(f"{roll} has more than {max_day} exams on one day")
    caps = room_capacity(rooms, result["slots"], cons)
    allow_adj = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
    for s in result["slots"]:
        seated = Counter()
        for rid, seats in result["seating"].get(str(s["id"]), {}).items():
            if rid not in caps[s["id"]]:
                errs.append(f"slot {s['id']} uses unavailable room {rid}"); continue
            r = caps[s["id"]][rid]
            at = {x["seat"]: x["exam"] for x in seats}
            if len(at) != len(seats):
                errs.append(f"slot {s['id']} {rid}: two students on one seat")
            if len({x["exam"] for x in seats}) > min([int(c["params"]["n"]) for c in cons if c["type"] == "max_exams_per_room"] or [99]):
                errs.append(f"slot {s['id']} {rid}: too many different exams in one room")
            if len(seats) > r["usable"]:
                errs.append(f"slot {s['id']} {rid}: over fill limit")
            for a, b in r["pairs"]:
                if a in at and at.get(b) == at[a] and at[a] not in allow_adj:
                    errs.append(f"slot {s['id']} {rid}: {at[a]} students adjacent")
            seated.update((x["roll"], x["exam"]) for x in seats)
        for e in s["exams"]:
            for roll in exams[e]["students"]:
                if seated[roll, e] != 1:
                    errs.append(f"{roll} not seated exactly once for {e}")
    return errs + validate_rules(result, exams, students, cons)


def validate_rules(result, exams, students, cons):
    """Every hard user rule, re-checked on the final output (not on the solver model)."""
    errs, S = [], {s["id"]: s for s in result["slots"]}
    at = {e: S[s["id"]] for s in result["slots"] for e in s["exams"]}
    match = lambda p, s: (not p.get("date") or s["date"] == p["date"]) and (not p.get("slot") or s["slot"] == int(p["slot"]))
    where = defaultdict(dict)                                   # roll -> exam -> room
    for sid, rs in result["seating"].items():
        for rid, seats in rs.items():
            for x in seats:
                where[x["roll"]][x["exam"]] = rid
    for c in cons:
        t, p, tag = c["type"], c["params"], f"[{c.get('id')}] {c.get('text') or c['type']}"
        if t == "fix_exam" and not match(p, at[p["exam"]]):
            errs.append(f"{tag}: {p['exam']} is at {at[p['exam']]['date']} slot {at[p['exam']]['slot']}")
        elif t == "forbid_exam" and match(p, at[p["exam"]]):
            errs.append(f"{tag}: {p['exam']} landed on a forbidden slot")
        elif t == "same_slot" and len({at[e]["id"] for e in p["exams"]}) > 1:
            errs.append(f"{tag}: not in one slot")
        elif t == "different_day" and len({at[e]["date"] for e in p["exams"]}) < len(p["exams"]):
            errs.append(f"{tag}: two of them share a day")
        elif t == "order" and not at[p["first"]]["id"] < at[p["then"]]["id"]:
            errs.append(f"{tag}: order broken")
        elif t == "holiday":
            errs += [f"{tag}: exam on {d}" for d in p["dates"] if any(s["date"] == d and s["exams"] for s in S.values())]
        elif t == "day_slots" and sum(1 for s in S.values() if s["date"] == p["date"]) > int(p["slots"]):
            errs.append(f"{tag}: too many slots on {p['date']}")
        elif t == "exam_rooms":
            bad = {where[r].get(p["exam"]) for r in exams[p["exam"]]["students"]} - set(p["rooms"])
            if bad:
                errs.append(f"{tag}: also seated in {sorted(bad)}")
        elif t == "student_rooms":
            errs += [f"{tag}: {r} sat in {rid} for {e}" for r in p["students"] for e, rid in where.get(r, {}).items() if rid not in p["rooms"]]
        elif t in ("no_back_to_back", "min_gap_days") and p.get("hard", True):
            only = set(p.get("exams") or exams)
            for roll, st in students.items():
                ss = sorted((at[e]["day"], at[e]["slot"]) for e in st["exams"] if e in only)
                for (d1, s1), (d2, s2) in zip(ss, ss[1:]):
                    if t == "no_back_to_back" and d1 == d2 and s2 == s1 + 1:
                        errs.append(f"{tag}: {roll} back to back"); break
                    if t == "min_gap_days" and d2 - d1 < int(p["days"]):
                        errs.append(f"{tag}: {roll} exams {d2 - d1} days apart"); break
    return errs


# ---------------- orchestration ----------------

def run(enrollment_text, rooms, constraints, calendar, invigilators_text="", time_limit=60, log=print, profile=None):
    exams, students = load_enrollment(enrollment_text)
    learned = []
    if profile:                                          # habits learned from past exams (history.py)
        import history
        learned = history.profile_constraints(profile, exams, calendar.get("start"))
        constraints = constraints + learned
    for i, c in enumerate(constraints):
        c.setdefault("id", f"c{i + 1}")
    cons, problems = check_constraints(constraints, exams, rooms)
    slots = build_slots(calendar, cons)
    if not slots:
        return {"ok": False, "errors": ["calendar has no exam slots"], "problems": problems}

    caps = room_capacity(rooms, slots, cons)
    allow_adj = {e for c in cons if c["type"] == "allow_adjacent" for e in c["params"]["exams"]}
    best_u = max(sum(r["usable"] for r in c.values()) for c in caps)
    best_s = max(sum(r["spaced"] for r in c.values()) for c in caps)
    if any(c["type"] == "adjacent_when_needed" for c in cons):
        big = sorted(e for e, ex in exams.items() if best_s < len(ex["students"]) <= best_u and e not in allow_adj)
        if big:
            cons.append({"id": "learned-adjacent-exams", "type": "allow_adjacent", "params": {"exams": big},
                         "text": f"learned: {', '.join(big)} too big to space out, seated side by side like past plans"})
            allow_adj |= set(big)
            learned.append(cons[-1])
    errors = []
    for e, ex in exams.items():                          # plain-language pre-checks before the solver
        n = len(ex["students"])
        if n > best_u:
            errors.append(f"{e} ({ex['name']}) has {n} students but the most seats in any slot is {best_u}. Add rooms or raise fill limits.")
        elif n > best_s and e not in allow_adj:
            errors.append(f"{e} ({ex['name']}) has {n} students but only {best_s} seats keep same-exam students apart. "
                          f"Add rooms, or add a rule like \"{e} students may sit side by side\".")
    for roll, rms in student_room_rules(cons).items():
        if not rms:
            errors.append(f"student {roll} has room rules that contradict each other (no room satisfies all of them)")
    worst = max((len(s["exams"]) for s in students.values()), default=0)
    if worst > len(slots):
        errors.append(f"a student has {worst} exams but there are only {len(slots)} slots")
    if errors:
        return {"ok": False, "errors": errors, "problems": problems}

    cuts = []
    for rnd in range(8):
        log(f"timetable round {rnd + 1} ({len(cuts)} seating cuts)")
        assign, status = solve_timetable(exams, students, slots, rooms, cons, cuts, time_limit)
        if assign is None:
            if status == "INFEASIBLE":
                _, core = solve_timetable(exams, students, slots, rooms, cons, cuts, time_limit, diagnose=True)
                core = minimal_core(core if isinstance(core, list) else [], exams, students, slots, rooms, cons, cuts)
                names = {c["id"]: c.get("text") or f"{c['type']} {c['params']}" for c in cons}
                if core:
                    msg = ["These rules can't all hold together:"] + [f"  - [{k}] {names[k]}" for k in core]
                else:
                    cal = [names[c["id"]] for c in cons if c["type"] in ("holiday", "day_slots")]
                    msg = [f"No timetable fits in {len(slots)} slots on {len({x['date'] for x in slots})} days with these rooms, even ignoring "
                           "your scheduling rules: students' exam clashes plus room capacity need more slots or seats. Add days, slots or rooms"
                           + (f", or drop some of these calendar rules: {'; '.join(cal)}" if cal else "") + "."]
                return {"ok": False, "errors": msg, "problems": problems}
            return {"ok": False, "errors": [f"solver stopped: {status}. Raise the time limit."], "problems": problems}
        by_slot = defaultdict(list)
        for e, t in assign.items():
            by_slot[t].append(e)
        seating, new_cuts = {}, []
        for t, seated in seat_all(by_slot, exams, caps, cons):
            codes = by_slot[t]
            if seated is None:
                new_cuts.append(frozenset(codes))
            else:
                seating[t] = seated
        if not new_cuts:
            break
        cuts += new_cuts
        # ponytail: cut bans the whole mix in every slot; per-slot cuts if room availability differs a lot by day
    else:
        return {"ok": False, "errors": ["could not find a seatable timetable after 8 rounds"], "problems": problems}

    invig, warn = assign_invigilators(seating, slots, load_invigilators(invigilators_text), cons)
    result = {
        "ok": True, "problems": problems, "warnings": warn, "learned": [c["text"] for c in learned],
        "slots": [dict(s, exams=sorted(by_slot.get(s["id"], []))) for s in slots],
        "exams": {e: {"name": x["name"], "size": len(x["students"])} for e, x in exams.items()},
        "rooms": {r["id"]: {"layout": r["layout"], "building": r.get("building", "")} for r in rooms},
        "seating": {str(t): {rid: [{"seat": i, "label": caps[t][rid]["seats"][i]["label"], "roll": roll,
                                    "name": students[roll]["name"], "exam": e} for i, roll, e in sorted(v)]
                             for rid, v in rs.items()} for t, rs in seating.items()},
        "invigilators": invig,
    }
    result["violations"] = validate(result, exams, students, rooms, cons)
    result["checks"] = room_checks(result, caps, cons)
    guessed = sorted({rid for rs in result["seating"].values() for rid in rs} & {r["id"] for r in rooms if r.get("placeholder")})
    if guessed:
        result["warnings"].insert(0, f"Seated students in rooms whose layout is a placeholder, not the real room: {', '.join(guessed)}. "
                                     "Replace those layouts (Rooms tab) before publishing seat numbers.")
    day_of = {s["id"]: s["date"] for s in slots}
    per_day = Counter()
    for st in students.values():
        per_day[max(Counter(day_of[assign[e]] for e in st["exams"]).values())] += 1
    result["stats"] = {"students": len(students), "exams": len(exams), "slots": len(slots),
                       "days": len({s["date"] for s in slots}), "rounds": rnd + 1,
                       "students_by_max_exams_per_day": dict(sorted(per_day.items()))}
    return result
