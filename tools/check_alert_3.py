"""
tools/check_alert_3.py
Alert 3: Excessive Gap Between Trucks

Fires when the period between the last recorded timestamp of the
PREVIOUS truck and the first recorded timestamp of the CURRENT truck
exceeds 20 minutes.

Requires persistent state (previous_truck_end from state.json).
Skips check on the very first file ever processed.
"""

import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

GAP_THRESHOLD_MINUTES = 20.0


def check_alert_3(df: pd.DataFrame, state: dict) -> dict:
    """
    Check inter-truck gap against threshold.

    Args:
        df    : parsed DataFrame from parse_counter_file()
        state : state dict from state_manager.load_state()
                Must contain key 'previous_truck_end' (ISO str or None)

    Returns:
        dict with keys:
            triggered           : bool
            gap_minutes         : float or None
            previous_truck_end  : str or None (ISO)
            new_truck_start     : str or None (ISO)
            is_first_file       : bool
    """
    result = {
        "triggered": False,
        "gap_minutes": None,
        "previous_truck_end": None,
        "new_truck_start": None,
        "is_first_file": False,
    }

    previous_truck_end_str = state.get("previous_truck_end")

    # First file ever — no previous truck to compare against
    if not previous_truck_end_str:
        result["is_first_file"] = True
        logger.info("Alert 3: first file ever processed — skipping gap check.")
        return result

    if df.empty:
        logger.warning("Alert 3: empty DataFrame — cannot determine truck start time.")
        return result

    # New truck start = first data row of current file
    new_truck_start = df["datetime"].iloc[0]
    result["new_truck_start"] = new_truck_start.isoformat()

    # Parse previous truck end
    try:
        previous_truck_end = datetime.fromisoformat(previous_truck_end_str)
    except (ValueError, TypeError) as e:
        logger.error(f"Alert 3: cannot parse previous_truck_end '{previous_truck_end_str}': {e}")
        return result

    result["previous_truck_end"] = previous_truck_end.isoformat()

    gap_seconds = (new_truck_start - previous_truck_end).total_seconds()
    gap_minutes = gap_seconds / 60.0
    result["gap_minutes"] = round(gap_minutes, 2)

    if gap_minutes < 0:
        logger.warning(
            f"Alert 3: negative gap ({gap_minutes:.1f} min) — "
            "possible clock error or files out of order. Skipping."
        )
        return result

    triggered = gap_minutes > GAP_THRESHOLD_MINUTES
    result["triggered"] = triggered

    if triggered:
        logger.warning(
            f"Alert 3 TRIGGERED: gap = {gap_minutes:.1f} min "
            f"(threshold: {GAP_THRESHOLD_MINUTES}) "
            f"prev_end={previous_truck_end}, new_start={new_truck_start}"
        )
    else:
        logger.info(
            f"Alert 3 OK: gap = {gap_minutes:.1f} min (threshold: {GAP_THRESHOLD_MINUTES})"
        )

    return result
