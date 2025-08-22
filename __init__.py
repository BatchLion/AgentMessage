"""AgentChat - 模块化智能体管理系统"""

__version__ = "2.0.0"

from .identity import IdentityManager, AgentIdentity, register_recall_id
from .mcp_server import AgentChatMCPServer

__all__ = [
    "IdentityManager",
    "AgentIdentity", 
    "register_recall_id",
    "AgentChatMCPServer",
]