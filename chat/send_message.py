import os
import re
import json
import time
import asyncio
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from chat.db import init_chat_history_db
from identity.identity_manager import IdentityManager

async def _send_message(
    sender_did: str,
    receiver_dids: list[str],
    message_data: dict,
    wait_for_replies: bool = False, # - wait_for_replies: 是否等待所有接收者的回复（默认 True）
    poll_interval: int = 5,# - poll_interval: 轮询间隔秒数（默认 5 秒）
    timeout: int = 300 # - timeout: 等待超时时间秒数（默认 300 秒）
) -> dict:
    """
    向服务器发送消息，并存储到 $AGENTCHAT_PUBLIC_DATABLOCKS/chat_history.db
    """
    # 参数校验
    if not isinstance(receiver_dids, list) or len(receiver_dids) == 0:
        return {
            "status": "error",
            "message": "receiver_dids 不能为空且必须为数组"
        }
    if not isinstance(message_data, dict):
        return {
            "status": "error",
            "message": "message_data 必须为对象"
        }
    
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
    
    # 新增：验证 receiver_dids 是否都存在于 identities.db 中
    try:
        public_dir_env = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
        if not public_dir_env:
            return {
                "status": "error",
                "message": "未设置AGENTCHAT_PUBLIC_DATABLOCKS环境变量，请在MCP配置文件中增加该环境变量的定义"
            }
        id_db_path = Path(public_dir_env) / "identities.db"
        if not id_db_path.exists():
            return {
                "status": "error",
                "message": "未找到 identities.db",
                "expected_path": str(id_db_path)
            }
        
        # 查询接收者 DID 在 identities.db 中的存在情况
        uniq_receivers = list(dict.fromkeys(receiver_dids))  # 去重保持顺序
        placeholders = ",".join("?" for _ in uniq_receivers)
        conn_ids = sqlite3.connect(id_db_path)
        try:
            cur = conn_ids.cursor()
            # 查询数据库中存在的 DIDs
            cur.execute(
                f"SELECT did FROM identities WHERE did IN ({placeholders})",
                tuple(uniq_receivers),
            )
            existing_dids = {row[0] for row in cur.fetchall()}
            
            # 找出不存在的 DIDs
            missing_dids = [did for did in uniq_receivers if did not in existing_dids]
            
            if missing_dids:
                # 如果有不存在的 DID，获取所有身份记录供校对
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
                    "message": f"接收者列表中有 {len(missing_dids)} 个 DID 不存在于 identities.db 数据库中。请从下面的身份记录中选择正确的接收者 DID，并重新发送消息。",
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
            "message": f"验证接收者 DID 失败: {str(e)}",
            "receiver_dids": receiver_dids
        }

    # 新增：接收者列表排除发送者校验
    if sender_did in receiver_dids:
        try:
            public_dir_env = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
            if not public_dir_env:
                return {
                    "status": "error",
                    "message": "未设置AGENTCHAT_PUBLIC_DATABLOCKS环境变量，请在MCP配置文件中增加该环境变量的定义"
                }
            id_db_path = Path(public_dir_env) / "identities.db"
            if not id_db_path.exists():
                return {
                    "status": "error",
                    "message": "未找到 identities.db",
                    "expected_path": str(id_db_path),
                    "receiver_dids": receiver_dids
                }
            
            # 查询接收者（含发送者自身）在 identities.db 中的身份记录
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
                "message": "接收者列表包含发送者（你正在给自己发消息）。请根据返回的身份记录确认接收者身份信息，并从接收者列表中移除你自己的DID后再重试。",
                "receiver_dids": receiver_dids,
                "sender_did": sender_did,
                "identities": identities,
                "database_path": str(id_db_path)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"校验接收者列表失败: {str(e)}",
                "receiver_dids": receiver_dids,
                "sender_did": sender_did
            }
    
    # 生成时间与ID
    now_utc = datetime.now(timezone.utc)
    beijing_time = now_utc.astimezone(timezone(timedelta(hours=8)))
    timestamp_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    epoch_ms = int(now_utc.timestamp() * 1000)
    
    # 计算 group_id（基于 DID 集合哈希）
    unique_dids = sorted(set([sender_did] + receiver_dids))
    group_basis = "|".join(unique_dids)
    group_hash = hashlib.sha256(group_basis.encode("utf-8")).hexdigest()[:16]
    group_id = f"grp_{group_hash}"
    
    # 生成 message_id（时间戳 + 内容哈希）
    try:
        msg_payload_preview = json.dumps(message_data, ensure_ascii=False, sort_keys=True)
    except Exception:
        msg_payload_preview = str(message_data)
    mid_basis = f"{sender_did}|{','.join(sorted(receiver_dids))}|{epoch_ms}|{msg_payload_preview}"
    message_id = f"msg_{epoch_ms}_{hashlib.sha256(mid_basis.encode('utf-8')).hexdigest()[:12]}"
    
    # 解析 @ 提及
    mention_dids: list[str] = []
    try:
        # 提取文本候选字段
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
            mention_dids = list(dict.fromkeys(receiver_dids))  # 去重保持顺序
        else:
            # 先基于 DID 匹配
            mentioned = set()
            for did in receiver_dids:
                if f"@{did}" in combined_text:
                    mentioned.add(did)
            
            # 再基于名称匹配（从 identities.db 读取接收者名称映射）
            try:
                public_dir_env = os.getenv("AGENTCHAT_PUBLIC_DATABLOCKS")
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
                # 名称解析失败不影响发送
                pass
            
            mention_dids = list(mentioned)
    except Exception:
        mention_dids = []
    
    # 写入 chat_history.db
    try:
        # 初始化数据库（内部会检查 AGENTCHAT_PUBLIC_DATABLOCKS 是否已设置）
        db_path = init_chat_history_db()
        
        # 初始化 read_status：所有接收者标记为未读（false）
        read_status = {did: False for did in receiver_dids}
        
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_history
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
        
        # 基础返回数据
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
        
        # 如果不等待回复，直接返回
        if not wait_for_replies:
            return {
                "status": "success",
                "message": "消息已发送",
                "data": base_data,
                "database_path": str(db_path),
            }
        
        # 等待回复功能
        start_time = time.time()
        replies = []
        
        while time.time() - start_time < timeout:
            # 轮询检查是否所有接收者都已回复
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.cursor()
                # 查找在该群组中发送时间晚于原消息的新消息
                cursor.execute(
                    """
                    SELECT message_id, timestamp, sender_did, message_data
                    FROM chat_history
                    WHERE group_id = ? 
                    AND timestamp > ?
                    AND sender_did IN ({})
                    ORDER BY timestamp ASC
                    """.format(",".join("?" for _ in receiver_dids)),
                    (group_id, timestamp_str, *receiver_dids),
                )
                new_messages = cursor.fetchall()
                
                # 收集回复并检查是否所有接收者都已回复
                replied_dids = set()
                for msg_id, msg_ts, msg_sender, msg_data_json in new_messages:
                    if msg_sender in receiver_dids:
                        replied_dids.add(msg_sender)
                        # 检查是否已经添加过这个回复
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
                            
                            # 新增：将该条“回复消息”对当前用户标记为已读
                            # 当前用户 DID 在本函数中为 sender_did
                            try:
                                cursor.execute(
                                    "SELECT read_status FROM chat_history WHERE message_id = ?",
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
                                        "UPDATE chat_history SET read_status = ? WHERE message_id = ?",
                                        (json.dumps(rs, ensure_ascii=False), msg_id),
                                    )
                                    conn.commit()
                            except Exception:
                                # 出错不影响主流程
                                pass
                    
                # 如果所有接收者都已回复，返回结果
                if len(replied_dids) == len(receiver_dids):
                    base_data["replies"] = replies
                    return {
                        "status": "success",
                        "message": f"消息已发送，所有 {len(receiver_dids)} 个接收者都已回复。你可以使用send_message回复或发送新消息。",
                        "data": base_data,
                        "database_path": str(db_path),
                    }
            finally:
                conn.close()
            
            # 等待一段时间后继续轮询
            await asyncio.sleep(poll_interval)
        
        # 超时情况
        base_data["replies"] = replies
        replied_count = len(set(r["sender_did"] for r in replies))
        return {
            "status": "timeout",
            "message": f"消息已发送，但等待回复超时。{replied_count}/{len(receiver_dids)} 个接收者已回复。你可以继续回复或发送新消息。",
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
            "message": f"数据库操作失败: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"发送消息失败: {str(e)}"
        }