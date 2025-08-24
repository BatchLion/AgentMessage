#!/usr/bin/env python3
"""
Modern Message Interface UI
A Flask web application for real-time message with agents
"""
import os
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import sys
import eventlet
eventlet.monkey_patch()
import hashlib

# Set the required environment variable for the message system
# Resolve data directory from env, fallback to repo data dir
public_env = os.getenv('AGENTMESSAGE_PUBLIC_DATABLOCKS')
if public_env:
    data_dir = Path(public_env)
else:
    data_dir = Path(__file__).parent.parent / "data"
    os.environ['AGENTMESSAGE_PUBLIC_DATABLOCKS'] = str(data_dir.absolute())

# Add parent directory to path to import message module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from message.send_message import _send_message
from identity.identity_manager import IdentityManager
from identity.models import AgentIdentity

app = Flask(__name__)
app.config['SECRET_KEY'] = 'message_interface_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_interval=25, ping_timeout=60)

# Database paths
DB_PATH = data_dir / "message_history.db"
IDENTITIES_DB_PATH = data_dir / "identities.db"
HOST_JSON_PATH = data_dir / "host.json"

NEW_CONVERSATION_PARTICIPANTS = {}
NEW_CONV_LOCK = threading.Lock()

# New feature: Database new message monitoring
class MessageMonitor:
    def __init__(self):
        self.last_check = datetime.now()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def start_monitoring(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            # Use Flask-SocketIO background task to avoid conflicts with eventlet
            self.thread = socketio.start_background_task(self._monitor_loop)
            self.thread.start()

    def _monitor_loop(self):
        while self.running:
            try:
                new_messages = self.get_new_messages()
                if new_messages:
                    for msg in new_messages:
                        socketio.emit('message_sent', {
                            'group_id': msg.get('group_id'),
                            'message_id': msg.get('message_id'),
                            'sender_did': msg.get('sender_did'),
                            'message_data': msg.get('message_data'),
                            'timestamp': msg.get('timestamp'),
                            'receiver_dids': msg.get('receiver_dids', []),
                            'client_msg_id': (msg.get('message_data') or {}).get('client_msg_id')
                        })
                    # Advance checkpoint only when new messages are found: advance to "maximum timestamp processed in this batch"
                    try:
                        latest_ts_str = max(
                            m.get('timestamp') for m in new_messages if m.get('timestamp')
                        )
                        self.last_check = datetime.strptime(latest_ts_str, "%Y-%m-%d %H:%M:%S")
                    except Exception as _e:
                        pass
                # Non-blocking sleep, compatible with eventlet
                socketio.sleep(2)
            except Exception as e:
                print(f"Monitor error: {e}")
                socketio.sleep(5)

    def get_new_messages(self):
        if not DB_PATH.exists():
            return []
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            # Look back 1 second and use >= to avoid missing same-second/late writes; works with frontend deduplication
            safe_check = (self.last_check - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                SELECT message_id, timestamp, sender_did, receiver_dids, 
                       group_id, message_data, mention_dids, read_status
                FROM message_history 
                WHERE datetime(timestamp) >= datetime(?)
                ORDER BY datetime(timestamp) ASC
            """, (safe_check,))
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                try:
                    message_data = json.loads(row[5]) if row[5] else {}
                    receiver_dids = json.loads(row[3]) if row[3] else []
                    messages.append({
                        'message_id': row[0],
                        'timestamp': row[1],
                        'sender_did': row[2],
                        'receiver_dids': receiver_dids,
                        'group_id': row[4],
                        'message_data': message_data
                    })
                except Exception as e:
                    print(f"Error parsing message {row[0]}: {e}")
                    continue
            return messages
        finally:
            conn.close()

# Start monitoring thread when loading the module (ensure starting only once)
_monitor_instance = MessageMonitor()
_monitor_instance.start_monitoring()

def ensure_host_identity():
    """Ensure HOST identity is registered in the identity manager"""
    try:
        identity_manager = IdentityManager()
        
        # Check if identity already exists
        if identity_manager.has_identity():
            existing_identity = identity_manager.load_identity()
            if existing_identity and existing_identity.name == "HOST":
                return existing_identity.did
        
        # Load HOST data from host.json
        if not HOST_JSON_PATH.exists():
            return None
            
        with open(HOST_JSON_PATH, 'r', encoding='utf-8') as f:
            host_data = json.load(f)
        
        # Create HOST identity using the DID from host.json
        host_identity = AgentIdentity(
            name=host_data.get('name', 'HOST'),
            description=host_data.get('description', 'The user of the MCP service and the host of the agents.'),
            capabilities=['message', 'message_sending'],
            did=host_data.get('did')
        )
        
        # Save the identity
        if identity_manager.save_identity(host_identity):
            print(f"HOST identity registered: {host_identity.did}")
            return host_identity.did
        else:
            print("Failed to save HOST identity")
            return None
            
    except Exception as e:
        print(f"Error ensuring HOST identity: {e}")
        return None

def get_host_did():
    """Get HOST DID from host.json file"""
    if not HOST_JSON_PATH.exists():
        return None
    
    try:
        with open(HOST_JSON_PATH, 'r', encoding='utf-8') as f:
            host_data = json.load(f)
            return host_data.get('did')
    except Exception as e:
        print(f"Error loading host DID: {e}")
        return None

def get_conversation_participants(group_id):
    """Get all participants (receiver DIDs) for a conversation group"""
    if not DB_PATH.exists():
        return []
    
    # Added: Prefer reading participants from memory map (for newly created conversations without messages yet)
    with NEW_CONV_LOCK:
        if group_id in NEW_CONVERSATION_PARTICIPANTS:
            participants = list(NEW_CONVERSATION_PARTICIPANTS[group_id])
            # Remove HOST DID (HOST does not send to itself)
            host_did = get_host_did()
            if host_did and host_did in participants:
                participants = [p for p in participants if p != host_did]
            return participants
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT sender_did, receiver_dids
            FROM message_history 
            WHERE group_id = ?
        """, (group_id,))
        
        all_participants = set()
        for row in cursor.fetchall():
            sender_did, receiver_dids_json = row
            all_participants.add(sender_did)
            
            try:
                receiver_dids = json.loads(receiver_dids_json) if receiver_dids_json else []
                all_participants.update(receiver_dids)
            except Exception:
                continue
        
        # Remove HOST DID from participants (HOST shouldn't send to themselves)
        host_did = get_host_did()
        if host_did and host_did in all_participants:
            all_participants.remove(host_did)
        
        return list(all_participants)
    finally:
        conn.close()

def get_agent_names():
    """Get mapping of DIDs to agent names from identities database"""
    if not IDENTITIES_DB_PATH.exists():
        return {}
    
    conn = sqlite3.connect(IDENTITIES_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT did, name FROM identities")
        return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception as e:
        print(f"Error loading agent names: {e}")
        return {}
    finally:
        conn.close()

def get_conversations():
    """Get list of conversations/groups with participant names"""
    if not DB_PATH.exists():
        return []
    
    # Get agent names mapping
    agent_names = get_agent_names()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                group_id,
                COUNT(*) as message_count,
                MAX(timestamp) as last_message,
                GROUP_CONCAT(DISTINCT sender_did) as participants
            FROM message_history 
            GROUP BY group_id 
            ORDER BY MAX(datetime(timestamp)) DESC
        """)
        
        conversations = []
        for row in cursor.fetchall():
            group_id, msg_count, last_msg, participants = row
            participants_list = participants.split(',') if participants else []
            
            # Convert participant DIDs to names
            participant_names = []
            for did in participants_list:
                name = agent_names.get(did)
                if name:
                    participant_names.append(name)
                else:
                    # Fallback to shortened DID
                    short_name = did.split(':')[-1][:8] if ':' in did else did[:8]
                    participant_names.append(short_name)
            
            # Create display name from participant names
            if len(participant_names) <= 2:
                display_name = " & ".join(participant_names)
            else:
                display_name = f"{participant_names[0]} & {len(participant_names)-1} others"
            
            conversations.append({
                'group_id': group_id,
                'message_count': msg_count,
                'last_message': last_msg,
                'participants': participants_list,
                'participant_names': participant_names,
                'display_name': display_name
            })
        
        return conversations
    finally:
        conn.close()

def get_agents():
    """Get list of available agents with their names"""
    if not DB_PATH.exists():
        return []
    
    # Get agent names mapping
    agent_names = get_agent_names()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                sender_did,
                COUNT(*) as message_count,
                MAX(timestamp) as last_active
            FROM message_history 
            GROUP BY sender_did 
            ORDER BY MAX(datetime(timestamp)) DESC
        """)
        
        agents = []
        for row in cursor.fetchall():
            sender_did, msg_count, last_active = row
            
            # Get agent name from identities database, fallback to DID
            agent_name = agent_names.get(sender_did)
            if not agent_name:
                # Fallback to shortened DID if no name found
                agent_name = sender_did.split(':')[-1][:8] if ':' in sender_did else sender_did[:8]
            
            # Check if active (last message within 24 hours)
            last_time = datetime.strptime(last_active, "%Y-%m-%d %H:%M:%S")
            is_online = (datetime.now() - last_time).total_seconds() < 86400
            
            agents.append({
                'did': sender_did,
                'display_name': agent_name,
                'description': f"Agent {agent_name}",
                'message_count': msg_count,
                'last_active': last_active,
                'is_online': is_online
            })
        
        return agents
    finally:
        conn.close()

def get_group_messages(group_id, limit=50):
    """Get messages for a specific group"""
    if not DB_PATH.exists():
        return []
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT message_id, timestamp, sender_did, receiver_dids, 
                   group_id, message_data, mention_dids, read_status
            FROM message_history 
            WHERE group_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (group_id, limit))
        
        messages = []
        for row in cursor.fetchall():
            try:
                message_data = json.loads(row[5]) if row[5] else {}
                receiver_dids = json.loads(row[3]) if row[3] else []
                mention_dids = json.loads(row[6]) if row[6] else []
                read_status = json.loads(row[7]) if row[7] else {}
                
                messages.append({
                    'message_id': row[0],
                    'timestamp': row[1],
                    'sender_did': row[2],
                    'receiver_dids': receiver_dids,
                    'group_id': row[4],
                    'message_data': message_data,
                    'mention_dids': mention_dids,
                    'read_status': read_status
                })
            except Exception as e:
                print(f"Error parsing message {row[0]}: {e}")
                continue
        
        return list(reversed(messages))  # Return in chronological order
    finally:
        conn.close()

