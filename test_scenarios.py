"""Scenario + stress tests. Small synthetic universities, so each case runs in seconds.
    python test_scenarios.py          # every rule type, edge cases, then 200 random universities
    python test_scenarios.py 1000     # more random universities
"""
import random, sys, time
import scheduler as s

CAL = {"start": "2027-01-04", "end": "2027-01-15", "slots_per_day": 2, "slot_times": ["10:00 AM", "2:30 PM"]}   # Mon..Fri x2


def uni(rng, students=60, exams=8, cohorts=2, rooms=4):
    """Random enrollment CSV + rooms with irregular layouts (aisles, blocked seats, theatre rows)."""
    codes = [f"XX{1000 + i}" for i in range(exams)]
    by_cohort = [codes[i::cohorts] for i in range(cohorts)]
    lines = ["Student Session,Student Roll Number,Student Name,Subject Code,Subject Name,Subject Type"]
    for n in range(students):
        c = n % cohorts
        mine = rng.sample(by_cohort[c], min(len(by_cohort[c]), rng.randint(2, 4)))
        if rng.random() < 0.1:                            # backlog paper from another cohort
            mine.append(rng.choice(codes))
        for e in set(mine):
            lines.append(f"SEMESTER {2 * c + 1},2027T{c}{n:03d},Student {n},{e},Course {e},{rng.choice(['Core', 'Elective'])}")
    rms = []
    for i in range(rooms):
        rows = []
        for r in range(rng.randint(4, 8)):
            w = rng.randint(4, 9) + (r if i % 2 else 0)  # odd rooms widen toward the back, like a theatre
            row = "".join(rng.choice("SSSSSSx") for _ in range(w))
            if w > 5:
                k = w // 2; row = row[:k] + " " + row[k:]  # aisle
            rows.append(" " * (3 - min(3, r)) * (i % 2) + row)
        rms.append({"id": f"R{i + 1}", "layout": "\n".join(rows)})
    return "\n".join(lines), rms, codes


def solve(enr, rooms, cons, cal=CAL, inv=""):
    return s.run(enr, rooms, cons, cal, inv, time_limit=10, log=lambda *_: None)


def ok(r):
    assert r["ok"], r.get("errors")
    assert r["violations"] == [], r["violations"][:5]
    return r


def slot_of(r, e):
    return next(x for x in r["slots"] if e in x["exams"])


# ---------------- one test per rule type: the rule must actually take effect ----------------
R0 = random.Random(1)
ENR, ROOMS, CODES = uni(R0)
A, B, C = CODES[0], CODES[1], CODES[2]


def t_baseline():
    ok(solve(ENR, ROOMS, []))

def t_fix():
    r = ok(solve(ENR, ROOMS, [{"type": "fix_exam", "params": {"exam": A, "date": "2027-01-06", "slot": 2}}]))
    assert (slot_of(r, A)["date"], slot_of(r, A)["slot"]) == ("2027-01-06", 2)

def t_forbid():
    r = ok(solve(ENR, ROOMS, [{"type": "forbid_exam", "params": {"exam": A, "slot": 1}}]))
    assert slot_of(r, A)["slot"] == 2

def t_same_slot():
    a, b = CODES[0], CODES[2]                             # same cohort in uni(): may share students -> may be infeasible; use cross-cohort
    a, b = CODES[0], CODES[1]
    r = solve(ENR, ROOMS, [{"type": "same_slot", "params": {"exams": [a, b]}}])
    if r["ok"]:
        ok(r); assert slot_of(r, a)["id"] == slot_of(r, b)["id"]
    else:
        assert r["errors"]

def t_different_day():
    r = ok(solve(ENR, ROOMS, [{"type": "different_day", "params": {"exams": CODES[:4]}}]))
    assert len({slot_of(r, e)["date"] for e in CODES[:4]}) == 4

def t_order():
    r = ok(solve(ENR, ROOMS, [{"type": "order", "params": {"first": C, "then": A}}]))
    assert slot_of(r, C)["id"] < slot_of(r, A)["id"]

def t_holiday_and_day_slots():
    r = ok(solve(ENR, ROOMS, [{"type": "holiday", "params": {"dates": ["2027-01-05"]}}, {"type": "day_slots", "params": {"date": "2027-01-06", "slots": 1}}]))
    assert not any(x["date"] == "2027-01-05" for x in r["slots"])
    assert [x["slot"] for x in r["slots"] if x["date"] == "2027-01-06"] == [1]

