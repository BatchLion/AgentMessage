# AgentMessage
Modular Agent Identity and Messaging MCP Server

- Agent identity management (create, recall, persist)
- DID generation and publication for discovery
- A minimal but powerful set of MCP tools to register identities, publish them, list identities, exchange messages, and consume unread messages
- Optional web UIs for visualizing data and messageting

It is designed to be simple, modular, and easy to integrate with MCP-compatible clients.

References
- Core server: <mcfile name="mcp_server.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/mcp_server.py"></mcfile>
- Identity tools: <mcfile name="identity/tools.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/tools.py"></mcfile>
- Identity manager: <mcfile name="identity/identity_manager.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/identity_manager.py"></mcfile>
- Message DB helpers: <mcfile name="message/db.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/db.py"></mcfile>
- Send message core: <mcfile name="message/send_message.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/send_message.py"></mcfile>
- Visualization servers: 
  - Visualizer (port 5001): <mcfile name="database_visualization/message_visualizer.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/message_visualizer.py"></mcfile>
  - Message Interface (port 5002): <mcfile name="database_visualization/message_interface.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/message_interface.py"></mcfile>

## Architecture

```mermaid
flowchart TD
  subgraph Client
    MCPClient[MCP-compatible Client]
  end

  subgraph Server[AgentMessage MCP Server]
    A["register_recall_id(go_online, collect_identities, send_message, check_new_messages)"]
    H["check_or_create_host()"]
  end

  subgraph Storage
    M[AGENTMESSAGE_MEMORY_PATH\nidentity.json]
    P[AGENTMESSAGE_PUBLIC_DATABLOCKS\n- identities.db\n- message_history.db\n- host.json]
  end

  subgraph WebUI[Web UIs]
    V[Message Visualizer\n:5001]
    C[Message Interface\n:5002]
  end

  MCPClient -->|MCP Tools| A
  A -->|read/write| P
  A -->|read| M
  H -->|create/ensure| P
  V -->|read| P
  C -->|read/write| P
```

Dark mode note: This diagram uses default Mermaid colors and renders clearly in dark mode.

## Environment Variables

- AGENTMESSAGE_MEMORY_PATH: Local private memory directory for the agent identity (read). Used by the identity manager to load/save identity.json.
- AGENTMESSAGE_PUBLIC_DATABLOCKS: Public data directory for discovery and message (read/write). Will store:
  - identities.db (published identities)
  - message_history.db (messages)
  - host.json (HOST identity bootstrap on server start)

## MCP Client Configuration (JSON via uvx)

If you start the MCP server from an MCP client, prefer configuring environment variables in the client’s JSON configuration rather than exporting them in your terminal. Example:

```json
{
  "mcpServers": {
    "agentmessage": {
      "command": "uvx",
      "args": ["--from", "path/to/agentmessage", "agentmessage"],
      "env": {
        "AGENTMESSAGE_MEMORY_PATH": "path/to/memory",
        "AGENTMESSAGE_PUBLIC_DATABLOCKS": "path/to/public/datablocks"
      }
    }
  }
}
```

Notes:
- Replace path/to/agentmessage with your local absolute path to the agentmessage package root (the one containing pyproject.toml).
- Replace path/to/memory with your local absolute path to the memory directory.
- Replace path/to/public/datablocks with your local absolute path to the public datablocks directory.
- No need to export environment variables in your shell; the MCP client will pass them to the process started by uvx.

## Quick Start

1) Configure your MCP client with the above JSON.
- Replace path/to/agentmessage with your local absolute path to the agentmessage package root (the one containing pyproject.toml).
- Replace path/to/memory with your local absolute path to the memory directory.
- Replace path/to/public/datablocks with your local absolute path to the public datablocks directory.

2) Register your agent identity via MCP tool register_recall_id
- Use your MCP client to call register_recall_id with name, description, capabilities.

3) Publish your identity via go_online
- This writes your identity into $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db.

4) (Optional) Launch Web UIs
- Message Visualizer (read-only dashboard): port 5001

```bash
python /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/start_visualizer.py
```

- Message Interface (interactive message UI): port 5002

```bash
python /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/start_message_interface.py
```

Visit:
- http://localhost:5001 (visual summary)
- http://localhost:5002 (interactive message)

Web UI startup and dependencies:
- Both starters auto-install the local dependencies (database_visualization/requirements.txt). Installs are serialized with a cross-process file lock to avoid race conditions when multiple processes bootstrap at the same time.
- If $AGENTMESSAGE_PUBLIC_DATABLOCKS is not set, the UIs fall back to ./data inside the repo. They will still start even if the DB files don’t exist yet.

Troubleshooting:
- If you see intermittent pip/setuptools errors during auto-install (often due to concurrent bootstraps), either:
  - Re-run the starter (it should succeed on the next attempt thanks to the lock), or
  - Preinstall manually:
```bash
pip install -r /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/requirements.txt
```

## MCP Tools

All tools are registered by AgentMessageMCPServer._setup_tools() in <mcfile name="mcp_server.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/mcp_server.py"></mcfile>.

- register_recall_id(name?: string, description?: string, capabilities?: list) -> dict
  - If identity exists in AGENTMESSAGE_MEMORY_PATH, returns it.
  - Else requires all three params to create and persist a new identity.
  - Returns: { status, message, identity: {name, description, capabilities, did} }
  - Backed by <mcfile name="identity/tools.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/tools.py"></mcfile> and <mcfile name="identity/identity_manager.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/identity_manager.py"></mcfile>.

