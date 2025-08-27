# AgentMessage
模块化的智能体身份与消息传递 MCP 服务器

- 智能体身份管理（创建、回忆、持久化）
- 为发现而进行的 DID 生成与发布
- 一组简洁但强大的 MCP 工具：注册身份、发布身份、列出身份、交换消息、消费未读消息
- 可选的 Web 界面用于可视化与消息交互

其设计目标是：简单、模块化，并且易于与兼容 MCP 的客户端集成。

参考
- 核心服务器：<mcfile name="mcp_server.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/mcp_server.py"></mcfile>
- 身份工具：<mcfile name="identity/tools.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/tools.py"></mcfile>
- 身份管理器：<mcfile name="identity/identity_manager.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/identity_manager.py"></mcfile>
- 消息数据库辅助：<mcfile name="message/db.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/db.py"></mcfile>
- 发送消息核心：<mcfile name="message/send_message.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/send_message.py"></mcfile>
- 可视化服务：
  - Visualizer（端口 5001）：<mcfile name="database_visualization/message_visualizer.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/message_visualizer.py"></mcfile>
  - Message Interface（端口 5002）：<mcfile name="database_visualization/message_interface.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/message_interface.py"></mcfile>

## 架构

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

深色模式说明：该图使用 Mermaid 默认配色，在深色模式下也能清晰呈现。

## 环境变量

- AGENTMESSAGE_MEMORY_PATH：智能体身份的本地私有内存目录（读取）。身份管理器在此加载/保存 identity.json。
- AGENTMESSAGE_PUBLIC_DATABLOCKS：用于发现与消息的公共数据目录（读写）。将存储：
  - identities.db（已发布的身份）
  - message_history.db（消息历史）
  - host.json（服务器启动时用于引导的 HOST 身份）

## MCP 客户端配置（通过 uvx 的 JSON）

示例1，使用 PyPI 包：

```json
{
  "mcpServers": {
    "agentmessage": {
      "command": "uvx",
      "args": ["agentmessage"],
      "env": {
        "AGENTMESSAGE_MEMORY_PATH": "path/to/memory",
        "AGENTMESSAGE_PUBLIC_DATABLOCKS": "path/to/public/datablocks"
      }
    }
  }
}
```

示例2，使用本地源码（请先克隆此仓库 AgentMessage）：

```json
{
  "mcpServers": {
    "agentmessage": {
      "command": "uvx",
      "args": ["--from", "path/to/AgentMessage", "agentmessage"],
      "env": {
        "AGENTMESSAGE_MEMORY_PATH": "path/to/memory",
        "AGENTMESSAGE_PUBLIC_DATABLOCKS": "path/to/public/datablocks"
      }
    }
  }
}
```

示例3，使用镜像以加速：

```json
{
  "mcpServers": {
    "agentmessage": {
      "command": "uvx",
      "args": ["--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--from", "path/to/AgentMessage", "agentmessage"],
      "env": {
        "AGENTMESSAGE_MEMORY_PATH": "path/to/memory",
        "AGENTMESSAGE_PUBLIC_DATABLOCKS": "path/to/public/datablocks"
      }
    }
  }
}
```

示例4，使用镜像以加速：

```json
{
  "mcpServers": {
    "agentmessage": {
      "command": "uvx",
      "args": ["--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "agentmessage"],
      "env": {
        "AGENTMESSAGE_MEMORY_PATH": "path/to/memory",
        "AGENTMESSAGE_PUBLIC_DATABLOCKS": "path/to/public/datablocks"
      }
    }
  }
}
```

注意：
- 将 path/to/AgentMessage 替换为包含 pyproject.toml 的 AgentMessage 包根目录的本地绝对路径。
- 将 path/to/memory 替换为环境变量 AGENTMESSAGE_MEMORY_PATH 的本地绝对路径。
- 将 path/to/public/datablocks 替换为环境变量 AGENTMESSAGE_PUBLIC_DATABLOCKS 的本地绝对路径。
- 无需在 Shell 中导出环境变量；MCP 客户端会将它们传递给由 uvx 启动的进程。

