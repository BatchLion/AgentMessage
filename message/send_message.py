import os
import re
import json
import time
import asyncio
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from message.db import init_message_history_db
from identity.identity_manager import IdentityManager

async def _send_message(
    sender_did: str,
    receiver_dids: list[str],
    message_data: dict,
    wait_for_replies: bool = False, # - wait_for_replies: Whether to wait for replies from all receivers (default True)
    poll_interval: int = 5,# - poll_interval: Polling interval in seconds (default 5 seconds)
    timeout: int = 300 # - timeout: Timeout for waiting in seconds (default 300 seconds)
) -> dict:
    """
    Send message to server and store it in $AGENTMESSAGE_PUBLIC_DATABLOCKS/message_history.db
    """
    # Parameter validation
    if not isinstance(receiver_dids, list) or len(receiver_dids) == 0:
        return {
            "status": "error",
            "message": "receiver_dids cannot be empty and must be an array"
        }
    if not isinstance(message_data, dict):
        return {
            "status": "error",
            "message": "message_data must be an object"
        }
    
    # Get sender identity
    try:
        identity_manager = IdentityManager()
        if not identity_manager.has_identity():
            return {
                "status": "error",
                "message": "Local identity information not found, please register identity first through register_recall_id"
            }
        identity = identity_manager.load_identity()
        if not identity:
            return {
                "status": "error",
                "message": "Unable to load local identity information"
            }
        sender_did = identity.did
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to read sender identity: {str(e)}"
        }
    
    # New: Verify if all receiver_dids exist in identities.db
    try:
        public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
        if not public_dir_env:
            return {
                "status": "error",
                "message": "AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable not set, please add this environment variable definition in MCP configuration file"
            }
        id_db_path = Path(public_dir_env) / "identities.db"
        if not id_db_path.exists():
            return {
                "status": "error",
                "message": "identities.db not found",
                "expected_path": str(id_db_path)
            }
        
        # Query receiver DIDs existence in identities.db
        uniq_receivers = list(dict.fromkeys(receiver_dids))  # Remove duplicates while preserving order
        placeholders = ",".join("?" for _ in uniq_receivers)
        conn_ids = sqlite3.connect(id_db_path)
        try:
            cur = conn_ids.cursor()
            # Query existing DIDs in database
            cur.execute(
                f"SELECT did FROM identities WHERE did IN ({placeholders})",
                tuple(uniq_receivers),
            )
            existing_dids = {row[0] for row in cur.fetchall()}
            
            # Find non-existing DIDs
            missing_dids = [did for did in uniq_receivers if did not in existing_dids]
            
            if missing_dids:
                # If there are non-existing DIDs, get all identity records for verification
                cur.execute(
                    """
                    SELECT did, name, description, capabilities, created_at, updated_at
                    FROM identities
                    ORDER BY datetime(updated_at) DESC
                    """
                )
                all_rows = cur.fetchall()
                
                all_identities = []
                for did, name, description, capabilities_text, created_at, updated_at in all_rows:
                    try:
                        capabilities = json.loads(capabilities_text) if capabilities_text else []
                        if not isinstance(capabilities, list):
                            capabilities = []
                    except Exception:
                        capabilities = []
                    
                    all_identities.append({
                        "did": did,
                        "name": name,
                        "description": description,
                        "capabilities": capabilities,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    })
                
                return {
                    "status": "error",
                    "message": f"There are {len(missing_dids)} DIDs in the receiver list that do not exist in the identities.db database. Please select the correct receiver DIDs from the identity records below and resend the message.",
                    "missing_dids": missing_dids,
                    "receiver_dids": receiver_dids,
                    "identities": all_identities,
                    "database_path": str(id_db_path)
                }
        finally:
            conn_ids.close()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to verify receiver DIDs: {str(e)}",
            "receiver_dids": receiver_dids
        }

    # New: Exclude sender from receiver list validation
    if sender_did in receiver_dids:
        try:
            public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
            if not public_dir_env:
                return {
                    "status": "error",
                    "message": "AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable not set, please add this environment variable definition in MCP configuration file"
                }
            id_db_path = Path(public_dir_env) / "identities.db"
            if not id_db_path.exists():
                return {
                    "status": "error",
                    "message": "identities.db not found",
                    "expected_path": str(id_db_path),
                    "receiver_dids": receiver_dids
                }
            
            # Query receivers (including sender) identity records in identities.db
            uniq_receivers = list(dict.fromkeys(receiver_dids))
            placeholders = ",".join("?" for _ in uniq_receivers)
            conn_ids = sqlite3.connect(id_db_path)
            try:
                cur = conn_ids.cursor()
                cur.execute(
                    f"""
                    SELECT did, name, description, capabilities, created_at, updated_at
                    FROM identities
                    WHERE did IN ({placeholders})
                    """,
                    tuple(uniq_receivers),
                )
                rows = cur.fetchall()
            finally:
                conn_ids.close()
            
            identities = []
            for did, name, description, capabilities_text, created_at, updated_at in rows:
                try:
                    capabilities = json.loads(capabilities_text) if capabilities_text else []
                    if not isinstance(capabilities, list):
                        capabilities = []
                except Exception:
                    capabilities = []
                identities.append({
                    "did": did,
                    "name": name,
                    "description": description,
                    "capabilities": capabilities,
                    "created_at": created_at,
                    "updated_at": updated_at,
                })
            
            return {
                "status": "error",
                "message": "Receiver list contains sender (you are sending a message to yourself). Please confirm the receiver identity information based on the returned identity records and remove your own DID from the receiver list before retrying.",
                "receiver_dids": receiver_dids,
                "sender_did": sender_did,
                "identities": identities,
                "database_path": str(id_db_path)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to validate receiver list: {str(e)}",
                "receiver_dids": receiver_dids,
                "sender_did": sender_did
            }
    
    # Generate timestamp and ID
    now_utc = datetime.now(timezone.utc)
    beijing_time = now_utc.astimezone(timezone(timedelta(hours=8)))
    timestamp_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    epoch_ms = int(now_utc.timestamp() * 1000)
    
    # Calculate group_id (based on DID set hash)
    unique_dids = sorted(set([sender_did] + receiver_dids))
    group_basis = "|".join(unique_dids)
    group_hash = hashlib.sha256(group_basis.encode("utf-8")).hexdigest()[:16]
    group_id = f"grp_{group_hash}"
    
    # Generate message_id (timestamp + content hash)
    try:
        msg_payload_preview = json.dumps(message_data, ensure_ascii=False, sort_keys=True)
    except Exception:
        msg_payload_preview = str(message_data)
    mid_basis = f"{sender_did}|{','.join(sorted(receiver_dids))}|{epoch_ms}|{msg_payload_preview}"
    message_id = f"msg_{epoch_ms}_{hashlib.sha256(mid_basis.encode('utf-8')).hexdigest()[:12]}"
    
    # Parse @ mentions
    mention_dids: list[str] = []
    try:
        # Extract text candidate fields
        text_candidates = []
        if "text" in message_data and isinstance(message_data["text"], str):
            text_candidates.append(message_data["text"])
        if "caption" in message_data and isinstance(message_data["caption"], str):
            text_candidates.append(message_data["caption"])
        if "message" in message_data and isinstance(message_data["message"], str):
            text_candidates.append(message_data["message"])
        if "content" in message_data and isinstance(message_data["content"], str):
            text_candidates.append(message_data["content"])
        combined_text = "\n".join(text_candidates)
        
        # @all
        if re.search(r"(^|\s)@all(\b|$)", combined_text):
            mention_dids = list(dict.fromkeys(receiver_dids))  # Remove duplicates while preserving order
        else:
            # First match based on DID
            mentioned = set()
            for did in receiver_dids:
                if f"@{did}" in combined_text:
                    mentioned.add(did)
            
            # Then match based on name (read receiver name mapping from identities.db)
            try:
                public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
                if public_dir_env:
                    id_db_path = Path(public_dir_env) / "identities.db"
                    if id_db_path.exists():
                        conn_ids = sqlite3.connect(id_db_path)
                        try:
                            cursor_ids = conn_ids.cursor()
                            placeholders = ",".join("?" for _ in receiver_dids)
                            cursor_ids.execute(
                                f"SELECT did, name FROM identities WHERE did IN ({placeholders})",
                                tuple(receiver_dids),
                            )
                            did_to_name = {row[0]: row[1] for row in cursor_ids.fetchall()}
                            name_to_did = {name: did for did, name in did_to_name.items() if isinstance(name, str)}
                            for name, did in name_to_did.items():
                                if f"@{name}" in combined_text:
                                    mentioned.add(did)
                        finally:
                            conn_ids.close()
            except Exception:
                # Name resolution failure does not affect sending
                pass
            
            mention_dids = list(mentioned)
    except Exception:
        mention_dids = []
    
    # Write to message_history.db
    try:
        # Initialize database (internally checks if AGENTMESSAGE_PUBLIC_DATABLOCKS is set)
        db_path = init_message_history_db()
        
        # Initialize read_status: mark all receivers as unread (false)
        read_status = {did: False for did in receiver_dids}
        
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO message_history
                (message_id, timestamp, sender_did, receiver_dids, group_id, message_data, mention_dids, read_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    timestamp_str,
                    sender_did,
                    json.dumps(receiver_dids, ensure_ascii=False),
                    group_id,
                    json.dumps(message_data, ensure_ascii=False),
                    json.dumps(mention_dids, ensure_ascii=False),
                    json.dumps(read_status, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        
        # Base return data
        base_data = {
            "message_id": message_id,
            "timestamp": timestamp_str,
            "sender_did": sender_did,
            "receiver_dids": receiver_dids,
            "group_id": group_id,
            "message_data": message_data,
            "mention_dids": mention_dids,
            "read_status": read_status,
        }
        
        # If not waiting for replies, return directly
        if not wait_for_replies:
            return {
                "status": "success",
                "message": "Message sent",
                "data": base_data,
                "database_path": str(db_path),
            }
        
        # Wait for replies functionality
        start_time = time.time()
        replies = []
        
        while time.time() - start_time < timeout:
            # Poll to check if all receivers have replied
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.cursor()
                # Find new messages sent later than the original message in the same group
                cursor.execute(
                    """
                    SELECT message_id, timestamp, sender_did, message_data
                    FROM message_history
                    WHERE group_id = ? 
                    AND timestamp > ?
                    AND sender_did IN ({})
                    ORDER BY timestamp ASC
                    """.format(",".join("?" for _ in receiver_dids)),
                    (group_id, timestamp_str, *receiver_dids),
                )
                new_messages = cursor.fetchall()
                
                # Collect replies and check if all receivers have replied
                replied_dids = set()
                for msg_id, msg_ts, msg_sender, msg_data_json in new_messages:
                    if msg_sender in receiver_dids:
                        replied_dids.add(msg_sender)
                        # Check if this reply has already been added
                        if not any(r["message_id"] == msg_id for r in replies):
                            try:
                                msg_data = json.loads(msg_data_json) if msg_data_json else {}
                            except Exception:
                                msg_data = {}
                            
                            replies.append({
                                "message_id": msg_id,
                                "timestamp": msg_ts,
                                "sender_did": msg_sender,
                                "message_data": msg_data
                            })
                            
                            # New: Mark this "reply message" as read for current user
                            # Current user DID in this function is sender_did
                            try:
                                cursor.execute(
                                    "SELECT read_status FROM message_history WHERE message_id = ?",
                                    (msg_id,),
                                )
                                row = cursor.fetchone()
                                try:
                                    rs = json.loads(row[0]) if row and row[0] else {}
                                except Exception:
                                    rs = {}
                                
                                if not rs.get(sender_did, False):
                                    rs[sender_did] = True
                                    cursor.execute(
                                        "UPDATE message_history SET read_status = ? WHERE message_id = ?",
                                        (json.dumps(rs, ensure_ascii=False), msg_id),
                                    )
                                    conn.commit()
                            except Exception:
                                # Error does not affect main flow
                                pass
                    
                # If all receivers have replied, return result
                if len(replied_dids) == len(receiver_dids):
                    base_data["replies"] = replies
                    return {
                        "status": "success",
                        "message": f"Message sent, all {len(receiver_dids)} receivers have replied. You can use send_message to reply or send new messages.",
                        "data": base_data,
                        "database_path": str(db_path),
                    }
            finally:
                conn.close()
            
            # Wait for a while before continuing polling
            await asyncio.sleep(poll_interval)
        
        # Timeout case
        base_data["replies"] = replies
        replied_count = len(set(r["sender_did"] for r in replies))
        return {
            "status": "timeout",
            "message": f"Message sent, but waiting for replies timed out. {replied_count}/{len(receiver_dids)} receivers have replied. You can continue to reply or send new messages.",
            "data": base_data,
            "database_path": str(db_path),
        }
        
    except EnvironmentError as e:
        return {
            "status": "error",
            "message": f"{str(e)}"
        }
    except NotADirectoryError as e:
        return {
            "status": "error",
            "message": f"{str(e)}"
        }
    except sqlite3.OperationalError as e:
        return {
            "status": "error",
            "message": f"Database operation failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to send message: {str(e)}"
        }