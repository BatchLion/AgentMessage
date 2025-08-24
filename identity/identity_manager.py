"""Identity manager"""

import os
import json
from pathlib import Path
from typing import Optional
from .models import AgentIdentity
from .did_generator import DIDGenerator

class IdentityManager:
    """Identity manager"""
    
    def __init__(self):
        self.did_generator = DIDGenerator()
        self.memory_path = self._get_memory_path()
        self.identity_file = self.memory_path / "identity.json"
        
        # Ensure directory exists
        self.memory_path.mkdir(parents=True, exist_ok=True)
    
    def _get_memory_path(self) -> Path:
        """Get memory path"""
        memory_path = os.getenv('AGENTMESSAGE_MEMORY_PATH')
        if memory_path:
            return Path(memory_path)
        else:
            # Default path
            return Path.home() / ".agentmessage" / "memory"
    
    def load_identity(self) -> Optional[AgentIdentity]:
        """Load identity information"""
        if not self.identity_file.exists():
            return None
        
        try:
            with open(self.identity_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return AgentIdentity.from_dict(data)
        except Exception as e:
            print(f"Failed to load identity information: {e}")
            return None
    
    def save_identity(self, identity: AgentIdentity) -> bool:
        """Save identity information"""
        try:
            with open(self.identity_file, 'w', encoding='utf-8') as f:
                json.dump(identity.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to save identity information: {e}")
            return False
    
    def create_identity(self, name: str, description: str, capabilities: list) -> AgentIdentity:
        """Create new identity information"""
        did = self.did_generator.generate_did(name)
        identity = AgentIdentity(
            name=name,
            description=description,
            capabilities=capabilities,
            did=did
        )
        return identity
    
    def has_identity(self) -> bool:
        """Check if identity information already exists"""
        return self.identity_file.exists() and self.load_identity() is not None