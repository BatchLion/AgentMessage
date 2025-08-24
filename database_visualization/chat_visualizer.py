#!/usr/bin/env python3
"""
Real-time Message History Visualizer
A Flask web application with WebSocket support for visualizing message history
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'message_visualizer_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Database path
public_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
data_dir = Path(public_env) if public_env else (Path(__file__).parent.parent / "data")
DB_PATH = data_dir / "message_history.db"

class MessageMonitor:
    def __init__(self):
        self.last_check = datetime.now()
        self.running = False
        
    def start_monitoring(self):
        """Start monitoring for new messages"""
        self.running = True
        thread = threading.Thread(target=self._monitor_loop)
        thread.daemon = True
        thread.start()
        
    def _monitor_loop(self):
        """Monitor database for new messages"""
        while self.running:
            try:
                new_messages = self.get_new_messages()
                if new_messages:
                    socketio.emit('new_messages', {'messages': new_messages})
                    self.last_check = datetime.now()
                time.sleep(2)  # Check every 2 seconds
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(5)
    
    def get_new_messages(self):
        """Get messages newer than last check"""
        if not DB_PATH.exists():
            return []
            
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_id, timestamp, sender_did, receiver_dids, 
                       group_id, message_data, mention_dids, read_status
                FROM message_history 
                WHERE datetime(timestamp) > datetime(?)
                ORDER BY timestamp DESC
            """, (self.last_check.strftime("%Y-%m-%d %H:%M:%S"),))
            
            rows = cursor.fetchall()
            messages = []
            for row in rows:
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
            
            return messages
        finally:
            conn.close()

monitor = MessageMonitor()

def get_message_data(limit=50, group_id=None, sender_did=None):
    """Get message messages with optional filtering"""
    if not DB_PATH.exists():
        return []
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT message_id, timestamp, sender_did, receiver_dids, 
                   group_id, message_data, mention_dids, read_status
            FROM message_history 
        """
        params = []
        
        conditions = []
        if group_id:
            conditions.append("group_id = ?")
            params.append(group_id)
        if sender_did:
            conditions.append("sender_did = ?")
            params.append(sender_did)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        messages = []
        for row in rows:
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
                
        return messages
    finally:
        conn.close()

def get_statistics():
    """Get message statistics"""
    if not DB_PATH.exists():
        return {}
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        # Total messages
        cursor.execute("SELECT COUNT(*) FROM message_history")
        total_messages = cursor.fetchone()[0]
        
        # Unique senders
        cursor.execute("SELECT COUNT(DISTINCT sender_did) FROM message_history")
        unique_senders = cursor.fetchone()[0]
        
        # Unique groups
        cursor.execute("SELECT COUNT(DISTINCT group_id) FROM message_history")
        unique_groups = cursor.fetchone()[0]
        
        # Messages per sender
        cursor.execute("""
            SELECT sender_did, COUNT(*) as count 
            FROM message_history 
            GROUP BY sender_did 
            ORDER BY count DESC
        """)
        sender_stats = cursor.fetchall()
        
        # Messages per group
        cursor.execute("""
            SELECT group_id, COUNT(*) as count 
            FROM message_history 
            GROUP BY group_id 
            ORDER BY count DESC
        """)
        group_stats = cursor.fetchall()
        
        # Messages per day (last 7 days)
        cursor.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM message_history 
            WHERE DATE(timestamp) >= DATE('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """)
        daily_stats = cursor.fetchall()
        
        return {
            'total_messages': total_messages,
            'unique_senders': unique_senders,
            'unique_groups': unique_groups,
            'sender_stats': sender_stats,
            'group_stats': group_stats,
            'daily_stats': daily_stats
        }
    finally:
        conn.close()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('message_dashboard.html')

@app.route('/api/messages')
def api_messages():
    """API endpoint for getting messages"""
    limit = request.args.get('limit', 50, type=int)
    group_id = request.args.get('group_id')
    sender_did = request.args.get('sender_did')
    
    messages = get_message_data(limit, group_id, sender_did)
    return jsonify(messages)

@app.route('/api/statistics')
def api_statistics():
    """API endpoint for getting statistics"""
    stats = get_statistics()
    return jsonify(stats)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to message visualizer'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('request_messages')
def handle_request_messages(data):
    """Handle request for messages"""
    limit = data.get('limit', 50)
    group_id = data.get('group_id')
    sender_did = data.get('sender_did')
    
    messages = get_message_data(limit, group_id, sender_did)
    emit('messages_response', {'messages': messages})

if __name__ == '__main__':
    # Start monitoring for new messages
    monitor.start_monitoring()
    
    # Run the Flask app
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)