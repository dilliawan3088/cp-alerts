---
description: Monitor Google Drive for new bird counter CSV files, analyze unloading data, and send Email + WhatsApp alerts
---

# Bird Counter Monitor — Workflow SOP

**WAT Framework | Version 1.0 | March 2026**

---

## Objective

Continuously poll a Google Drive folder for new Autonics DAQMaster CSV files.
For each new file, parse the bird count data and run three alert checks.
Send Email + WhatsApp notifications for any triggered alerts.
Persist state between runs so no file is ever double-processed.

---

## Trigger

- **Default mode**: Continuous polling loop, sleeping `POLL_INTERVAL_SECONDS` (default: 90) between cycles.
- **Single-cycle mode**: Pass `--once` flag to `main.py` to run exactly one poll cycle (useful for testing and cron-based scheduling).
- **Future**: Google Drive webhook / Pub/Sub can replace polling for near-real-time triggers.

---

## Required Inputs / Credentials

| Variable | Description |
|---|---|
| `GDRIVE_FOLDER_ID` | Google Drive folder ID where DAQMaster saves CSV files |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to Service Account JSON key (read-only Drive access) |
| `SMTP_HOST` | SMTP relay host (e.g. smtp.gmail.com) |
| `SMTP_PORT` | SMTP port (typically 587 for TLS) |
| `SMTP_USER` | Sender email address |
| `SMTP_PASSWORD` | Email app password or SMTP secret |
| `ALERT_EMAIL_TO` | Comma-separated list of alert recipient emails |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | Twilio sandbox / registered WhatsApp sender (whatsapp:+1...) |
| `WHATSAPP_RECIPIENT` | Recipient WhatsApp number (whatsapp:+92...) |
| `POLL_INTERVAL_SECONDS` | Seconds to wait between Drive polls (recommended: 60–120) |

All stored in `.env` file at project root. Never commit this file.

---

## Execution Sequence

### Phase 1 — Fetch New Files

**Tool**: `tools/fetch_gdrive_csv.py` → `fetch_new_csvs(processed_files)`

1. Authenticate with Google Drive using Service Account credentials.
2. List all files in `GDRIVE_FOLDER_ID`.
3. Filter out filenames already in `state.processed_files`.
4. Download new files to `.tmp/` directory.
5. Return list of local file paths, sorted chronologically by filename.

**On error**: Log the error, skip this cycle. Exponential backoff on rate limits (up to 5 retries).

---

### Phase 2 — Parse CSV

**Tool**: `tools/parse_counter_csv.py` → `parse_counter_file(filepath)`

1. Read file (CSV or XLSX). **Skip the first 14 rows** — these are DAQMaster metadata.
2. Row 15 is the column header row: `Date`, `Time`, `Data`.
3. Parse `Time` column using custom format `HH:MM:SS:mmm` (four colon-separated parts).
4. Convert `Data` column to integer (cumulative bird count).
5. Combine `Date` + `Time` into a `datetime` object per row.
6. Drop rows where `Time` or `Data` is NaN.
7. Return clean `DataFrame` with columns: `date`, `time_str`, `datetime`, `bird_count`.

**Critical notes**:
- `Data` is a **cumulative counter** (always increasing). Last value = total birds.
- Do NOT treat Data as per-second counts.
- If file has no parseable data rows, log warning and skip alerts for this file.

---

### Phase 3 — Run Alert Checks

#### Alert 1 — Low Unloading Speed
**Tool**: `tools/check_alert_1.py` → `check_alert_1(df)`

- Find first row where `bird_count > 0` → `start_time`
- Last row → `end_time`, `total_birds = max(bird_count)`
- `speed = total_birds / total_minutes`
- **Trigger if `speed < 60 birds/min`**
- Returns: `{triggered, speed, total_birds, total_minutes, start_time, end_time, warning}`

#### Alert 2 — Counting Break Detected
**Tool**: `tools/check_alert_2.py` → `check_alert_2(df)`

- Only check rows where `bird_count >= 100` (prerequisite threshold)
- Group consecutive rows with identical `bird_count` values
- For each group: `duration = last_timestamp - first_timestamp`
- **Trigger if `duration >= 10 minutes`**
- Multiple breaks per file are possible — return all
- Returns: `[{triggered, bird_count, break_start, break_end, duration_minutes}, ...]`

#### Alert 3 — Excessive Gap Between Trucks
**Tool**: `tools/check_alert_3.py` → `check_alert_3(df, state)`

- `new_truck_start` = first row's `datetime` in current file
- `previous_truck_end` = from `state.json` (set after processing previous file)
- **Skip on first file ever (no previous state)**
- `gap_minutes = (new_truck_start - previous_truck_end).total_seconds() / 60`
- **Trigger if `gap > 20 minutes`**
- Returns: `{triggered, gap_minutes, previous_truck_end, new_truck_start, is_first_file}`

---

### Phase 4 — Send Notifications

For each triggered alert, send BOTH email and WhatsApp.

**Email Tool**: `tools/send_email_alert.py` → `send_email_alert(alert_type, alert_data, filename)`
- Sends HTML-formatted email to all `ALERT_EMAIL_TO` recipients
- Returns `{sent, error}`

**WhatsApp Tool**: `tools/send_whatsapp_alert.py` → `send_whatsapp_alert(alert_type, alert_data, filename)`
- Sends plain-text message with emoji formatting via Twilio
- Returns `{sent, error}`

**On notification failure**: Log the error but **do not block** file processing or state updates.

---

### Phase 5 — Update State

**Tool**: `tools/state_manager.py`

1. Call `mark_file_processed(filename, last_timestamp, state)` — adds file to `processed_files`, saves `previous_truck_end`.
2. Call `save_state(state)` — persists to `state.json`.
3. Optionally clean `.tmp/` directory of processed files.

---

## Error Handling Rules

| Error Type | Behavior |
|---|---|
| Drive auth failure | Log error, abort cycle, retry on next poll |
| Drive rate limit | Exponential backoff (2^n seconds, max 5 retries) |
| File download failure | Skip that file, log, continue with others |
| CSV parse failure | Log error, skip file, do not mark as processed |
| Email send failure | Log error, continue — do NOT block state update |
| WhatsApp send failure | Log error, continue — do NOT block state update |
| state.json corrupt | Reset to empty defaults, log warning |

---

## Edge Cases

| Scenario | Handling |
|---|---|
| **First file ever** | Skip Alert 3. Save last timestamp as baseline for next truck. |
| **Empty CSV (all zeros)** | Log warning. Skip Alert 1 and 2. Still save timestamp for Alert 3. |
| **Multiple new files** | Process in chronological order (sort by filename). Run full alert suite for each. |
| **Counter reset mid-file** | `parse_counter_file` detects if Data value decreases. Use max before reset as subtotal. |
| **Midnight crossing** | Full datetime (Date + Time combined) handles day boundaries correctly. |
| **Duplicate file** | `state.processed_files` list prevents re-processing. |
| **Files arrive simultaneously** | Sort by filename (contains timestamp). Process sequentially. |
| **Negative gap (Alert 3)** | Log as clock error or ordering issue. Do not trigger alert. |