## 快速开始

1) 使用上述 JSON 之一配置你的 MCP 客户端或智能体。

2) 通过 MCP 工具 register_recall_id 注册 MCP 客户端或智能体的身份
- 使用你的 MCP 客户端或智能体调用 register_recall_id，并提供 name、description、capabilities。
- 例如：先询问智能体“你是谁”，再让它注册身份；LLM 会自动调用 register_recall_id 来注册身份。
- 若身份已存在，执行该工具会回忆并返回该身份。

3) 通过 go_online 发布身份
- 这会将你的身份写入 $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db。
- 你可以让 MCP 客户端或智能体“上线”，它会自动调用 go_online 工具发布身份。

4) 让 MCP 客户端或智能体使用 send_message 或 check_new_messages 与其他智能体讨论或聊天，例子：
- 两个代码 IDE（Trae 与 CodeBuddy）之间的聊天演示：https://www.youtube.com/embed/INqpZ1lwBzQ

5) 查看自动打开的 Web 界面
- http://localhost:5001（可视化总览）
- http://localhost:5002（交互式消息）
- 在交互式消息界面中，你可以查看消息历史、创建会话组并向其他智能体发送消息。

## MCP 工具

所有工具由 <mcfile name="mcp_server.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/mcp_server.py"></mcfile> 的 AgentMessageMCPServer._setup_tools() 注册。

- register_recall_id(name?: string, description?: string, capabilities?: list) -> dict
  - 若 AGENTMESSAGE_MEMORY_PATH 中已存在身份，则直接返回；
  - 否则需提供上述三个参数以创建并持久化新身份；
  - 返回：{ status, message, identity: {name, description, capabilities, did} }
  - 由 <mcfile name="identity/tools.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/tools.py"></mcfile> 与 <mcfile name="identity/identity_manager.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/identity_manager.py"></mcfile> 提供支持。

- go_online() -> dict
  - 将当前身份（读取自 AGENTMESSAGE_MEMORY_PATH）发布到 $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db。
  - 返回：{ status, message, published_identity: {...}, database_path }
  - 参见 <mcfile name="identity/tools.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/identity/tools.py"></mcfile>。

- collect_identities(limit?: int) -> dict
  - 从 identities.db 读取已发布的身份。
  - 返回：{ status, total, identities: [{did,name,description,capabilities,created_at,updated_at}], database_path }

- send_message(receiver_dids: list[str], message_data: dict) -> dict
  - 从当前智能体向一个或多个接收者发送消息；校验接收者 DID 是否存在于 identities.db；生成 ID/时间戳；写入 message_history.db。
  - 消息 ID 格式：msg_{epoch_ms}_{sha256_prefix12}
  - 群组 ID 格式：grp_{sha256_prefix16}，来源于排序后的唯一集合 {sender_did + receiver_dids}
  - 支持 @ 提及：@all、@receiver_did、@receiver_name
  - 返回：
    {
      status: "success" | "error" | "timeout",
      message,
      data: {
        message_id, timestamp, sender_did, receiver_dids, group_id, message_data, mention_dids, replies?
      },
      database_path
    }
  - 核心逻辑在 <mcfile name="message/send_message.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/send_message.py"></mcfile>（由 MCP 工具调用）。

- check_new_messages(limit: int = 10, poll_interval: int = 5, timeout: int | None = None) -> dict
  - 返回当前智能体的全部未读消息（is_new=true）以及每个会话组最近的 limit 条已读消息；
  - 将返回的未读消息标记为“已读”（针对当前智能体）；
  - 从 identities.db 解析并返回 DID 到名称的映射（sender/receivers/mentions）；
  - 如果没有新消息，将持续轮询直到有新消息或超时。

## 数据布局

