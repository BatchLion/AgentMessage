"""身份管理器"""

import os
import json
from pathlib import Path
from typing import Optional
from .models import AgentIdentity
from .did_generator import DIDGenerator

class IdentityManager:
    """身份管理器"""
    
    def __init__(self):
        self.did_generator = DIDGenerator()
        self.memory_path = self._get_memory_path()
        self.identity_file = self.memory_path / "identity.json"
        
        # 确保目录存在
        self.memory_path.mkdir(parents=True, exist_ok=True)
    
    def _get_memory_path(self) -> Path:
        """获取内存路径"""
        memory_path = os.getenv('AGENTCHAT_MEMORY_PATH')
        if memory_path:
            return Path(memory_path)
        else:
            # 默认路径
            return Path.home() / ".agentchat" / "memory"
    
    def load_identity(self) -> Optional[AgentIdentity]:
        """加载身份信息"""
        if not self.identity_file.exists():
            return None
        
        try:
            with open(self.identity_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return AgentIdentity.from_dict(data)
        except Exception as e:
            print(f"加载身份信息失败: {e}")
            return None
    
    def save_identity(self, identity: AgentIdentity) -> bool:
        """保存身份信息"""
        try:
            with open(self.identity_file, 'w', encoding='utf-8') as f:
                json.dump(identity.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存身份信息失败: {e}")
            return False
    
    def create_identity(self, name: str, description: str, capabilities: list) -> AgentIdentity:
        """创建新的身份信息"""
        did = self.did_generator.generate_did(name)
        identity = AgentIdentity(
            name=name,
            description=description,
            capabilities=capabilities,
            did=did
        )
        return identity
    
    def has_identity(self) -> bool:
        """检查是否已有身份信息"""
        return self.identity_file.exists() and self.load_identity() is not None