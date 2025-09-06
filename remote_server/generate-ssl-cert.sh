#!/bin/bash

# SSL Certificate Generation Script for AgentMessage
# This script generates self-signed certificates for development/testing
# For production, replace with certificates from a trusted CA

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

# Create SSL directory
SSL_DIR="./ssl"
mkdir -p "$SSL_DIR"

# Certificate configuration
COUNTRY="US"
STATE="State"
CITY="City"
ORGANIZATION="AgentMessage"
ORGANIZATIONAL_UNIT="IT Department"
COMMON_NAME="localhost"
EMAIL="admin@agentmessage.local"

# Get domain name from user or use localhost
read -p "Enter domain name (default: localhost): " DOMAIN
DOMAIN=${DOMAIN:-localhost}
COMMON_NAME="$DOMAIN"

print_status "Generating SSL certificate for domain: $DOMAIN"

# Generate private key
print_status "Generating private key..."
openssl genrsa -out "$SSL_DIR/server.key" 2048

# Create certificate signing request configuration
cat > "$SSL_DIR/csr.conf" << EOF
[req]
default_bits = 2048
prompt = no
distinguished_name = dn
req_extensions = v3_req

[dn]
C=$COUNTRY
ST=$STATE
L=$CITY
O=$ORGANIZATION
OU=$ORGANIZATIONAL_UNIT
CN=$COMMON_NAME
emailAddress=$EMAIL

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = localhost
DNS.3 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate certificate signing request
print_status "Generating certificate signing request..."
openssl req -new -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.csr" -config "$SSL_DIR/csr.conf"

# Generate self-signed certificate
print_status "Generating self-signed certificate..."
openssl x509 -req -in "$SSL_DIR/server.csr" -signkey "$SSL_DIR/server.key" -out "$SSL_DIR/server.crt" -days 365 -extensions v3_req -extfile "$SSL_DIR/csr.conf"

# Set appropriate permissions
chmod 600 "$SSL_DIR/server.key"
chmod 644 "$SSL_DIR/server.crt"

# Clean up temporary files
rm "$SSL_DIR/server.csr" "$SSL_DIR/csr.conf"

print_success "SSL certificate generated successfully!"
print_status "Certificate files:"
echo "  Private key: $SSL_DIR/server.key"
echo "  Certificate: $SSL_DIR/server.crt"
echo ""
print_warning "This is a self-signed certificate for development/testing only."
print_warning "For production, obtain certificates from a trusted Certificate Authority."
echo ""
print_status "Certificate details:"
openssl x509 -in "$SSL_DIR/server.crt" -text -noout | grep -A 1 "Subject:"
openssl x509 -in "$SSL_DIR/server.crt" -text -noout | grep -A 1 "Not After"