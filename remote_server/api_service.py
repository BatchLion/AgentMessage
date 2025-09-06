#!/usr/bin/env python3
"""
AgentMessage Remote Database API Service

This module provides a simple HTTP API for the remote database service,
allowing external applications to interact with the AgentMessage database.
"""

import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional

from config import RemoteConfig
from database import RemoteDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Global database instance
_db_instance = None

def get_database_instance():
    """Get or create the global database instance."""
    global _db_instance
    if _db_instance is None:
        config = RemoteConfig()
        _db_instance = RemoteDatabase(config)
        # Ensure tables are created
        result = _db_instance.create_tables()
        if result['status'] != 'success':
            logger.error(f"Failed to create database tables: {result.get('message', 'Unknown error')}")
        else:
            logger.info("Database tables created successfully")
    return _db_instance

class DatabaseAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for database API endpoints."""
    
    def __init__(self, *args, **kwargs):
        self.db = get_database_instance()
        super().__init__(*args, **kwargs)
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response with appropriate headers."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        # CORS headers are now handled by nginx, but keep for direct access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        # Add security headers (nginx also adds these, but redundancy is good)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        
        response_json = json.dumps(data, indent=2, cls=DateTimeEncoder)
        self.wfile.write(response_json.encode('utf-8'))
    
    def _send_error_response(self, message: str, status_code: int = 400):
        """Send error response."""
        self._send_json_response({
            'error': True,
            'message': message,
            'status_code': status_code
        }, status_code)
    
    def _get_request_body(self) -> Optional[Dict[str, Any]]:
        """Parse JSON request body."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return None
            
            body = self.rfile.read(content_length)
            return json.loads(body.decode('utf-8'))
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing request body: {e}")
            return None
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self._send_json_response({'message': 'CORS preflight'})
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)
            
            if path == '/health':
                self._handle_health_check()
            elif path == '/identities':
                self._handle_get_identities(query_params)
            elif path.startswith('/identities/'):
                did = path.split('/')[-1]
                self._handle_get_identity(did)
            else:
                self._send_error_response('Endpoint not found', 404)
                
        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            self._send_error_response(f'Internal server error: {str(e)}', 500)
    
    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path == '/identities':
                self._handle_create_identity()
            else:
                self._send_error_response('Endpoint not found', 404)
                
        except Exception as e:
            logger.error(f"Error handling POST request: {e}")
            self._send_error_response(f'Internal server error: {str(e)}', 500)
    
    def do_PUT(self):
        """Handle PUT requests."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path.startswith('/identities/'):
                did = path.split('/')[-1]
                self._handle_update_identity(did)
            else:
                self._send_error_response('Endpoint not found', 404)
                
        except Exception as e:
            logger.error(f"Error handling PUT request: {e}")
            self._send_error_response(f'Internal server error: {str(e)}', 500)
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path.startswith('/identities/'):
                did = path.split('/')[-1]
                self._handle_delete_identity(did)
            else:
                self._send_error_response('Endpoint not found', 404)
                
        except Exception as e:
            logger.error(f"Error handling DELETE request: {e}")
            self._send_error_response(f'Internal server error: {str(e)}', 500)
    
    def _handle_health_check(self):
        """Handle health check endpoint."""
        try:
            # Test database connection
            result = self.db.create_tables()
            
            self._send_json_response({
                'status': 'healthy',
                'service': 'AgentMessage Remote Database API',
                'database': 'connected' if result['status'] == 'success' else 'error',
                'database_message': result.get('message', '')
            })
        except Exception as e:
            self._send_error_response(f'Health check failed: {str(e)}', 503)
    
    def _handle_get_identities(self, query_params: Dict[str, list]):
        """Handle GET /identities endpoint."""
        try:           
            result = self.db.get_identities()
            
            if result['status'] == 'success':
                self._send_json_response({
                    'success': True,
                    'identities': result['identities'],
                    'count': len(result['identities']),
                    'total': result.get('total', 0)
                })
            else:
                self._send_error_response(result['message'], 500)
                
        except Exception as e:
            self._send_error_response(f'Error retrieving identities: {str(e)}', 500)
    
    def _handle_get_identity(self, did: str):
        """Handle GET /identities/{did} endpoint."""
        try:
            result = self.db.get_identity_by_did(did)
            
            if result['status'] == 'success':
                # Return the identity data directly (not nested under 'identity' key)
                identity_data = result['identity']
                identity_data['success'] = True
                self._send_json_response(identity_data)
            elif result['status'] == 'not_found':
                self._send_error_response('Identity not found', 404)
            else:
                self._send_error_response(result['message'], 500)
                
        except Exception as e:
            self._send_error_response(f'Error retrieving identity: {str(e)}', 500)
    
    def _handle_create_identity(self):
        """Handle POST /identities endpoint."""
        try:
            body = self._get_request_body()
            if not body:
                self._send_error_response('Request body required', 400)
                return
            
            # Validate required fields
            required_fields = ['did', 'name', 'description', 'capabilities']
            for field in required_fields:
                if field not in body:
                    self._send_error_response(f'Missing required field: {field}', 400)
                    return
            
            result = self.db.insert_identity(body)
            
            if result['status'] == 'success':
                self._send_json_response({
                    'success': True,
                    'message': 'Identity created successfully',
                    'did': body['did']
                }, 201)
            else:
                self._send_error_response(result['message'], 400)
                
        except Exception as e:
            self._send_error_response(f'Error creating identity: {str(e)}', 500)
    
    def _handle_update_identity(self, did: str):
        """Handle PUT /identities/{did} endpoint."""
        try:
            body = self._get_request_body()
            if not body:
                self._send_error_response('Request body required', 400)
                return
            
            # Add DID to body
            body['did'] = did
            
            result = self.db.insert_identity(body)  # This will update if exists
            
            if result['status'] == 'success':
                self._send_json_response({
                    'success': True,
                    'message': 'Identity updated successfully',
                    'did': did
                })
            else:
                self._send_error_response(result['message'], 400)
                
        except Exception as e:
            self._send_error_response(f'Error updating identity: {str(e)}', 500)
    
    def _handle_delete_identity(self, did: str):
        """Handle DELETE /identities/{did} endpoint."""
        try:
            result = self.db.delete_identity(did)
            
            if result['status'] == 'success':
                self._send_json_response({
                    'success': True,
                    'message': 'Identity deleted successfully',
                    'did': did
                })
            else:
                self._send_error_response(result['message'], 400)
                
        except Exception as e:
            self._send_error_response(f'Error deleting identity: {str(e)}', 500)
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        # Get real client IP from proxy headers
        real_ip = self.headers.get('X-Real-IP', self.address_string())
        forwarded_for = self.headers.get('X-Forwarded-For', '')
        forwarded_proto = self.headers.get('X-Forwarded-Proto', 'http')
        
        # Log with proxy information if available
        if forwarded_for:
            logger.info(f"{real_ip} (via {forwarded_for}) [{forwarded_proto}] - {format % args}")
        else:
            logger.info(f"{real_ip} [{forwarded_proto}] - {format % args}")

def run_api_server(host: str = '0.0.0.0', port: int = 8000):
    """Run the API server."""
    try:
        server = HTTPServer((host, port), DatabaseAPIHandler)
        logger.info(f"Starting AgentMessage Database API server on {host}:{port}")
        logger.info(f"Available endpoints:")
        logger.info(f"  GET  /health - Health check")
        logger.info(f"  GET  /identities - List all identities")
        logger.info(f"  GET  /identities/{{did}} - Get specific identity")
        logger.info(f"  POST /identities - Create new identity")
        logger.info(f"  PUT  /identities/{{did}} - Update identity")
        logger.info(f"  DELETE /identities/{{did}} - Delete identity")
        
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down API server...")
        server.shutdown()
    except Exception as e:
        logger.error(f"Error starting API server: {e}")
        raise

if __name__ == '__main__':
    import os
    
    # Get configuration from environment
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '8000'))
    
    run_api_server(host, port)