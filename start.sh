#!/bin/sh
# Start the Exam Planner and open it in the browser.
cd "$(dirname "$0")"
(sleep 1.5; xdg-open http://localhost:8000 >/dev/null 2>&1) &
exec .venv/bin/python server.py
