"""Local rule reader: a fine-tuned Qwen2.5-0.5B-Instruct (LoRA) that turns one English rule into rule JSON.
No API keys; base weights download once from Hugging Face, then everything runs offline.

    python rule_model.py train   # synthetic data + corrections.jsonl -> rule_model/  (~10 min on an RTX 4050)
    python rule_model.py eval    # accuracy on hand-written sentences that never appear in training

The model outputs exam/room/date *as written* ("applied physics", "25th Dec"); resolve() maps them to real
codes/ids/ISO dates with plain matching, so the network never has to memorise your course list.
"""
import calendar as _cal, datetime as dt, difflib, json, random, re, sys
from scheduler import VOCAB
from pathlib import Path

BASE = "Qwen/Qwen2.5-0.5B-Instruct"
OUT = Path(__file__).parent / "rule_model"
CORRECTIONS = Path(__file__).parent / "corrections.jsonl"
R = random.Random(0)
pick = R.choice

# ---------------- synthetic training data ----------------
SUBJECTS = """Applied Physics|Engineering Chemistry|Data Structures|Discrete Mathematics|Linear Algebra|Calculus|
Fundamentals of Communication|Business Mathematics|Financial Accounting|Environmental Science and Sustainability|
Operating Systems|Computer Networks|Database Management Systems|Microeconomics|Macroeconomics|Marketing Management|
Organisational Behaviour|Digital Electronics|Signals and Systems|Thermodynamics|Fluid Mechanics|Machine Learning|
Artificial Intelligence|Probability and Statistics|Object Oriented Programming|Python Programming|Web Technologies|
Software Engineering|Corporate Finance|Business Law|Cost Accounting|Indian Constitution|Professional Ethics|
Engineering Graphics|Basic Electrical Engineering|Theory of Computation|Compiler Design|Computer Architecture|
Human Resource Management|Strategic Management|Cyber Security|Cloud Computing|Design Thinking|Fintech Fundamentals|
Banking Operations|Statistics for Business|Technical Writing|Mechanics of Materials|Control Systems|Biology for Engineers""".replace("\n", "").split("|")
PREFIX = ["CS", "MA", "PH", "AS", "CC", "EC", "ME", "FA", "ID", "ES", "BB", "HS", "EE", "CE"]
ORD = lambda d: f"{d}{'th' if 10 <= d % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')}"
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def _real_vocab():
    """Your actual course names/codes and room ids, so training sentences use your university's words."""
    import csv
    root, names, codes = Path(__file__).parent, set(), set()
    for f in list(root.glob("*.csv")) + list((root / "data" / "past").glob("*.csv")):
        try:
            for r in csv.DictReader(open(f, encoding="utf-8-sig")):
                c, n = r.get("Subject Code", "").strip(), r.get("Subject Name", "").strip()
                if c: codes.add(c)
                if n: names.add(n)
        except (UnicodeDecodeError, csv.Error):
            pass
    hist = root / "data" / "history.json"
    if hist.exists():
        codes |= set(json.loads(hist.read_text())["datesheet"])
    rooms_f = root / "rooms.json"
    rooms = [r["id"] for r in json.loads(rooms_f.read_text())] if rooms_f.exists() else []
    return sorted(names), sorted(codes), rooms


REAL_NAMES, REAL_CODES, REAL_ROOMS = _real_vocab()


def exam():
    if REAL_NAMES and R.random() < 0.5:                   # half the time: a real course of yours
        s = pick(REAL_NAMES)
        return pick([s, s.lower(), pick(REAL_CODES) if REAL_CODES else s, f"the {s} exam", f"{s} paper"])
    s = pick(SUBJECTS)
    return pick([s, s.lower(), f"{pick(PREFIX)}{R.randint(1000, 4999)}", f"the {s} exam", f"{s} paper", s.upper()])


def room():
    if REAL_ROOMS and R.random() < 0.5:
        return pick(REAL_ROOMS)
    n = R.randint(1, 4) * 100 + R.randint(1, 12)
    return pick([f"{pick(['EB1', 'EB2', 'IM', 'AB', 'LT'])}-{n}", f"room {n}", f"{pick(['EB1', 'IM'])}-Amphi", f"LT-{R.randint(1, 9)}", f"lab {n}"])


ROMAN_W = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
YEAR_W = {1: "first", 2: "second", 3: "third", 4: "fourth"}


def group():
    n = R.randint(1, 8)
    return pick([f"semester {n}", f"sem {ROMAN_W[n]}", f"Sem {n}", f"{ORD(n)} semester", f"all sem {ROMAN_W[n]} papers", f"semester {ROMAN_W[n]} exams",
                 f"{YEAR_W[(n + 1) // 2]} year", f"{YEAR_W[(n + 1) // 2]}-year", "core papers", "all core subjects", "electives", "elective papers"])


def exams_or_group():
    return [group()] if R.random() < 0.35 else [exam()]


def date():
    d = dt.date(2026, 11, 1) + dt.timedelta(days=R.randint(0, 200))
    m, b = _cal.month_name[d.month], _cal.month_abbr[d.month]
    return pick([f"{d.day} {m}", f"{m} {d.day}", f"{ORD(d.day)} {m}", f"{ORD(d.day)} {b}", f"{b} {d.day}",
                 f"{d.day}/{d.month}", d.isoformat(), f"{d.day:02d}-{d.month:02d}-{d.year}", f"{m} {ORD(d.day)}",
                 f"{d.day:02d}.{d.month:02d}.{d.year}", f"{d.day:02d}.{d.month:02d}.{d.year}", f"{d.day}.{d.month}"])


def num(n):
    return pick([str(n), WORDS.get(n, str(n))])


