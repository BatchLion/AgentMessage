"""Chat history database initialization and management (Step 2.1)
- Database path: $AGENTMESSAGE_PUBLIC_DATABLOCKS/chat_history.db
- Table: chat_history
- Fields:
  - message_id: unique message ID
  - timestamp: Beijing time (UTC+8) string (format: YYYY-MM-DD HH:MM:SS)
  - sender_did: sender DID
  - receiver_dids: list of receiver DIDs (JSON array string)
  - group_id: hash computed from the set of sender DID and receiver DIDs, used to uniquely identify 1:1/group chat
  - message_data: message payload (JSON object string: text, code, images, audio, video, file info, etc.)
  - mention_dids: list of mentioned receiver DIDs (JSON array string)
  - read_status: read status per receiver (JSON object string; key=DID, value=boolean)

Notes:
- This file only initializes the database and table schema; it does not implement message writing logic.
- If AGENTMESSAGE_PUBLIC_DATABLOCKS is not set, an exception is raised. Please define this environment variable in the MCP configuration file.
"""

import os
import sqlite3
from pathlib import Path


def get_data_dir() -> Path:
    """Return the data directory path: $AGENTMESSAGE_PUBLIC_DATABLOCKS"""
    public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
    if not public_dir_env:
        raise EnvironmentError("AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable is not set. Please define it in the MCP configuration file.")
    data_dir = Path(public_dir_env)
    if data_dir.exists() and not data_dir.is_dir():
        raise NotADirectoryError(f"AGENTMESSAGE_PUBLIC_DATABLOCKS points to a non-directory: {str(data_dir)}")
    return data_dir


def get_chat_db_path() -> Path:
    """Return the full path to $AGENTMESSAGE_PUBLIC_DATABLOCKS/chat_history.db"""
    return get_data_dir() / "chat_history.db"


def init_chat_history_db() -> Path:
    """Initialize $AGENTMESSAGE_PUBLIC_DATABLOCKS/chat_history.db and necessary tables and indexes"""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = get_chat_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Create chat_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                message_id   TEXT PRIMARY KEY,
                timestamp    TEXT NOT NULL,
                sender_did   TEXT NOT NULL,
                receiver_dids TEXT NOT NULL, -- JSON array string
                group_id     TEXT NOT NULL,
                message_data  TEXT NOT NULL, -- JSON object string
                mention_dids  TEXT NOT NULL, -- JSON array string
                read_status   TEXT NOT NULL DEFAULT '{}' -- JSON object string; record read status for each receiver
            )
        """)

        # Check whether the read_status column needs to be added (migrate existing database)
        cursor.execute("PRAGMA table_info(chat_history)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'read_status' not in columns:
            cursor.execute("ALTER TABLE chat_history ADD COLUMN read_status TEXT NOT NULL DEFAULT '{}'")

        # Common indexes (SQLite requires separate CREATE INDEX statements; cannot inline them in CREATE TABLE)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_history_group_id_idx ON chat_history(group_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_history_sender_did_idx ON chat_history(sender_did)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_history_timestamp_idx ON chat_history(timestamp)"
        )

        conn.commit()
    finally:
        conn.close()

    return db_path