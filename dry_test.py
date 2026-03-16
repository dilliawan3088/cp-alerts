"""
dry_test.py — Offline dry test for all 3 alert checks.
Uses the generated sample CSV — no Google Drive or notifications needed.
Run from c:\Alerts: python dry_test.py
"""
import sys, os
sys.path.insert(0, r"c:\Alerts")

from tools.parse_counter_csv import parse_counter_file
from tools.check_alert_1 import check_alert_1
from tools.check_alert_2 import check_alert_2
from tools.check_alert_3 import check_alert_3
from tools.state_manager import load_state

SAMPLE = r"c:\Alerts\.tmp\CP202620260306173641.csv"

def section(title):
    print(f"\n{'═'*55}")
    print(f"  {title}")
    print(f"{'═'*55}")

def ok(label, value, expected=None):
    mark = "✅" if expected is None else ("✅" if value == expected else "❌")
    note = f" (expected: {expected})" if expected is not None and value != expected else ""
    print(f"  {mark}  {label}: {value}{note}")

# ── Parse ─────────────────────────────────────────────────────────────────────
section("STEP 1: Parse CSV")
df = parse_counter_file(SAMPLE)
ok("Rows parsed", len(df))
ok("Max bird count (total birds)", df["bird_count"].max(), 2828)
ok("Start datetime", str(df["datetime"].iloc[0]))
ok("End datetime",   str(df["datetime"].iloc[-1]))

duration_min = (df["datetime"].iloc[-1] - df["datetime"].iloc[0]).total_seconds() / 60
first_bird_row = df[df["bird_count"] > 0].iloc[0]
speed_duration = (df["datetime"].iloc[-1] - first_bird_row["datetime"]).total_seconds() / 60
ok("Duration first_bird→end (min)", round(speed_duration, 1))

# ── Alert 1 ───────────────────────────────────────────────────────────────────
section("STEP 2: Alert 1 — Low Unloading Speed")
a1 = check_alert_1(df)
ok("Triggered", a1["triggered"], True)
ok("Speed (birds/min)", a1["speed"])
ok("Total birds", a1["total_birds"], 2828)
ok("Total minutes", a1["total_minutes"])
ok("Start time", a1["start_time"])
ok("End time",   a1["end_time"])

# ── Alert 2 ───────────────────────────────────────────────────────────────────
section("STEP 3: Alert 2 — Counting Break Detected")
breaks = check_alert_2(df)
ok("Number of breaks found", len(breaks))
if breaks:
    b = breaks[0]
    ok("Triggered", b["triggered"], True)
    ok("Break at count", b["bird_count"], 2090)
    ok("Break start", b["break_start"])
    ok("Break end",   b["break_end"])
    ok("Duration (min)", b["duration_minutes"])
else:
    print("  ❌  No breaks found!")

# ── Alert 3 ───────────────────────────────────────────────────────────────────
section("STEP 4: Alert 3 — Inter-Truck Gap (first file)")
state = load_state()
# Force fresh state (no previous truck)
test_state_fresh = {"last_processed_file": None, "previous_truck_end": None, "processed_files": []}
a3_first = check_alert_3(df, test_state_fresh)
ok("is_first_file", a3_first["is_first_file"], True)
ok("Triggered (should be False)", a3_first["triggered"], False)
print()

# Alert 3 — Simulate a 25-minute gap (should trigger)
section("STEP 5: Alert 3 — Simulated 25-min gap (should trigger)")
from datetime import datetime, timedelta
fake_prev_end = df["datetime"].iloc[0] - timedelta(minutes=25)
test_state_gap = {
    "last_processed_file": "prev_truck.csv",
    "previous_truck_end": fake_prev_end.isoformat(),
    "processed_files": ["prev_truck.csv"],
}
a3_gap = check_alert_3(df, test_state_gap)
ok("Triggered", a3_gap["triggered"], True)
ok("Gap minutes", a3_gap["gap_minutes"], 25.0)

# Alert 3 — Simulate a 15-minute gap (should NOT trigger)
section("STEP 6: Alert 3 — Simulated 15-min gap (should NOT trigger)")
fake_prev_end2 = df["datetime"].iloc[0] - timedelta(minutes=15)
test_state_nogap = {
    "last_processed_file": "prev_truck.csv",
    "previous_truck_end": fake_prev_end2.isoformat(),
    "processed_files": ["prev_truck.csv"],
}
a3_nogap = check_alert_3(df, test_state_nogap)
ok("Triggered", a3_nogap["triggered"], False)
ok("Gap minutes", a3_nogap["gap_minutes"], 15.0)

# ── Summary ───────────────────────────────────────────────────────────────────
section("SUMMARY")
all_pass = (
    a1["triggered"] == True and
    a1["speed"] < 60 and
    len(breaks) >= 1 and
    breaks[0]["bird_count"] == 2090 and
    breaks[0]["duration_minutes"] >= 10 and
    a3_first["is_first_file"] == True and
    a3_gap["triggered"] == True and
    a3_nogap["triggered"] == False
)
if all_pass:
    print("  ✅  ALL TESTS PASSED — Alert logic is working correctly!")
else:
    print("  ❌  SOME TESTS FAILED — review output above.")
print()