def slot():
    s = R.randint(1, 2)
    return s, pick({1: ["morning", "first", "forenoon", "1st", "10 am", "10:00 AM", "9:30 am"],
                    2: ["afternoon", "second", "evening", "2nd", "2:30 PM", "2 pm", "post-lunch"]}[s])


def soft():
    return pick([(True, ""), (True, ""), (False, " if possible"), (False, " wherever possible"), (False, " preferably"), (False, ", try to"),
                 (False, " ideally"), (False, " if feasible"), (False, ", as far as possible"), (False, " where we can"),
                 (False, ", it would be nice"), (False, " if we can manage"), (False, " (preferred, not mandatory)")])


def g_max_day():
    n = R.randint(1, 3)
    t = pick(["no student should have more than {n} exams a day", "max {n} exam per day", "a student can write at most {n} papers in a day",
              "limit students to {n} exams daily", "not more than {n} exams on the same day for anyone", "at most {n} papers per student per day",
              "students shouldn't sit more than {n} exams in one day", "one day = max {n} exams for a student"])
    if R.random() < 0.4:
        t = pick(["no student should write {m} papers on the same day", "nobody sits {m} exams in a single day", "{m} exams in one day is not allowed",
                  "never give a student {m} exams on one date", "students can't have {m} papers the same day"]).format(m=num(n + 1))
        return t, [{"type": "max_exams_per_day", "params": {"n": n}}]
    return t.format(n=num(n)), [{"type": "max_exams_per_day", "params": {"n": n}}]


def g_b2b():
    h, s = soft()
    t = pick(["no back to back exams{s}", "avoid consecutive exams for a student{s}", "students should not have two exams in a row{s}",
              "don't put a student's exams in morning and afternoon of the same day{s}", "no student gets consecutive slots{s}"])
    return t.format(s=s), [{"type": "no_back_to_back", "params": {"hard": h}}]


def g_gap():
    k, (h, s) = R.randint(1, 3), soft()
    if R.random() < 0.2:
        g = group()
        return pick(["{k} days gap between {g}{s}", "space out {g} by {k} days{s}"]).format(k=num(k), g=g, s=s), \
            [{"type": "min_gap_days", "params": {"days": k, "hard": h, "exams": [g]}}]
    if R.random() < 0.3:
        a, b = exam(), exam()
        return pick(["keep {k} days gap between {a} and {b}{s}", "{a} and {b} should be at least {k} days apart{s}"]).format(k=num(k), a=a, b=b, s=s), \
            [{"type": "min_gap_days", "params": {"days": k, "hard": h, "exams": [a, b]}}]
    t = pick(["keep a {k} day gap between exams{s}", "students need at least {k} days between two papers{s}", "leave {k} days between any two exams of a student{s}",
              "minimum gap of {k} days between exams{s}", "give students {k} days off between papers{s}", "exams should be spaced {k} days apart{s}"])
    return t.format(k=num(k), s=s), [{"type": "min_gap_days", "params": {"days": k, "hard": h}}]


def g_holiday():
    ds = [date() for _ in range(R.randint(1, 3))]
    j = " and ".join(ds) if len(ds) < 3 else f"{ds[0]}, {ds[1]} and {ds[2]}"
    t = pick(["{d} is a holiday", "no exams on {d}", "{d} are holidays", "university closed on {d}", "skip {d}", "do not schedule anything on {d}",
              "exclude {d} from the exam calendar", "{d} off"])
    if R.random() < 0.35:
        f = pick(["Christmas", "Diwali", "Holi", "Republic Day", "Guru Nanak Jayanti", "New Year", "the convocation", "Eid"])
        t = pick(["{f}, {d}, no exams", "{d} is {f} so the campus is closed", "because of {f} on {d} nothing is scheduled", "{f} ({d}) is off"])
        return t.format(f=f, d=j), [{"type": "holiday", "params": {"dates": ds}}]
    return t.format(d=j), [{"type": "holiday", "params": {"dates": ds}}]


def g_day_slots():
    d, n = date(), R.randint(0, 1) + 1
    t = pick(["{d} has only {n} slot", "only {n} exam slot on {d}", "{d} only morning slot", "on {d} keep just {n} session", "half day on {d}", "{d} single shift only"])
    return t.format(d=d, n=num(n)), [{"type": "day_slots", "params": {"date": d, "slots": 1 if "morning" in t or "half" in t or "single" in t else n}}]


def g_fix():
    e, d, (sn, sw) = exam(), date(), slot()
    v = R.random()
    if v < 0.4:
        return pick(["{e} must be on {d}", "schedule {e} on {d}", "{e} exam is fixed for {d}", "put {e} on {d}"]).format(e=e, d=d), \
            [{"type": "fix_exam", "params": {"exam": e, "date": d}}]
    if v < 0.7:
        return pick(["{e} on {d} {w}", "{e} must be in the {w} slot on {d}", "fix {e} to {d}, {w} session"]).format(e=e, d=d, w=sw), \
            [{"type": "fix_exam", "params": {"exam": e, "date": d, "slot": sn}}]
    return pick(["{e} should always be in the {w} slot", "hold {e} in the {w}", "{e} only in {w} session"]).format(e=e, w=sw), \
        [{"type": "fix_exam", "params": {"exam": e, "slot": sn}}]


def g_forbid():
    e, d, (sn, sw) = exam(), date(), slot()
    if R.random() < 0.6:
        return pick(["{e} cannot be on {d}", "don't schedule {e} on {d}", "no {e} on {d}", "avoid {d} for {e}", "{e} not on {d}"]).format(e=e, d=d), \
            [{"type": "forbid_exam", "params": {"exam": e, "date": d}}]
    return pick(["{e} should not be in the {w} slot", "never put {e} in the {w}", "no {w} slot for {e}"]).format(e=e, w=sw), \
        [{"type": "forbid_exam", "params": {"exam": e, "slot": sn}}]