@app.route('/')
def index():
    """Main message interface"""
    return render_template('message_interface.html')

@app.route('/api/conversations')
def api_conversations():
    """API endpoint for getting conversations"""
    conversations = get_conversations()
    return jsonify(conversations)

@app.route('/api/agents')
def api_agents():
    """API endpoint for getting agents"""
    agents = get_agents()
    return jsonify(agents)

@app.route('/api/messages/<group_id>')
def api_group_messages(group_id):
    """API endpoint for getting messages in a group"""
    limit = request.args.get('limit', 50, type=int)
    messages = get_group_messages(group_id, limit)
    return jsonify(messages)

@app.route('/api/agent-names')
def api_agent_names():
    """API endpoint for getting DID to name mappings"""
    agent_names = get_agent_names()
    return jsonify(agent_names)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to message interface'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Handle joining a conversation"""
    group_id = data.get('group_id')
    if group_id:
        messages = get_group_messages(group_id)
        emit('conversation_messages', {'group_id': group_id, 'messages': messages})

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a new message using the actual send_message function"""
    try:
        group_id = data.get('group_id')
        message_text = data.get('message_text', '').strip()
        client_msg_id = data.get('client_msg_id')  # Added: client message ID passed from frontend
        
        if not group_id or not message_text:
            emit('message_error', {'error': 'Missing group_id or message_text'})
            return
        
        # Ensure HOST identity is registered and get DID
        host_did = ensure_host_identity()
        if not host_did:
            emit('message_error', {'error': 'Failed to register or load HOST identity'})
            return
        
        # Get conversation participants (excluding HOST)
        receiver_dids = get_conversation_participants(group_id)
        if not receiver_dids:
            emit('message_error', {'error': 'No participants found for this conversation'})
            return
        
        # Prepare message data
        message_data = {
            'text': message_text,
            'timestamp': datetime.now().isoformat()
        }
        if client_msg_id:
            message_data['client_msg_id'] = client_msg_id  # Added: write into message_data for persistence and later polling association
        
        # Send message asynchronously
        def send_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Use asyncio.wait_for to timeout after 10 seconds
                result = loop.run_until_complete(
                    asyncio.wait_for(
                        _send_message(
                            sender_did=host_did,
                            receiver_dids=receiver_dids,
                            message_data=message_data
                        ),
                        timeout=10.0  # 10 second timeout
                    )
                )
                
                if result.get('status') == 'success' or result.get('status') == 'timeout':
                    # Broadcast the new message to all connected clients
                    socketio.emit('message_sent', {
                        'group_id': group_id,
                        'message_id': result['data']['message_id'],
                        'sender_did': host_did,
                        'message_data': message_data,
                        'timestamp': result['data']['timestamp'],
                        'receiver_dids': receiver_dids,
                        'client_msg_id': client_msg_id  # Added: also carry at top-level for direct frontend matching
                    })
                    
                    socketio.emit('message_success', {
                        'message': 'Message sent successfully',
                        'data': result['data']
                    })
                else:
                    # Send error response
                    socketio.emit('message_error', {
                        'error': result.get('message', 'Unknown error occurred')
                    })
            except asyncio.TimeoutError:
                # Message sent but timed out waiting for replies - this is normal
                socketio.emit('message_success', {
                    'message': 'Message sent successfully (agents will reply separately)',
                    'timeout': True
                })
                
                # Still broadcast the message since it was likely sent
                socketio.emit('message_sent', {
                    'group_id': group_id,
                    'sender_did': host_did,
                    'message_data': message_data,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'receiver_dids': receiver_dids,
                    'client_msg_id': client_msg_id  # Added: also carry in timeout branch placeholder broadcast for later replacement
                })
            except Exception as e:
                socketio.emit('message_error', {
                    'error': f'Failed to send message: {str(e)}'
                })
            finally:
                loop.close()
        
        # Run in separate thread to avoid blocking
        thread = threading.Thread(target=send_async)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        emit('message_error', {'error': f'Error processing message: {str(e)}'})

@app.route('/api/conversation-participants/<group_id>')
def api_conversation_participants(group_id):
    """API endpoint for getting conversation participants"""
    participants = get_conversation_participants(group_id)
    return jsonify(participants)

def _compute_group_id_with_host(receiver_dids: list[str]) -> str:
    # Use the same group_id computation as message/send_message.py: first 16 of sha256(sorted([HOST]+receivers)) plus 'grp_'
    host_did = get_host_did()
    if not host_did:
        return None
    unique_dids = sorted(set([host_did] + receiver_dids))
    basis = "|".join(unique_dids)
    group_hash = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"grp_{group_hash}"

def find_existing_conversation(participant_dids):
    """Find existing conversation with the exact same participants (including HOST)"""
    if not DB_PATH.exists():
        return None
    host_did = get_host_did()
    if not host_did:
        return None

    target_group_id = _compute_group_id_with_host(participant_dids)
    if not target_group_id:
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT group_id, COUNT(*) as message_count, MAX(timestamp) as last_message
            FROM message_history
            WHERE group_id = ?
            GROUP BY group_id
        """, (target_group_id,))
        row = cursor.fetchone()
        if row:
            group_id, msg_count, last_msg = row
            return {
                "group_id": group_id,
                "message_count": msg_count,
                "last_message": last_msg,
                "exists": True
            }
        return None
    finally:
        conn.close()

