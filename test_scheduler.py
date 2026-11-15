"""Runs the real end-term data through the whole pipeline; fails if any hard rule is broken.
python test_scheduler.py"""
import json, time
from collections import Counter
import scheduler as s

ENROLL = open("End Term Date Sheet Draft.csv", encoding="utf-8-sig").read()
ROOMS = json.load(open("rooms.json"))
CAL = {"start": "2026-12-01", "end": "2026-12-28", "slots_per_day": 2, "slot_times": ["09:30-12:30", "14:00-17:00"]}


def test_layout():
    seats = s.parse_layout({"layout": "SxS S\nSSS"})
    assert len(seats) == 6
    assert s.adjacent_pairs(seats, ["side"]) == [(3, 4), (4, 5)]       # x and the aisle break adjacency
    assert s.spaced_capacity(3, [(0, 1), (1, 2)]) == 2


def test_unknown_constraints_are_reported():
    cons = [{"id": "a", "type": "teleport_students", "params": {}, "text": "teleport"},
            {"id": "b", "type": "fix_exam", "params": {"exam": "NOPE1"}, "text": "fix NOPE1"}]
    ok, problems = s.check_constraints(cons, {"CC1101": {}}, ROOMS)
    assert ok == [] and len(problems) == 2


def test_infeasible_rules_are_named():
    cons = [{"type": "allow_adjacent", "params": {"exams": ["CC1101"]}},
            {"type": "fix_exam", "params": {"exam": "CC1101", "date": "2026-12-01", "slot": 1}, "text": "CC1101 first morning"},
            {"type": "forbid_exam", "params": {"exam": "CC1101", "date": "2026-12-01"}, "text": "nothing for CC1101 on Dec 1"}]
    r = s.run(ENROLL, ROOMS, cons, CAL, time_limit=30, log=lambda *_: None)
    assert not r["ok"] and any("CC1101 first morning" in e for e in r["errors"]), r["errors"]


def test_full_period():
    cons = [{"type": "allow_adjacent", "params": {"exams": ["CC1101"]}, "text": "CC1101 may sit side by side"},
            {"type": "room_fill", "params": {"max_fraction": 0.9}},
            {"type": "invigilation", "params": {"per_students": 30, "min_per_room": 1, "max_per_day": 2}}]
    invig = "name,unavailable\n" + "\n".join(f"Prof {i}," for i in range(40))
    t0 = time.time()
    r = s.run(ENROLL, ROOMS, cons, CAL, invig, time_limit=60)
    assert r["ok"], r["errors"]
    assert r["violations"] == [], r["violations"][:10]
    days = Counter(sl["date"] for sl in r["slots"] if sl["exams"])
    print(f"{time.time() - t0:.0f}s", r["stats"], "days used:", len(days), r["warnings"][:3])


def test_history_parsing():
    import history
    if not history.PAST.exists():
        return
    h = history.parse_all()
    may16 = next(x for x in h["sittings"] if x["date"] == "2026-05-16")
    assert [(e["exam"], e["count"]) for e in may16["rooms"]["EB1-009"]] == [("LS1109", 39), ("AS1108", 20), ("CC1103", 3), ("AS1106", 2)]
    pm = next(x for x in h["sittings"] if x["date"] == "2026-09-21" and "PM" in x["time"])
    assert [(e["exam"], e["count"]) for e in pm["rooms"]["EB1-009"]] == [("CS1133", 31), ("AS1201", 8), ("AS1211", 23)]
    assert h["datesheet"]["CS1133"]["date"] == "2026-09-21" and "PM" in h["datesheet"]["CS1133"]["time"]


if __name__ == "__main__":
    for f in [test_layout, test_history_parsing, test_unknown_constraints_are_reported, test_infeasible_rules_are_named, test_full_period]:
        f(); print("ok", f.__name__)
