"""聊天历史数据库初始化与管理（步骤 2.1）

- 数据库存放路径：$AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db
- 表：chat_history
- 字段：
    - message_id: 消息唯一ID
    - timestamp: 北京时间（UTC+8）字符串（格式例如：YYYY-MM-DD HH:MM:SS）
    - sender_did: 发送者DID
    - receiver_dids: 接收者DID列表（JSON数组字符串）
    - group_id: 由发送者DID与接收者DID集合计算的哈希，用于唯一标识单聊/群聊
    - message_data: 消息数据（JSON对象字符串，包含文本、代码、图片、音频、视频、文件信息等）
    - mention_dids: 被@的接收者DID列表（JSON数组字符串）
    - read_status: 每个接收者的已读状态（JSON对象字符串，键为DID，值为布尔值）

注意：
- 本文件仅负责数据库与表结构初始化，不包含消息写入逻辑（将在 2.3 实现）。
- 若未设置 AGENTCHAT_PUBLIC_DATABLOCKS，将抛出异常，请在 MCP 配置文件中增加该环境变量的定义。
"""

import os
import sqlite3
from pathlib import Path


def get_data_dir() -> Path:
    """返回数据目录路径：$AGENTCHAT_PUBLIC_DATABLOCKS"""
    public_dir_env = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
    if not public_dir_env:
        raise EnvironmentError(
            "未设置AGENTCHAT_PUBLIC_DATABLOCKS环境变量，请在MCP配置文件中增加该环境变量的定义"
        )
    data_dir = Path(public_dir_env)
    if data_dir.exists() and not data_dir.is_dir():
        raise NotADirectoryError(f"AGENTCHAT_PUBLIC_DATABLOCKS指向的路径不是目录: {str(data_dir)}")
    return data_dir


def get_chat_db_path() -> Path:
    """返回 $AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db 的完整路径"""
    return get_data_dir() / "chat_history.db"


def init_chat_history_db() -> Path:
    """初始化 $AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db 和必要的表结构、索引"""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = get_chat_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # 创建聊天历史表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                message_id TEXT PRIMARY KEY,
                timestamp  TEXT NOT NULL,
                sender_did TEXT NOT NULL,
                receiver_dids TEXT NOT NULL, -- JSON 数组字符串
                group_id   TEXT NOT NULL,
                message_data  TEXT NOT NULL, -- JSON 对象字符串
                mention_dids  TEXT NOT NULL, -- JSON 数组字符串
                read_status   TEXT NOT NULL DEFAULT '{}' -- JSON 对象字符串，记录每个接收者的已读状态
            )
            """
        )

        # 检查是否需要添加 read_status 列（迁移现有数据库）
        cursor.execute("PRAGMA table_info(chat_history)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'read_status' not in columns:
            cursor.execute("ALTER TABLE chat_history ADD COLUMN read_status TEXT NOT NULL DEFAULT '{}'")

        # 常用索引（SQLite 需单独创建索引，不能在 CREATE TABLE 中内联）
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_history_group_id_idx ON chat_history(group_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_history_sender_did_idx ON chat_history(sender_did)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS chat_history_timestamp_idx ON chat_history(timestamp)"
        )

        conn.commit()
    finally:
        conn.close()

    return db_path