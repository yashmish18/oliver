import csv
import json
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore


# -----------------------------
# Data Models
# -----------------------------


@dataclass
class Room:
    room_id: str
    room_name: str
    capacity: int
    building: Optional[str] = None


@dataclass
class Student:
    roll_number: str
    name: str
    subject_code: str
    subject_name: str
    semester: str
    program: Optional[str] = None
    batch: Optional[str] = None
    site_code: Optional[str] = None


@dataclass
class RoomAssignment:
    room: Room
    students: List[Student]

    @property
    def utilization(self) -> float:
        if self.room.capacity <= 0:
            return 0.0
        return len(self.students) / self.room.capacity


# -----------------------------
# CSV Loading Helpers
# -----------------------------


def prompt_for_path(prompt: str, default: Optional[str] = None) -> Path:
    raw = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    if not raw and default:
        raw = default
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def load_rooms_from_csv(path: Path) -> List[Room]:
    rooms: List[Room] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"room_id", "room_name", "capacity"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing and {"room_id", "capacity"}.issubset(reader.fieldnames or []):
            # Accept files like room.csv that might have missing room_name column headers
            missing -= {"room_name"}
        if missing:
            raise ValueError(
                f"Rooms CSV missing required columns: {', '.join(sorted(missing))}"
            )
        for row in reader:
            try:
                capacity_raw = row.get("capacity") or row.get("Capacity") or row.get(
                    "capacitiy"
                )
                if capacity_raw is None:
                    continue
                capacity = int(float(capacity_raw))
            except (TypeError, ValueError):
                continue

            room_id = (row.get("room_id") or row.get("Room Number") or "").strip()
            if not room_id:
                continue

            room_name = (
                row.get("room_name")
                or row.get("Room Name")
                or row.get("room_id")
                or ""
            ).strip()

            building = (
                row.get("building") or row.get("Building") or row.get("Site Code")
            )
            rooms.append(
                Room(
                    room_id=room_id,
                    room_name=room_name or room_id,
                    capacity=capacity,
                    building=(building or "").strip() or None,
                )
            )
    if not rooms:
        raise ValueError(f"No rooms could be loaded from {path}")
    rooms.sort(key=lambda r: r.capacity, reverse=True)
    return rooms


