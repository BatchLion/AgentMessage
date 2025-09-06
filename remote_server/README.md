# AgentMessage Remote Database Service

This directory contains the remote database service components for AgentMessage, designed to be deployed on a remote server. It provides PostgreSQL database setup, connection management, and Docker containerization for easy deployment.

## 🎯 Purpose

This service is intended to be deployed on a **remote server** to provide centralized database functionality for AgentMessage agents. When `REMOTE_DISCOVERABLE=true` is set in the main AgentMessage application, agents will publish their identity information to this remote database service in addition to their local SQLite databases.

## Components

### Database Module
- `database.py`: PostgreSQL database operations and connection management
- `config.py`: Configuration management for remote database connections
- `api_service.py`: HTTPS API service for database operations
- `__init__.py`: Package initialization

### Docker Deployment
- `docker-compose.yml`: Docker Compose configuration for PostgreSQL, API service, Nginx, and PgAdmin
- `init-scripts/`: Database initialization scripts
- `Dockerfile`: Application container configuration
- `deploy.sh`: Automated deployment script with SSL certificate management

### SSL/HTTPS Configuration
- `nginx.conf`: Nginx reverse proxy configuration for SSL termination
- `generate-ssl-cert.sh`: Script for generating self-signed SSL certificates
- `ssl/`: Directory for SSL certificates (created automatically)

## Configuration

### Configuration Architecture

The remote server uses two types of configuration:

1. **Docker Internal Configuration**: Hardcoded in `docker-compose.yml` for communication between containers
   - API service connects to PostgreSQL using `REMOTE_DB_HOST=postgres` (Docker service name)
   - These settings are automatically configured and don't need modification

2. **External Client Configuration**: External AgentMessage applications need their own configuration
   - External clients configure REMOTE_DB_* variables in their own .env files
   - These settings tell external applications how to connect to this remote server
   - The remote server itself doesn't need these variables

### Environment Variables

### External Client Configuration

When external AgentMessage applications want to connect to this remote server, they should add the following to their own `.env` file:

```bash
# Remote Discovery Configuration
REMOTE_DISCOVERABLE=true

# Remote PostgreSQL Database Configuration
REMOTE_DB_HOST=your-server-domain.com  # Replace with your server's domain/IP
REMOTE_DB_PORT=5432
REMOTE_DB_NAME=agentmessage
REMOTE_DB_USER=agentmessage_user
REMOTE_DB_PASSWORD=your_postgres_password  # Same as POSTGRES_PASSWORD on remote server
REMOTE_DB_SSL_MODE=prefer
```

**Important Notes:**
- External clients need these REMOTE_DB_* variables in their own .env files
- The remote server itself does NOT need these variables
- `REMOTE_DB_HOST` should be your server's domain name or IP address
- `REMOTE_DB_PASSWORD` should match the `POSTGRES_PASSWORD` from your remote server

## 🚀 Remote Server Deployment

### Prerequisites
- A remote server with Docker and Docker Compose installed
- SSH access to the remote server
- Firewall configured to allow HTTPS (port 443), HTTP (port 9128), and PostgreSQL connections (port 5432)
- Domain name pointing to your server (recommended for production SSL certificates)

### Deployment Steps

1. **Copy files to remote server:**
```bash
# Copy the entire remote_server directory to your remote server
scp -r remote_server/ user@your-server:/opt/agentmessage/
```

2. **SSH into remote server:**
```bash
ssh user@your-server
cd /opt/agentmessage/remote_server
```

3. **Deploy using the deployment script:**
```bash
# Make the script executable (if not already)
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

4. **Configure firewall (if needed):**
```bash
# Allow HTTPS and HTTP connections
sudo ufw allow 443/tcp
sudo ufw allow 9128/tcp
# Allow PostgreSQL connections
sudo ufw allow 5432/tcp
```

## 🔒 SSL/HTTPS Configuration

**Enhanced Security**: The AgentMessage remote server now supports full HTTPS encryption with SSL/TLS certificates. All API communications and web interfaces are secured by default.

### SSL Certificate Management

The deployment system provides flexible SSL certificate handling:

**Automatic Certificate Detection:**
- The deployment script automatically detects SSL certificates in the `ssl/` directory
- Supports any `.crt` (certificate) and `.key` (private key) files
- Default certificate names: `server.crt` and `server.key`
- Environment variables `SSL_CERT_FILE` and `SSL_KEY_FILE` have secure defaults

**Certificate Requirements:**
- One SSL certificate file (`.crt` format) in the `ssl/` directory
- One private key file (`.key` format) in the `ssl/` directory
- Proper file permissions: 644 for certificates, 600 for private keys

### Obtaining SSL Certificates

#### 1. Let's Encrypt (Recommended for Production)

For production deployments, replace the self-signed certificates with certificates from a trusted Certificate Authority:

1. **Using Let's Encrypt (Recommended):**
```bash
# Install certbot
sudo apt-get install certbot

# Generate certificates
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to ssl directory
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/certificate.crt
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/private.key

