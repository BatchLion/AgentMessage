"""AgentChat MCP服务器入口"""

from fastmcp import FastMCP
from identity.tools import register_recall_id as _register_recall_id, go_online as _go_online
import sqlite3
import json
import os
from pathlib import Path
from chat.db import init_chat_history_db, get_chat_db_path
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

class AgentChatMCPServer:
    """AgentChat MCP服务器"""
    
    def __init__(self):
        self.mcp = FastMCP("agentchat")
        self._setup_tools()
    
    def _setup_tools(self):
        """设置MCP工具"""
        
        @self.mcp.tool()
        async def register_recall_id(
            name: str = None,
            description: str = None,
            capabilities: list[str] = None
        ) -> dict:
            """注册或回忆智能体身份信息
            
            参数说明:
            - name: 智能体名称（可选，创建新身份时必需）
            - description: 智能体描述（可选，创建新身份时必需）
            - capabilities: 智能体能力列表（可选，创建新身份时必需）
            
            功能说明:
            - 使用AGENTCHAT_MEMORY_PATH环境变量指定的身份记忆目录
            - 如果身份文件存在，返回现有身份信息（忽略输入参数）
            - 如果目录为空且提供了完整参数，创建新的智能体身份
            - 如果目录为空且未提供参数，提示用户提供必要信息
            
            环境变量要求:
            - AGENTCHAT_MEMORY_PATH: 指定智能体身份记忆存储目录
            
            返回格式:
            包含状态、消息和身份信息的字典
            
            使用场景:
            - 智能体启动时回忆自己的身份
            - 为新智能体创建独立的身份记忆
            - 获取智能体的DID、名称、描述、能力等信息
            """
            return _register_recall_id(name, description, capabilities)
        
        @self.mcp.tool()
        async def go_online() -> dict:
            """将智能体身份信息公开，使其他智能体可见
            
            功能说明:
            - 从AGENTCHAT_MEMORY_PATH检索智能体身份信息
            - 如果身份信息存在，将其发布到 $AGENTCHAT_PUBLIC_DATABLOCKS/identities.db 数据库中
            - 如果身份信息为空，提示先使用register_recall_id工具注册身份信息
            - 如果未设置AGENTCHAT_PUBLIC_DATABLOCKS，提示在MCP配置文件中增加该环境变量的定义
            
            环境变量要求:
            - AGENTCHAT_MEMORY_PATH: 指定智能体身份记忆存储目录（读取）
            - AGENTCHAT_PUBLIC_DATABLOCKS: 指定公开数据库目录（写入 identities.db）
            
            返回格式:
            包含操作状态、消息和发布的身份信息的字典，例如:
            {
              "status": "success" | "error",
              "message": "说明信息",
              "published_identity": {
                "did": "...",
                "name": "...",
                "description": "...",
                "capabilities": [...]
              },
              "database_path": "/absolute/path/to/identities.db"
            }
            
            使用场景:
            - 智能体希望让其他智能体发现自己时
            - 将私有身份信息发布到公共数据库
            - 加入智能体网络，实现身份可见性
            
            注意事项:
            - 发布前请确保已通过register_recall_id工具注册身份
            - 请确保已设置AGENTCHAT_PUBLIC_DATABLOCKS且指向可写目录
            - 发布的信息将存储在本地公共数据库中供其他智能体查询
            """
            return _go_online()
        
        # 新增：收集 identities.db 中的公开身份记录
        @self.mcp.tool()
        async def collect_identities(limit: int | None = None) -> dict:
            """获取 identities.db 数据库中的公开身份记录
            
            读取路径:
            - $AGENTCHAT_PUBLIC_DATABLOCKS/identities.db
            
            参数:
            - limit: 可选，限制返回的记录条数
            
            返回:
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
              "database_path": "<db绝对路径>"
            }
            """
            try:
                public_dir_env = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
                if not public_dir_env:
                    return {
                        "status": "error",
                        "message": "未设置AGENTCHAT_PUBLIC_DATABLOCKS环境变量，请在MCP配置文件中增加该环境变量的定义"
                    }
                
                db_path = Path(public_dir_env) / "identities.db"
                if not db_path.exists():
                    return {
                        "status": "error",
                        "message": "未找到 identities.db",
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
                    # capabilities 存储为 JSON 文本，需要反序列化为列表
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
                    "message": f"数据库操作失败: {str(e)}"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"读取身份信息失败: {str(e)}"
                }
        
        @self.mcp.tool()
        async def send_message(
            receiver_dids: list[str],
            message_data: dict,
            wait_for_replies: bool = False,
            poll_interval: int = 5,
            timeout: int = 300
        ) -> dict:
            """向receiver_dids列表中的每个接收者发送消息，并存储到 $AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db
            
            入参:
            - receiver_dids: 接收者 DID 列表（不能为空）
            - message_data: 消息数据对象（可包含文本、代码、图片、音频、视频、文件名与格式等）
            - wait_for_replies: 是否等待所有接收者的回复（默认 True）
            - poll_interval: 轮询间隔秒数（默认 5 秒）
            - timeout: 等待超时时间秒数（默认 300 秒）
            
            处理流程:
            - 读取发送者 DID（当前智能体）
            - 验证接收者 DID 列表是否都存在于 identities.db 数据库中
            - 生成唯一 message_id（规则：msg_{epoch_ms}_{sha256前12位}）
            - 生成北京时间 timestamp（UTC+8，格式 YYYY-MM-DD HH:MM:SS）
            - 计算 group_id（将 sender_did 与 receiver_dids 组成集合，排序后取 sha256 前16位，加前缀 grp_）
            - 解析 @ 提及（支持 @all、@接收者DID、@接收者name）
            - 将消息保存到 $AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db 的 chat_history 表
            - 如果 wait_for_replies=True，轮询等待所有接收者回复
            
            返回:
            {
              "status": "success" | "error" | "timeout",
              "message": "说明信息",
              "data": {
                "message_id": "...",
                "timestamp": "YYYY-MM-DD HH:MM:SS",
                "sender_did": "...",
                "receiver_dids": [...],
                "group_id": "grp_xxx",
                "message_data": {...},
                "mention_dids": [...],
                "replies": [...] // 当 wait_for_replies=True 时包含接收到的回复
              },
              "database_path": "/absolute/path/to/chat_history.db"
            }
            """
            # 获取发送者身份
            try:
                identity_manager = IdentityManager()
                if not identity_manager.has_identity():
                    return {
                        "status": "error",
                        "message": "未找到本机身份信息，请先通过 register_recall_id 注册身份"
                    }
                identity = identity_manager.load_identity()
                if not identity:
                    return {
                        "status": "error",
                        "message": "无法加载本机身份信息"
                    }
                sender_did = identity.did
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"读取发送者身份失败: {str(e)}"
                }
            
            from chat.send_message import _send_message
            return await _send_message(sender_did, receiver_dids, message_data,
                                       wait_for_replies, poll_interval, timeout)

        @self.mcp.tool()
        async def chat_room(limit: int = 10, poll_interval: int = 5, timeout: int | None = None) -> dict:
            """创建聊天室视图，基于每条消息的 read_status 字段返回未读消息，并读取后将当前用户标记为已读
            
            参数:
            - limit: 每个群组返回的已读消息条数上限（默认10）。返回“全部未读消息 + 最近的 limit 条已读消息”，并按时间升序排列；当为非正数时，不做限制（返回全部消息）。
            - poll_interval: 轮询无新消息时的间隔秒数（默认 5 秒）
            - timeout: 轮询等待新消息的超时时间（秒）。为 None 时将一直等待直到出现新消息。
            
            行为说明:
            - 获取本机身份DID
            - 在 $AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db 中查找接收者包含本机DID的消息
            - 根据 read_status 字段判断消息是否已读，标记 is_new
            - 将当前用户在查询到的未读消息中的已读状态设为 true
            - 返回时将 DID 转换为 name（sender_name、receiver_names、mention_names），同时保留原始 DID 字段（sender_did、receiver_dids、mention_dids）
            """
            try:
                # 当前身份
                identity_manager = IdentityManager()
                if not identity_manager.has_identity():
                    return {
                        "status": "error",
                        "message": "未找到本机身份信息，请先通过 register_recall_id 注册身份"
                    }
                identity = identity_manager.load_identity()
                if not identity:
                    return {
                        "status": "error",
                        "message": "无法加载本机身份信息"
                    }
                my_did = identity.did

                # 新增：当没有新消息时轮询，直到有新消息或超时
                start_time = time.time()
                while True:
                    # 初始化/定位聊天数据库（使用 $AGENTCHAT_PUBLIC_DATABLOCKS）
                    db_path = init_chat_history_db()
                    conn = sqlite3.connect(db_path)
                    try:
                        cursor = conn.cursor()

                        # 查找所有包含本机DID作为接收者的群组
                        cursor.execute(
                            """
                            SELECT DISTINCT group_id
                            FROM chat_history
                            WHERE receiver_dids LIKE ?
                            """,
                            (f'%"{my_did}"%',),
                        )
                        groups_with_messages = [row[0] for row in cursor.fetchall()]

                        groups = []
                        total_new = 0

                        # 预备 identities.db 路径，供 DID->name 转换
                        did_to_name_cache: dict[str, str] = {}
                        public_dir_env = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
                        id_db_path = Path(public_dir_env) / "identities.db" if public_dir_env else None
                        id_conn = None
                        if id_db_path and id_db_path.exists():
                            try:
                                id_conn = sqlite3.connect(id_db_path)
                            except Exception:
                                id_conn = None

                        for gid in sorted(groups_with_messages):
                            # 取该组内所有消息（升序），在内存中过滤出未读与已读，返回“全部未读 + 最近 limit 条已读”
                            cursor.execute(
                                """
                                SELECT message_id, timestamp, sender_did, receiver_dids, message_data, mention_dids, read_status
                                FROM chat_history
                                WHERE group_id = ?
                                ORDER BY timestamp ASC
                                """,
                                (gid,),
                            )
                            rows = cursor.fetchall()

                            # 第一次遍历：解析 JSON，分离未读/已读，收集 DID 集合
                            unread_items = []  # [(mid, ts, sender, receivers, msg_data, mentions, existing_rs)]
                            read_items = []    # 同上
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

                            # 选取最近的 limit 条已读消息
                            if isinstance(limit, int) and limit > 0:
                                selected_read = read_items[-limit:]
                            else:
                                selected_read = read_items

                            # 组合返回集：全部未读 + 选中的已读，然后按时间升序排序
                            selected_msgs = unread_items + selected_read
                            selected_msgs.sort(key=lambda x: x[1])  # 按 timestamp 排序

                            # 查询 DID -> name 映射（按本次返回的消息所涉及的 DID 批量查询）
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

                            # 构建返回消息
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

                            # 写回：将未读的消息标记为已读（仅更新当前用户的 read_status）
                            for mid, existing_rs in messages_to_mark_read:
                                try:
                                    existing_rs = existing_rs if isinstance(existing_rs, dict) else {}
                                    existing_rs[my_did] = True
                                    cursor.execute(
                                        "UPDATE chat_history SET read_status = ? WHERE message_id = ?",
                                        (json.dumps(existing_rs, ensure_ascii=False), mid),
                                    )
                                except Exception:
                                    # 单条失败不影响整体
                                    pass

                            total_new += new_count
                            # 仅当该群组存在新消息时，才返回该群组（返回“全部未读 + 最近 limit 条已读”）
                            if new_count > 0:
                                groups.append({
                                    "group_id": gid,
                                    "new_count": new_count,
                                    "messages": messages
                                })

                        if id_conn:
                            id_conn.close()

                        conn.commit()

                        # 如果有新消息，立即返回并提醒使用 send_message 回复
                        if total_new > 0:
                            prompt_msg = f"你有{total_new}条新消息。请使用 send_message 回复，或继续选择消息进行回复。"
                            return {
                                "status": "success",
                                "message": "已生成聊天室视图（含新消息）",
                                "groups": groups,
                                "database_path": str(db_path),
                                "prompt": prompt_msg
                            }
                    finally:
                        conn.close()

                    # 无新消息 -> 判断是否超时或继续轮询
                    if timeout is not None and time.time() - start_time >= timeout:
                        return {
                            "status": "timeout",
                            "message": "等待新消息超时",
                            "groups": [],
                            "database_path": str(db_path),
                            "prompt": "暂无新消息。"
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
                    "message": f"数据库操作失败: {str(e)}"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"生成聊天室视图失败: {str(e)}"
                }

    def run(self, transport: str = "stdio"):
        """运行MCP服务器"""
        self.mcp.run(transport=transport)

