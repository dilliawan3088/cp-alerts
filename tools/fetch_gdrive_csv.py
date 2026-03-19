"""
tools/fetch_gdrive_csv.py
Authenticates with Google Drive via Service Account and downloads
new CSV files from the configured folder to .tmp/.
"""

import os
import io
import time
import logging
from typing import List
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")


def _get_drive_service():
    """Build and return an authenticated Google Drive service client."""
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise EnvironmentError("GOOGLE_SERVICE_ACCOUNT_JSON is not set in .env")

    credentials = service_account.Credentials.from_service_account_file(
        sa_json, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return service


def _list_files_in_folder(service, folder_id: str, retries: int = 5) -> list:
    """List ALL CSV/XLSX files in the given Drive folder, handling pagination."""
    # Only fetch files from the last 24 hours to avoid processing the massive backlog
    # and hitting Gmail daily limits. 
    yesterday_iso = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    
    query = (
        f"'{folder_id}' in parents and trashed = false "
        f"and createdTime > '{yesterday_iso}' "
        f"and (mimeType = 'text/csv' or mimeType = 'application/vnd.ms-excel' "
        f"or mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
    )
    all_files = []
    page_token = None

    while True:
        for attempt in range(retries):
            try:
                results = (
                    service.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name, createdTime, modifiedTime)",
                        orderBy="name",
                        pageSize=1000,
                        pageToken=page_token,
                    )
                    .execute()
                )
                all_files.extend(results.get("files", []))
                page_token = results.get("nextPageToken")
                break  # success — exit retry loop
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Drive list error (attempt {attempt+1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
        else:
            raise RuntimeError(f"Failed to list files from Drive folder after {retries} attempts.")

        if not page_token:
            break  # no more pages

    logger.info(f"Drive pagination complete — {len(all_files)} total file(s) found.")
    return all_files


def _download_file(service, file_id: str, file_name: str, retries: int = 5) -> str:
    """Download a single file from Drive to .tmp/ directory."""
    os.makedirs(TMP_DIR, exist_ok=True)
    dest_path = os.path.join(TMP_DIR, file_name)

    for attempt in range(retries):
        try:
            request = service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            with open(dest_path, "wb") as f:
                f.write(buffer.getvalue())

            logger.info(f"Downloaded: {file_name} → {dest_path}")
            return dest_path
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"Download error for {file_name} (attempt {attempt+1}): {e}. Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Failed to download {file_name} after {retries} attempts.")


def fetch_new_csvs(processed_files: List[str], limit: int = 10) -> List[str]:
    """
    Main entry point.
    Lists Drive folder root only (not Processed/ subfolder), downloads new ones.
    NOTE: processed_files parameter kept for backward compatibility but no longer
    used — the Drive folder structure itself tracks what has been processed.
    """
    folder_id = os.getenv("GDRIVE_FOLDER_ID")
    if not folder_id:
        raise EnvironmentError("GDRIVE_FOLDER_ID is not set in .env")

    os.makedirs(TMP_DIR, exist_ok=True)

    try:
        service = _get_drive_service()
    except Exception as e:
        logger.error(f"Google Drive authentication failed: {e}")
        raise

    all_files = _list_files_in_folder(service, folder_id)
    logger.info(f"Found {len(all_files)} file(s) in Drive folder.")

    new_files = [f for f in all_files if f["name"] not in processed_files]
    logger.info(f"{len(new_files)} total new file(s) found in Drive.")

    # Sort new files by name before slicing to ensure chronological order
    new_files.sort(key=lambda f: f["name"])

    # Limit downloads to prevent OOM
    if len(new_files) > limit:
        logger.info(f"Limiting download to first {limit} file(s) for this cycle.")
        new_files = new_files[:limit]

    downloaded_paths = []
    for file_meta in new_files:
        try:
            path = _download_file(service, file_meta["id"], file_meta["name"])
            downloaded_paths.append(path)
        except Exception as e:
            logger.error(f"Skipping {file_meta['name']} due to download error: {e}")

    # Sort chronologically by filename (filenames contain timestamps like CP202620260306173641)
    downloaded_paths.sort(key=lambda p: os.path.basename(p))
    return downloaded_paths


def get_or_create_processed_folder(service, parent_folder_id: str) -> str:
    """Find or create a 'Processed' subfolder inside the Drive folder. Returns its ID."""
    query = (
        f"'{parent_folder_id}' in parents and trashed = false "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and name = 'Processed'"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get("files", [])
    if folders:
        return folders[0]["id"]

    # Create the folder
    folder_metadata = {
        "name": "Processed",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    logger.info("Created 'Processed' subfolder in Google Drive.")
    return folder["id"]


def move_file_to_processed(file_name: str) -> bool:
    """
    Move a file from the main Drive folder to the 'Processed' subfolder.
    This replaces state.json as the permanent memory of which files are done.
    Returns True if successful, False otherwise.
    """
    folder_id = os.getenv("GDRIVE_FOLDER_ID")
    if not folder_id:
        logger.error("GDRIVE_FOLDER_ID not set — cannot move file.")
        return False

    try:
        service = _get_drive_service()
    except Exception as e:
        logger.error(f"Drive auth failed during move: {e}")
        return False

    # Find the file by name in the parent folder
    query = f"'{folder_id}' in parents and trashed = false and name = '{file_name}'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if not files:
        logger.warning(f"move_file_to_processed: '{file_name}' not found in Drive root.")
        return False

    file_id = files[0]["id"]
    processed_folder_id = get_or_create_processed_folder(service, folder_id)

    # Move: add new parent, remove old parent
    service.files().update(
        fileId=file_id,
        addParents=processed_folder_id,
        removeParents=folder_id,
        fields="id, parents",
    ).execute()
    logger.info(f"Moved '{file_name}' → Processed/ folder.")
    return True