# Set proper permissions
sudo chown $USER:$USER ssl/certificate.crt ssl/private.key
sudo chmod 644 ssl/certificate.crt
sudo chmod 600 ssl/private.key
```

2. **Using Commercial SSL Certificates:**
    - Place your certificate file as any `.crt` file in the `ssl/` directory
    - Place your private key file as any `.key` file in the `ssl/` directory
   - Ensure proper file permissions (644 for .crt, 600 for .key)
   - Update `SERVER_DOMAIN` in your `.env` file to match your domain name

3. **Domain and Port Configuration:**
   - For production: Set `SERVER_DOMAIN=yourdomain.com` in your `.env` file
   - For local testing: Keep `SERVER_DOMAIN=localhost`
   - Configure ports: Set `HTTPS_PORT` and `HTTP_PORT` as needed
   - Default ports: HTTPS=443, HTTP=9128
   - The Nginx configuration will automatically use these settings

### Certificate Renewal

For Let's Encrypt certificates, set up automatic renewal:

```bash
# Add to crontab
0 12 * * * /usr/bin/certbot renew --quiet && docker-compose restart nginx
```

## Quick Start (Local Testing)

### 1. Interactive Deployment

**Run the deployment script**:
```bash
cd remote_server
chmod +x deploy.sh
./deploy.sh
```

The deployment script will now prompt you for:
- **Domain name** (default: localhost)
- **HTTPS port** (default: 443)
- **HTTP port** (default: 9128)
- **PostgreSQL port** (default: 5432)
- **API service internal port** (default: 8000)
- **Redis port** (default: 6379)
- **PostgreSQL password** (secure input)
- **PgAdmin password** (secure input)
- **PgAdmin email** (default: admin@example.com)

**Note**: PgAdmin is accessed through the HTTPS proxy at `https://your-domain/pgadmin/` for enhanced security.
- **Port conflict resolution** (automatic detection)

**Streamlined deployment process**:
- The script will securely prompt for passwords with hidden input
- No need to manually edit configuration files
- All configuration is handled automatically during deployment
- Validates SSL certificates (required for deployment)
- Deploys all services
- Displays access information

### 2. Manual Environment Setup (Alternative)

Alternatively, you can manually create your `.env` file with the following configuration:

```bash
# Remote Discovery Configuration
REMOTE_DISCOVERABLE=true

# Domain Configuration for SSL/HTTPS
SERVER_DOMAIN=localhost  # Change to your domain name for production
HTTPS_PORT=443          # HTTPS port (configurable)
HTTP_PORT=9128          # HTTP port (configurable)

# Service Ports
POSTGRES_PORT=5432
API_SERVICE_PORT=8000
REDIS_PORT=6379

# Database Configuration
POSTGRES_DB=agentmessage
POSTGRES_USER=agentmessage_user
POSTGRES_PASSWORD=your_secure_password_here

# PgAdmin Configuration
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=your_pgadmin_password_here

# Note: REMOTE_DB_* variables are not needed in the remote server's .env file
# They are only needed by external AgentMessage clients connecting to this server
```

### 3. Start Services with Docker

```bash
# Navigate to the remote_server directory
cd remote_server

# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f postgres
```

### 3. Verify Database Connection

```bash
# Connect to PostgreSQL container
docker-compose exec postgres psql -U agentmessage_user -d agentmessage

# List tables
\dt

# Check identities table
SELECT * FROM identities;
```

### 4. Access PgAdmin (Optional)

- URL: https://localhost:9187 (or http://localhost:9187 for local testing)
- Email: admin@example.com
- Password: admin123

## Database Schema

### Identities Table
```sql
CREATE TABLE identities (
    did TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    capabilities JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Messages Table (Future Use)
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_did TEXT NOT NULL,
    receiver_did TEXT NOT NULL,
    content JSONB NOT NULL,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL
);
```

## 🌐 HTTPS API Endpoints

The remote database service provides a secure RESTful HTTPS API for managing agent identities. All communication is encrypted using SSL/TLS for enhanced security.

### Security Features
- **Full HTTPS Encryption**: All API endpoints use SSL/TLS encryption
- **Secure Headers**: CORS and security headers configured for production use
- **Certificate Validation**: SSL certificates ensure secure client-server communication
- **Database SSL**: PostgreSQL connections support SSL/TLS encryption

### Available Endpoints

All endpoints are accessible via HTTPS at `https://your-domain.com/` or `https://localhost/` for local testing:

- `GET /health` - Service health check (HTTPS encrypted)
- `GET /identities` - List all identities (supports `limit` and `offset` query parameters)
- `GET /identities/{did}` - Get specific identity by DID
- `POST /identities` - Create new identity
- `PUT /identities/{did}` - Update existing identity
- `DELETE /identities/{did}` - Delete identity

### API Examples

