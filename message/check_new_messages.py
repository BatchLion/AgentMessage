import os
import re
import json
import time
import asyncio
import hashlib
import sqlite3
from pathlib import Path

from message.db import init_message_history_db
from identity.identity_manager import IdentityManager

async def _check_new_messages(
        poll_interval: int = 5,
        timeout: int | None = None,
        with_history: bool = False
    ) -> dict:
    """
    **Function**:
    - Check new messages sent to you.
    - **Could be used to check 3 recent history messages**: If with_history is True, return 3 history messages previous to the first new one in the same chat group.
    - Used to chat or communicate or interactive or cooperate with other agents.
    - Used to discuss with other agents about a specific topic.
    **Attention**:
    - **Neverforget to reply**: Never forget to use send_message to reply the message sender and all the other receivers after receiving the message unless the message requires no replies.
    - **Reply the sender and all the other receivers**: When replying, don't just reply one or some of them. If the message has 2 or more receivers, please reply to the sender and all the other receivers (excluding the sender itself).
    - **Only the latest group is returned**: If there are new messages in more than one groups, only the group with the latest new message will be returned and marked as read. Other groups' messages will remain unread for future processing.
    - **Reply the returned group**: When replying, don't just reply one or some of them. If the message has 2 or more receivers, please reply to the sender and all the other receivers (excluding the sender itself).
    **Parameter setting**:
    - When chatting, set poll_interval < 5 seconds and timeout > 300 seconds.
    - When cooperating with other agents under a specific task, set poll_interval < 5 seconds and timeout = 0 seconds but never forget to reply the message sender after finishing the subtask relevant.
    
    Parameters:
    - poll_interval: Polling interval in seconds when no new messages (default 5 seconds)
    - timeout: Polling timeout in seconds waiting for new messages. When None or less or equal to 0, will wait indefinitely until new messages appear.
    - with_history: Whether to return 3 history messages.

    Return:
    - success:
    {
        "status": "success",
        "message": "There are new messages. Please use send_message to reply.",
        "groups": [
        {
            "group_id": str,
            "new_count": int,
            "messages": [
            {
                "message_id": str,
                "timestamp": int|float,
                "sender_did": str,
                "sender_name": str,
                "receiver_dids": list[str],
                "receiver_names": list[str],
                "message_data": dict,
                "mention_dids": list[str],
                "mention_names": list[str],
                "is_new": bool
            }
            ]
        }
        ],
        "database_path": str,
        "prompt": str
    }
    - timeout:
    {
        "status": "timeout",
        "message": "Timeout waiting for new messages.",
        "groups": [],
        "database_path": str,
        "prompt": "There are no new messages."
    }
    - error:
    {
        "status": "error",
        "message": str
    }
    """
    limit: int = 0
    if with_history:
        limit = 3  # limit: Maximum number of read messages returned per group (default 10). Returns "all unread messages + last limit read messages", sorted by time ascending; when non-positive, no limit (returns all messages).
    
    try:
        # Get local identity DID
        identity_manager = IdentityManager()
        if not identity_manager.has_identity():
            return {
                "status": "error",
                "message": "Failed to get local identity DID, register your id with register_recall_id."
            }
        identity = identity_manager.load_identity()
        if not identity:
            return {
                "status": "error",
                "message": "Failed to load local identity."
            }
        my_did = identity.did

        # New: Poll when no new messages, until timeout or new messages
        start_time = time.time()
        while True:
            # Initialize/ locate message database (using $AGENTMESSAGE_PUBLIC_DATABLOCKS)
            db_path = init_message_history_db()
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.cursor()

                # Find groups with messages containing local DID as receiver
                cursor.execute(
                    """
                    SELECT DISTINCT group_id
                    FROM message_history
                    WHERE receiver_dids LIKE ?
                    """,
                    (f'%"{my_did}"%',),
                )
                groups_with_messages = [row[0] for row in cursor.fetchall()]

                groups = []
                total_new = 0
                latest_group_info = None  # (group_id, latest_timestamp, new_count, messages, messages_to_mark_read)

                # Prepare identities.db path for DID->name conversion
                did_to_name_cache: dict[str, str] = {}
                public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
                id_db_path = Path(public_dir_env) / "identities.db" if public_dir_env else None
                id_conn = None
                if id_db_path and id_db_path.exists():
                    try:
                        id_conn = sqlite3.connect(id_db_path)
                    except Exception:
                        id_conn = None

                for gid in sorted(groups_with_messages):
                    # Collect all messages in the group (ascending order), filter unread and read, return "all unread + last limit read"
                    cursor.execute(
                        """
                        SELECT message_id, timestamp, sender_did, receiver_dids, message_data, mention_dids, read_status
                        FROM message_history
                        WHERE group_id = ?
                        ORDER BY timestamp ASC
                        """,
                        (gid,),
                    )
                    rows = cursor.fetchall()

                    # First pass: Parse JSON, separate unread/read, collect DID sets
                    unread_items = []  # [(mid, ts, sender, receivers, msg_data, mentions, existing_rs)]
                    read_items = []    # [(mid, ts, sender, receivers, msg_data, mentions, existing_rs)]
                    dids_in_group: set[str] = set()
                    messages_to_mark_read = []
                    new_count = 0

                    for (mid, ts, sender, recv_json, data_json, mention_json, read_status_json) in rows:
                        try:
                            receivers = json.loads(recv_json) if recv_json else []
                        except Exception:
                            receivers = []
                        try:
                            msg_data = json.loads(data_json) if data_json else {}
                        except Exception:
                            msg_data = {}
                        try:
                            mentions = json.loads(mention_json) if mention_json else []
                        except Exception:
                            mentions = []
                        try:
                            read_status = json.loads(read_status_json) if read_status_json else {}
                        except Exception:
                            read_status = {}

                        dids_in_group.add(sender)
                        for r in receivers:
                            dids_in_group.add(r)
                        for m in mentions:
                            dids_in_group.add(m)

                        is_read = bool(read_status.get(my_did, True))
                        if not is_read:
                            new_count += 1
                            messages_to_mark_read.append((mid, read_status))
                            unread_items.append((mid, ts, sender, receivers, msg_data, mentions, True))   # True -> is_new
                        else:
                            read_items.append((mid, ts, sender, receivers, msg_data, mentions, False))  # False -> is_new

                    # Select last limit read messages
                    if isinstance(limit, int) and limit > 0:
                        selected_read = read_items[-limit:]
                    elif isinstance(limit, int) and limit == 0:
                        selected_read = []
                    else:
                        selected_read = read_items

                    # Combine returned set: all unread + selected read, then sort by time ascending
                    selected_msgs = unread_items + selected_read
                    selected_msgs.sort(key=lambda x: x[1])  # Sort by timestamp ascending

                    # Select DID -> name mappings (batch query based on DIDs in returned messages)
                    did_to_name = {}
                    if id_conn and dids_in_group:
                        try:
                            placeholders = ",".join("?" for _ in dids_in_group)
                            id_cur = id_conn.cursor()
                            id_cur.execute(
                                f"SELECT did, name FROM identities WHERE did IN ({placeholders})",
                                tuple(dids_in_group),
                            )
                            for did, name in id_cur.fetchall():
                                if isinstance(name, str) and name:
                                    did_to_name[did] = name
                        except Exception:
                            did_to_name = {}

                    # Construct returned messages
                    messages = []
                    for (mid, ts, sender, receivers, msg_data, mentions, is_new) in selected_msgs:
                        sender_name = did_to_name.get(sender, sender)
                        receiver_names = [did_to_name.get(d, d) for d in receivers]
                        mention_names = [did_to_name.get(d, d) for d in mentions]

                        messages.append({
                            "message_id": mid,
                            "timestamp": ts,
                            "sender_did": sender,
                            "sender_name": sender_name,
                            "receiver_dids": receivers,
                            "receiver_names": receiver_names,
                            "message_data": msg_data,
                            "mention_dids": mentions,
                            "mention_names": mention_names,
                            "is_new": is_new
                        })

                    # Track the group with latest timestamp if it has new messages
                    if new_count > 0:
                        # Find the latest timestamp among unread messages in this group
                        latest_timestamp = max(ts for (mid, ts, sender, receivers, msg_data, mentions, is_new) in unread_items)
                        
                        # Update latest_group_info if this group has a later timestamp
                        if latest_group_info is None or latest_timestamp > latest_group_info[1]:
                            latest_group_info = (gid, latest_timestamp, new_count, messages, messages_to_mark_read)
                    
                    total_new += new_count

                if id_conn:
                    id_conn.close()

                # If there are new messages, only process the group with the latest timestamp
                if total_new > 0 and latest_group_info is not None:
                    gid, latest_timestamp, new_count, messages, messages_to_mark_read = latest_group_info
                    
                    # Mark only the latest group's unread messages as read
                    for mid, existing_rs in messages_to_mark_read:
                        try:
                            existing_rs = existing_rs if isinstance(existing_rs, dict) else {}
                            existing_rs[my_did] = True
                            cursor.execute(
                                "UPDATE message_history SET read_status = ? WHERE message_id = ?",
                                (json.dumps(existing_rs, ensure_ascii=False), mid),
                            )
                        except Exception:
                            # Single update failure does not affect overall
                            pass
                    
                    conn.commit()
                    
                    # Return only the latest group
                    groups = [{
                        "group_id": gid,
                        "new_count": new_count,
                        "messages": messages
                    }]
                    
                    # Compute group member DIDs and exclude the local receiver
                    dids_in_group: set[str] = set()
                    mention_dids_in_group: set[str] = set()
                    for _msg in messages:
                        try:
                            if isinstance(_msg, dict):
                                s = _msg.get("sender_did")
                                if s:
                                    dids_in_group.add(s)
                                for r in (_msg.get("receiver_dids") or []):
                                    dids_in_group.add(r)
                                for m in (_msg.get("mention_dids") or []):
                                    mention_dids_in_group.add(m)
                        except Exception:
                            # Skip malformed message dicts without breaking the flow
                            pass
                    group_member_dids = sorted(dids_in_group)
                    group_member_dids_other_than_receiver = [did for did in group_member_dids if did != my_did]

                    prompt_msg = ""
                    if my_did in mention_dids_in_group:
                        prompt_msg = f"You have {new_count} new messages in the latest group. The group members include {group_member_dids}, Please use send_message to reply to {group_member_dids_other_than_receiver}. Note you are mentioned in the messages."
                    else:
                        prompt_msg = f"You have {new_count} new messages in the latest group. The group members include {group_member_dids}, Please use send_message to reply to {group_member_dids_other_than_receiver}."
                    return {
                        "status": "success",
                        "message": "There are new messages. Please use send_message to reply.",
                        "groups": groups,
                        "database_path": str(db_path),
                        "prompt": prompt_msg
                    }
                
                conn.commit()
            finally:
                conn.close()

            # There are no new messages -> check timeout or continue polling
            if timeout is not None and timeout > 0 and time.time() - start_time >= timeout:
                return {
                    "status": "timeout",
                    "message": "Timeout waiting for new messages.",
                    "groups": [],
                    "database_path": str(db_path),
                    "prompt": "There are no new messages."
                }

            await asyncio.sleep(poll_interval)

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
            "message": f"Failed to check new messages: {str(e)}"
        }