@app.route('/api/host-info')
def api_host_info():
    """Get HOST DID and display name for frontend to display as always-selected"""
    host_did = get_host_did()
    if not host_did:
        return jsonify({"error": f"HOST DID not found. Please check {HOST_JSON_PATH}"}), 500
    agent_names = get_agent_names()
    host_name = agent_names.get(host_did, "HOST")
    return jsonify({
        "did": host_did,
        "display_name": host_name,
        "description": "Local host agent",
        "is_host": True
    })

@app.route('/api/create-conversation', methods=['POST'])
def api_create_conversation():
    """
    Intelligent conversation creation logic
    Check for existing conversations with HOST and selected agents
    Create a new blank in-memory conversation if none found
    
    Request body parameters: { "agent_dids": [did1, did2, ...], "theme": "optional" }
    
    Error handling for missing agent_dids or HOST DID
    Logic for removing the HOST DID from agent_dids
    Find existing conversations, map DIDs to names for display
    Handle the creation of new in-memory conversations with a group_id and NEW_CONVERSATION_PARTICIPANTS lock
    """
    try:
        data = request.get_json(silent=True) or {}
        agent_dids = data.get('agent_dids') or []
        agent_dids = [d for d in agent_dids if isinstance(d, str) and d.strip()]
        if not agent_dids:
            return jsonify({"error": "agent_dids is required"}), 400

        host_did = get_host_did()
        if not host_did:
            return jsonify({"error": "HOST DID not found. Please check ../data/host.json"}), 500

        # Remove HOST DID from agent_dids if present
        agent_dids = [d for d in agent_dids if d != host_did]

        # First check for existing conversation
        existing_conv = find_existing_conversation(agent_dids)
        agent_names_map = get_agent_names()

        def to_names(dids):
            names = []
            for did in dids:
                name = agent_names_map.get(did)
                if name:
                    names.append(name)
                else:
                    short_name = did.split(':')[-1][:8] if ':' in did else did[:8]
                    names.append(short_name)
            return names

        participant_names = to_names(agent_dids)
        if len(participant_names) <= 2:
            display_name = " & ".join(participant_names)
        else:
            display_name = f"{participant_names[0]} & {len(participant_names)-1} others"

        if existing_conv:
            return jsonify({
                "group_id": existing_conv["group_id"],
                "message_count": existing_conv["message_count"],
                "last_message": existing_conv["last_message"],
                "participants": agent_dids,
                "participant_names": participant_names,
                "display_name": display_name,
                "exists": True,
                "action": "opened_existing"
            })

        # Create new in-memory conversation if none found
        group_id = _compute_group_id_with_host(agent_dids)
        if not group_id:
            return jsonify({"error": "Failed to compute group_id"}), 500

        with NEW_CONV_LOCK:
            NEW_CONVERSATION_PARTICIPANTS[group_id] = list(agent_dids)

        return jsonify({
            "group_id": group_id,
            "message_count": 0,
            "last_message": None,
            "participants": agent_dids,
            "participant_names": participant_names,
            "display_name": display_name,
            "exists": False,
            "action": "created_new"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to create conversation: {e}"}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5002)