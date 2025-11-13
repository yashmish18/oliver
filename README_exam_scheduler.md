# Intelligent Exam Room Allocation Tool

## Overview

`exam_scheduler.py` creates flexible, mixed-course seating plans for exam sessions using enrollment and room capacity CSVs. It supports three allocation strategies:

- **Smart Randomized Mix** – shuffle courses to create unpredictable, multi-course rooms.
- **Course-Wise Split** – dedicate rooms to individual courses to keep cohorts together.
- **Balanced Utilization** – fill rooms with the largest remaining course pools to maximize seat usage.

The script prompts for exam dates, slots per day, slot timings, maximum courses per room, and optional course/semester filters. It prints readable summaries for every slot and can export combined reports in CSV, JSON, and (optionally) Excel.

## Prerequisites

- Python 3.9+
- Optional: `pandas` and `openpyxl` (needed only for Excel export)

## Input Files

Place CSVs in the working directory (or provide full paths when prompted):

- `rooms_config.csv` **or** `room.csv`
- `processed_enrollment.csv`
- `End Term Date Sheet Draft.csv` (optional, used for filtering if merged manually)

The loader ignores `layout`, `rows`, and `cols_per_row` columns, focusing on `room_id`, `room_name`, `capacity`, and `building`.

## Running the Script

```bash
python exam_scheduler.py
```

Follow the interactive prompts:

1. Confirm paths to the rooms and enrollment CSVs.
2. Choose an allocation strategy.
3. Provide optional filters (semesters/courses).
4. Enter exam days, slots per day, slot timings.
5. Specify how many distinct courses to mix per room.
6. (Optional) Enter a random seed for reproducible allocation.
7. Decide whether to export the summary files.

## Outputs

When summary export is enabled, the tool creates an `output/` directory with:

- `exam_schedule_summary.csv` – compact per-room snapshot for every slot.
- `exam_schedule_summary.json` – structured data (per date, per slot, per room).
- `exam_schedule_summary.xlsx` – Excel version when `pandas` & `openpyxl` are installed.

All summaries include room utilization, courses seated, semesters represented, and a fully-utilized indicator.

## Testing Notes

The scheduler is interactive; automated testing is not wired up. To validate locally:

1. Prepare small sample CSVs based on the provided layouts.
2. Run `python exam_scheduler.py`.
3. Step through prompts, verifying that the terminal summary and exported files match expectations (e.g., room capacities aren't exceeded).

For deterministic runs during QA, supply a numeric random seed when prompted.