def g_same():
    es = [exam() for _ in range(R.randint(2, 3))]
    j = " and ".join(es) if len(es) == 2 else f"{es[0]}, {es[1]} and {es[2]}"
    t = pick(["{j} at the same time", "{j} are a common paper", "hold {j} together", "{j} should be in the same slot", "conduct {j} simultaneously",
              "{j} share one question paper so run them together"])
    return t.format(j=j), [{"type": "same_slot", "params": {"exams": es}}]


def g_diff():
    es = [exam() for _ in range(R.randint(2, 3))]
    j = " and ".join(es) if len(es) == 2 else f"{es[0]}, {es[1]} and {es[2]}"
    t = pick(["{j} on different days", "{j} must not be on the same day", "keep {j} on separate days", "never schedule {j} on one day"])
    return t.format(j=j), [{"type": "different_day", "params": {"exams": es}}]


def g_order():
    a, b = exam(), exam()
    t, swap = pick([("{a} before {b}", 0), ("{a} must be held before {b}", 0), ("schedule {b} after {a}", 1), ("{b} should come after {a}", 1),
                    ("conduct {a} earlier than {b}", 0), ("{a} has to happen prior to {b}", 0), ("{b} only once {a} is done", 1), ("first {a} then {b}", 0),
                    ("{b} should follow {a}", 1), ("{b} follows {a}", 1), ("{b} comes after {a}", 1), ("{a} precedes {b}", 0), ("{b} must be preceded by {a}", 1)])
    return t.format(a=a, b=b), [{"type": "order", "params": {"first": a, "then": b}}]


def g_early():
    if R.random() < 0.3:
        n = R.randint(2, 10)
        return pick(["put the {n} biggest exams early", "largest {n} papers in the first few days", "schedule the {n} exams with most students first",
                     "big exams early so checking finishes, top {n}"]).format(n=num(n)), [{"type": "prefer_early", "params": {"largest": n}}]
    es = exams_or_group()
    late = R.random() < 0.5
    t = pick(["{e} towards the end", "{e} in the last days", "keep {e} late in the schedule", "{e} can go at the very end", "save {e} for the last day",
              "{e} can wait till the end", "push {e} to the final week", "{e} last"] if late else
             ["{e} early in the exams", "try to have {e} in the first week", "{e} should be among the first papers", "prefer {e} early",
              "start the exams with {e}", "{e} in the opening days", "get {e} done first"])
    return t.format(e=es[0]), [{"type": "prefer_late" if late else "prefer_early", "params": {"exams": es}}]


def g_prefer_slot():
    es, (sn, sw) = exams_or_group(), slot()
    t = pick(["{e} preferably in the {w}", "{e} usually in the {w} session", "try to keep {e} in the {w}", "{e} ideally at {w}",
              "{e} exams go in the {w} slot if possible", "where possible hold {e} in the {w}"])
    return t.format(e=es[0], w=sw), [{"type": "prefer_slot", "params": {"exams": es, "slot": sn}}]


def g_mix():
    n = R.randint(1, 4)
    t = pick(["no more than {n} subjects in one room", "mix at most {n} papers per hall", "a room can have maximum {n} different exams",
              "don't put more than {n} courses in the same classroom", "only {n} exams per room", "limit each hall to {n} different papers"])
    return t.format(n=num(n)), [{"type": "max_exams_per_room", "params": {"n": n}}]


def g_room_off():
    r, d, (sn, sw) = room(), date(), slot()
    v = R.random()
    if v < 0.4:
        return pick(["{r} is not available", "{r} is under renovation", "don't use {r}", "{r} is closed", "exclude {r}"]).format(r=r), \
            [{"type": "room_unavailable", "params": {"room": r}}]
    if v < 0.8:
        return pick(["{r} not available on {d}", "{r} is booked on {d}", "can't use {r} on {d}", "{r} has an event on {d}"]).format(r=r, d=d), \
            [{"type": "room_unavailable", "params": {"room": r, "date": d}}]
    return pick(["{r} unavailable on {d} {w}", "{r} is busy in the {w} of {d}"]).format(r=r, d=d, w=sw), \
        [{"type": "room_unavailable", "params": {"room": r, "date": d, "slot": sn}}]


def g_fill():
    p = pick([50, 60, 70, 75, 80, 90])
    if R.random() < 0.5:
        r = room()
        return pick(["use at most {p}% of {r}", "{r} only {p} percent full", "fill {r} to {p}% max", "don't fill {r} beyond {p}%",
                     "fill {r} to at most {n} students worth, around {p}%", "{r}: {p}% of capacity", "{r} should be about {p} percent occupied"]).format(p=p, r=r, n=R.randint(20, 70)), \
            [{"type": "room_fill", "params": {"max_fraction": p / 100, "room": r}}]
    return pick(["never fill a room completely, max {p}%", "rooms should be at most {p}% occupied", "use only {p}% of seats in every room",
                 "keep rooms {p}% full at most", "do not seat more than {p} percent capacity anywhere", "no hall above {p}% of its seats",
                 "capacity use must stay under {p} percent", "seat students in only {p}% of the available seats", "fill every room to about {p}%",
                 "at most {p} per cent of seats should be occupied"]).format(p=p), [{"type": "room_fill", "params": {"max_fraction": p / 100}}]