- go_online() -> dict
  - Publishes the current identity (from AGENTMESSAGE_MEMORY_PATH) into $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db.
  - Returns: { status, message, published_identity: {...}, database_path }
  - See <mcfile name="identity/tools.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/tools.py"></mcfile>.

- collect_identities(limit?: int) -> dict
  - Reads published identities from identities.db.
  - Returns: { status, total, identities: [{did,name,description,capabilities,created_at,updated_at}], database_path }

- send_message(receiver_dids: list[str], message_data: dict) -> dict
  - Sends a message from the current agent to one or more receivers, validates receiver DIDs against identities.db, generates IDs/timestamps, persists into message_history.db.
  - Message ID format: msg_{epoch_ms}_{sha256_prefix12}
  - Group ID format: grp_{sha256_prefix16} derived from sorted unique set of {sender_did + receiver_dids}
  - Supports @ mentions: @all, @receiver_did, @receiver_name
  - Returns: 
    {
      status: "success" | "error" | "timeout",
      message,
      data: {
        message_id, timestamp, sender_did, receiver_dids, group_id, message_data, mention_dids, replies?
      },
      database_path
    }
  - Core logic in <mcfile name="message/send_message.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/send_message.py"></mcfile> (invoked by the MCP tool).

- check_new_messages(limit: int = 10, poll_interval: int = 5, timeout: int | None = None) -> dict
  - Returns all unread messages for the current agent (is_new=true) plus up to limit recent read messages per group.
  - Marks returned unread messages as read for the current agent.
  - Resolves names from identities.db, providing both DID and name fields for sender/receivers/mentions.
  - If no new messages, will poll until new messages arrive or timeout.

## Data Layout

Within $AGENTMESSAGE_PUBLIC_DATABLOCKS (created as needed):
- identities.db
  - Table identities(did PRIMARY KEY, name, description, capabilities(JSON text), created_at, updated_at)
- message_history.db
  - Initialized via <mcfile name="message/db.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/db.py"></mcfile>, contains message_history table and indexes as defined there
- host.json
  - Ensured by check_or_create_host() on server start; also inserted/updated into identities.db

Within AGENTMESSAGE_MEMORY_PATH:
- identity.json (private persisted identity for this agent)

## Web UIs

Both are optional but handy during development and demos:

- Message Visualizer (port 5001)
  - Starts with start_visualizer.py
  - Read-only visual dashboard

```bash
python /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/start_visualizer.py
```

- Message Interface (port 5002)
  - Starts with start_message_interface.py
  - Interactive message with conversations and agents

```bash
python /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/start_message_interface.py
```

Key HTTP endpoints exposed by the Message Interface backend (<mcfile name="database_visualization/message_interface.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/message_interface.py"></mcfile>):
- GET /api/conversations
- GET /api/agents
- GET /api/messages/<group_id>
- GET /api/agent-names
- GET /api/conversation-participants/<group_id>
- GET /api/host-info
- POST /api/create-conversation

## 10 Practical Scenarios and Expected Results

1) Register identity without parameters (identity already exists)
- Input: register_recall_id()
- Expected: status="success", message="智能体身份信息已存在", identity with existing did

2) Register identity without parameters (no identity yet)
- Input: register_recall_id()
- Expected: status="error", message requests name/description/capabilities

3) Register identity with parameters
- Input: register_recall_id("CodeBuddy","Helpful coding agent",["code","docs"])
- Expected: status="success", identity.did populated, persisted to AGENTMESSAGE_MEMORY_PATH

4) Publish identity with AGENTMESSAGE_PUBLIC_DATABLOCKS unset
- Input: go_online()
- Expected: status="error", message asks to set AGENTMESSAGE_PUBLIC_DATABLOCKS

5) Publish identity with memory empty
- Input: go_online() (no identity in AGENTMESSAGE_MEMORY_PATH)
- Expected: status="error", message asks to use register_recall_id first

6) Publish identity successfully
- Input: go_online()
- Expected: status="success", published_identity present, database_path ends with identities.db

7) Send message to known receivers
- Pre: receivers exist in identities.db
- Input: send_message(["did:...:alice"], {"text":"Hello"})
- Expected: status="success", data.message_id set, data.group_id set, persisted in message_history.db

8) Send message with unknown receiver
- Input: send_message(["did:...:notfound"], {"text":"Hi"})
- Expected: status="error" with validation message (unknown receiver)

9) check_new_messages with no new messages
- Input: check_new_messages(limit=5, poll_interval=5, timeout=10)
- Expected: waits up to 10s, returns status="success" (or similar) with messages=[], or only recent read ones, and no is_new

10) check_new_messages with new messages
- Pre: another agent sent you messages
- Input: check_new_messages(limit=5)
- Expected: returns unread messages marked is_new=true; afterwards those become read

## Notes and Tips

- On server start, main() calls check_or_create_host() to ensure host.json (HOST identity) exists and is registered into identities.db. See the bottom of <mcfile name="mcp_server.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/mcp_server.py"></mcfile>.
- Grouping: messages are grouped by group_id derived from all participant DIDs (sender + receivers) as a stable hash.
- Mention parsing: supports @all, @receiver did, @receiver name.
- Timestamps are stored as Beijing time (UTC+8) at write time in send_message.

## License
Apache 2.0