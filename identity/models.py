"""Identity data models"""

import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class AgentIdentity(BaseModel):
    """Agent identity information model"""
    
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    capabilities: List[str] = Field(..., description="Agent capabilities list")
    did: str = Field(..., description="Decentralized identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update time")
    
    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "did": self.did,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentIdentity':
        """Create instance from dictionary"""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        return cls(**data)