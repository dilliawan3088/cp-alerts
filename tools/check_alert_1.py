"""
tools/check_alert_1.py
Alert 1: High Unloading Speed

Fires when the birds-per-minute rate for a truck is ABOVE 60.
Formula: speed = total_birds ÷ total_minutes (from first bird to last row)
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def check_alert_1(df: pd.DataFrame) -> dict:
    """
    Check if unloading speed is below threshold.

    Args:
        df: parsed DataFrame from parse_counter_file() with columns:
            datetime, bird_count, date, time_str

    Returns:
        dict with keys:
            triggered     : bool
            speed         : float (birds/min, None if no birds)
            total_birds   : int
            total_minutes : float
            start_time    : str (ISO)
            end_time      : str (ISO)
            warning       : str or None
    """
    result = {
        "triggered": False,
        "speed": None,
        "total_birds": 0,
        "total_minutes": 0.0,
        "start_time": None,
        "end_time": None,
        "warning": None,
    }

    if df.empty:
        result["warning"] = "DataFrame is empty — no data to analyze."
        logger.warning("Alert 1: empty DataFrame.")
        return result

    # Find first row where bird_count > 0
    birds_rows = df[df["bird_count"] > 0]

    if birds_rows.empty:
        result["warning"] = "No birds counted in this file (all zeros)."
        logger.info("Alert 1: no birds found — skipping.")
        return result

    start_row = birds_rows.iloc[0]
    end_row = df.iloc[-1]

    start_time = start_row["datetime"]
    end_time = end_row["datetime"]
    total_birds = int(end_row["bird_count"])  # cumulative counter — last value = total

    duration_seconds = (end_time - start_time).total_seconds()
    if duration_seconds <= 0:
        result["warning"] = "Start and end times are equal — cannot calculate speed."
        logger.warning("Alert 1: zero duration.")
        return result

    total_minutes = duration_seconds / 60.0
    speed = total_birds / total_minutes

    THRESHOLD = 60.0
    triggered = speed > THRESHOLD

    result.update({
        "triggered": triggered,
        "speed": round(speed, 2),
        "total_birds": total_birds,
        "total_minutes": round(total_minutes, 2),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "warning": None,
    })

    if triggered:
        logger.warning(
            f"Alert 1 TRIGGERED: {total_birds} birds in {total_minutes:.1f} min "
            f"= {speed:.1f} birds/min — ABOVE threshold ({THRESHOLD})"
        )
    else:
        logger.info(f"Alert 1 OK: {speed:.1f} birds/min (below or equal to threshold {THRESHOLD})")

    return result
