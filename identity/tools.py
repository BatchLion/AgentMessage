"""
Identity management tools
Provides functions for registering, recalling identity information and going online
"""

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
    """Register or recall agent identity information
    
    Args:
        name: Agent name (optional)
        description: Agent description (optional)
        capabilities: Agent capability list (optional)
    
    Returns:
        Dictionary containing identity information or prompt information
    """
    identity_manager = IdentityManager()
    
    # Check if identity information already exists
    if identity_manager.has_identity():
        # If identity information already exists, return directly
        existing_identity = identity_manager.load_identity()
        if existing_identity:
            return {
                "status": "success",
                "message": "Agent identity information already exists",
                "identity": {
                    "name": existing_identity.name,
                    "description": existing_identity.description,
                    "capabilities": existing_identity.capabilities,
                    "did": existing_identity.did
                }
            }
    
    # If no identity information exists, check parameters
    if not name or not description or not capabilities:
        return {
            "status": "error",
            "message": "Please provide name, description, and capabilities parameters",
            "required_params": {
                "name": "Agent name",
                "description": "Agent description",
                "capabilities": "Agent capability list (array format)"
            }
        }
    
    # Create new identity information
    try:
        new_identity = identity_manager.create_identity(name, description, capabilities)
        
        # Save identity information
        if identity_manager.save_identity(new_identity):
            return {
                "status": "success",
                "message": "Agent identity information created successfully",
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
                "message": "Failed to save identity information"
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create identity information: {str(e)}"
        }

def go_online() -> Dict[str, Any]:
    """Make agent identity information public and visible to other agents
    
    This tool retrieves identity information from AGENTMESSAGE_MEMORY_PATH,
    and publishes the identity to $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db.
    If identity information is empty, prompts to use register_recall_id tool first;
    If AGENTMESSAGE_PUBLIC_DATABLOCKS is not set, prompts to add the environment variable definition in the MCP configuration file.
    
    Environment Variables:
    - AGENTMESSAGE_MEMORY_PATH: Specifies the agent identity memory storage directory (read)
    - AGENTMESSAGE_PUBLIC_DATABLOCKS: Specifies the public database directory (write identities.db)
    Returns:
        Dictionary containing operation status, message, published identity information, and database path, e.g.:
        {
            "status": "success" | "error",
            "message": "Agent identity information has been successfully published to the public database | Failed to publish identity information: {error message}",
            "published_identity": {
                "did": "...",
                "name": "...",
                "description": "...",
                "capabilities": [...]
            },
            "database_path": "/absolute/path/to/identities.db"
        }
    """
    # Check AGENTMESSAGE_MEMORY_PATH environment variable
    memory_path = os.getenv('AGENTMESSAGE_MEMORY_PATH')
    if not memory_path:
        return {
            "status": "error",
            "message": "AGENTMESSAGE_MEMORY_PATH environment variable is not set"
        }
    
    # Use IdentityManager to load identity information
    identity_manager = IdentityManager()
    
    if not identity_manager.has_identity():
        return {
            "status": "error",
            "message": "Identity information in AGENTMESSAGE_MEMORY_PATH is empty, please use register_recall_id tool to register identity information first, then retry"
        }
    
    # Load identity information
    identity = identity_manager.load_identity()
    if not identity:
        return {
            "status": "error",
            "message": "Failed to load identity information, please check if the identity file is corrupted"
        }
    
    try:
        # Use AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable to specify public database directory
        public_dir_env = os.getenv('AGENTMESSAGE_PUBLIC_DATABLOCKS')
        if not public_dir_env:
            return {
                "status": "error",
                "message": "AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable is not set, please add it to the MCP configuration file and retry"
            }
        data_dir = Path(public_dir_env)
        if data_dir.exists() and not data_dir.is_dir():
            return {
                "status": "error",
                "message": f"AGENTMESSAGE_PUBLIC_DATABLOCKS points to a non-directory path: {str(data_dir)}"
            }
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Connect to $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db database
        db_path = data_dir / "identities.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create identities table (if not exists)
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
        
        # Convert capabilities list to JSON string
        import json
        capabilities_json = json.dumps(identity.capabilities, ensure_ascii=False)
        
        # Insert or update identity information
        cursor.execute("""
            INSERT OR REPLACE INTO identities 
            (did, name, description, capabilities, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (identity.did, identity.name, identity.description, capabilities_json))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": "Agent identity information has been successfully published to the public database",
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
            "message": f"Failed to publish identity information: {str(e)}"
        }