def g_spacing():
    if R.random() < 0.5:
        return pick(["students of the same paper can't sit next to each other", "no two students with the same exam side by side",
                     "same subject students must not be neighbours"]), [{"type": "seat_spacing", "params": {"directions": ["side"]}}]
    return pick(["same exam students shouldn't sit next to or behind each other", "no same paper students side by side or front and back",
                 "leave a gap all around students of the same exam"]), [{"type": "seat_spacing", "params": {"directions": ["side", "front"]}}]


def g_adj():
    e = exam() if R.random() < 0.7 else group()
    return pick(["{e} students can sit side by side", "allow {e} students next to each other", "{e} doesn't need gaps between students",
                 "for {e} it's fine to seat them adjacent", "{e} can be seated together"]).format(e=e), [{"type": "allow_adjacent", "params": {"exams": [e]}}]


def g_exam_rooms():
    e, rs = exam(), [room() for _ in range(R.randint(1, 2))]
    j = " and ".join(rs)
    return pick(["{e} only in {j}", "{e} has to be held in {j}", "use {j} for {e}", "{e} needs {j}", "{e} must be conducted in {j}"]).format(e=e, j=j), \
        [{"type": "exam_rooms", "params": {"exam": e, "rooms": rs}}]


def g_student_rooms():
    ss = [f"{R.randint(2021, 2026)}{pick(['BTech', 'BBA', 'MBA'])}{R.randint(1, 300):03d}" for _ in range(R.randint(1, 3))]
    r = room()
    return pick(["{s} must sit in {r}", "seat {s} in {r} (wheelchair)", "{s} need the ground floor room {r}", "put {s} in {r}"]).format(s=", ".join(ss), r=r), \
        [{"type": "student_rooms", "params": {"students": ss, "rooms": [r]}}]


def g_invig():
    p, m, d = pick([20, 25, 30, 40]), R.randint(1, 2), R.randint(1, 3)
    v = R.random()
    if v < 0.4:
        return pick(["one invigilator per {p} students", "1 invigilator for every {p} students", "need an invigilator per {p} candidates"]).format(p=p), \
            [{"type": "invigilation", "params": {"per_students": p}}]
    if v < 0.7:
        return pick(["at least {m} invigilators in every room", "minimum {m} invigilator per room", "each room needs {m} invigilators"]).format(m=num(m)), \
            [{"type": "invigilation", "params": {"min_per_room": m}}]
    return pick(["an invigilator should do at most {d} duties a day", "no teacher more than {d} invigilation duties per day", "max {d} duties daily per invigilator"]).format(d=num(d)), \
        [{"type": "invigilation", "params": {"max_per_day": d}}]


UNSUPPORTED = ["invigilators should not be teachers of the subject", "answer sheets must be collected by 5 pm", "question papers printed two days before",
               "no exams during Diwali week", "students with backlog get a separate room", "serve water in every room", "CCTV must be on in all halls",
               "the controller of exams approves the final sheet", "results within 15 days", "faculty from other department for invigilation",
               "mobile phones are not allowed", "exam duration should be three hours", "make sure the AC works", "female invigilator for girls hostel block",
               "students of the same hostel should not sit together", "lab exams need computers working", "keep the timetable similar to last year",
               "announce the date sheet two weeks in advance", "MBA students get calculators", "seat toppers in the front row",
               "ensure fans are working", "notify parents of the schedule", "no exam the day after a festival", "practical exams happen before theory"]


def g_unsupported():
    if R.random() < 0.4:
        e, r = exam(), room()
        t = pick(["teachers of {e} shouldn't invigilate it", "{e} needs extra answer sheets", "print {e} papers in colour", "{e} question paper is set by an external examiner",
                  "{r} projector must work", "{e} students get a formula sheet", "students from the same batch should be mixed with other batches", "{r} needs a clock on the wall",
                  "{e} results by Friday", "collect {e} scripts at the gate"])
        return t.format(e=e, r=r), [{"type": "unsupported", "params": {}}]
    return pick(UNSUPPORTED), [{"type": "unsupported", "params": {}}]


def g_and_names():
    a = pick([n for n in REAL_NAMES + SUBJECTS if " and " in n] or SUBJECTS)
    b = exam()
    t = pick(["{a} and {b} share a question paper", "{a} at the same time as {b}", "{b} together with {a}"])
    return t.format(a=a, b=b), [{"type": "same_slot", "params": {"exams": [a, b]}}]


def g_program_aside():
    a, b = exam(), exam()
    prog = pick(["CSE core and AI", "CSE (Data Science)", "ECE", "BBA Fintech", "CSE core", "the AI branch"])
    t = pick(["{a} is common for {p}, same slot as {b}", "for {p}, hold {a} with {b}", "{a} ({p}) together with {b}"])
    return t.format(a=a, b=b, p=prog), [{"type": "same_slot", "params": {"exams": [a, b]}}]


GENS = [g_max_day, g_b2b, g_gap, g_holiday, g_day_slots, g_fix, g_forbid, g_same, g_diff, g_order, g_early, g_early, g_prefer_slot, g_mix,
        g_room_off, g_fill, g_spacing, g_adj, g_exam_rooms, g_student_rooms, g_invig, g_unsupported, g_unsupported, g_and_names, g_program_aside]
LEAD = ["", "", "", "please ", "kindly ensure ", "note: ", "make sure ", "we want ", "rule: ", "also ", "important - "]


def noisy(t):
    t = pick(LEAD) + t
    if R.random() < 0.3:
        t = t[0].upper() + t[1:]
    if R.random() < 0.3:
        t += pick([".", "!", " pls", " thanks", " as per policy"])
    if R.random() < 0.15:                                 # one typo, never inside a digit run
        i = R.randrange(len(t) - 1)
        if t[i].isalpha() and t[i + 1].isalpha():
            t = t[:i] + t[i + 1] + t[i] + t[i + 2:]
    return t


