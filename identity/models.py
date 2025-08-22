"""身份数据模型"""

import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class AgentIdentity(BaseModel):
    """智能体身份信息模型"""
    
    name: str = Field(..., description="智能体名称")
    description: str = Field(..., description="智能体描述")
    capabilities: List[str] = Field(..., description="智能体能力列表")
    did: str = Field(..., description="去中心化标识符")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
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
        """从字典创建实例"""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        return cls(**data)