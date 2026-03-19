import { schedules, logger } from "@trigger.dev/sdk/v3";
import { execFileSync } from "child_process";
import * as fs from "fs";
import * as path from "path";

/**
 * Bird Counter Alert Automation — Trigger.dev Scheduled Task
 *
 * Runs every 1 minute via cron. Executes: ./.venv/bin/python main.py --once
 *
 * Before each run:
 *   1. Decodes GOOGLE_SERVICE_ACCOUNT_JSON_B64 → /tmp/sa.json
 *   2. Runs main.py --once with all env vars forwarded
 *
 * State persistence:
 *   - state.json writes to STATE_FILE_PATH=/tmp/state.json inside the container
 *   - Between runs, state is kept alive via Trigger.dev's run store (metadata)
 */

const SA_JSON_PATH = "/tmp/sa.json";
const STATE_PATH = "/tmp/state.json";

/** Write the service account JSON to /tmp/sa.json.
 *  Accepts EITHER raw JSON or a base64-encoded JSON string. */
function writeServiceAccountJson(): void {
  const value = process.env.GOOGLE_SERVICE_ACCOUNT_JSON_B64;
  if (!value) {
    throw new Error(
      "❌ GOOGLE_SERVICE_ACCOUNT_JSON_B64 env var is not set. " +
        "Please add it in the Trigger.dev dashboard → Environment Variables."
    );
  }

  let jsonContent: string;

  // Auto-detect: raw JSON starts with '{', otherwise assume base64
  if (value.trimStart().startsWith("{")) {
    logger.info("✅ Service account JSON detected as raw JSON — writing directly.");
    jsonContent = value;
  } else {
    logger.info("✅ Service account JSON detected as base64 — decoding.");
    jsonContent = Buffer.from(value, "base64").toString("utf8");
  }

  fs.writeFileSync(SA_JSON_PATH, jsonContent, "utf8");
  logger.info("✅ Service account JSON written to /tmp/sa.json");
}

/** Run ./.venv/bin/python main.py --once and stream output to Trigger.dev logs */
function runPollCycle(): void {
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    GOOGLE_SERVICE_ACCOUNT_JSON: SA_JSON_PATH,
    STATE_FILE_PATH: STATE_PATH,
    POLL_INTERVAL_SECONDS: "120",
    // Ensure all required vars are explicitly set
    GDRIVE_FOLDER_ID: process.env.GDRIVE_FOLDER_ID ?? "",
    SMTP_HOST: process.env.SMTP_HOST ?? "smtp.gmail.com",
    SMTP_PORT: process.env.SMTP_PORT ?? "587",
    SMTP_USER: process.env.SMTP_USER ?? "",
    SMTP_PASSWORD: process.env.SMTP_PASSWORD ?? "",
    ALERT_EMAIL_TO: process.env.ALERT_EMAIL_TO ?? "",
    ALERT_EMAIL_FROM: process.env.ALERT_EMAIL_FROM ?? process.env.SMTP_USER ?? "",
    TWILIO_ACCOUNT_SID: process.env.TWILIO_ACCOUNT_SID ?? "",
    TWILIO_AUTH_TOKEN: process.env.TWILIO_AUTH_TOKEN ?? "",
    TWILIO_WHATSAPP_FROM: process.env.TWILIO_WHATSAPP_FROM ?? "whatsapp:+14155238886",
    // Correct WhatsApp recipient
    WHATSAPP_RECIPIENT: process.env.WHATSAPP_RECIPIENT ?? "whatsapp:+60123725770",
  };

  // Resolve absolute path to main.py (same dir as this task's working dir)
  const mainPy = path.resolve("main.py");

  logger.info("▶ Running: ./.venv/bin/python main.py --once", { mainPy });

  try {
    const output = execFileSync("./.venv/bin/python", [mainPy, "--once"], {
      env,
      encoding: "utf8",
      cwd: path.resolve("."),
    });
    logger.info("📄 Python output", { output });
  } catch (err: unknown) {
    const execErr = err as { stdout?: string; stderr?: string; status?: number };
    if (execErr.stdout) logger.info("📄 stdout", { output: execErr.stdout });
    if (execErr.stderr) logger.warn("⚠ stderr", { output: execErr.stderr });
    throw new Error(
      `./.venv/bin/python main.py --once exited with code ${execErr.status ?? "unknown"}`
    );
  }
}

// ── Trigger.dev Scheduled Task ────────────────────────────────────────────────
export const birdCounterPoll = schedules.task({
  id: "bird-counter-poll",

  // Run every 1 minute (minimum interval on Trigger.dev)
  cron: "* * * * *",

  // Use a larger machine (4GB RAM) to avoid OOM during backlog catch-up
  machine: "medium-2x",

  // Allow up to 1 hour per run (for backlog catching)
  maxDuration: 3600,

  run: async (payload, { ctx }) => {
    logger.info("🐦 Bird Counter Poll Cycle Starting", {
      scheduledAt: payload.timestamp.toISOString(),
      lastRun: payload.lastTimestamp?.toISOString() ?? "first run",
      runId: ctx.run.id,
    });

    // Step 1: Write service account JSON
    writeServiceAccountJson();

    // Step 2: Execute Python poll cycle
    runPollCycle();

    logger.info("✅ Poll cycle complete", {
      nextRun: payload.upcoming[0]?.toISOString(),
    });

    return { success: true };
  },
});