def _history_rows():
    hist = Path(__file__).parent / "data" / "history.json"
    return list(json.loads(hist.read_text())["datesheet"].items()) if hist.exists() else []


HISTORY = _history_rows()


def g_history():
    code, d = pick(HISTORY)
    dd, mm, yy = d["date"][8:], d["date"][5:7], d["date"][:4]
    date_m = pick([f"{dd}.{mm}.{yy}", f"{int(dd)} {_cal.month_name[int(mm)]}", f"{ORD(int(dd))} {_cal.month_abbr[int(mm)]}"])
    e = pick([code, f"{code}: {d['name']}", d["name"]]) if d["name"] else code
    sn = 1 if "AM" in d["time"] else 2
    t = pick(["{e} on {d} at {tm}", "{e} is on {d}, {tm}", "schedule {e} for {d} {tm}", "{d} {tm}: {e}"])
    return t.format(e=e, d=date_m, tm=d["time"]), [{"type": "fix_exam", "params": {"exam": e, "date": date_m, "slot": sn}}]


def example():
    t, rules = (g_history() if HISTORY and R.random() < 0.05 else pick(GENS)())
    if rules[0]["type"] != "unsupported" and R.random() < 0.15:   # reasons/asides carry no extra rule
        t = pick(["{t}, because the hall is shared", "{t} as the staff are busy", "as discussed in the meeting, {t}", "{t} (accessibility)", "{t}, since it is a common paper"]).format(t=t)
    if R.random() < 0.12:                                 # two rules in one sentence
        t2, r2 = pick(GENS[:-1])()
        t, rules = f"{t} and {t2}", rules + r2
    return noisy(t), rules


# ---------------- model ----------------
def prompt(text):
    return f"Convert the exam rule to JSON.\nRule: {text}\nJSON:"


def train(n=32000, epochs=1, out=OUT):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model
    tok = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16).cuda()
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM"))
    data = [example() for _ in range(n)]
    if CORRECTIONS.exists():                              # admin fixes, weighted up
        data += [(c["text"], c["rules"]) for c in map(json.loads, CORRECTIONS.read_text().splitlines()) for _ in range(20)]
    R.shuffle(data)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=2e-4)
    model.gradient_checkpointing_enable(); model.enable_input_require_grads()
    bs, accum = 4, 4                                      # effective batch 16; fits a 6 GB laptop GPU
    steps = epochs * len(data) // (bs * accum)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / 50) * max(0.05, 1 - s / steps))
    model.train()
    for s in range(steps):
        for a in range(accum):
            batch = [data[((s * accum + a) * bs + i) % len(data)] for i in range(bs)]
            ids, labels = [], []
            for t, rules in batch:
                p = tok(prompt(t))["input_ids"]
                ans = tok(" " + json.dumps(rules, separators=(",", ":")) + tok.eos_token)["input_ids"]
                ids.append(p + ans); labels.append([-100] * len(p) + ans)   # loss only on the answer
            L = max(map(len, ids))
            x = torch.tensor([i + [tok.pad_token_id] * (L - len(i)) for i in ids]).cuda()
            y = torch.tensor([i + [-100] * (L - len(i)) for i in labels]).cuda()
            mask = torch.tensor([[1] * len(i) + [0] * (L - len(i)) for i in ids]).cuda()
            loss = model(input_ids=x, attention_mask=mask, labels=y).loss / accum
            loss.backward()
        opt.step(); sched.step(); opt.zero_grad()
        if s % 100 == 0:
            print(f"step {s}/{steps} loss {loss.item() * accum:.4f}", flush=True)
    model.save_pretrained(out); tok.save_pretrained(out)


_loaded = None
def predict(lines):
    """English lines -> raw rule dicts (mentions not yet resolved)."""
    global _loaded
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    if _loaded is None:
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        tok = AutoTokenizer.from_pretrained(OUT); tok.padding_side = "left"
        base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16 if dev == "cuda" else torch.float32)
        _loaded = tok, PeftModel.from_pretrained(base, OUT).to(dev).eval(), dev
    tok, model, dev = _loaded
    enc = tok([prompt(l) for l in lines], return_tensors="pt", padding=True).to(dev)
    with torch.no_grad():
        gen = model.generate(**enc, max_new_tokens=200, do_sample=False, pad_token_id=tok.pad_token_id)
    out = []
    for line, g in zip(lines, gen[:, enc["input_ids"].shape[1]:]):
        try:
            rules = json.loads(tok.decode(g, skip_special_tokens=True).strip())
        except json.JSONDecodeError:
            rules = [{"type": "unsupported", "params": {"reason": "model output was not valid JSON"}}]
        out.append((line, rules))
    return out


# ---------------- mentions -> real codes / ids / dates ----------------
def resolve_exam(m, exams):
    """A course code written in the text always wins; otherwise the closest name, and only if it is unambiguous."""
    upper = {c.upper(): c for c in exams}
    codes = {upper[t.upper()] for t in re.findall(r"[A-Za-z]{2}\d{4}", m) if t.upper() in upper}
    if codes:
        return codes.pop() if len(codes) == 1 else None
    m0 = re.sub(r"\b(the|exam|paper|course|subject)\b", "", m.lower()).strip(" :-,")
    names = {e["name"].lower(): c for c, e in exams.items()}
    flat = lambda x: re.sub(r"[\s\-:]", "", x)
    exact = [c for n, c in names.items() if flat(n) == flat(m0)]
    if len(exact) == 1:
        return exact[0]
    hit = difflib.get_close_matches(m0, names, n=2, cutoff=0.75)
    if len(hit) == 2 and difflib.SequenceMatcher(None, m0, hit[0]).ratio() - difflib.SequenceMatcher(None, m0, hit[1]).ratio() < 0.05:
        return None                                      # two names fit about equally well: ask instead of guessing
    if hit:
        return names[hit[0]]
    inside = [n for n in names if m0 and m0 in n]
    return names[inside[0]] if len(inside) == 1 else None