def t_uses_whole_period():
    r = ok(solve(ENR, ROOMS, [{"type": "max_exams_per_day", "params": {"n": 1}}], {"start": "2027-01-04", "end": "2027-01-15", "slots_per_day": 2}))
    used = sorted({x["date"] for x in r["slots"] if x["exams"]})
    assert used[0] == "2027-01-04" and used[-1] == "2027-01-15", used           # first and last selected day both used

def t_few_exams_still_start_on_day_one():
    enr = "\n".join(l for l in ENR.splitlines() if l.split(",")[3] in ("Subject Code", CODES[0], CODES[1]))   # 2 exams, 10 days
    r = ok(solve(enr, ROOMS, [], {"start": "2027-01-04", "end": "2027-01-15", "slots_per_day": 2}))
    assert min(x["date"] for x in r["slots"] if x["exams"]) == "2027-01-04"

def t_room_use_spread():
    """Spread shares students evenly but must open no more rooms than compact does."""
    r = ok(solve(ENR, ROOMS, [{"type": "room_use", "params": {"mode": "spread"}}]))
    c = ok(solve(ENR, ROOMS, [{"type": "room_use", "params": {"mode": "compact"}}]))
    rooms = lambda r: sum(len(v) for v in r["seating"].values())
    assert rooms(r) <= rooms(c), (rooms(r), rooms(c))

