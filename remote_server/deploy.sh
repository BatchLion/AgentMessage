#!/bin/bash

# AgentMessage Remote Database Service Deployment Script
# This script helps deploy the remote database service on a remote server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed."
}

# Check if .env file exists
check_env_file() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating a template..."
        interactive_config
        create_env_template
    else
        print_success ".env file found."
        # Load existing configuration
        source .env
    fi
}

# Check SSL certificates (required for deployment)
check_ssl_certificates() {
    if [ ! -d "ssl" ]; then
        print_error "SSL directory not found. Deployment stopped."
        print_status "Please create an 'ssl' directory and place your SSL certificates there."
        print_status "Required files:"
        print_status "  - One .crt file (SSL certificate)"
        print_status "  - One .key file (SSL private key)"
        print_status ""
        print_status "Please obtain SSL certificates from a trusted Certificate Authority and place them in the ssl/ directory."
        print_status ""
        print_status "For Let's Encrypt certificates:"
        print_status "  sudo apt-get install certbot"
        print_status "  sudo certbot certonly --standalone -d your-domain.com"
        print_status "  sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/"
        print_status "  sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/"
        print_status "  sudo chown \$USER:\$USER ssl/*"
        print_status "  sudo chmod 644 ssl/*.pem && sudo chmod 600 ssl/*key*"
        exit 1
    fi
    
    # Find .crt and .key files
    CRT_FILE=$(find ssl -name "*.crt" -type f | head -1)
    KEY_FILE=$(find ssl -name "*.key" -type f | head -1)
    
    if [ -z "$CRT_FILE" ] || [ -z "$KEY_FILE" ]; then
        print_error "SSL certificates not found. Deployment stopped."
        print_status "Required files in ssl/ directory:"
        print_status "  - One .crt file (SSL certificate)"
        print_status "  - One .key file (SSL private key)"
        print_status ""
        print_status "Please obtain SSL certificates from a trusted Certificate Authority and place them in the ssl/ directory."
        print_status "For Let's Encrypt certificates, you can use:"
        print_status "  sudo certbot certonly --standalone -d your-domain.com"
        print_status "  sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/server.crt"
        print_status "  sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/server.key"
        print_status "  sudo chown \$USER:\$USER ssl/server.crt ssl/server.key"
        print_status "  sudo chmod 644 ssl/server.crt && sudo chmod 600 ssl/server.key"
        print_status ""
        print_error "Deployment stopped. SSL certificates are required for secure HTTPS operation."
        exit 1
    fi
    
    # Extract just the filename from the full path
    SSL_CERT_FILE=$(basename "$CRT_FILE")
    SSL_KEY_FILE=$(basename "$KEY_FILE")
    
    # Export SSL file environment variables for docker-compose
    export SSL_CERT_FILE
    export SSL_KEY_FILE
    
    print_success "SSL certificates found:"
    print_status "  Certificate: $SSL_CERT_FILE"
    print_status "  Private key: $SSL_KEY_FILE"
    
    # Check certificate expiry
    if openssl x509 -checkend 86400 -noout -in "$CRT_FILE" >/dev/null 2>&1; then
        print_success "SSL certificate is valid for at least 24 hours."
    else
        print_warning "SSL certificate expires within 24 hours. Consider renewing."
    fi
}