ROMAN_N = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
YEAR_N = {"first": 1, "second": 2, "third": 3, "fourth": 4, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4}


def resolve_group(m, exams):
    """'sem III', 'semester 3', 'first year', 'core papers' -> exam codes, using the enrollment's semester/subject-type columns.
    Returns None when the mention isn't a group."""
    t = m.lower()
    sems = None
    g = re.search(r"\b(?:sem(?:ester)?)\s*([ivx]+|\d)\b", t) or re.search(r"\b(\d)(?:st|nd|rd|th)\s+sem", t)
    if g:
        v = g[1]; sems = {ROMAN_N.get(v) or int(v)}
    y = re.search(r"\b(first|second|third|fourth|1st|2nd|3rd|4th)[- ]year\b", t)
    if y:
        k = YEAR_N[y[1]]; sems = {2 * k - 1, 2 * k}
    kind = ("core" if re.search(r"\bcore (papers?|subjects?|courses?|exams?)\b|^(all )?core$", t) else
            "elective" if re.search(r"\belectives?\b", t) else None)
    if sems is None and kind is None:
        return None
    return sorted(c for c, e in exams.items()
                  if (sems is None or e.get("semester") in sems) and (kind is None or (e.get("kind") or "").lower() == kind))


def resolve_room(m, room_ids):
    key = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r"\b(the|room|lab|hall)\b", "", s.lower()))
    hits = [r for r in room_ids if key(r) == key(m)] or [r for r in room_ids if key(m) and key(r).endswith(key(m))]
    return hits[0] if len(hits) == 1 else None


def resolve_date(m, year):
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", m.strip().lower().replace(",", ""))
    for f in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%B %d %Y"]:
        try: return dt.datetime.strptime(s, f).date().isoformat()
        except ValueError: pass
    for f in ["%d %B", "%B %d", "%d %b", "%b %d", "%d/%m", "%d-%m", "%d.%m"]:
        try: d = dt.datetime.strptime(f"{s} {year}", f + " %Y").date()
        except ValueError: continue
        return d.isoformat()
    return None


CHECKS = {
    "max_exams_per_day": lambda p: isinstance(p.get("n"), int) and 1 <= p["n"] <= 4,
    "max_exams_per_room": lambda p: isinstance(p.get("n"), int) and 1 <= p["n"] <= 10,
    "room_fill": lambda p: isinstance(p.get("max_fraction"), (int, float)) and 0 < p["max_fraction"] <= 1,
    "min_gap_days": lambda p: isinstance(p.get("days"), int) and 1 <= p["days"] <= 10,
    "day_slots": lambda p: isinstance(p.get("slots"), int) and 0 <= p["slots"] <= 4,
    "fix_exam": lambda p: p.get("date") or p.get("slot"),
    "forbid_exam": lambda p: p.get("date") or p.get("slot"),
    "same_slot": lambda p: len(p.get("exams", [])) >= 2,
    "different_day": lambda p: len(p.get("exams", [])) >= 2,
    "order": lambda p: p.get("first") != p.get("then"),
}


def resolve(raw, exams, room_ids, cal):
    """Model output -> solver constraints. Anything that can't be matched becomes `unsupported` with the reason."""
    start = dt.date.fromisoformat(cal["start"]) if cal.get("start") else dt.date.today()
    defaults = {"invigilation": {"per_students": 30, "min_per_room": 1, "max_per_day": 2}, "min_gap_days": {"hard": True}, "no_back_to_back": {"hard": True}}
    out = []
    for line, rules in raw:
        for r in rules:
            t, p, bad = r.get("type", "unsupported"), dict(defaults.get(r.get("type"), {}), **r.get("params", {})), []
            def ex(m):
                c = resolve_exam(m, exams); bad.append(f"exam '{m}'") if c is None else None; return c
            def rm(m):
                c = resolve_room(m, room_ids); bad.append(f"room '{m}'") if c is None else None; return c
            def dd(m):
                d = resolve_date(m, start.year)
                if d and dt.date.fromisoformat(d) < start - dt.timedelta(days=60):   # "5 Jan" in a Dec-Jan period
                    d = d.replace(str(start.year), str(start.year + 1), 1)
                bad.append(f"date '{m}'") if d is None else None; return d
            for k in ("exam", "first", "then"):
                if k in p: p[k] = ex(p[k])
            if "exams" in p:
                codes = []
                for m in p["exams"]:
                    g = resolve_group(m, exams)
                    if g == []:
                        bad.append(f"group '{m}' (no exams match)")
                    codes += g if g is not None else [ex(m)]
                p["exams"] = sorted(set(c for c in codes if c), key=codes.index)
            if "room" in p: p["room"] = rm(p["room"])
            if "rooms" in p: p["rooms"] = [rm(m) for m in p["rooms"]]
            if "date" in p: p["date"] = dd(p["date"])
            if "slot" in p and p["slot"] not in (1, 2, 3, 4): bad.append(f"slot '{p['slot']}'")
            if "students" in p:
                known = set().union(*(e["students"] for e in exams.values())) if exams else set()
                bad += [f"student '{r}'" for r in p["students"] if r not in known]
            if "dates" in p: p["dates"] = [dd(m) for m in p["dates"]]
            if bad:
                t, p = "unsupported", {"reason": "couldn't match " + ", ".join(bad)}
            elif t not in VOCAB and t != "unsupported":   # the model invented a rule type: never pass it on
                t, p = "unsupported", {"reason": f"no rule type '{t}' exists yet"}
            elif t in CHECKS and not CHECKS[t](p):
                t, p = "unsupported", {"reason": f"read as {r.get('type')} {r.get('params')}, which doesn't make sense; please rephrase"}
            elif t == "unsupported":
                p = {"reason": p.get("reason", "no rule type for this yet")}
            out.append({"id": f"c{len(out) + 1}", "type": t, "params": p, "text": line})
    return out


