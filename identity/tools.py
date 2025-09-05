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
import psycopg2
import json
from dotenv import load_dotenv

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

def discovered_locally() -> Dict[str, Any]:
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

async def collect_local_identities(limit: int | None = None) -> dict:
    """Collect identities from identities.db database
    Path:
    - $AGENTMESSAGE_PUBLIC_DATABLOCKS/identities.db
    
    Parameters:
    - limit: Optional, limit the number of records returned
    
    Returns:
    {
        "status": "success",
        "total": <int>,
        "identities": [
        {
            "did": "...",
            "name": "...",
            "description": "...",
            "capabilities": [...],
            "created_at": "YYYY-MM-DD HH:MM:SS",
            "updated_at": "YYYY-MM-DD HH:MM:SS"
        },
        ...
        ],
        "database_path": "<Absolute path of identities.db>"
    }
    """
    try:
        public_dir_env = os.getenv("AGENTMESSAGE_PUBLIC_DATABLOCKS")
        if not public_dir_env:
            return {
                "status": "error",
                "message": "AGENTMESSAGE_PUBLIC_DATABLOCKS environment variable is not set. Please define it in the MCP configuration file."
            }
        
        db_path = Path(public_dir_env) / "identities.db"
        if not db_path.exists():
            return {
                "status": "error",
                "message": "identities.db file not found",
                "expected_path": str(db_path)
            }
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        sql = """
            SELECT did, name, description, capabilities, created_at, updated_at
            FROM identities
            ORDER BY datetime(updated_at) DESC
        """
        if limit is not None and isinstance(limit, int) and limit > 0:
            sql += " LIMIT ?"
            cursor.execute(sql, (limit,))
        else:
            cursor.execute(sql)
        
        rows = cursor.fetchall()
        conn.close()
        
        identities = []
        for did, name, description, capabilities_text, created_at, updated_at in rows:
            # capabilities is stored as JSON text, needs to be deserialized into a list
            try:
                capabilities = json.loads(capabilities_text) if capabilities_text else []
                if not isinstance(capabilities, list):
                    capabilities = []
            except Exception:
                capabilities = []
            
            identities.append({
                "did": did,
                "name": name,
                "description": description,
                "capabilities": capabilities,
                "created_at": created_at,
                "updated_at": updated_at,
                "position": "local"
            })
        
        return {
            "status": "success",
            "total": len(identities),
            "identities": identities,
            "database_path": str(db_path)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database operation failed: {str(e)}"
        }

def discovered_globally() -> Dict[str, Any]:
    """Make agent identity information public and visible to other agents on remote server
    
    This tool retrieves identity information from AGENTMESSAGE_MEMORY_PATH,
    and publishes the identity to remote PostgreSQL server specified in .env file.
    If identity information is empty, prompts to use register_recall_id tool first;
    If remote database configuration is not set, prompts to configure .env file.
    
    Environment Variables (from .env file):
    - REMOTE_DB_HOST: Remote PostgreSQL server host
    - REMOTE_DB_PORT: Remote PostgreSQL server port
    - REMOTE_DB_NAME: Remote database name
    - REMOTE_DB_USER: Remote database user
    - REMOTE_DB_PASSWORD: Remote database password
    - REMOTE_DB_SSL_MODE: SSL mode for connection
    
    Returns:
        Dictionary containing operation status, message, published identity information, and database info, e.g.:
        {
            "status": "success" | "error",
            "message": "Agent identity information has been successfully published to the remote database | Failed to publish identity information: {error message}",
            "published_identity": {
                "did": "...",
                "name": "...",
                "description": "...",
                "capabilities": [...]
            },
            "remote_database": "host:port/database"
        }
    """
    # Load environment variables from .env file
    load_dotenv()
    
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
    
    # Get remote database configuration from environment variables
    db_host = os.getenv('REMOTE_DB_HOST')
    db_port = os.getenv('REMOTE_DB_PORT', '5432')
    db_name = os.getenv('REMOTE_DB_NAME')
    db_user = os.getenv('REMOTE_DB_USER')
    db_password = os.getenv('REMOTE_DB_PASSWORD')
    db_ssl_mode = os.getenv('REMOTE_DB_SSL_MODE', 'prefer')
    
    if not all([db_host, db_name, db_user, db_password]):
        return {
            "status": "error",
            "message": "Remote database configuration is incomplete. Please check .env file for REMOTE_DB_HOST, REMOTE_DB_NAME, REMOTE_DB_USER, and REMOTE_DB_PASSWORD"
        }
    
    try:
        # Connect to remote PostgreSQL database
        connection_string = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password} sslmode={db_ssl_mode}"
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        # Create identities table (if not exists)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS identities (
                did TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                capabilities JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Convert capabilities list to JSON
        capabilities_json = json.dumps(identity.capabilities, ensure_ascii=False)
        
        # Insert or update identity information
        cursor.execute("""
            INSERT INTO identities 
            (did, name, description, capabilities, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (did) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                capabilities = EXCLUDED.capabilities,
                updated_at = CURRENT_TIMESTAMP
        """, (identity.did, identity.name, identity.description, capabilities_json))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "status": "success",
            "message": "Agent identity information has been successfully published to the remote database",
            "published_identity": {
                "did": identity.did,
                "name": identity.name,
                "description": identity.description,
                "capabilities": identity.capabilities
            },
            "remote_database": f"{db_host}:{db_port}/{db_name}"
        }
        
    except psycopg2.Error as e:
        return {
            "status": "error",
            "message": f"Failed to connect to remote database: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to publish identity information to remote database: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Collect identities failed: {str(e)}"
        }