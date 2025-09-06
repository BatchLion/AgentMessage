"""Remote server configuration management"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class RemoteConfig:
    """Remote PostgreSQL database configuration manager"""
    
    def __init__(self, env_file: str = '.env'):
        """Initialize configuration manager
        
        Args:
            env_file: Path to environment file
        """
        self.env_file = env_file
        load_dotenv(env_file)
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database connection configuration
        
        Returns:
            Dictionary containing database configuration
        """
        return {
            'host': os.getenv('REMOTE_DB_HOST', 'localhost'),
            'port': int(os.getenv('REMOTE_DB_PORT', '5432')),
            'database': os.getenv('REMOTE_DB_NAME', 'agentmessage'),
            'user': os.getenv('REMOTE_DB_USER', 'agentmessage_user'),
            'password': os.getenv('REMOTE_DB_PASSWORD', ''),
            'sslmode': os.getenv('REMOTE_DB_SSL_MODE', 'prefer'),
            'connect_timeout': int(os.getenv('REMOTE_DB_CONNECTION_TIMEOUT', '30')),
            'application_name': 'AgentMessage'
        }
    
    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration
        
        Returns:
            Dictionary containing connection pool settings
        """
        return {
            'minconn': int(os.getenv('REMOTE_DB_MIN_CONNECTIONS', '5')),
            'maxconn': int(os.getenv('REMOTE_DB_MAX_CONNECTIONS', '20'))
        }
    
    def is_remote_discoverable(self) -> bool:
        """Check if remote discovery is enabled
        
        Returns:
            True if remote discovery is enabled
        """
        return os.getenv('REMOTE_DISCOVERABLE', 'false').lower() == 'true'
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate database configuration
        
        Returns:
            Dictionary with validation status and missing fields
        """
        config = self.get_database_config()
        required_fields = ['host', 'database', 'user', 'password']
        missing_fields = []
        
        for field in required_fields:
            if not config.get(field):
                missing_fields.append(f'REMOTE_DB_{field.upper()}')
        
        return {
            'valid': len(missing_fields) == 0,
            'missing_fields': missing_fields,
            'config': config
        }
    
    def get_connection_string(self) -> Optional[str]:
        """Get PostgreSQL connection string
        
        Returns:
            Connection string or None if configuration is invalid
        """
        validation = self.validate_config()
        if not validation['valid']:
            return None
        
        config = validation['config']
        return (
            f"host={config['host']} "
            f"port={config['port']} "
            f"dbname={config['database']} "
            f"user={config['user']} "
            f"password={config['password']} "
            f"sslmode={config['sslmode']} "
            f"connect_timeout={config['connect_timeout']} "
            f"application_name={config['application_name']}"
        )