# Interactive configuration
interactive_config() {
    print_status "Configuring domain and ports..."
    
    # Domain configuration
    read -p "Enter your domain name (default: localhost): " domain_input
    SERVER_DOMAIN=${domain_input:-localhost}
    
    # Web service ports
    read -p "Enter HTTPS port (default: 443): " https_port_input
    HTTPS_PORT=${https_port_input:-443}
    
    read -p "Enter HTTP port (default: 9128): " http_port_input
    HTTP_PORT=${http_port_input:-9128}
    
    # Database and service ports
    read -p "Enter PostgreSQL port (default: 5432): " postgres_port_input
    POSTGRES_PORT=${postgres_port_input:-5432}
    
    # PgAdmin is accessed through nginx proxy, no external port needed
    
    read -p "Enter API service internal port (default: 8000): " api_port_input
    API_SERVICE_PORT=${api_port_input:-8000}
    
    read -p "Enter Redis port (default: 6379): " redis_port_input
    REDIS_PORT=${redis_port_input:-6379}
    
    # Check for port conflicts
    check_port_availability $HTTPS_PORT "HTTPS"
    check_port_availability $HTTP_PORT "HTTP"
    check_port_availability $POSTGRES_PORT "PostgreSQL"
    check_port_availability $API_SERVICE_PORT "API Service"
    check_port_availability $REDIS_PORT "Redis"
    
    # Password configuration
    print_status "Configuring passwords..."
    
    read -s -p "Enter PostgreSQL password: " postgres_password
    echo
    POSTGRES_PASSWORD=$postgres_password
    
    read -s -p "Enter PgAdmin password: " pgadmin_password
    echo
    PGADMIN_PASSWORD=$pgadmin_password
    
    read -p "Enter PgAdmin email (default: admin@example.com): " pgadmin_email_input
    PGADMIN_EMAIL=${pgadmin_email_input:-admin@example.com}
    
    print_success "Configuration complete!"
    print_status "Domain: $SERVER_DOMAIN"
    print_status "HTTPS: $HTTPS_PORT, HTTP: $HTTP_PORT"
    print_status "PostgreSQL: $POSTGRES_PORT, Redis: $REDIS_PORT"
    print_status "API Service: $API_SERVICE_PORT, PgAdmin: via HTTPS proxy"
}

# Check if port is available
check_port_availability() {
    local port=$1
    local service_name=$2
    
    if lsof -i :$port >/dev/null 2>&1; then
        print_error "Port $port is already in use by another service."
        print_status "Please choose a different port for $service_name or stop the service using port $port."
        read -p "Enter alternative $service_name port: " new_port
        
        # Update the appropriate variable
        case "$service_name" in
            "HTTPS") HTTPS_PORT=$new_port ;;
            "HTTP") HTTP_PORT=$new_port ;;
            "PostgreSQL") POSTGRES_PORT=$new_port ;;
            "API Service") API_SERVICE_PORT=$new_port ;;
            "Redis") REDIS_PORT=$new_port ;;
        esac
        
        check_port_availability $new_port "$service_name"
    fi
}

# Create .env template
create_env_template() {
    cat > .env << EOF
# Remote Discovery Configuration
REMOTE_DISCOVERABLE=true

# Domain Configuration for SSL/HTTPS
SERVER_DOMAIN=$SERVER_DOMAIN
HTTPS_PORT=$HTTPS_PORT
HTTP_PORT=$HTTP_PORT

# Service Port Configuration
POSTGRES_PORT=5432
API_SERVICE_PORT=8000
REDIS_PORT=6379

# Note: REMOTE_DB_* variables are not needed in the remote server's .env file
# They are only needed by external AgentMessage clients connecting to this server
# External clients should configure:
# REMOTE_DB_HOST=$SERVER_DOMAIN
# REMOTE_DB_PORT=$POSTGRES_PORT
# REMOTE_DB_NAME=agentmessage
# REMOTE_DB_USER=agentmessage_user
# REMOTE_DB_PASSWORD=<same_as_POSTGRES_PASSWORD>
# REMOTE_DB_SSL_MODE=prefer

# PostgreSQL Environment Variables for Docker
POSTGRES_DB=agentmessage
POSTGRES_USER=agentmessage_user
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# PgAdmin Configuration
PGADMIN_EMAIL=$PGADMIN_EMAIL
PGADMIN_PASSWORD=$PGADMIN_PASSWORD
EOF
    print_success ".env file created with your configuration"
}

