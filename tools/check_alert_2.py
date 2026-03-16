"""
tools/check_alert_2.py
Alert 2: Counting Break Detected

Fires when the cumulative counter stays flat (no new birds) for 10+ consecutive
minutes AFTER the count has already reached 100+ birds.

There can be MULTIPLE break events in a single file — all are returned.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

MIN_BIRD_COUNT = 100          # prerequisite: ignore flats before this threshold
MIN_BREAK_MINUTES = 10.0      # minimum flat duration to trigger alert


def check_alert_2(df: pd.DataFrame) -> list:
    """
    Scan for counting breaks (flat periods ≥ 10 minutes after 100+ birds).

    Args:
        df: parsed DataFrame from parse_counter_file()

    Returns:
        List of dicts, one per break event:
            triggered       : True  (always True for items in the list)
            bird_count      : int   (cumulative count where break occurred)
            break_start     : str   (ISO datetime of first flat row)
            break_end       : str   (ISO datetime of last flat row)
            duration_minutes: float
        Returns empty list if no breaks found.
    """
    if df.empty:
        logger.warning("Alert 2: empty DataFrame.")
        return []

    # Only consider rows where cumulative count has reached the prerequisite threshold
    df_qualified = df[df["bird_count"] >= MIN_BIRD_COUNT].copy()

    if df_qualified.empty:
        logger.info(f"Alert 2: count never reached {MIN_BIRD_COUNT} — no break check needed.")
        return []

    # Group consecutive rows with the same bird_count value
    # Use a "group change" flag: True whenever bird_count changes from the previous row
    df_qualified = df_qualified.reset_index(drop=True)
    df_qualified["group"] = (
        df_qualified["bird_count"] != df_qualified["bird_count"].shift()
    ).cumsum()

    breaks = []
    for group_id, group_df in df_qualified.groupby("group"):
        if len(group_df) < 2:
            continue  # Single row — no meaningful duration

        bird_count = int(group_df["bird_count"].iloc[0])
        break_start_dt = group_df["datetime"].iloc[0]
        break_end_dt = group_df["datetime"].iloc[-1]

        duration_seconds = (break_end_dt - break_start_dt).total_seconds()
        duration_minutes = duration_seconds / 60.0

        if duration_minutes >= MIN_BREAK_MINUTES:
            event = {
                "triggered": True,
                "bird_count": bird_count,
                "break_start": break_start_dt.isoformat(),
                "break_end": break_end_dt.isoformat(),
                "duration_minutes": round(duration_minutes, 2),
            }
            breaks.append(event)
            logger.warning(
                f"Alert 2 TRIGGERED: flat at count {bird_count} "
                f"from {break_start_dt} to {break_end_dt} "
                f"({duration_minutes:.1f} min)"
            )

    if not breaks:
        logger.info("Alert 2: no counting breaks detected.")

    return breaks