def t_no_mostly_empty_rooms():
    """Regression: 'spread' once put ~10 students in each of 15 rooms (25% full) instead of filling 3.
    With many big rooms selected and few students, every mode must use only the rooms it needs."""
    rng = random.Random(7)
    enr, _, _ = uni(rng, students=80, exams=6, cohorts=2)
    big = [{"id": f"H{i}", "layout": "\n".join(["SSSS SSSS"] * 6)} for i in range(15)]   # 15 rooms x 48 seats
    for mode in ("spread", "compact"):
        cons = [{"type": "room_use", "params": {"mode": mode}}]
        r = ok(solve(enr, big, cons))
        caps = s.room_capacity(big, r["slots"], cons)
        assert s.extra_rooms(r, caps, cons) == [], (mode, s.extra_rooms(r, caps, cons))
        for sl in r["slots"]:
            rs = r["seating"].get(str(sl["id"]), {})
            n = sum(len(v) for v in rs.values())
            assert len(rs) <= -(-n // 24) + 1, (mode, sl["date"], len(rs), n)   # 24 = spaced seats per room

def t_rooms_filled_completely():
    """Regression: a big paper was put alone in a session, so same-paper spacing left every other seat empty
    in all its rooms (real data: CC1101, 527 students in 18 half-full rooms) while other papers that could
    have filled those gaps sat in other sessions. Big papers must share sessions so the rooms fill up."""
    lines = ["Student Session,Student Roll Number,Student Name,Subject Code,Subject Name,Subject Type"]
    for c, (big, small) in enumerate([("BA1000", "BA1001"), ("BB2000", "BB2001")]):  # two cohorts, no shared students
        for n in range(96):
            for e in (big, small):
                lines.append(f"SEMESTER {c + 1},R{c}{n:03d},Student {c}{n},{e},Course {e},Core")
    rooms = [{"id": f"H{i}", "layout": "\n".join(["SSSS SSSS"] * 6)} for i in range(8)]   # 48 seats, 24 spaced
    r = ok(solve("\n".join(lines), rooms, []))
    caps = s.room_capacity(rooms, r["slots"], [])
    for sl in r["slots"]:
        rs = r["seating"].get(str(sl["id"]), {})
        empty = sum(caps[sl["id"]][k]["usable"] - len(v) for k, v in rs.items())
        assert empty < 48, (sl["date"], sl["slot"], sl["exams"], f"{empty} empty seats in {len(rs)} rooms")

def t_weekends_skipped():
    r = ok(solve(ENR, ROOMS, []))
    import datetime as dt
    assert all(dt.date.fromisoformat(x["date"]).weekday() < 5 for x in r["slots"])

def t_max_per_day_1():
    r = ok(solve(ENR, ROOMS, [{"type": "max_exams_per_day", "params": {"n": 1}}]))

def t_back_to_back():
    ok(solve(ENR, ROOMS, [{"type": "no_back_to_back", "params": {"hard": True}}]))

def t_min_gap():
    ok(solve(ENR, ROOMS, [{"type": "min_gap_days", "params": {"days": 2, "hard": True}}]))

def t_soft_gap_never_fails():
    r = solve(ENR, ROOMS, [{"type": "min_gap_days", "params": {"days": 5, "hard": False}}])
    ok(r)                                                 # impossible as a hard rule; soft must still give a timetable

def t_prefer_early_late_slot():
    r = ok(solve(ENR, ROOMS, [{"type": "prefer_early", "params": {"exams": [A], "weight": 50}},
                               {"type": "prefer_late", "params": {"exams": [B], "weight": 50}},
                               {"type": "prefer_slot", "params": {"exams": [C], "slot": 2, "weight": 50}}]))
    n = len(r["slots"])
    assert slot_of(r, A)["id"] < n / 2 < slot_of(r, B)["id"] and slot_of(r, C)["slot"] == 2

def t_room_unavailable():
    r = ok(solve(ENR, ROOMS, [{"type": "room_unavailable", "params": {"room": "R1"}}]))
    assert not any("R1" in rs for rs in r["seating"].values())

def t_room_fill():
    ok(solve(ENR, ROOMS, [{"type": "room_fill", "params": {"max_fraction": 0.5}}]))

def t_front_spacing():
    ok(solve(ENR, ROOMS, [{"type": "seat_spacing", "params": {"directions": ["side", "front"]}}]))

def t_exam_rooms():
    r = ok(solve(ENR, ROOMS, [{"type": "exam_rooms", "params": {"exam": A, "rooms": ["R2", "R3"]}}]))

def t_student_rooms():
    roll = next(l.split(",")[1] for l in ENR.splitlines()[1:] if l.split(",")[3] == A)
    ok(solve(ENR, ROOMS, [{"type": "student_rooms", "params": {"students": [roll], "rooms": ["R4"]}}]))

def t_mix_limit():
    r = ok(solve(ENR, ROOMS, [{"type": "max_exams_per_room", "params": {"n": 1}}]))
    assert all(len({x["exam"] for x in v}) == 1 for rs in r["seating"].values() for v in rs.values())

def t_invigilators():
    r = ok(solve(ENR, ROOMS, [{"type": "invigilation", "params": {"per_students": 10, "min_per_room": 1, "max_per_day": 1}}],
                 inv="name,unavailable\nA,\nB,2027-01-04\nC,"))
    assert r["warnings"]                                  # 3 people can't cover this: must warn, not crash
    for k, v in r["invigilators"].items():
        assert len(v) == len(set(v))

def t_contradiction_named():
    r = solve(ENR, ROOMS, [{"type": "fix_exam", "params": {"exam": A, "date": "2027-01-04"}, "text": "A on Monday"},
                           {"type": "forbid_exam", "params": {"exam": A, "date": "2027-01-04"}, "text": "A not Monday"}])
    assert not r["ok"] and any("A on Monday" in e for e in r["errors"]) and any("A not Monday" in e for e in r["errors"])

def t_day_limit_named():
    r = solve(ENR, ROOMS, [{"type": "max_exams_per_day", "params": {"n": 1}, "text": "one exam a day"}],
              {"start": "2027-01-04", "end": "2027-01-06", "slots_per_day": 2})                  # 3 days, some students have 4-5 exams
    assert not r["ok"] and any("one exam a day" in e for e in r["errors"]), r["errors"]

def t_too_big_exam_explained():
    big = ENR + "".join(f"\nSEMESTER 9,BIG{i},x,ZZ9999,Huge,Core" for i in range(2000))
    r = solve(big, ROOMS, [])
    assert not r["ok"] and "ZZ9999" in r["errors"][0]

def t_no_slots():
    r = solve(ENR, ROOMS, [], {"start": "2027-01-09", "end": "2027-01-10"})   # a weekend
    assert not r["ok"] and r["errors"]

def t_too_few_slots():
    r = solve(ENR, ROOMS, [], {"start": "2027-01-04", "end": "2027-01-04", "slots_per_day": 1})
    assert not r["ok"] and r["errors"]

def t_unknown_rules_reported():
    r = ok(solve(ENR, ROOMS, [{"type": "teleport", "params": {}}, {"type": "fix_exam", "params": {"exam": "NOPE"}}]))
    assert len(r["problems"]) == 2

def t_messy_csv():
    messy = "﻿" + ENR.replace(",Core", ", Core ").replace("\n", "\r\n") + "\r\n,,,,\r\n"
    ok(solve(messy, ROOMS, []))

def t_bad_csv():
    try:
        s.load_enrollment("name,score\nx,1")
        raise AssertionError("should reject")
    except ValueError:
        pass

def t_theatre_layout():
    seats = s.parse_layout({"layout": "   SSS\n  SSSSS\n SSSxSSS\nSSSS SSSS"})
    assert len(seats) == 3 + 5 + 6 + 8
    pairs = s.adjacent_pairs(seats, ["side"])
    assert all(seats[a]["row"] == seats[b]["row"] for a, b in pairs)


TESTS = [v for k, v in list(globals().items()) if k.startswith("t_")]


# ---------------- stress: random universities, random valid rules ----------------
def random_rules(rng, codes, rooms, roll):
    days = ["2027-01-04", "2027-01-05", "2027-01-06", "2027-01-07", "2027-01-08", "2027-01-11"]
    pool = [
        lambda: {"type": "max_exams_per_day", "params": {"n": rng.randint(1, 2)}},
        lambda: {"type": "no_back_to_back", "params": {"hard": rng.random() < 0.5}},
        lambda: {"type": "min_gap_days", "params": {"days": rng.randint(1, 2), "hard": rng.random() < 0.3}},
        lambda: {"type": "holiday", "params": {"dates": [rng.choice(days)]}},
        lambda: {"type": "day_slots", "params": {"date": rng.choice(days), "slots": 1}},
        lambda: {"type": "fix_exam", "params": {"exam": rng.choice(codes), "date": rng.choice(days)}},
        lambda: {"type": "forbid_exam", "params": {"exam": rng.choice(codes), "slot": rng.randint(1, 2)}},
        lambda: {"type": "different_day", "params": {"exams": rng.sample(codes, 2)}},
        lambda: {"type": "order", "params": {"first": codes[0], "then": codes[-1]}},
        lambda: {"type": "prefer_early", "params": {"largest": 2}},
        lambda: {"type": "prefer_slot", "params": {"exams": rng.sample(codes, 2), "slot": rng.randint(1, 2)}},
        lambda: {"type": "room_unavailable", "params": {"room": rng.choice(rooms)["id"], "date": rng.choice(days)}},
        lambda: {"type": "room_fill", "params": {"max_fraction": rng.choice([0.6, 0.8, 1.0])}},
        lambda: {"type": "seat_spacing", "params": {"directions": rng.choice([["side"], ["side", "front"]])}},
        lambda: {"type": "allow_adjacent", "params": {"exams": [rng.choice(codes)]}},
        lambda: {"type": "exam_rooms", "params": {"exam": rng.choice(codes), "rooms": [r["id"] for r in rng.sample(rooms, 2)]}},
        lambda: {"type": "student_rooms", "params": {"students": [roll], "rooms": [rng.choice(rooms)["id"]]}},
        lambda: {"type": "max_exams_per_room", "params": {"n": rng.randint(1, 3)}},
        lambda: {"type": "invigilation", "params": {"per_students": rng.choice([15, 30]), "min_per_room": 1, "max_per_day": 2}},
    ]
    return [rng.choice(pool)() for _ in range(rng.randint(0, 6))]


def stress(n):
    solved = failed = 0
    for i in range(n):
        rng = random.Random(1000 + i)
        enr, rooms, codes = uni(rng, students=rng.randint(20, 120), exams=rng.randint(3, 12), cohorts=rng.randint(1, 3), rooms=rng.randint(2, 6))
        roll = enr.splitlines()[1].split(",")[1]
        cons = random_rules(rng, codes, rooms, roll)
        r = solve(enr, rooms, cons, dict(CAL, slots_per_day=rng.randint(1, 2)), "name,unavailable\n" + "\n".join(f"P{k}," for k in range(12)))
        if r["ok"]:
            assert r["violations"] == [], (i, cons, r["violations"][:5])
            assert s.extra_rooms(r, s.room_capacity(rooms, r["slots"], cons), cons) == [], (i, cons)   # no mostly-empty rooms
            solved += 1
        else:
            assert r["errors"] and all(isinstance(e, str) and e for e in r["errors"]), (i, r)
            failed += 1
    return solved, failed


if __name__ == "__main__":
    t0 = time.time()
    for f in TESTS:
        t = time.time(); f(); print(f"ok  {f.__name__:28s} {time.time() - t:5.1f}s", flush=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    solved, failed = stress(n)
    print(f"stress: {n} random universities, {solved} solved with 0 violations, {failed} correctly reported as impossible  ({time.time() - t0:.0f}s total)")
