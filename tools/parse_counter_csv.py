"""
tools/parse_counter_csv.py
Reads Autonics DAQMaster CSV/XLSX export files.

IMPORTANT:
  - The first 13 rows are a metadata header — skip them with skiprows=13.
  - Row 14 is the column header: Date, Time, Data
  - Date format: M/D/YYYY  (e.g. 3/11/2026)
  - Time column format: HH:MM:SS:mmm  (colon-separated, INCLUDING milliseconds)
  - Data column is a CUMULATIVE counter (running total, not per-second count)
"""

import os
import logging
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _parse_time_str(time_str: str):
    """
    Parse time string in HH:MM:SS:mmm format.
    Returns a timedelta from midnight, or None on failure.
    """
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) != 4:
            return None
        hours, minutes, seconds, millis = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        return timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=millis)
    except (ValueError, AttributeError):
        return None


def _parse_date_str(date_str: str):
    """Parse date string in M/D/YYYY format (e.g. 3/11/2026). Returns date or None."""
    try:
        return datetime.strptime(str(date_str).strip(), "%m/%d/%Y").date()
    except (ValueError, AttributeError):
        return None


def parse_counter_file(filepath: str) -> pd.DataFrame:
    """
    Parse an Autonics DAQMaster CSV or XLSX file.

    Skips the 13-row metadata header. Row 14 must contain column headers:
    Date, Time, Data.

    Returns a DataFrame with columns:
        - date        : str   (original date string)
        - time_str    : str   (original time string HH:MM:SS:mmm)
        - datetime    : datetime (combined date + time as Python datetime)
        - bird_count  : int   (cumulative count, numeric)

    Raises:
        FileNotFoundError: if filepath doesn't exist
        ValueError: if file format is unexpected
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext in (".xlsx", ".xls"):
            df_raw = pd.read_excel(filepath, skiprows=13, header=0, engine="openpyxl")
        elif ext == ".csv":
            # Try UTF-8 first, fall back to latin-1
            try:
                df_raw = pd.read_csv(filepath, skiprows=13, header=0, encoding="utf-8")
            except UnicodeDecodeError:
                df_raw = pd.read_csv(filepath, skiprows=13, header=0, encoding="latin-1")
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    except Exception as e:
        raise ValueError(f"Failed to read file {filepath}: {e}")

    # Normalize column names (strip whitespace, case-insensitive match)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    col_map = {c.lower(): c for c in df_raw.columns}

    required_cols = ["date", "time", "data"]
    for rc in required_cols:
        if rc not in col_map:
            raise ValueError(
                f"Expected column '{rc}' not found in {filepath}. "
                f"Found columns: {list(df_raw.columns)}"
            )

    date_col = col_map["date"]
    time_col = col_map["time"]
    data_col = col_map["data"]

    df = pd.DataFrame()
    df["date"] = df_raw[date_col].astype(str).str.strip()
    df["time_str"] = df_raw[time_col].astype(str).str.strip()

    # Convert bird count to numeric; coerce errors to NaN
    df["bird_count"] = pd.to_numeric(df_raw[data_col], errors="coerce")

    # Drop rows where time is missing or not parseable
    df = df[df["time_str"].notna() & (df["time_str"] != "") & (df["time_str"] != "nan")]

    # Build datetime column
    datetimes = []
    for _, row in df.iterrows():
        parsed_date = _parse_date_str(row["date"])
        parsed_time_delta = _parse_time_str(row["time_str"])
        if parsed_date is None or parsed_time_delta is None:
            datetimes.append(None)
        else:
            dt = datetime(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
            ) + parsed_time_delta
            datetimes.append(dt)

    df["datetime"] = datetimes

    # Drop rows where datetime couldn't be constructed
    before = len(df)
    df = df.dropna(subset=["datetime", "bird_count"])
    after = len(df)
    if before != after:
        logger.warning(f"Dropped {before - after} rows with unparseable date/time/count.")

    df["bird_count"] = df["bird_count"].astype(int)
    df = df.reset_index(drop=True)

    logger.info(
        f"Parsed {filepath}: {len(df)} rows, "
        f"date range {df['datetime'].min()} → {df['datetime'].max()}, "
        f"max birds = {df['bird_count'].max()}"
    )

    return df