def _normalize_semester(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return "UNKNOWN"
    return cleaned.upper()


def load_students_from_csv(path: Path) -> List[Student]:
    students: List[Student] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        # Determine mapping dynamically
        mappings = {
            "roll": [
                "Student Roll Number",
                "Roll Number",
                "Enrollment Number",
                "student_roll_number",
            ],
            "name": ["Student Name", "Name", "student_name"],
            "subject_code": ["Subject Code", "Course Code", "subject_code"],
            "subject_name": ["Subject Name", "Course Name", "subject_name"],
            "semester": ["Student Session", "Semester", "student_session"],
            "program": ["Program", "Programme"],
            "batch": ["Batch"],
            "site_code": ["Site Code", "Campus"],
        }

        def find_column(possible: Sequence[str]) -> Optional[str]:
            for option in possible:
                if option in fieldnames:
                    return option
            return None

        column_map = {key: find_column(options) for key, options in mappings.items()}
        required_keys = ("roll", "name", "subject_code", "subject_name", "semester")
        missing_required = [key for key in required_keys if not column_map[key]]
        if missing_required:
            pretty_missing = ", ".join(missing_required)
            raise ValueError(
                f"Students CSV missing required columns ({pretty_missing}) - "
                f"expected headers similar to processed_enrollment.csv layout."
            )

        for row in reader:
            try:
                roll_number = (row[column_map["roll"]]).strip()
                name = (row[column_map["name"]]).strip()
                subject_code = (row[column_map["subject_code"]]).strip()
                subject_name = (row[column_map["subject_name"]]).strip()
                semester = _normalize_semester(row[column_map["semester"]])
            except KeyError:
                continue

            if not (roll_number and subject_code):
                continue

            students.append(
                Student(
                    roll_number=roll_number,
                    name=name or "UNKNOWN",
                    subject_code=subject_code,
                    subject_name=subject_name or subject_code,
                    semester=semester,
                    program=(
                        row[column_map["program"]].strip()
                        if column_map["program"]
                        else None
                    ),
                    batch=(
                        row[column_map["batch"]].strip()
                        if column_map["batch"]
                        else None
                    ),
                    site_code=(
                        row[column_map["site_code"]].strip()
                        if column_map["site_code"]
                        else None
                    ),
                )
            )
    if not students:
        raise ValueError(f"No student records could be loaded from {path}")
    return students


# -----------------------------
# Allocation Logic
# -----------------------------


def group_students_by_course(
    students: Iterable[Student],
) -> Dict[str, List[Student]]:
    courses: Dict[str, List[Student]] = defaultdict(list)
    for student in students:
        course_key = course_identifier(student)
        courses[course_key].append(student)
    return courses


def course_identifier(student: Student) -> str:
    return f"{student.subject_code}|{student.subject_name}"


def split_course_key(course_key: str) -> Tuple[str, str]:
    code, name = course_key.split("|", 1)
    return code, name


def select_courses_for_room(
    algorithm: str,
    available_courses: List[str],
    course_pools: Dict[str, Deque[Student]],
    max_courses_per_room: int,
    rng: random.Random,
) -> List[str]:
    if not available_courses:
        return []

    if algorithm == "course-wise":
        return [
            max(
                available_courses,
                key=lambda key: len(course_pools[key]),
            )
        ]

    limit = max_courses_per_room if max_courses_per_room > 0 else 1
    if algorithm == "balanced":
        ordered = sorted(
            available_courses, key=lambda key: len(course_pools[key]), reverse=True
        )
        return ordered[:limit]

    # Smart randomized mix (default)
    limit = min(limit, len(available_courses))
    return rng.sample(available_courses, k=limit)


def allocate_room(
    room: Room,
    algorithm: str,
    max_courses_per_room: int,
    course_pools: Dict[str, Deque[Student]],
    rng: random.Random,
) -> RoomAssignment:
    available = [key for key, queue in course_pools.items() if queue]
    if not available:
        return RoomAssignment(room=room, students=[])

    selected_courses = select_courses_for_room(
        algorithm=algorithm,
        available_courses=available,
        course_pools=course_pools,
        max_courses_per_room=max_courses_per_room,
        rng=rng,
    )

    if not selected_courses:
        return RoomAssignment(room=room, students=[])

    if algorithm == "smart":
        rng.shuffle(selected_courses)
    elif algorithm == "balanced":
        # Already sorted by remaining population, but shuffle ties to avoid bias
        tied_groups: Dict[int, List[str]] = defaultdict(list)
        for key in selected_courses:
            tied_groups[len(course_pools[key])].append(key)
        randomized: List[str] = []
        for _, group in sorted(tied_groups.items(), reverse=True):
            rng.shuffle(group)
            randomized.extend(group)
        selected_courses = randomized

    assignment: List[Student] = []
    slots_remaining = room.capacity
    index = 0
    course_cycle = selected_courses.copy()

    while slots_remaining > 0 and course_cycle:
        course_key = course_cycle[index % len(course_cycle)]
        queue = course_pools[course_key]
        if queue:
            assignment.append(queue.popleft())
            slots_remaining -= 1
            index += 1
        else:
            course_cycle.pop(index % len(course_cycle))
            if not course_cycle:
                break
            if index >= len(course_cycle):
                index = 0

    return RoomAssignment(room=room, students=assignment)


def allocate_rooms_for_slot(
    rooms: Sequence[Room],
    students_for_slot: Dict[str, List[Student]],
    algorithm_type: str,
    max_courses_per_room: int,
    rng: random.Random,
) -> Tuple[List[RoomAssignment], Dict[str, List[Student]]]:
    course_pools: Dict[str, Deque[Student]] = {
        key: deque(students) for key, students in students_for_slot.items()
    }
    assignments: List[RoomAssignment] = []
    total_students = sum(len(queue) for queue in course_pools.values())
    if total_students == 0:
        return assignments, {}

    remaining_students_before = total_students
    for room in rooms:
        if sum(len(queue) for queue in course_pools.values()) == 0:
            break
        assignment = allocate_room(
            room=room,
            algorithm=algorithm_type,
            max_courses_per_room=max_courses_per_room,
            course_pools=course_pools,
            rng=rng,
        )
        if assignment.students:
            assignments.append(assignment)

    residual: Dict[str, List[Student]] = {
        key: list(queue) for key, queue in course_pools.items() if queue
    }

    if residual:
        assigned_total = remaining_students_before - sum(len(students) for students in residual.values())
        print(
            "⚠️  Warning: Not enough seats for all students in this slot. "
            f"Assigned {assigned_total} out of {remaining_students_before}. "
            "Consider adding more rooms or additional slots."
        )

    return assignments, residual


# -----------------------------
# Scheduling Pipeline
# -----------------------------


def prompt_algorithm_choice() -> str:
    options = {
        "1": ("Smart Randomized Mix", "smart"),
        "2": ("Course-Wise Split", "course-wise"),
        "3": ("Balanced Utilization", "balanced"),
    }
    print("\nSelect Algorithm Type:")
    for key, (label, _) in options.items():
        print(f"  {key}. {label}")
    while True:
        choice = input("Choice [1-3]: ").strip()
        if choice in options:
            return options[choice][1]
        print("Invalid selection. Please choose 1, 2, or 3.")


def prompt_int(prompt: str, minimum: int = 1, default: Optional[int] = None) -> int:
    while True:
        raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a valid integer.")
            continue
        if value < minimum:
            print(f"Value must be at least {minimum}.")
            continue
        return value


def prompt_list(prompt: str) -> List[str]:
    raw = input(f"{prompt} (comma separated, leave blank for all): ").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def prompt_exam_schedule() -> List[Dict[str, str]]:
    schedule: List[Dict[str, str]] = []
    num_days = prompt_int("How many exam days do you want to schedule?", minimum=1)
    for day_index in range(num_days):
        print(f"\nDay {day_index + 1}:")
        date_value = input("  Exam Date (e.g., 2025-05-18): ").strip()
        if not date_value:
            date_value = f"Day {day_index + 1}"
        slots_count = prompt_int("  Number of slots for this day?", minimum=1)
        for slot_index in range(slots_count):
            slot_name = input(
                f"    Slot {slot_index + 1} label (e.g., Morning): "
            ).strip() or f"Slot {slot_index + 1}"
            slot_time = input(
                "    Slot timing (e.g., 09:00 AM - 12:00 PM): "
            ).strip() or "TBD"
            schedule.append(
                {"date": date_value, "slot_name": slot_name, "slot_time": slot_time}
            )
    return schedule


def distribute_courses_across_slots(
    course_keys: Sequence[str], num_slots: int, rng: random.Random
) -> Dict[int, List[str]]:
    if num_slots <= 0:
        raise ValueError("Number of slots must be positive.")
    shuffled = list(course_keys)
    rng.shuffle(shuffled)
    mapping: Dict[int, List[str]] = {index: [] for index in range(num_slots)}
    for offset, course_key in enumerate(shuffled):
        slot_index = offset % num_slots
        mapping[slot_index].append(course_key)
    return mapping


def filter_students(
    students: Iterable[Student],
    allowed_semesters: Optional[Sequence[str]] = None,
    allowed_courses: Optional[Sequence[str]] = None,
) -> List[Student]:
    normalized_semesters = {sem.upper() for sem in allowed_semesters or []}
    normalized_courses = {course.upper() for course in allowed_courses or []}

    filtered: List[Student] = []
    for student in students:
        if normalized_semesters and student.semester.upper() not in normalized_semesters:
            continue
        if normalized_courses:
            candidate = {student.subject_code.upper(), student.subject_name.upper()}
            if candidate.isdisjoint(normalized_courses):
                continue
        filtered.append(student)
    return filtered


def summarize_assignments(
    exam_schedule: List[Dict[str, str]],
    slot_assignments: Dict[int, List[RoomAssignment]],
) -> List[Dict[str, object]]:
    summary: List[Dict[str, object]] = []
    for slot_index, slot in enumerate(exam_schedule):
        room_assignments = slot_assignments.get(slot_index, [])
        for assignment in room_assignments:
            courses = sorted(
                {
                    f"{student.subject_name} ({student.subject_code})"
                    for student in assignment.students
                }
            )
            semesters = sorted({student.semester for student in assignment.students})
            summary.append(
                {
                    "Exam Date": slot["date"],
                    "Slot": slot["slot_name"],
                    "Slot Timing": slot["slot_time"],
                    "Room Name": assignment.room.room_name,
                    "Room ID": assignment.room.room_id,
                    "Building": assignment.room.building or "",
                    "Total Capacity": assignment.room.capacity,
                    "Students Assigned": len(assignment.students),
                    "Courses Seated": ", ".join(courses) if courses else "",
                    "Semesters Seated": ", ".join(semesters) if semesters else "",
                    "Fully Utilized": "✅ Yes"
                    if len(assignment.students) >= assignment.room.capacity
                    else f"❌ No ({len(assignment.students)}/{assignment.room.capacity})",
                    "Utilization %": round(
                        100 * assignment.utilization, 2
                    ),
                }
            )
    return summary


def export_summary(summary: List[Dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "exam_schedule_summary.csv"
    json_path = output_dir / "exam_schedule_summary.json"
    excel_path = output_dir / "exam_schedule_summary.xlsx"

    if summary:
        fieldnames = list(summary[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary)
        print(f"✅ Summary CSV exported to {csv_path}")

        structured: Dict[str, Dict[str, object]] = {}
        for row in summary:
            slot_key = f"{row['Exam Date']}|{row['Slot']}"
            entry = structured.setdefault(
                slot_key,
                {
                    "exam_date": row["Exam Date"],
                    "slot_name": row["Slot"],
                    "slot_time": row["Slot Timing"],
                    "rooms": [],
                },
            )
            entry["rooms"].append(
                {
                    "room_id": row["Room ID"],
                    "room_name": row["Room Name"],
                    "building": row["Building"],
                    "capacity": row["Total Capacity"],
                    "students_assigned": row["Students Assigned"],
                    "courses": row["Courses Seated"],
                    "semesters": row["Semesters Seated"],
                    "fully_utilized": row["Fully Utilized"],
                    "utilization_percent": row["Utilization %"],
                }
            )
        with json_path.open("w", encoding="utf-8") as json_file:
            json.dump(list(structured.values()), json_file, indent=2)
        print(f"✅ Summary JSON exported to {json_path}")

        if pd is not None:
            try:
                dataframe = pd.DataFrame(summary)
                dataframe.to_excel(excel_path, index=False)
                print(f"✅ Summary Excel exported to {excel_path}")
            except Exception as exc:  # pragma: no cover - optional dependency failure
                print(
                    f"⚠️  Unable to export Excel file automatically ({exc}). "
                    "Install pandas + openpyxl to enable Excel export."
                )
        else:
            print(
                "ℹ️  Install pandas and openpyxl to enable Excel export "
                f"(skipped writing {excel_path})."
            )
    else:
        print("No assignments were generated; nothing to export.")


def print_summary_table(summary: List[Dict[str, object]]) -> None:
    if not summary:
        print("No room allocations were produced.")
        return

    grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = defaultdict(list)
    for row in summary:
        grouped[(row["Exam Date"], row["Slot"])].append(row)

    for (exam_date, slot_name), rows in grouped.items():
        print("\n" + "=" * 80)
        print(f"Exam Date: {exam_date} | Slot: {slot_name}")
        print("=" * 80)
        header = [
            "Room Name",
            "Room ID",
            "Capacity",
            "Assigned",
            "Courses Seated",
            "Semesters Seated",
            "Fully Utilized",
        ]
        print(f"{header[0]:<20} {header[1]:<10} {header[2]:<10} {header[3]:<10} {header[4]:<40} {header[5]:<20} {header[6]}")
        for row in rows:
            print(
                f"{row['Room Name']:<20} "
                f"{row['Room ID']:<10} "
                f"{row['Total Capacity']:<10} "
                f"{row['Students Assigned']:<10} "
                f"{row['Courses Seated']:<40} "
                f"{row['Semesters Seated']:<20} "
                f"{row['Fully Utilized']}"
            )
    print("\nFinished generating room allocation summary.")


# -----------------------------
# Main Entry Point
# -----------------------------


def main() -> None:
    print("🧠 Intelligent Exam Room Allocation\n")
    try:
        rooms_path = prompt_for_path(
            "Enter rooms CSV path", default="rooms_config.csv"
        )
    except FileNotFoundError:
        rooms_path = prompt_for_path("Enter rooms CSV path", default="room.csv")

    students_path = prompt_for_path(
        "Enter student enrollment CSV path", default="processed_enrollment.csv"
    )

    rooms = load_rooms_from_csv(rooms_path)
    students = load_students_from_csv(students_path)

    print(f"\nLoaded {len(rooms)} rooms and {len(students)} student-course enrollments.")

    allowed_semesters = prompt_list("Semesters to include (optional filter)")
    allowed_courses = prompt_list("Subject codes or names to include (optional filter)")

    filtered_students = filter_students(
        students,
        allowed_semesters=allowed_semesters,
        allowed_courses=allowed_courses,
    )
    print(f"Using {len(filtered_students)} enrollments after applying filters.")

    if not filtered_students:
        print("No students remain after filtering. Exiting.")
        return

    algorithm_type = prompt_algorithm_choice()

    max_courses_per_room = prompt_int(
        "How many courses should be assigned together in a single room?",
        minimum=1,
        default=3,
    )

    exam_schedule = prompt_exam_schedule()
    num_slots = len(exam_schedule)
    if num_slots == 0:
        print("No slots were defined. Exiting.")
        return

    seed_input = input("Optional random seed (leave blank for system random): ").strip()
    rng = random.Random()
    if seed_input:
        try:
            rng.seed(int(seed_input))
        except ValueError:
            rng.seed(seed_input)

    course_groups = group_students_by_course(filtered_students)
    slot_course_map = distribute_courses_across_slots(
        list(course_groups.keys()), num_slots=num_slots, rng=rng
    )

    slot_assignments: Dict[int, List[RoomAssignment]] = {}
    spillover_courses: Dict[str, List[Student]] = {}

    for slot_index, slot in enumerate(exam_schedule):
        assigned_course_keys = slot_course_map.get(slot_index, [])
        students_for_slot: Dict[str, List[Student]] = {}
        for key in assigned_course_keys:
            students_for_slot[key] = course_groups.get(key, []).copy()
        print(
            f"\nAllocating slot {slot_index + 1}/{num_slots} "
            f"({slot['date']} - {slot['slot_name']}): "
            f"{len(assigned_course_keys)} course(s)"
        )
        assignments, residual = allocate_rooms_for_slot(
            rooms=rooms,
            students_for_slot=students_for_slot,
            algorithm_type=algorithm_type,
            max_courses_per_room=max_courses_per_room,
            rng=rng,
        )
        slot_assignments[slot_index] = assignments
        if residual:
            spillover_courses.update(residual)

    if spillover_courses:
        total_unplaced = sum(len(students) for students in spillover_courses.values())
        print(
            f"\n⚠️  {total_unplaced} students could not be seated across the configured "
            "slots. Consider adding more slots or rooms."
        )

    summary = summarize_assignments(exam_schedule, slot_assignments)
    print_summary_table(summary)

    export = input("\nExport summary files? [Y/n]: ").strip().lower()
    if export in ("", "y", "yes"):
        output_dir = Path("output")
        export_summary(summary, output_dir=output_dir)
    else:
        print("Skipped exporting summary files.")


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")