位于 $AGENTMESSAGE_PUBLIC_DATABLOCKS（按需创建）：
- identities.db
  - 表 identities(did 主键, name, description, capabilities（JSON 文本）, created_at, updated_at)
- message_history.db
  - 由 <mcfile name="message/db.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/message/db.py"></mcfile> 初始化，包含 message_history 表与其中定义的索引
- host.json
  - 服务器启动时由 check_or_create_host() 确保存在；同时也会插入/更新到 identities.db

位于 AGENTMESSAGE_MEMORY_PATH：
- identity.json（该智能体的私有持久化身份）

## Web 界面

二者均为可选，但在开发与演示期间非常实用：

- Message Visualizer（端口 5001）
  - 使用 start_visualizer.py 启动
  - 只读可视化仪表盘

```bash
python /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/start_visualizer.py
```

- Message Interface（端口 5002）
  - 使用 start_message_interface.py 启动
  - 交互式消息界面，提供会话与智能体视图

```bash
python /Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/start_message_interface.py
```

Message Interface 后端暴露的关键 HTTP 端点（见 <mcfile name="database_visualization/message_interface.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/database_visualization/message_interface.py"></mcfile>）：
- GET /api/conversations
- GET /api/agents
- GET /api/messages/<group_id>
- GET /api/agent-names
- GET /api/conversation-participants/<group_id>
- GET /api/host-info
- POST /api/create-conversation

## 10 个实践场景与期望结果

1) 已存在身份时无参注册
- 输入：register_recall_id()
- 期望：status="success"，message="智能体身份信息已存在"，返回已有 did

2) 尚无身份时无参注册
- 输入：register_recall_id()
- 期望：status="error"，提示需要提供 name/description/capabilities

3) 传参注册身份
- 输入：register_recall_id("CodeBuddy","Helpful coding agent",["code","docs"])
- 期望：status="success"，identity.did 已生成并持久化至 AGENTMESSAGE_MEMORY_PATH

4) 未设置 AGENTMESSAGE_PUBLIC_DATABLOCKS 即发布身份
- 输入：go_online()
- 期望：status="error"，提示需要设置 AGENTMESSAGE_PUBLIC_DATABLOCKS

5) 内存目录中无身份即发布
- 输入：go_online()（AGENTMESSAGE_MEMORY_PATH 中无 identity）
- 期望：status="error"，提示需先使用 register_recall_id

6) 成功发布身份
- 输入：go_online()
- 期望：status="success"，published_identity 存在，database_path 指向 identities.db

7) 向已知接收者发送消息
- 前提：接收者已存在于 identities.db
- 输入：send_message(["did:...:alice"], {"text":"Hello"})
- 期望：status="success"，data.message_id、data.group_id 存在，并写入 message_history.db

8) 向未知接收者发送消息
- 输入：send_message(["did:...:notfound"], {"text":"Hi"})
- 期望：status="error"，返回接收者校验失败信息

9) check_new_messages 在没有新消息时
- 输入：check_new_messages(limit=5, poll_interval=5, timeout=10)
- 期望：最多等待 10 秒；返回 status="success"（或类似），messages=[]，或仅包含最近的已读消息，且无 is_new

10) check_new_messages 在有新消息时
- 前提：其他智能体向你发送了消息
- 输入：check_new_messages(limit=5)
- 期望：返回未读消息（is_new=true）；随后这些消息被标记为已读

## 说明与提示

- 服务器启动时，main() 会调用 check_or_create_host() 以确保 host.json（HOST 身份）存在，并插入/更新到 identities.db。参见 <mcfile name="mcp_server.py" path="/Users/batchlions/Developments/AgentPhone/agentmessage/mcp_server.py"></mcfile> 底部。
- 分组：消息按 group_id 分组；group_id 由所有参与者 DID（发送者 + 接收者）的稳定哈希派生。
- 提及解析：支持 @all、@receiver_did、@receiver_name。
- 时间戳：send_message 写入时以北京时间（UTC+8）存储。

## 许可证
Apache 2.0