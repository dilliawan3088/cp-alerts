# 🐦 Bird Counter Automation

Automated alert system for monitoring truck unloading at a poultry processing plant.
Watches a Google Drive folder for new Autonics DAQMaster CSV files, analyzes bird count data,
and sends **Email + WhatsApp notifications** whenever an alert condition is triggered.

---

## 🏗 Directory Structure

```
Alerts/
├── workflows/
│   └── bird_counter_monitor.md    # Workflow SOP (full execution spec)
├── tools/
│   ├── state_manager.py           # Reads/writes state.json
│   ├── fetch_gdrive_csv.py        # Downloads new CSVs from Google Drive
│   ├── parse_counter_csv.py       # Parses DAQMaster CSV (skips 14-row header)
│   ├── check_alert_1.py           # Alert: Low unloading speed
│   ├── check_alert_2.py           # Alert: Counting break mid-unload
│   ├── check_alert_3.py           # Alert: Excessive gap between trucks
│   ├── send_email_alert.py        # Sends HTML email via SMTP
│   └── send_whatsapp_alert.py     # Sends WhatsApp message via Twilio
├── .env                           # Credentials (never commit this)
├── .env.example                   # Template — copy to .env and fill in
├── .tmp/                          # Downloaded CSVs (auto-created)
├── state.json                     # Persistent state (auto-created)
├── bird_counter.log               # Runtime log file (auto-created)
├── main.py                        # Main orchestrator
├── requirements.txt               # Python dependencies
└── README.md
```

---

## ⚙️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in all values. See `.env.example` for all required keys.

### 3. Google Drive — Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable the **Google Drive API**
3. Create a **Service Account** → Generate a JSON key
4. Save the JSON key file and set `GOOGLE_SERVICE_ACCOUNT_JSON=path/to/key.json` in `.env`
5. Share your Drive folder with the service account email (Viewer permission)
6. Copy the folder ID from the Drive URL and set `GDRIVE_FOLDER_ID=...` in `.env`

### 4. Email (Gmail)

1. Use a Gmail account with [2-Step Verification enabled](https://myaccount.google.com/security)
2. Generate an **App Password** (16-character code)
3. Set `SMTP_USER=your@gmail.com` and `SMTP_PASSWORD=your_app_password` in `.env`

### 5. WhatsApp (Twilio)

1. Create a [Twilio account](https://www.twilio.com)
2. Activate the **WhatsApp sandbox** (or register a number)
3. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `WHATSAPP_RECIPIENT` in `.env`

---

## 🚀 How to Run

### Continuous loop (production)

```bash
python main.py
```

Polls Google Drive every `POLL_INTERVAL_SECONDS` seconds (default: 90). Runs until stopped with Ctrl+C.

### Single cycle (testing / cron)

```bash
python main.py --once
```

Runs one poll cycle and exits. Ideal for scheduled execution via Task Scheduler or cron.

---

## 🚨 The Three Alerts

| Alert | What It Detects | Threshold |
|---|---|---|
| **Alert 1 — Low Speed** | Truck unloading too slowly | < 60 birds/minute |
| **Alert 2 — Counting Break** | Counter stops mid-unload | ≥ 10 min flat after 100+ birds |
| **Alert 3 — Truck Gap** | Too much idle time between trucks | > 20 min gap (cross-file) |

All alerts send **both Email and WhatsApp** simultaneously.  
Notification failures are logged but never block file processing.

---

## 📁 CSV File Format

Files are exported by Autonics DAQMaster. Structure:

- **Rows 1–14**: Metadata header (automatically skipped)
- **Row 15**: Column names — `Date`, `Time`, `Data`
- **Row 16+**: Data rows — one per second of recording

| Column | Format | Example |
|---|---|---|
| Date | YYYY-MM-DD | 2026-03-06 |
| Time | HH:MM:SS:mmm | 17:42:23:869 |
| Data | Integer (cumulative) | 1523 |

> ⚠ **Important**: `Data` is a **cumulative running total**, not a per-second count.
> The final value = total birds for the truck.

---

## 📋 Logs

Runtime logs are written to both:
- **Console** (stdout)
- **`bird_counter.log`** file in the project root

---

## 🔒 Security Notes

- Never commit `.env`, `state.json`, or your Service Account JSON key to version control.
- Add them to `.gitignore`:
  ```
  .env
  state.json
  *.json
  .tmp/
  bird_counter.log
  ```
