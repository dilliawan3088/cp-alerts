"""
tools/state_manager.py
Manages persistent state for the Bird Counter Automation.
State is stored in state.json at the project root by default.

For cloud deployments (e.g. Trigger.dev), set the STATE_FILE_PATH
environment variable to override the path (e.g. /tmp/state.json).
"""

import json
import os
import logging
from datetime import datetime

# Allow override via env var for cloud/serverless deployments
_default_state_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state.json")
STATE_FILE = os.environ.get("STATE_FILE_PATH", _default_state_file)

logger = logging.getLogger(__name__)

DEFAULT_STATE = {
    "last_processed_file": None,
    "previous_truck_end": None,
    "processed_files": []
}


def load_state() -> dict:
    """Load state from state.json. Creates file with defaults if it doesn't exist."""
    if not os.path.exists(STATE_FILE):
        logger.info("state.json not found — creating with defaults.")
        save_state(DEFAULT_STATE.copy())
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Ensure all required keys exist (in case schema evolves)
        for key, default_val in DEFAULT_STATE.items():
            if key not in state:
                state[key] = default_val
        return state
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read state.json: {e}. Resetting to defaults.")
        save_state(DEFAULT_STATE.copy())
        return DEFAULT_STATE.copy()


def save_state(state: dict) -> None:
    """Persist state dict to state.json."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.debug("State saved to state.json.")
    except OSError as e:
        logger.error(f"Failed to write state.json: {e}")
        raise


def is_file_processed(filename: str, state: dict) -> bool:
    """Return True if filename is already in the processed_files list."""
    return filename in state.get("processed_files", [])


def mark_file_processed(filename: str, last_timestamp: datetime, state: dict) -> dict:
    """
    Mark a file as processed:
      - Add its name to processed_files list
      - Update last_processed_file
      - Update previous_truck_end with the ISO-format last timestamp
    Returns the updated state dict (also mutates it in-place).
    """
    if filename not in state["processed_files"]:
        state["processed_files"].append(filename)

    state["last_processed_file"] = filename

    if last_timestamp is not None:
        if isinstance(last_timestamp, datetime):
            state["previous_truck_end"] = last_timestamp.isoformat()
        elif isinstance(last_timestamp, str):
            state["previous_truck_end"] = last_timestamp
        else:
            logger.warning(f"Unexpected timestamp type: {type(last_timestamp)}")

    return state