# Build and start services
deploy_services() {
    print_status "Building and starting AgentMessage remote database services..."
    
    # Pull latest images
    docker compose pull
    
    # Build custom images if needed
    docker compose build
    
    # Start services
    docker compose up -d
    
    print_success "Services started successfully!"
}

# Check service health
check_services() {
    print_status "Checking service health..."
    
    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U agentmessage_user -d agentmessage &> /dev/null; then
            print_success "PostgreSQL is ready!"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Show service status
    echo ""
    print_status "Service status:"
    docker compose ps
}

# Test database connection
test_database() {
    print_status "Testing database connection..."
    
    if docker compose exec -T postgres psql -U agentmessage_user -d agentmessage -c "SELECT 1;" &> /dev/null; then
        print_success "Database connection test passed!"
    else
        print_error "Database connection test failed!"
        return 1
    fi
}

# Show deployment information
show_info() {
    echo ""
    print_success "=== AgentMessage Remote Database Service Deployed ==="
    echo ""
    echo "📊 Database Access:"
    echo "   Host: $SERVER_DOMAIN (or your server IP)"
    echo "   Port: 5432"
    echo "   Database: agentmessage"
    echo "   User: agentmessage_user"
    echo ""
    echo "🚀 API Service (HTTPS):"
    echo "   URL: https://$SERVER_DOMAIN:$HTTPS_PORT"
    echo "   Health Check: https://$SERVER_DOMAIN:$HTTPS_PORT/health"
    echo "   Identities API: https://$SERVER_DOMAIN:$HTTPS_PORT/identities"
    echo "   HTTP (port $HTTP_PORT) redirects to HTTPS automatically"
    echo ""
    echo "🔧 PgAdmin Access:"
    echo "   URL: https://$SERVER_DOMAIN:$HTTPS_PORT/pgadmin/"
    echo "   Email: ${PGADMIN_EMAIL:-admin@example.com}"
    echo "   Password: ${PGADMIN_PASSWORD:-change_this_password}"
    echo ""
    echo "📋 Useful Commands:"
    echo "   View logs: docker compose logs -f"
    echo "   Stop services: docker compose down"
    echo "   Restart services: docker compose restart"
    echo "   Database backup: docker compose exec postgres pg_dump -U agentmessage_user agentmessage > backup.sql"
    echo ""
}

# Main deployment function
main() {
    echo "🚀 AgentMessage Remote Database Service Deployment"
    echo "================================================="
    echo ""
    
    check_docker
    check_env_file
    check_ssl_certificates
    
    # Ask for confirmation if .env was just created
    if [ ! -f ".env.backup" ]; then
        cp .env .env.backup 2>/dev/null || true
        echo ""
        read -p "Have you updated the passwords in .env file? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Please update the passwords in .env file before deployment."
            print_status "Edit .env file and run this script again."
            exit 1
        fi
    fi
    
    deploy_services
    check_services
    test_database
    show_info
    
    print_success "Deployment completed successfully! 🎉"
}

# Handle script arguments
case "${1:-}" in
    "stop")
        print_status "Stopping services..."
        docker compose down
        print_success "Services stopped."
        ;;
    "restart")
        print_status "Restarting services..."
        docker compose restart
        print_success "Services restarted."
        ;;
    "logs")
        docker compose logs -f
        ;;
    "status")
        docker compose ps
        ;;
    "backup")
        BACKUP_FILE="agentmessage_backup_$(date +%Y%m%d_%H%M%S).sql"
        print_status "Creating database backup: $BACKUP_FILE"
        docker compose exec -T postgres pg_dump -U agentmessage_user agentmessage > "$BACKUP_FILE"
        print_success "Backup created: $BACKUP_FILE"
        ;;
    "help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)  Deploy the remote database service"
        echo "  stop       Stop all services"
        echo "  restart    Restart all services"
        echo "  logs       Show service logs"
        echo "  status     Show service status"
        echo "  backup     Create database backup"
        echo "  help       Show this help message"
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac