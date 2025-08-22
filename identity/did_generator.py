"""DID生成器"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional

class DIDGenerator:
    """DID生成器 - 生成唯一的去中心化标识符"""
    
    def __init__(self, method: str = "agentchat"):
        self.method = method
    
    def generate_did(self, agent_name: str, endpoint: str = None) -> str:
        """生成DID
        
        格式: did:agentchat:{network}:{identifier}
        """
        # 生成唯一标识符
        timestamp = datetime.utcnow().isoformat()
        unique_string = f"{agent_name}:{endpoint}:{timestamp}:{uuid.uuid4()}"
        
        # 使用SHA-256生成哈希
        hash_object = hashlib.sha256(unique_string.encode())
        identifier = hash_object.hexdigest()[:32]  # 取前32位
        
        return f"did:{self.method}:local:{identifier}"
    
    def validate_did(self, did: str) -> bool:
        """验证DID格式"""
        parts = did.split(':')
        return (
            len(parts) == 4 and
            parts[0] == 'did' and
            parts[1] == self.method and
            parts[2] in ['local', 'remote'] and
            len(parts[3]) == 32
        )