```bash
# Health check
curl https://your-server/health

# List identities
curl https://your-server/identities?limit=10&offset=0

# Get specific identity
curl https://your-server/identities/did:example:agent1

# Create new identity
curl -X POST https://your-server/identities \
  -H "Content-Type: application/json" \
  -d '{
    "did": "did:example:agent1",
    "name": "Test Agent",
    "description": "A test agent",
    "capabilities": ["chat", "analysis"]
  }'

# Update identity
curl -X PUT https://your-server/identities/did:example:agent1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Agent",
    "description": "An updated test agent",
    "capabilities": ["chat", "analysis", "translation"]
  }'

# Delete identity
curl -X DELETE https://your-server/identities/did:example:agent1

# For local testing with self-signed certificates, add -k flag:
curl -k https://localhost/health

# For HTTP access (redirects to HTTPS):
curl http://localhost:9128/health
```

## Usage Examples

### Python Database Operations

```python
from remote_server import RemoteDatabase, RemoteConfig

# Initialize database connection
config = RemoteConfig()
db = RemoteDatabase(config)

# Create tables
result = db.create_tables()
print(result)

# Insert identity
identity_data = {
    'did': 'did:example:agent1',
    'name': 'Test Agent',
    'description': 'A test agent',
    'capabilities': ['chat', 'analysis']
}
result = db.insert_identity(identity_data)
print(result)

# Get all identities
identities = db.get_identities(limit=10)
print(identities)

# Get specific identity
identity = db.get_identity_by_did('did:example:agent1')
print(identity)
```

### Using with AgentMessage MCP Server

1. Set `REMOTE_DISCOVERABLE=true` in your `.env` file
2. Start the remote server with Docker
3. Use the `go_online` tool in your MCP client
4. The agent identity will be published to both local and remote databases

## Maintenance

### Backup Database
```bash
# Create backup
docker-compose exec postgres pg_dump -U agentmessage_user agentmessage > backup.sql

# Restore backup
docker-compose exec -T postgres psql -U agentmessage_user agentmessage < backup.sql
```

### Update Services
```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose down
docker-compose up -d
```

### Monitor Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f pgadmin
```

## Security Considerations

1. **Change Default Passwords**: Update all default passwords in production
2. **Network Security**: Use proper firewall rules and VPN for remote access
3. **SSL/TLS**: Enable SSL for PostgreSQL connections in production
4. **Backup Strategy**: Implement regular database backups
5. **Access Control**: Limit database user permissions as needed

## Troubleshooting

### Configurable Service Ports

All service ports are now configurable through the `.env` file:

- **POSTGRES_PORT** (default: 5432): PostgreSQL database external access port
- **API_SERVICE_PORT** (default: 8000): Internal API service port (used by nginx proxy)
- **REDIS_PORT** (default: 6379): Redis cache service port
- **HTTPS_PORT** (default: 443): HTTPS web service port
- **HTTP_PORT** (default: 9128): HTTP redirect service port

**Notes**: 
- The `API_SERVICE_PORT` is for internal Docker communication. External clients should use the HTTPS/HTTP ports.
- **PgAdmin** is accessed through the HTTPS proxy at `https://your-domain/pgadmin/` for enhanced security (no separate port needed).

### Port Conflict Issues
- **Port already allocated error**: The deployment script now automatically detects port conflicts
- If you encounter "port is already allocated", the script will prompt for alternative ports
- Common conflicting services:
  - Port 443: Other HTTPS services, Apache, Nginx
  - Port 80/9128: Other web servers
- To check what's using a port: `lsof -i :PORT_NUMBER`
- To stop conflicting services: `sudo systemctl stop SERVICE_NAME`

### Database Connection Issues
- Check if PostgreSQL container is running: `docker compose ps`
- View database logs: `docker compose logs postgres`
- Verify database credentials in `.env` file

### API Service Issues
- Check API service logs: `docker compose logs api`
- Verify the service is running: `curl https://YOUR_DOMAIN:YOUR_HTTPS_PORT/health`
- Check SSL certificate validity
- Ensure firewall allows configured ports

### SSL Certificate Issues
- Check certificate expiry: `openssl x509 -in ssl/your-certificate.crt -text -noout` (replace with your actual .crt filename)
- Verify certificate files exist in `ssl/` directory
- Ensure certificates are from a trusted Certificate Authority
- For Let's Encrypt renewal: `sudo certbot renew --quiet && docker-compose restart nginx`

### Interactive Configuration Issues
- If deployment script doesn't prompt for configuration, delete `.env` file and run again
- To reconfigure: `rm .env && ./deploy.sh`
- Check script permissions: `chmod +x deploy.sh`

### Common Issues

1. **Connection Refused**
   - Check if Docker services are running: `docker-compose ps`
   - Verify port availability: `netstat -an | grep 5432`

2. **Permission Denied**
   - Check database user permissions
   - Verify `.env` file configuration

3. **Database Not Found**
   - Ensure initialization scripts ran successfully
   - Check Docker logs: `docker-compose logs postgres`

### Reset Database
```bash
# Stop services and remove volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

## Dependencies

- Docker and Docker Compose
- Python packages: `psycopg2-binary`, `python-dotenv`
- PostgreSQL 15+
- Redis (optional, for caching)

## Contributing

When adding new database operations:
1. Add methods to `RemoteDatabase` class
2. Update initialization scripts if schema changes are needed
3. Add appropriate error handling and logging
4. Update this README with usage examples