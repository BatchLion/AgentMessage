"""Remote PostgreSQL database operations"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from config import RemoteConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_datetime_to_string(obj):
    """Convert datetime objects to ISO format strings recursively."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_datetime_to_string(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_string(item) for item in obj]
    return obj

class RemoteDatabase:
    """Remote PostgreSQL database manager"""
    
    def __init__(self, config: Optional[RemoteConfig] = None):
        """Initialize database manager
        
        Args:
            config: Remote configuration instance
        """
        self.config = config or RemoteConfig()
        self._connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        validation = self.config.validate_config()
        if not validation['valid']:
            logger.error(f"Invalid database configuration: {validation['missing_fields']}")
            return
        
        try:
            pool_config = self.config.get_connection_pool_config()
            connection_string = self.config.get_connection_string()
            
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                pool_config['minconn'],
                pool_config['maxconn'],
                connection_string
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            self._connection_pool = None
    
    @contextmanager
    def get_connection(self):
        """Get database connection from pool
        
        Yields:
            Database connection
        """
        if not self._connection_pool:
            raise Exception("Database connection pool not initialized")
        
        conn = None
        try:
            conn = self._connection_pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self._connection_pool.putconn(conn)
    
    def create_tables(self) -> Dict[str, Any]:
        """Create necessary database tables
        
        Returns:
            Operation result
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create identities table
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
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_identities_name 
                    ON identities(name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_identities_created_at 
                    ON identities(created_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_identities_capabilities 
                    ON identities USING GIN(capabilities)
                """)
                
                conn.commit()
                
                return {
                    'status': 'success',
                    'message': 'Database tables created successfully'
                }
                
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return {
                'status': 'error',
                'message': f'Failed to create tables: {str(e)}'
            }
    
    def insert_identity(self, identity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update agent identity
        
        Args:
            identity_data: Identity information
            
        Returns:
            Operation result
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Convert capabilities to JSON if it's a list
                capabilities = identity_data['capabilities']
                if isinstance(capabilities, list):
                    capabilities_json = json.dumps(capabilities, ensure_ascii=False)
                else:
                    capabilities_json = capabilities
                
                cursor.execute("""
                    INSERT INTO identities 
                    (did, name, description, capabilities, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (did) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        capabilities = EXCLUDED.capabilities,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING did, created_at, updated_at
                """, (
                    identity_data['did'],
                    identity_data['name'],
                    identity_data['description'],
                    capabilities_json
                ))
                
                result = cursor.fetchone()
                conn.commit()
                
                return {
                    'status': 'success',
                    'message': 'Identity inserted/updated successfully',
                    'did': result[0],
                    'created_at': result[1],
                    'updated_at': result[2]
                }
                
        except Exception as e:
            logger.error(f"Failed to insert identity: {e}")
            return {
                'status': 'error',
                'message': f'Failed to insert identity: {str(e)}'
            }
    
    def get_identities(self, limit: Optional[int] = None, offset: int = 0) -> Dict[str, Any]:
        """Retrieve agent identities
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of identities
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Build query
                query = """
                    SELECT did, name, description, capabilities, 
                           created_at, updated_at
                    FROM identities 
                    ORDER BY updated_at DESC
                """
                
                params = []
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)
                
                if offset > 0:
                    query += " OFFSET %s"
                    params.append(offset)
                
                cursor.execute(query, params)
                identities = cursor.fetchall()
                
                # Convert to list of dictionaries and parse JSON capabilities
                result_identities = []
                for identity in identities:
                    identity_dict = dict(identity)
                    # Parse capabilities JSON
                    if isinstance(identity_dict['capabilities'], str):
                        identity_dict['capabilities'] = json.loads(identity_dict['capabilities'])
                    # Convert datetime objects to strings
                    identity_dict = convert_datetime_to_string(identity_dict)
                    result_identities.append(identity_dict)
                
                # Get total count using a regular cursor (not RealDictCursor)
                count_cursor = conn.cursor()
                count_cursor.execute("SELECT COUNT(*) FROM identities")
                total_count = count_cursor.fetchone()[0]
                
                return {
                    'status': 'success',
                    'total': total_count,
                    'count': len(result_identities),
                    'identities': result_identities
                }
                
        except Exception as e:
            logger.error(f"Failed to get identities: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception args: {e.args}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'status': 'error',
                'message': f'Failed to get identities: {str(e)}',
                'total': 0,
                'count': 0,
                'identities': []
            }
    
    def get_identity_by_did(self, did: str) -> Dict[str, Any]:
        """Get specific identity by DID
        
        Args:
            did: Decentralized identifier
            
        Returns:
            Identity information or None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                cursor.execute("""
                    SELECT did, name, description, capabilities, 
                           created_at, updated_at
                    FROM identities 
                    WHERE did = %s
                """, (did,))
                
                identity = cursor.fetchone()
                
                if identity:
                    identity_dict = dict(identity)
                    # Parse capabilities JSON
                    if isinstance(identity_dict['capabilities'], str):
                        identity_dict['capabilities'] = json.loads(identity_dict['capabilities'])
                    # Convert datetime objects to strings
                    identity_dict = convert_datetime_to_string(identity_dict)
                    
                    return {
                        'status': 'success',
                        'identity': identity_dict
                    }
                else:
                    return {
                        'status': 'not_found',
                        'message': f'Identity with DID {did} not found'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get identity by DID: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get identity: {str(e)}'
            }
    
    def delete_identity(self, did: str) -> Dict[str, Any]:
        """Delete identity by DID
        
        Args:
            did: Decentralized identifier
            
        Returns:
            Operation result
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM identities WHERE did = %s", (did,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    return {
                        'status': 'success',
                        'message': f'Identity {did} deleted successfully'
                    }
                else:
                    return {
                        'status': 'not_found',
                        'message': f'Identity with DID {did} not found'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to delete identity: {e}")
            return {
                'status': 'error',
                'message': f'Failed to delete identity: {str(e)}'
            }
    
    def close(self):
        """Close connection pool"""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("Database connection pool closed")
    
    # Removed __del__ method to prevent automatic connection pool closure
    # The connection pool will be managed manually