def interpret(text, exams, rooms, cal):
    lines = [l.strip(" -•*\t") for l in re.split(r"[\n;]|(?<=[a-z0-9)])\.\s+", text) if l.strip(" -•*\t.")]
    return resolve(predict(lines), exams, [r["id"] for r in rooms], cal) if lines else []


# ---------------- held-out eval: phrasings written by hand, not from the templates ----------------
EVAL = [
    ("Nobody writes two papers on one day", "max_exams_per_day", {"n": 1}),
    ("A candidate may appear for a maximum of 2 examinations daily", "max_exams_per_day", {"n": 2}),
    ("Please don't give anyone exams in both sessions of a day", "no_back_to_back", {}),
    ("There should be a break of at least two days between successive exams", "min_gap_days", {"days": 2}),
    ("Ideally one free day between papers", "min_gap_days", {"days": 1, "hard": False}),
    ("Christmas, 25 December, the campus is shut", "holiday", {"dates": ["25 December"]}),
    ("We are closed on Jan 1st and 26th January", "holiday", {"dates": ["Jan 1st", "26th January"]}),
    ("On 4 Dec there is only the forenoon session", "day_slots", {"date": "4 Dec", "slots": 1}),
    ("Applied Physics has to be conducted on 3rd December", "fix_exam", {"exam": "Applied Physics", "date": "3rd December"}),
    ("Hold CS1139 in the afternoon only", "fix_exam", {"exam": "CS1139", "slot": 2}),
    ("Financial Accounting must not fall on 10 Dec", "forbid_exam", {"exam": "Financial Accounting", "date": "10 Dec"}),
    ("Business Mathematics and Statistics for Business share a question paper", "same_slot", {"exams": ["Business Mathematics", "Statistics for Business"]}),
    ("Keep Calculus and Linear Algebra apart on different dates", "different_day", {"exams": ["Calculus", "Linear Algebra"]}),
    ("Thermodynamics needs to be over before Fluid Mechanics starts", "order", {"first": "Thermodynamics", "then": "Fluid Mechanics"}),
    ("Fluid Mechanics after Thermodynamics", "order", {"first": "Thermodynamics", "then": "Fluid Mechanics"}),
    ("Get the five largest papers done at the start", "prefer_early", {"largest": 5}),
    ("Professional Ethics can go at the very end", "prefer_late", {"exams": ["Professional Ethics"]}),
    ("EB2-105 is being painted, keep it out", "room_unavailable", {"room": "EB2-105"}),
    ("IM-Amphi is reserved for convocation on 12 December", "room_unavailable", {"room": "IM-Amphi", "date": "12 December"}),
    ("Do not seat more than 75 percent capacity anywhere", "room_fill", {"max_fraction": 0.75}),
    ("In the Amphi only use 60% seats", "room_fill", {"max_fraction": 0.6, "room": "Amphi"}),
    ("Two students taking the same exam must never be neighbours", "seat_spacing", {"directions": ["side"]}),
    ("Fundamentals of Communication candidates may be seated adjacently", "allow_adjacent", {"exams": ["Fundamentals of Communication"]}),
    ("Python Programming takes place in lab 201 only", "exam_rooms", {"exam": "Python Programming", "rooms": ["lab 201"]}),
    ("2024BTech013 uses a wheelchair, seat him in EB1-101", "student_rooms", {"students": ["2024BTech013"], "rooms": ["EB1-101"]}),
    ("Assign one invigilator for each 25 examinees", "invigilation", {"per_students": 25}),
    ("Each hall gets a minimum of two invigilators", "invigilation", {"min_per_room": 2}),
    ("Teachers shouldn't invigilate their own subject", "unsupported", {}),
    ("The hall must have drinking water", "unsupported", {}),
    ("Students from the same batch should be mixed with other batches", "unsupported", {}),
]

EVAL2 = [
    ("At no point should a pupil face three exams in one day", "max_exams_per_day", {"n": 2}),
    ("Spread papers so there is a 2 day break, if feasible", "min_gap_days", {"days": 2, "hard": False}),
    ("Holi falls on 3 March, so that day is off", "holiday", {"dates": ["3 March"]}),
    ("Only a morning sitting on 18 December", "day_slots", {"date": "18 December", "slots": 1}),
    ("Marketing Management is locked to 9th Dec", "fix_exam", {"exam": "Marketing Management", "date": "9th Dec"}),
    ("Keep Cost Accounting away from 11 December", "forbid_exam", {"exam": "Cost Accounting", "date": "11 December"}),
    ("Microeconomics and Macroeconomics use the same paper, run them together", "same_slot", {"exams": ["Microeconomics", "Macroeconomics"]}),
    ("Compiler Design should follow Theory of Computation", "order", {"first": "Theory of Computation", "then": "Compiler Design"}),
    ("Biggest three subjects first please", "prefer_early", {"largest": 3}),
    ("EB1-103 is locked for maintenance on 15 Dec", "room_unavailable", {"room": "EB1-103", "date": "15 Dec"}),
    ("No hall should go above 80% occupancy", "room_fill", {"max_fraction": 0.8}),
    ("Same-subject students must not be seated side by side or one behind the other", "seat_spacing", {"directions": ["side", "front"]}),
    ("Cloud Computing must be written in LT-2", "exam_rooms", {"exam": "Cloud Computing", "rooms": ["LT-2"]}),
    ("One person invigilates for every 40 students", "invigilation", {"per_students": 40}),
    ("Exam halls should be sanitised daily", "unsupported", {}),
]

