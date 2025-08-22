"""身份管理工具"""

import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from .identity_manager import IdentityManager
from .models import AgentIdentity

def register_recall_id(
    name: Optional[str] = None,
    description: Optional[str] = None,
    capabilities: Optional[list] = None
) -> Dict[str, Any]:
    """注册或回忆智能体身份信息
    
    Args:
        name: 智能体名称（可选）
        description: 智能体描述（可选）
        capabilities: 智能体能力列表（可选）
    
    Returns:
        包含身份信息或提示信息的字典
    """
    identity_manager = IdentityManager()
    
    # 检查是否已有身份信息
    if identity_manager.has_identity():
        # 如果已有身份信息，直接返回
        existing_identity = identity_manager.load_identity()
        if existing_identity:
            return {
                "status": "success",
                "message": "智能体身份信息已存在",
                "identity": {
                    "name": existing_identity.name,
                    "description": existing_identity.description,
                    "capabilities": existing_identity.capabilities,
                    "did": existing_identity.did
                }
            }
    
    # 如果没有身份信息，检查参数
    if not name or not description or not capabilities:
        return {
            "status": "error",
            "message": "请提供智能体的name、description和capabilities参数",
            "required_params": {
                "name": "智能体名称",
                "description": "智能体描述",
                "capabilities": "智能体能力列表（数组格式）"
            }
        }
    
    # 创建新的身份信息
    try:
        new_identity = identity_manager.create_identity(name, description, capabilities)
        
        # 保存身份信息
        if identity_manager.save_identity(new_identity):
            return {
                "status": "success",
                "message": "智能体身份信息创建成功",
                "identity": {
                    "name": new_identity.name,
                    "description": new_identity.description,
                    "capabilities": new_identity.capabilities,
                    "did": new_identity.did
                }
            }
        else:
            return {
                "status": "error",
                "message": "保存身份信息失败"
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"创建身份信息失败: {str(e)}"
        }

def go_online() -> Dict[str, Any]:
    """将智能体身份信息公开，使其他智能体可见
    
    该工具从AGENTCHAT_MEMORY_PATH检索身份信息，
    并将身份发布到 $AGENTCHAT_PUBLIC_DATABLOCKS/identities.db。
    如果身份信息为空，提示先使用register_recall_id工具；
    如果未设置AGENTCHAT_PUBLIC_DATABLOCKS，则提示在MCP配置文件中增加该环境变量的定义。
    
    环境变量:
    - AGENTCHAT_MEMORY_PATH: 指定智能体身份记忆存储目录（读取）
    - AGENTCHAT_PUBLIC_DATABLOCKS: 指定公开数据库目录（写入 identities.db）
    
    Returns:
        包含操作状态、消息、已发布身份信息以及数据库路径的字典，例如:
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
    """
    # 检查AGENTCHAT_MEMORY_PATH环境变量
    memory_path = os.getenv('AGENTCHAT_MEMORY_PATH')
    if not memory_path:
        return {
            "status": "error",
            "message": "未设置AGENTCHAT_MEMORY_PATH环境变量"
        }
    
    # 使用IdentityManager加载身份信息
    identity_manager = IdentityManager()
    
    if not identity_manager.has_identity():
        return {
            "status": "error",
            "message": "AGENTCHAT_MEMORY_PATH中的身份信息为空，请先使用register_recall_id工具注册身份信息，然后重试"
        }
    
    # 加载身份信息
    identity = identity_manager.load_identity()
    if not identity:
        return {
            "status": "error",
            "message": "无法加载身份信息，请检查身份文件是否损坏"
        }
    
    try:
        # 使用 AGENTCHAT_PUBLIC_DATABLOCKS 环境变量指定公开数据库目录
        public_dir_env = os.getenv('AGENTCHAT_PUBLIC_DATABLOCKS')
        if not public_dir_env:
            return {
                "status": "error",
                "message": "未设置AGENTCHAT_PUBLIC_DATABLOCKS环境变量，请在MCP配置文件中增加该环境变量的定义后重试"
            }
        data_dir = Path(public_dir_env)
        if data_dir.exists() and not data_dir.is_dir():
            return {
                "status": "error",
                "message": f"AGENTCHAT_PUBLIC_DATABLOCKS指向的路径不是目录: {str(data_dir)}"
            }
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # 连接到 $AGENTCHAT_PUBLIC_DATABLOCKS/identities.db 数据库
        db_path = data_dir / "identities.db"
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
        
        # 将capabilities列表转换为JSON字符串
        import json
        capabilities_json = json.dumps(identity.capabilities, ensure_ascii=False)
        
        # 插入或更新身份信息
        cursor.execute("""
            INSERT OR REPLACE INTO identities 
            (did, name, description, capabilities, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (identity.did, identity.name, identity.description, capabilities_json))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"智能体身份信息已成功发布到公开数据库",
            "published_identity": {
                "did": identity.did,
                "name": identity.name,
                "description": identity.description,
                "capabilities": identity.capabilities
            },
            "database_path": str(db_path)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"发布身份信息失败: {str(e)}"
        }