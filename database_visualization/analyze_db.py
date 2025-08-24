#!/usr/bin/env python3
"""
Analyze the message_history.db database structure and content
"""
import sqlite3
import json
from pathlib import Path
import os

def analyze_message_db():
    public_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
    data_dir = Path(public_env) if public_env else (Path(__file__).parent.parent / "data")
    db_path = data_dir / "message_history.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Get table schema
        print("=== DATABASE SCHEMA ===")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='message_history'")
        schema = cursor.fetchone()
        if schema:
            print(schema[0])
        
        print("\n=== TABLE INFO ===")
        cursor.execute("PRAGMA table_info(message_history)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"Column: {col[1]}, Type: {col[2]}, NotNull: {col[3]}, Default: {col[4]}")
        
        # Get indexes
        print("\n=== INDEXES ===")
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='message_history'")
        indexes = cursor.fetchall()
        for idx in indexes:
            print(f"Index: {idx[0]}")
            if idx[1]:
                print(f"  SQL: {idx[1]}")
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM message_history")
        count = cursor.fetchone()[0]
        print(f"\n=== RECORD COUNT ===")
        print(f"Total messages: {count}")
        
        if count > 0:
            # Get sample data
            print(f"\n=== SAMPLE DATA (first 3 records) ===")
            cursor.execute("SELECT * FROM message_history ORDER BY timestamp DESC LIMIT 3")
            rows = cursor.fetchall()
            
            for i, row in enumerate(rows, 1):
                print(f"\n--- Record {i} ---")
                print(f"Message ID: {row[0]}")
                print(f"Timestamp: {row[1]}")
                print(f"Sender DID: {row[2]}")
                print(f"Receiver DIDs: {row[3]}")
                print(f"Group ID: {row[4]}")
                print(f"Message Data: {row[5]}")
                print(f"Mention DIDs: {row[6]}")
                print(f"Read Status: {row[7]}")
            
            # Get statistics
            print(f"\n=== STATISTICS ===")
            cursor.execute("SELECT COUNT(DISTINCT sender_did) FROM message_history")
            unique_senders = cursor.fetchone()[0]
            print(f"Unique senders: {unique_senders}")
            
            cursor.execute("SELECT COUNT(DISTINCT group_id) FROM message_history")
            unique_groups = cursor.fetchone()[0]
            print(f"Unique groups: {unique_groups}")
            
            cursor.execute("SELECT sender_did, COUNT(*) as msg_count FROM message_history GROUP BY sender_did ORDER BY msg_count DESC")
            sender_stats = cursor.fetchall()
            print(f"\nMessages per sender:")
            for sender, count in sender_stats:
                print(f"  {sender}: {count} messages")
            
            cursor.execute("SELECT group_id, COUNT(*) as msg_count FROM message_history GROUP BY group_id ORDER BY msg_count DESC")
            group_stats = cursor.fetchall()
            print(f"\nMessages per group:")
            for group, count in group_stats:
                print(f"  {group}: {count} messages")
    
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_message_db()