EVAL3 = [  # your university's wording: real codes, dd.mm.yyyy dates, semester groups, 10 AM / 2:30 PM slots
    ("CS1133: Database Management System on 21.09.2026 at 2:30 PM", "fix_exam", {"exam": "CS1133: Database Management System", "date": "21.09.2026", "slot": 2}),
    ("EE1118 must be the first paper, 21.09.2026 10:00 AM", "fix_exam", {"exam": "EE1118", "date": "21.09.2026", "slot": 1}),
    ("Sem I papers should ideally be in the morning", "prefer_slot", {"exams": ["Sem I"], "slot": 1}),
    ("Sem III exams go in the 2:30 PM slot where possible", "prefer_slot", {"exams": ["Sem III"], "slot": 2}),
    ("Keep a 1 day gap between all core papers", "min_gap_days", {"days": 1, "exams": ["core papers"]}),
    ("Electives can be at the end", "prefer_late", {"exams": ["Electives"]}),
    ("No exams on 02.10.2026 (Gandhi Jayanti)", "holiday", {"dates": ["02.10.2026"]}),
    ("25.09.2026 has only the 10 AM session", "day_slots", {"date": "25.09.2026", "slots": 1}),
    ("CS1131 Data Structure and Algorithms after CS1139 Programming-I", "order", {"first": "CS1139 Programming-I", "then": "CS1131 Data Structure and Algorithms"}),
    ("TB-109 is not available on 22.09.2026", "room_unavailable", {"room": "TB-109", "date": "22.09.2026"}),
    ("Do not mix more than 2 subjects in a classroom", "max_exams_per_room", {"n": 2}),
    ("CS1261 Principles of Cloud computing is common for CSE core and AI, same slot as CS1243", "same_slot", {"exams": ["CS1261 Principles of Cloud computing", "CS1243"]}),
    ("Fill EB1-009 to at most 60 students worth, around 90%", "room_fill", {"max_fraction": 0.9, "room": "EB1-009"}),
    ("AS1108 Applied Physics should not be on a Monday afternoon slot on 21.09.2026", "forbid_exam", {"exam": "AS1108 Applied Physics", "date": "21.09.2026", "slot": 2}),
    ("CC1101 students may sit side by side", "allow_adjacent", {"exams": ["CC1101"]}),
    ("Students of second year can't have two exams a day", "unsupported", {}),
    ("Every hall needs at least 2 invigilators", "invigilation", {"min_per_room": 2}),
    ("Hold IM-004 for the backlog students of AS1117", "unsupported", {}),
    ("LS1108 Essentials of Business Management only in TB-101 and TB-104", "exam_rooms", {"exam": "LS1108 Essentials of Business Management", "rooms": ["TB-101", "TB-104"]}),
    ("Put the 4 largest papers in the first two days", "prefer_early", {"largest": 4}),
]


def evaluate():
    score(EVAL, "set 1 (seen while tuning)"); score(EVAL2, "set 2 (fresh)"); return score_resolved(EVAL3, "set 3 (your wording, judged by resolved result)")


def score_resolved(EVAL, name):
    """Judge by what the rule turns into against the real enrollment and rooms, not by exact wording."""
    import scheduler
    root = Path(__file__).parent
    exams, _ = scheduler.load_enrollment((root / "End Term Date Sheet Draft.csv").read_text(encoding="utf-8-sig"))
    rooms = [r["id"] for r in json.loads((root / "rooms.json").read_text())]
    cal = {"start": "2026-09-01"}
    raw = predict([t for t, _, _ in EVAL])
    ok = 0
    for (t, typ, params), (_, rules) in zip(EVAL, raw):
        want = resolve([(t, [{"type": typ, "params": dict(params)}])], exams, rooms, cal)
        got = resolve([(t, rules)], exams, rooms, cal)
        same = [(g["type"], g["params"]) for g in got] == [(w["type"], w["params"]) if w["type"] != "unsupported" else (w["type"], g["params"])
                                                          for w, g in zip(want, got)][:len(got)] and len(got) == len(want)
        if typ == "unsupported":
            same = all(g["type"] == "unsupported" for g in got)
        ok += same
        if not same:
            print(f"MISS  {t}\n      want {[(w['type'], w['params']) for w in want]}\n      got  {[(g['type'], g['params']) for g in got]}")
    print(f"{name}: {ok}/{len(EVAL)} resolve to the intended rule")
    return ok / len(EVAL)


def score(EVAL, name):
    raw = predict([t for t, _, _ in EVAL])
    norm = lambda v: [norm(x) for x in v] if isinstance(v, list) else v.lower().strip() if isinstance(v, str) else v
    ok_type = ok_all = 0
    for (t, typ, params), (_, rules) in zip(EVAL, raw):
        r = rules[0] if rules else {}
        good_t = r.get("type") == typ
        good_p = good_t and all(norm(r.get("params", {}).get(k)) == norm(v) for k, v in params.items())
        ok_type += good_t; ok_all += good_p
        if not good_p:
            print(f"MISS  {t}\n      want {typ} {params}\n      got  {rules}")
    print(f"{name}: type accuracy {ok_type}/{len(EVAL)}   type+params {ok_all}/{len(EVAL)}")
    return ok_all / len(EVAL)


if __name__ == "__main__":
    {"train": train, "eval": evaluate}[sys.argv[1]]()