def check_or_create_host() -> dict | None:
    """检查或创建HOST信息。
    行为：
    - 检查 $AGENTCHAT_PUBLIC_DATABLOCKS/host.json 是否存在且包含 name、description、did
    - 若存在且完整：打印提示并返回该信息
    - 若不存在或不完整：生成 DID，创建并保存到 host.json，然后打印并返回
    - 将HOST信息添加到 identities.db 数据库中
    """
    try:
        public_dir = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
        if not public_dir:
            print("警告: 未设置 AGENTCHAT_PUBLIC_DATABLOCKS 环境变量，无法创建/读取 host.json")
            return None

        public_path = Path(public_dir)
        public_path.mkdir(parents=True, exist_ok=True)

        host_file = public_path / "host.json"
        host_data = None
        is_new_host = False

        # 若存在则尝试读取并校验
        if host_file.exists():
            try:
                with open(host_file, "r", encoding="utf-8") as f:
                    host_data = json.load(f)
                if all(k in host_data for k in ["name", "description", "did"]):
                    print("HOST信息已存在：")
                    print(f"  名称: {host_data.get('name')}")
                    print(f"  描述: {host_data.get('description')}")
                    print(f"  DID: {host_data.get('did')}")
                else:
                    host_data = None
            except Exception as e:
                print(f"读取 host.json 失败，将重新创建：{e}")
                host_data = None

        # 不存在或不完整，创建新的
        if not host_data:
            is_new_host = True
            did_gen = DIDGenerator()
            host_did = did_gen.generate_did("HOST")  # 形如 did:agentchat:local:xxxx

            host_data = {
                "name": "HOST",
                "description": "The user of the MCP service and the host of the agents.",
                "did": host_did,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "role": "host",
            }
            with open(host_file, "w", encoding="utf-8") as f:
                json.dump(host_data, f, ensure_ascii=False, indent=2)

            print("已创建HOST信息：")
            print(f"  名称: {host_data['name']}")
            print(f"  描述: {host_data['description']}")
            print(f"  DID: {host_data['did']}")
            print(f"  保存位置: {host_file}")

        # 将HOST信息添加到identities.db数据库
        try:
            db_path = public_path / "identities.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 创建identities表（如果不存在）
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
            
            # HOST的capabilities设置为空数组
            capabilities_json = json.dumps([], ensure_ascii=False)
            
            # 插入或更新HOST身份信息
            cursor.execute("""
                INSERT OR REPLACE INTO identities 
                (did, name, description, capabilities, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (host_data['did'], host_data['name'], host_data['description'], capabilities_json))
            
            conn.commit()
            conn.close()
            
            if is_new_host:
                print(f"  已将HOST信息添加到数据库: {db_path}")
            else:
                print(f"  已更新HOST信息到数据库: {db_path}")
                
        except Exception as e:
            print(f"警告: 将HOST信息添加到identities.db失败: {e}")
            # 不影响主要功能，继续执行

        return host_data

    except Exception as e:
        print(f"检查或创建 HOST 信息时发生错误：{e}")
        return None

# New: launch visualization tools at startup
def _launch_visual_tools():
    try:
        base_dir = Path(__file__).parent / "database_visualization"
        start_visualizer = base_dir / "start_visualizer.py"
        start_chat = base_dir / "start_chat_interface.py"

        if start_visualizer.exists():
            subprocess.Popen(
                [sys.executable, str(start_visualizer)],
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            print(f"警告: 未找到 {start_visualizer}")

        if start_chat.exists():
            subprocess.Popen(
                [sys.executable, str(start_chat)],
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            print(f"警告: 未找到 {start_chat}")

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
        print(f"警告: 启动可视化工具失败: {e}")

def main():
    """主函数 - uvx入口点"""
    # 启动前先检查/创建 HOST 信息
    check_or_create_host()

    # New: auto-start UI tools in background and open browser
    _launch_visual_tools()

    server = AgentChatMCPServer()
    server.run()

if __name__ == "__main__":
    main()
