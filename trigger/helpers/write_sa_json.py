"""
trigger/helpers/write_sa_json.py

Called by the Trigger.dev scheduled task before running main.py.
Decodes the base64-encoded service account JSON from the
GOOGLE_SERVICE_ACCOUNT_JSON_B64 env var and writes it to the
path specified by SA_JSON_OUTPUT_PATH (default: /tmp/sa.json).
"""
import os
import base64
import sys

b64_data = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "")
output_path = os.environ.get("SA_JSON_OUTPUT_PATH", "/tmp/sa.json")

if not b64_data:
    print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON_B64 is not set.", file=sys.stderr)
    sys.exit(1)

try:
    json_bytes = base64.b64decode(b64_data)
    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"Service account JSON written to {output_path}")
except Exception as e:
    print(f"ERROR: Failed to decode/write service account JSON: {e}", file=sys.stderr)
    sys.exit(1)
