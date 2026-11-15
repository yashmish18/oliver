"""Writes the sample files in this folder. Run: .venv/bin/python samples/make_samples.py"""
import csv, random
from pathlib import Path

HERE = Path(__file__).parent
R = random.Random(42)
FIRST = "Aarav Aditi Arjun Ananya Dev Diya Ishaan Kavya Kabir Meera Nikhil Neha Om Pooja Rahul Riya Rohan Sanya Tanvi Vihaan Yash Zara".split()
LAST = "Sharma Verma Gupta Singh Mehta Jain Agarwal Mishra Rathore Choudhary Joshi Saxena".split()
COHORTS = [  # (roll prefix, semester, how many, courses (code, name, type))
    ("2026BTech", 1, 110, [("AS1108", "Applied Physics", "Core"), ("AS1109", "Calculus and Ordinary Differential Equations", "Core"),
                           ("CS1139", "Programming-I", "Core"), ("ES1115", "Environmental Science and Sustainability", "Core"),
                           ("EE1118", "Fundamentals of Electrical and Electronics Engineering", "Core")]),
    ("2025BTech", 3, 90, [("CS1131", "Data Structure and Algorithms", "Core"), ("CS1133", "Database Management System", "Core"),
                          ("CS1134", "Computer Organization and Architecture", "Core"), ("LS1108", "Essentials of Business Management", "Core"),
                          ("CS1142", "Discrete Mathematics", "Core")]),
    ("2024BTech", 5, 60, [("CS1224", "Artificial Intelligence", "Core"), ("CS1261", "Principles of Cloud computing", "Elective"),
                          ("CS1243", "Big Data Analytics with Hadoop and Spark", "Elective"), ("EE1232", "Digital Image Processing", "Elective"),
                          ("FA1201", "Computational Finance", "Elective")]),
]
HEAD = ["Student Session", "Student Roll Number", "Student Name", "Subject Code", "Subject Name", "Subject Type"]

rows = []
for prefix, sem, n, courses in COHORTS:
    for i in range(1, n + 1):
        roll, name = f"{prefix}{i:03d}", f"{R.choice(FIRST)} {R.choice(LAST)}"
        core = [c for c in courses if c[2] == "Core"]
        mine = core + R.sample([c for c in courses if c[2] == "Elective"], k=min(2, len(courses) - len(core)))
        rows += [[f"SES0001-SEMESTER {sem}", roll, name, c, nm, t] for c, nm, t in mine]
for roll in ("2024BTech007", "2024BTech031"):                      # two backlog students re-taking a first-year paper
    rows.append(["SES0001-SEMESTER 5", roll, "Backlog Student", "AS1109", "Calculus and Ordinary Differential Equations", "Backlog"])

with open(HERE / "enrollment_sample.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([HEAD] + rows)
with open(HERE / "enrollment_semicolon_windows.csv", "w", newline="", encoding="cp1252") as f:   # how some Excel installs save CSV
    csv.writer(f, delimiter=";").writerows([HEAD] + rows)
try:
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Enrollment"
    ws.append(["JK Lakshmipat University - Sample enrollment (title row, ignored)"]); ws.append([])
    for r in [HEAD] + rows:
        ws.append(r)
    wb.save(HERE / "enrollment_sample.xlsx")
except ImportError:
    pass

names = [f"Dr. {a} {b}" for a, b in zip(R.sample(FIRST, 18), (LAST * 2)[:18])]
with open(HERE / "invigilators_sample.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["name", "unavailable"])
    for i, n in enumerate(names):
        w.writerow([n, "2026-12-02;2026-12-03" if i % 6 == 0 else ""])

(HERE / "room_LAB-201.csv").write_text("S,S,S,,S,S,S\nS,S,S,,S,S,S\nS,x,S,,S,x,S\nS,S,S,,S,S,S\n,,,,S,S,S\n", encoding="utf-8")
(HERE / "rules_sample.txt").write_text("""Max one exam per day for every student.
25.12.2026 is a holiday.
04.12.2026 has only the 10 AM session.
Sem I papers should ideally be in the morning.
CS1139 Programming-I before CS1131.
LS1108 and ES1115 share a question paper.
Do not seat more than 90 percent capacity anywhere.
Serve tea in every room.
""", encoding="utf-8")
(HERE / "rules_sample_with_clash.txt").write_text("""CS1261 and CS1243 share a question paper.
""", encoding="utf-8")   # some students take both, so the planner must refuse and say why
print(f"{len(rows)} enrollment rows, {len({r[1] for r in rows})} students, {len({r[3] for r in rows})} exams")
