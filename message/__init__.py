"""Message module (Step 2.1: database initialization)"""

from .db import init_message_history_db, get_message_db_path, get_data_dir

__all__ = [
    "init_message_history_db",
    "get_message_db_path",
    "get_data_dir",
]