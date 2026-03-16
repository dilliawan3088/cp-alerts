"""Quick connection test for Google Drive credentials."""
import os, sys, json

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

sa_path_rel = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
sa_path = os.path.join(PROJECT_ROOT, sa_path_rel)

# Verify JSON
with open(sa_path) as f:
    sa = json.load(f)
print("Service Account JSON : OK")
print(f"  project_id         : {sa['project_id']}")
print(f"  client_email       : {sa['client_email']}")

# Test Drive authentication
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    sa_path,
    scopes=["https://www.googleapis.com/auth/drive.readonly"]
)
service = build("drive", "v3", credentials=creds, cache_discovery=False)

# List files in folder
folder_id = os.getenv("GDRIVE_FOLDER_ID", "")
results = service.files().list(
    q=f"'{folder_id}' in parents and trashed=false",
    fields="files(id, name, createdTime)",
    orderBy="name",
    pageSize=20
).execute()

files = results.get("files", [])
print(f"\nDrive folder access  : OK")
print(f"  Folder ID          : {folder_id}")
print(f"  Files found        : {len(files)}")
for f in files:
    print(f"    - {f['name']}")
if not files:
    print("  (folder is empty — no CSV files uploaded yet)")

print("\nAll credentials verified OK. System is ready to run.")
