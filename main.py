#!/usr/bin/env python3
"""
main.py — Bird Counter Automation Orchestrator

Polls Google Drive for new Autonics DAQMaster CSV files,
runs 3 alert checks on each, sends Email + WhatsApp notifications,
and persists state between runs.

Usage:
    python main.py           # continuous loop (uses POLL_INTERVAL_SECONDS)
    python main.py --once    # single poll cycle (for testing / cron)
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

# ── Project imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from tools.state_manager import (
    load_state,
    save_state,
    is_file_processed,
    mark_file_processed,
)
from tools.fetch_gdrive_csv import fetch_new_csvs, move_file_to_processed
from tools.parse_counter_csv import parse_counter_file
from tools.check_alert_1 import check_alert_1
from tools.check_alert_2 import check_alert_2
from tools.check_alert_3 import check_alert_3
from tools.send_whatsapp_alert import send_whatsapp_alert
from tools.db_upload import upload_alert_to_neon, upload_raw_data_to_neon

# ── Logging setup ────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(__file__), "bird_counter.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")


# ── Helper: send both email and WhatsApp for a triggered alert ────────────────
def notify_all(alert_type: str, alert_data: dict, filename: str):
    """
    Send WhatsApp notification for a triggered alert.
    Errors are logged but never raise.
    """
    logger.info(f"Sending notifications for {alert_type} — file: {filename}")

    try:
        result = send_whatsapp_alert(alert_type, alert_data, filename)
        if not result["sent"]:
            logger.error(f"WhatsApp failed ({alert_type}): {result['error']}")
    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp ({alert_type}): {e}")


# ── Core: process a single CSV file ──────────────────────────────────────────
def process_file(filepath: str, state: dict) -> dict:
    """
    Parse a single CSV and run all 3 alert checks.
    Returns updated state dict. Saves state after success.
    Never crashes — all errors are caught and logged.
    """
    filename = os.path.basename(filepath)
    logger.info(f"━━━ Processing: {filename} ━━━")
    alerts_fired = []

    # ── Step 1: Parse CSV ────────────────────────────────────────────────────
    try:
        df = parse_counter_file(filepath)
    except Exception as e:
        logger.error(f"Parse failed for {filename}: {e}. Skipping file.")
        return state  # Do NOT mark as processed — retry next cycle

    if df.empty:
        logger.warning(f"{filename}: DataFrame empty after parsing. Skipping alerts.")
        # Still mark as processed so we don't loop on a corrupt file
        last_ts = None
    else:
        last_ts = df["datetime"].iloc[-1]
        # Upload all raw rows to the DB for the dashboard
        upload_raw_data_to_neon(filename, df)

    # ── Step 2: Alert 1 ──────────────────────────────────────────────────────
    try:
        a1 = check_alert_1(df)
        if a1.get("triggered"):
            alerts_fired.append("Alert1-LowSpeed")
            notify_all("alert_1", a1, filename)
            upload_alert_to_neon(filename, "Speed", a1.get("total_birds", 0), a1)
        if a1.get("warning"):
            logger.warning(f"Alert 1 warning: {a1['warning']}")
    except Exception as e:
        logger.error(f"Alert 1 check failed for {filename}: {e}")

    # ── Step 3: Alert 2 ──────────────────────────────────────────────────────
    try:
        breaks = check_alert_2(df)
        for i, brk in enumerate(breaks, 1):
            if brk.get("triggered"):
                alerts_fired.append(f"Alert2-Break#{i}")
                notify_all("alert_2", brk, filename)
                upload_alert_to_neon(filename, "Break", brk.get("bird_count", 0), brk)
    except Exception as e:
        logger.error(f"Alert 2 check failed for {filename}: {e}")

    # ── Step 4: Alert 3 ──────────────────────────────────────────────────────
    try:
        a3 = check_alert_3(df, state)
        if a3.get("triggered"):
            alerts_fired.append("Alert3-TruckGap")
            notify_all("alert_3", a3, filename)
            upload_alert_to_neon(filename, "Gap", 0, a3)
        if a3.get("is_first_file"):
            logger.info("Alert 3: first file — gap check skipped.")
    except Exception as e:
        logger.error(f"Alert 3 check failed for {filename}: {e}")

    # ── Step 5: Update state ──────────────────────────────────────────────────
    state = mark_file_processed(filename, last_ts, state)
    save_state(state)

    # ── Summary for this file ─────────────────────────────────────────────────
    if alerts_fired:
        logger.warning(f"✔ {filename} processed — ALERTS FIRED: {', '.join(alerts_fired)}")
    else:
        logger.info(f"✔ {filename} processed — No alerts triggered.")

    return state


# ── Core: one complete poll cycle ─────────────────────────────────────────────
def run_once():
    """
    Execute a single poll cycle:
      1. Load state
      2. Fetch new files from Drive
      3. Process each file
      4. Log summary
    """
    logger.info("═══════════════ Poll Cycle Starting ═══════════════")
    state = load_state()

    # Fetch new files (limit per cycle to avoid OOM)
    try:
        new_files = fetch_new_csvs(state.get("processed_files", []), limit=10)
    except Exception as e:
        logger.error(f"fetch_new_csvs failed: {e}. Aborting cycle.")
        return

    if not new_files:
        logger.info("No new files found. Cycle complete.")
        return

    # Process each file in chronological order (already sorted by fetch_new_csvs)
    for filepath in new_files:
        filename = os.path.basename(filepath)
        try:
            state = process_file(filepath, state)
            # Move the file to Processed/ on Google Drive as permanent state
            move_file_to_processed(filename)
        except Exception as e:
            logger.error(f"Unhandled error processing {filepath}: {e}")

    logger.info("═══════════════ Poll Cycle Complete ════════════════")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Bird Counter Automation — monitors Google Drive for DAQMaster CSVs"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit (default: continuous loop)",
    )
    args = parser.parse_args()

    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "90"))

    logger.info("🐦 Bird Counter Automation starting up.")
    logger.info(f"Mode: {'single-cycle' if args.once else 'continuous loop'}")
    if not args.once:
        logger.info(f"Poll interval: {poll_interval} seconds")

    if args.once:
        run_once()
    else:
        while True:
            try:
                run_once()
            except KeyboardInterrupt:
                logger.info("Interrupted by user. Shutting down.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")

            logger.info(f"Sleeping {poll_interval}s until next cycle...")
            time.sleep(poll_interval)

    logger.info("🐦 Bird Counter Automation stopped.")


if __name__ == "__main__":
    main()
