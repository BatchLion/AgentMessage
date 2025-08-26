"""AgentMessage MCP server entry point"""

from fastmcp import FastMCP
from identity.tools import register_recall_id as _register_recall_id, go_online as _go_online
import sqlite3
import json
import os
from pathlib import Path
from message.db import init_message_history_db, get_message_db_path
import hashlib
import re
from datetime import datetime, timezone, timedelta
from identity.identity_manager import IdentityManager
import asyncio
import time
from identity.did_generator import DIDGenerator
import subprocess
import sys
import threading
import webbrowser

class AgentMessageMCPServer:
    """AgentMessage MCP server"""
    
    def __init__(self):
        self.mcp = FastMCP("agentmessage")
        self._setup_tools()
    
    def _setup_tools(self):
        """Set up MCP tools"""
        
        @self.mcp.tool()
        async def register_recall_id(
            name: str = None,
            description: str = None,
            capabilities: list[str] = None
        ) -> dict:
            """Register or recall agent identity information
            
            Parameters:
            - name: Agent name (optional, required when creating a new identity)
            - description: Agent description (optional, required when creating a new identity)
            - capabilities: Agent capabilities list (optional, required when creating a new identity)
            Functionality:
            - Use the identity memory directory specified by the AGENTMESSAGE_MEMORY_PATH environment variable
            - If the identity file exists, return the existing identity (ignore input parameters)
            - If the directory is empty and all parameters are provided, create a new agent identity
            - If the directory is empty and parameters are not provided, prompt the user to supply required information
            Environment variables:
            - AGENTMESSAGE_MEMORY_PATH: identity memory storage directory
            Return format:
            - A dictionary containing status, message, and identity information
            Use cases:
            - Recall the agent identity at startup
            - Create a separate identity memory for a new agent
            - Obtain the agent’s DID, name, description, capabilities
            """
            return _register_recall_id(name, description, capabilities)
        
        @self.mcp.tool()
        async def go_online() -> dict:
            """Publish the agent identity to make it discoverable by other agents
            Functionality:
            - Retrieve agent identity from AGENTMESSAGE_MEMORY_PATH
            - If identity exists, publish it to $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db
            - If identity is empty, prompt to use register_recall_id first
            - If AGENTMESSAGE_PUBLIC_DATABLOCKS is not set, prompt to define it in the MCP configuration file
            Environment variables:
            - AGENTMESSAGE_MEMORY_PATH: identity memory storage directory (read)
            - AGENTMESSAGE_PUBLIC_DATABLOCKS: public database directory (write identities.db)
            Return format:
            - A dictionary containing operation status, message, and published identity, e.g.:
              { "status": "...", "message": "Explanation", "published_identity": {...} }
            Notes:
            - Ensure identity has been registered using register_recall_id before publishing
            - Ensure AGENTMESSAGE_PUBLIC_DATABLOCKS is set and points to a writable directory
            - Published information is stored locally for other agents to query
            """
            return _go_online()
        
        # Collect identities from identities.db
        @self.mcp.tool()
        async def collect_identities(limit: int | None = None) -> dict:
            """Collect identities from identities.db database
            Path:
            - $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db
            
            Parameters:
            - limit: Optional, limit the number of records returned
            
            Returns:
            {
              "status": "success",
              "total": <int>,
              "identities": [
                {
                  "did": "...",
                  "name": "...",
                  "description": "...",
                  "capabilities": [...],
                  "created_at": "YYYY-MM-DD HH:MM:SS",
                  "updated_at": "YYYY-MM-DD HH:MM:SS"
                },
                ...
              ],
              "database_path": "<Absolute path of identities.db>"
            }
            """
            try:
                public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
                if not public_dir_env:
                    return {
                        "status": "error",
                        "message": "AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable is not set. Please define it in the MCP configuration file."
                    }
                
                db_path = Path(public_dir_env) / "identities.db"
                if not db_path.exists():
                    return {
                        "status": "error",
                        "message": "identities.db file not found",
                        "expected_path": str(db_path)
                    }
                
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                sql = """
                    SELECT did, name, description, capabilities, created_at, updated_at
                    FROM identities
                    ORDER BY datetime(updated_at) DESC
                """
                if limit is not None and isinstance(limit, int) and limit > 0:
                    sql += " LIMIT ?"
                    cursor.execute(sql, (limit,))
                else:
                    cursor.execute(sql)
                
                rows = cursor.fetchall()
                conn.close()
                
                identities = []
                for did, name, description, capabilities_text, created_at, updated_at in rows:
                    # capabilities is stored as JSON text, needs to be deserialized into a list
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
                    "status": "success",
                    "total": len(identities),
                    "identities": identities,
                    "database_path": str(db_path)
                }
            except sqlite3.OperationalError as e:
                return {
                    "status": "error",
                    "message": f"Database operation failed: {str(e)}"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Collect identities failed: {str(e)}"
                }
        
        @self.mcp.tool()
        async def send_message(
            receiver_dids: list[str],
            message_data: dict,
            wait_for_replies: bool = True,
            poll_interval: int = 5,
            timeout: int = 300
        ) -> dict:
            """
            ***Please never forget to reply the message sender after receiving a new message, unless the message requires no replies.***
            Send messages to other agents, i.e. each receiver in the receiver_dids list.
            Used to chat or communicate or interactive or cooperate with other agents.
            Used to discuss with other agents about a specific topic.
            When chatting or discussing with other agents, you can wait for replies with poll_interval < 5 and timeout > 300.
            When cooperating with other agents under a specific task, set poll_interval < 5 seconds and timeout = 0 seconds but never forget to reply the message sender after finishing the subtask relevant.
            If you wait for replies, please reply all the receivers after each receiver replies or timeout.
            Use @ mentions to mention other agents (supports @all, @receiverDID, @receiverName)
            
            Parameters:
            - receiver_dids: List of receiver DIDs (cannot be empty)
            - message_data: Message data object (can contain text, code, images, audio, video, filenames and formats)
            - wait_for_replies: Whether to wait for all receivers to reply (default True)
            - poll_interval: Polling interval in seconds (default 5 seconds)
            - timeout: Wait timeout in seconds (default 300 seconds)
            
            Returns:
            {
              "status": "success" | "error" | "timeout",
              "message": "...",
              "data": {
                "message_id": "...",
                "timestamp": "YYYY-MM-DD HH:MM:SS",
                "sender_did": "...",
                "receiver_dids": [...],
                "group_id": "grp_xxx",
                "message_data": {...},
                "mention_dids": [...],
                "replies": [...] // When wait_for_replies=True, contains received replies
              },
              "database_path": "/absolute/path/to/message_history.db"
            }
            """
            # Get sender identity
            try:
                identity_manager = IdentityManager()
                if not identity_manager.has_identity():
                    return {
                        "status": "error",
                        "message": "User identity not found. Please register first with register_recall_id."
                    }
                identity = identity_manager.load_identity()
                if not identity:
                    return {
                        "status": "error",
                        "message": "Failed to load user identity."
                    }
                sender_did = identity.did
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Get sender identity failed: {str(e)}"
                }
            
            from message.send_message import _send_message
            return await _send_message(sender_did, receiver_dids, message_data,
                                       wait_for_replies, poll_interval, timeout)

        @self.mcp.tool()
        async def check_new_messages(
                poll_interval: int = 5,
                timeout: int | None = None
            ) -> dict:
            """
            Check new messages sent to you, return unread messages based on read_status field of each message, and mark current user as read after reading.
            Used to chat or communicate or interactive or cooperate with other agents.
            Never forget to reply the message sender after receiving the message unless the message requires no replies.
            When replying, if the message has 2 or more recipients, please send the reply to the sender and all the other recipients (excluding the sender itself).
            When chatting, set poll_interval < 5 seconds and timeout > 300 seconds.
            When cooperating with other agents under a specific task, set poll_interval < 5 seconds and timeout = 0 seconds but never forget to reply the message sender after finishing the subtask relevant.
            
            Parameters:
            - poll_interval: Polling interval in seconds when no new messages (default 5 seconds)
            - timeout: Polling timeout in seconds waiting for new messages. When None, will wait indefinitely until new messages appear.
            
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
            limit: int = 0  # limit: Maximum number of read messages returned per group (default 10). Returns "all unread messages + last limit read messages", sorted by time ascending; when non-positive, no limit (returns all messages).
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

                            # Write back: Mark unread messages as read (only update current user's read_status)
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

                            total_new += new_count
                            # Only return this group when it has new messages (return "all unread + last limit read")
                            if new_count > 0:
                                groups.append({
                                    "group_id": gid,
                                    "new_count": new_count,
                                    "messages": messages
                                })

                        if id_conn:
                            id_conn.close()

                        conn.commit()

                        # If there are new messages, return immediately and remind users to use send_message to reply
                        if total_new > 0:
                            prompt_msg = f"You have {total_new} new messages. Please use send_message to reply."
                            return {
                                "status": "success",
                                "message": "There are new messages. Please use send_message to reply.",
                                "groups": groups,
                                "database_path": str(db_path),
                                "prompt": prompt_msg
                            }
                    finally:
                        conn.close()

                    # There are no new messages -> check timeout or continue polling
                    if timeout is not None and time.time() - start_time >= timeout:
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

    def run(self, transport: str = "stdio"):
        """Run the MCP server"""
        self.mcp.run(transport=transport)

def check_or_create_host() -> dict | None:
    """Check or create HOST information.
    Behavior:
    - Check if $AGENTMESSAGE_PUBLIC_DATABLOCKS/host.json exists and contains name, description, did
    - If exists and complete: print prompt and return the information
    - If not exists or incomplete: generate DID, create and save to host.json, then print and return
    - Add HOST information to identities.db database
    """
    try:
        public_dir = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
        if not public_dir:
            print("Warning: AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable is not set. Cannot create/read host.json.")
            return None

        public_path = Path(public_dir)
        public_path.mkdir(parents=True, exist_ok=True)

        host_file = public_path / "host.json"
        host_data = None
        is_new_host = False

        # If host.json exists, try to read and validate
        if host_file.exists():
            try:
                with open(host_file, "r", encoding="utf-8") as f:
                    host_data = json.load(f)
                if all(k in host_data for k in ["name", "description", "did"]):
                    print("HOST information exists:")
                    print(f"  Name: {host_data.get('name')}")
                    print(f"  Description: {host_data.get('description')}")
                    print(f"  DID: {host_data.get('did')}")
                else:
                    host_data = None
            except Exception as e:
                print(f"Warning: Failed to read host.json: {e}. Will create a new one.")
                host_data = None

        # If host.json does not exist or is incomplete, create a new one
        if not host_data:
            is_new_host = True
            did_gen = DIDGenerator()
            host_did = did_gen.generate_did("HOST")  # did:agentmessage:local:xxxx

            host_data = {
                "name": "HOST",
                "description": "The user of the MCP service and the host of the agents.",
                "did": host_did,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "role": "host",
            }
            with open(host_file, "w", encoding="utf-8") as f:
                json.dump(host_data, f, ensure_ascii=False, indent=2)

            print("Created HOST information:")
            print(f"  Name: {host_data['name']}")
            print(f"  Description: {host_data['description']}")
            print(f"  DID: {host_data['did']}")
            print(f"  Saved to: {host_file}")

        # Add HOST information to identities.db database
        try:
            db_path = public_path / "identities.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create identities table (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS identities (
                    did TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # HOST capabilities is an empty array
            capabilities_json = json.dumps([], ensure_ascii=False)
            
            # Insert or update HOST identity information
            cursor.execute("""
                INSERT OR REPLACE INTO identities 
                (did, name, description, capabilities, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (host_data['did'], host_data['name'], host_data['description'], capabilities_json))
            
            conn.commit()
            conn.close()
            
            if is_new_host:
                print(f"  Added HOST information to database: {db_path}")
            else:
                print(f"  Updated HOST information to database: {db_path}")
                
        except Exception as e:
            print(f"Warning: Failed to add HOST information to identities.db: {e}")
            # Do not affect the main function, continue execution

        return host_data

    except Exception as e:
        print(f"Warning: Failed to check or create HOST information: {e}")
        return None

# New: launch visualization tools at startup
def _launch_visual_tools():
    try:
        base_dir = Path(__file__).parent / "database_visualization"
        start_visualizer = base_dir / "start_visualizer.py"
        start_message = base_dir / "start_message_interface.py"

        if start_visualizer.exists():
            subprocess.Popen(
                [sys.executable, str(start_visualizer)],
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            print(f"Warning: Failed to find {start_visualizer}")

        if start_message.exists():
            subprocess.Popen(
                [sys.executable, str(start_message)],
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            print(f"Warning: Failed to find {start_message}")

        # Open browser tabs shortly after spawning servers
        def _open_tabs():
            try:
                time.sleep(10)
                webbrowser.open("http://localhost:5001")
                webbrowser.open("http://localhost:5002")
            except Exception as e:
                print(e)
                pass

        t = threading.Thread(target=_open_tabs, daemon=True)
        t.start()

    except Exception as e:
        print(f"Warning: Failed to launch visualization tools: {e}")

def main():
    """Main function - uvx entry point"""
    # Check or create HOST information before startup
    check_or_create_host()

    # New: auto-start UI tools in background and open browser
    _launch_visual_tools()

    server = AgentMessageMCPServer()
    server.run()

if __name__ == "__main__":
    main()
