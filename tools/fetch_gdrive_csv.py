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
from dotenv import load_dotenv

load_dotenv()

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
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
    query = (
        f"'{folder_id}' in parents and trashed = false "
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


def fetch_new_csvs(processed_files: List[str]) -> List[str]:
    """
    Main entry point.
    Lists Drive folder, filters out already-processed files,
    downloads new ones to .tmp/, returns sorted list of local paths.

    Args:
        processed_files: list of filenames already processed (from state)

    Returns:
        List of local file paths, sorted chronologically by filename.
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
    logger.info(f"{len(new_files)} new file(s) to process.")

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
