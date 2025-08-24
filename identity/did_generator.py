"""
DID (Decentralized Identifier) generator module
Used to generate and validate DID identifiers for AgentMessage
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional

class DIDGenerator:
    """
    DID generator class
    Used to generate and validate DID identifiers that comply with AgentMessage specifications
    """
    
    def __init__(self, method: str = "agentmessage"):
        self.method = method
    
    def generate_did(self, agent_name: str, endpoint: str = None) -> str:
        """Generate DID
        
        format: did:agentmessage:{network}:{identifier}
        """
        # Generate unique identifier
        timestamp = datetime.utcnow().isoformat()
        unique_string = f"{agent_name}:{endpoint}:{timestamp}:{uuid.uuid4()}"
        
        # Generate hash using SHA-256
        hash_object = hashlib.sha256(unique_string.encode())
        identifier = hash_object.hexdigest()[:32]  # 取前32位
        
        return f"did:{self.method}:local:{identifier}"
    
    def validate_did(self, did: str) -> bool:
        """Validate DID format
        
        format: did:agentmessage:{network}:{identifier}
        """
        parts = did.split(':')
        return (
            len(parts) == 4 and
            parts[0] == 'did' and
            parts[1] == self.method and
            parts[2] in ['local', 'remote'] and
            len(parts[3]) == 32
        )