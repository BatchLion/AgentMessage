"""AgentMessage - Modular agent management system"""

__version__ = "2.0.0"

from .identity import IdentityManager, AgentIdentity, register_recall_id
from .mcp_server import AgentMessageMCPServer

__all__ = [
    "IdentityManager",
    "AgentIdentity", 
    "register_recall_id",
    "AgentMessageMCPServer",
]