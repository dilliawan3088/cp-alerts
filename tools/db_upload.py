"""
tools/db_upload.py
Handles uploading alert results to the NeonDB bird_counter_alerts table.
"""

import os
import json
import logging
import psycopg2
from psycopg2.extras import Json, execute_values
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def upload_alert_to_neon(filename: str, alert_type: str, bird_count: int, metrics: dict):
    """
    Connects to Neon PostgreSQL and inserts a record into bird_counter_alerts.
    """
    db_url = os.getenv("NEON_DATABASE_URL")
    if not db_url:
        logger.warning("NEON_DATABASE_URL not set. Skipping DB upload.")
        return False

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        insert_query = """
            INSERT INTO bird_counter_alerts (filename, alert_type, bird_count, metrics, triggered_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        cur.execute(insert_query, (
            filename,
            alert_type,
            bird_count,
            Json(metrics),
            datetime.now()
        ))

        conn.commit()
        cur.close()
        logger.info(f"Successfully uploaded {alert_type} alert for {filename} to NeonDB.")
        return True

    except Exception as e:
        logger.error(f"Failed to upload alert to NeonDB: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def upload_raw_data_to_neon(filename: str, df):
    """
    Uploads all rows from the parsed DataFrame to the counter_log_raw table in batches.
    """
    db_url = os.getenv("NEON_DATABASE_URL")
    if not db_url:
        return False

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Prepare parameters for batch insert: (filename, datetime, bird_count)
        data_to_insert = [
            (filename, row['datetime'], int(row['bird_count']))
            for _, row in df.iterrows()
        ]

        insert_query = """
            INSERT INTO counter_log_raw (filename, datetime, bird_count)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        execute_values(cur, insert_query, data_to_insert)

        conn.commit()
        cur.close()
        logger.info(f"Successfully uploaded {len(data_to_insert)} raw rows for {filename} to NeonDB.")
        return True

    except Exception as e:
        logger.error(f"Failed to upload raw data to NeonDB: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
