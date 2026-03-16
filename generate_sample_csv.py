"""
Generate a sample DAQMaster CSV file matching the exact format described in AlertsPlan.txt.

File: CP202620260306173641.csv
Simulates a truck that:
  - Starts loading at 17:36:42 on 2026-03-06
  - Ends at 18:45:24
  - Total birds = 2828
  - Has a 14.3-minute flat break at count 2090 (Alert 2 trigger)
  - Speed = ~41.2 birds/min (Alert 1 trigger)
"""

import os
import sys
from datetime import datetime, timedelta

OUTPUT_DIR = r"c:\Alerts\.tmp"
FILENAME = "CP202620260306173641.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, FILENAME)

DATE_STR = "2026-03-06"
START_DT = datetime(2026, 3, 6, 17, 36, 42)

# 14-row DAQMaster metadata header (exact columns don't matter)
HEADER = "\n".join([
    "Device Name,CP2026",
    "Channel Count,1",
    "Recording Mode,Continuous",
    "Sample Rate,1S",
    "Scale,1",
    "Unit,Count",
    "Description,Bird Counter",
    "Firmware Version,1.20",
    "Hardware Version,2.0",
    "Serial Number,20261234",
    "Start Date,2026-03-06",
    "Start Time,17:36:42",
    "Stop Date,2026-03-06",
    "Stop Time,18:45:24",
])

# Build data rows: one row per second
rows = []
current_dt = START_DT
cumulative = 0

# Phase 1: 17:36:42 → 18:18:12 (ramp up to 2090 birds — 2490 seconds)
phase1_end = datetime(2026, 3, 6, 18, 18, 12)
phase1_duration_secs = int((phase1_end - START_DT).total_seconds())

# Rate to reach 2090 birds in phase1_duration_secs seconds
# 2090 birds / 2490 sec ≈ 0.839 birds/sec
for i in range(phase1_duration_secs + 1):
    cumulative = int(2090 * i / phase1_duration_secs)
    dt = START_DT + timedelta(seconds=i)
    t = dt.strftime("%H:%M:%S") + ":000"
    rows.append(f"{DATE_STR},{t},{cumulative}")
    current_dt = dt

# Phase 2: Flat break — 18:18:12 → 18:32:30 (858 seconds of no change)
flat_start = datetime(2026, 3, 6, 18, 18, 12)
flat_end = datetime(2026, 3, 6, 18, 32, 30)
flat_secs = int((flat_end - flat_start).total_seconds())

for i in range(flat_secs + 1):
    dt = flat_start + timedelta(seconds=i)
    t = dt.strftime("%H:%M:%S") + ":000"
    rows.append(f"{DATE_STR},{t},2090")
    current_dt = dt

# Phase 3: 18:32:30 → 18:45:24 ramp up to 2828 total birds
phase3_start = datetime(2026, 3, 6, 18, 32, 30)
phase3_end = datetime(2026, 3, 6, 18, 45, 24)
phase3_secs = int((phase3_end - phase3_start).total_seconds())
birds_remaining = 2828 - 2090  # = 738

for i in range(phase3_secs + 1):
    extra = int(birds_remaining * i / phase3_secs)
    cumulative = 2090 + extra
    dt = phase3_start + timedelta(seconds=i)
    t = dt.strftime("%H:%M:%S") + ":000"
    rows.append(f"{DATE_STR},{t},{cumulative}")
    current_dt = dt

# Write file
with open(output_path, "w", encoding="utf-8") as f:
    f.write(HEADER + "\n")
    f.write("Date,Time,Data\n")
    for row in rows:
        f.write(row + "\n")

total_rows = len(rows)
print(f"Created: {output_path}")
print(f"Total data rows: {total_rows}")
print(f"Start: {START_DT}  |  End: {current_dt}")
print(f"Max birds: 2828")
print(f"Flat break at 2090: {flat_secs}s ({flat_secs/60:.1f} min)")
