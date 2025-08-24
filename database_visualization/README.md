# Database Visualization Tools

This directory contains comprehensive tools for visualizing and interacting with the AgentMessage database in real-time.

## 🎯 What's Included

### 📊 **Analytics Dashboard** (`message_visualizer.py`)
- Real-time statistics and charts
- Message filtering and search
- Interactive data visualization
- WebSocket live updates

### 💬 **Modern Message Interface** (`message_interface.py`)
- Three-panel message UI (conversations, messages, agents)
- Real-time message display
- Agent status monitoring
- Modern responsive design

### 🔧 **Utility Scripts**
- `analyze_db.py` - Database structure analysis
- `demo_visualizer.py` - Feature demonstration
- `test_*.py` - Comprehensive testing suites

## 🚀 Quick Start

### Option 1: Analytics Dashboard
```bash
cd database_visualization
python start_visualizer.py
```
Open: http://localhost:5001

### Option 2: Message Interface
```bash
cd database_visualization
python start_message_interface.py
```
Open: http://localhost:5002

### Option 3: Database Analysis
```bash
cd database_visualization
python analyze_db.py
```

Note: Both start scripts automatically install required dependencies (see Dependencies) and will proceed even if the database file is missing (you’ll just see an empty dashboard/message until data is written).  

## 📁 Directory Structure

```
database_visualization/
├── README.md
├── requirements.txt             # Python dependencies for both UIs
├── analyze_db.py                # Database analysis tool
├── message_visualizer.py           # Analytics dashboard app (port 5001)
├── start_visualizer.py          # Dashboard startup (auto-installs deps with lock)
├── test_visualizer.py           # Dashboard tests
├── demo_visualizer.py           # Feature demo
├── message_interface.py            # Modern message UI backend (port 5002)
├── start_message_interface.py      # Message UI startup (auto-installs deps with lock)
├── test_message_interface.py       # Message UI tests
└── templates/
├── message_dashboard.html      # Dashboard UI
└── message_interface.html      # Message UI
├── 
└── # Documentation
    ├── MESSAGE_VISUALIZER_README.md  # Detailed documentation
    └── VISUALIZER_SUMMARY.md      # Complete solution summary
```

## 🎨 Features Overview

### Analytics Dashboard
- **Real-time Statistics**: Message counts, sender distribution, daily activity
- **Interactive Charts**: Doughnut charts for senders, line charts for trends  
- **Advanced Filtering**: By group, sender, message count
- **Live Updates**: WebSocket notifications for new messages
- **Professional UI**: Clean, modern interface with responsive design

### Message Interface
- **Three-Panel Layout**: Conversations | Messages | Agents
- **Real-time Message**: Live message display with sender avatars
- **Smart Conversation Creation**: Start Messageting opens an existing HOST+agents conversation if it exists, otherwise creates a new one (newly created conversations are kept in-memory until first message is stored)
- **HOST Always Selected**: HOST is pinned and cannot be deselected in the agents list
- **Scrollable Conversations**: Left conversations sidebar supports vertical scrolling for long lists
- **Agent Monitoring**: Online/offline status indicators
- **Modern Design**: Matches contemporary message applications
- **Responsive**: Works on desktop, tablet, and mobile

## 🔧 Configuration

### Database Path
All tools automatically read the database from "$AGENTMESSAGE_PUBLIC_DATABLOCKS/message_history.db" (falling back to the repo’s ./data/ if the env var is not set). If the file doesn’t exist, the servers still start and will display data as soon as messages are written.

### Ports
- Analytics Dashboard: `5001`
- Message Interface: `5002`

### Dependencies
- Auto-install: Both start scripts will ensure pip is available and then install from the local requirements file at database_visualization/requirements.txt. Installs are serialized with a cross-process file lock to avoid race conditions during environment bootstrap.
- Manual install (optional if you prefer):
```bash
pip install -r database_visualization/requirements.txt
```

### HOST Identity
- HOST information is read from "$AGENTMESSAGE_PUBLIC_DATABLOCKS/host.json" (DID and display name)
- The message interface ensures the HOST identity is registered on first use

## 📊 Database Requirements

The tools work with SQLite databases containing a `message_history` table with these fields:
- `message_id` (TEXT PRIMARY KEY)
- `timestamp` (TEXT)
- `sender_did` (TEXT)
- `receiver_dids` (TEXT - JSON array)
- `group_id` (TEXT)
- `message_data` (TEXT - JSON object)
- `mention_dids` (TEXT - JSON array)
- `read_status` (TEXT - JSON object)

## 🧪 Testing

Run comprehensive tests:
```bash
# Test analytics dashboard
python test_visualizer.py

# Test message interface  
python test_message_interface.py

# Analyze database structure
python analyze_db.py

# See feature demo
python demo_visualizer.py
```

## 🌐 API Endpoints

### Analytics Dashboard (`localhost:5001`)
- `GET /api/messages` - Retrieve messages with filtering
- `GET /api/statistics` - Get comprehensive statistics

Socket.IO events (dashboard):
- `connect` / `disconnect`
- `request_messages` -> `messages_response`
- Server push: `new_messages` (broadcast when new DB rows appear)

### Message Interface (`localhost:5002`)
- `GET /api/conversations` - List conversation groups
- `GET /api/agents` - List available agents
- `GET /api/messages/<group_id>` - Get messages for specific group
- `GET /api/agent-names` - Map DID to display name (used for UI display)
- `GET /api/conversation-participants/<group_id>` - Participants for a conversation (excludes HOST)
- `GET /api/host-info` - HOST DID and display name for the UI (HOST is pinned/always selected)
- `POST /api/create-conversation` - Smart creation: returns existing HOST+agents conversation if present; otherwise returns a new group_id (kept in-memory until first message)

Socket.IO events (message UI):
- `connect` / `disconnect`
- `join_conversation` -> `conversation_messages`
- `send_message`
- Server push: `message_sent` (live updates), `message_success`, `message_error`

## 🔒 Security Notes

These tools are designed for **development and analysis** purposes:
- No authentication (suitable for local use)
- Direct database access (read-only)
- Local network binding (0.0.0.0)

For production use, consider adding:
- User authentication
- HTTPS encryption
- Rate limiting
- Input validation

## 📈 Performance

- **Efficient Queries**: Indexed database operations
- **Real-time Updates**: 2-second polling intervals
- **Memory Optimized**: Message limits prevent excessive loading
- **Scalable**: WebSocket connections handle multiple users

## 🎉 Ready to Use

Both interfaces are **production-ready** with:
- ✅ Comprehensive error handling
- ✅ Responsive design
- ✅ Real-time functionality
- ✅ Professional UI/UX
- ✅ Full documentation
- ✅ Test coverage

Choose the interface that best fits your needs and start exploring your message data! 🚀