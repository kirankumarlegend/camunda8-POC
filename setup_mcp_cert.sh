#!/bin/bash
# Setup MCP Server SSL Certificate
# This script helps download and configure the SSL certificate for the MCP server

set -e

CERT_DIR="./certs"
CERT_FILE="$CERT_DIR/mcp-server.crt"
MCP_SERVER_HOST="cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net"

echo "🔐 MCP Server SSL Certificate Setup"
echo "===================================="
echo ""

# Create certs directory
mkdir -p "$CERT_DIR"

# Option 1: Download certificate from server
echo "📥 Downloading certificate from $MCP_SERVER_HOST..."
if command -v openssl &> /dev/null; then
    openssl s_client -showcerts -connect "$MCP_SERVER_HOST:443" </dev/null 2>/dev/null | \
        openssl x509 -outform PEM > "$CERT_FILE" 2>/dev/null || {
        echo "⚠️  Could not download certificate automatically"
        echo ""
        echo "Please manually download the certificate:"
        echo "1. Visit https://$MCP_SERVER_HOST in your browser"
        echo "2. Click the lock icon → Certificate → Details → Export"
        echo "3. Save as: $CERT_FILE"
        echo ""
        exit 1
    }
    echo "✅ Certificate downloaded to $CERT_FILE"
else
    echo "⚠️  openssl not found"
    echo ""
    echo "Please manually download the certificate:"
    echo "1. Visit https://$MCP_SERVER_HOST in your browser"
    echo "2. Click the lock icon → Certificate → Details → Export"
    echo "3. Save as: $CERT_FILE"
    echo ""
    exit 1
fi

# Verify certificate
echo ""
echo "🔍 Verifying certificate..."
openssl x509 -in "$CERT_FILE" -text -noout | head -20

# Update .env file
ENV_FILE=".env"
echo ""
echo "📝 Updating $ENV_FILE..."

if [ ! -f "$ENV_FILE" ]; then
    echo "Creating $ENV_FILE..."
    cat > "$ENV_FILE" << EOF
# Zeebe
ZEEBE_GATEWAY_ADDRESS=localhost:26500

# MCP Server
MCP_SERVER_BASE_URL=https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net
MCP_SERVER_CERT_PATH=$(pwd)/$CERT_FILE
MCP_SERVER_VERIFY_SSL=true

# MDS API
MDS_API_URL=https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job

# GCS
GCS_BUCKET=cbs-evaluation

# AEM
AEM_FOLDER_PATH=/content/dam/library/camunda-eval

# Postgres
DATABASE_URL=postgresql://martech_admin:sparktech_dev_OTgxNjU5@10.190.155.17:5432/martech?sslmode=disable
EOF
else
    # Update existing .env
    if grep -q "MCP_SERVER_CERT_PATH" "$ENV_FILE"; then
        sed -i.bak "s|MCP_SERVER_CERT_PATH=.*|MCP_SERVER_CERT_PATH=$(pwd)/$CERT_FILE|" "$ENV_FILE"
    else
        echo "MCP_SERVER_CERT_PATH=$(pwd)/$CERT_FILE" >> "$ENV_FILE"
    fi
    
    if grep -q "MCP_SERVER_VERIFY_SSL" "$ENV_FILE"; then
        sed -i.bak "s|MCP_SERVER_VERIFY_SSL=.*|MCP_SERVER_VERIFY_SSL=true|" "$ENV_FILE"
    else
        echo "MCP_SERVER_VERIFY_SSL=true" >> "$ENV_FILE"
    fi
fi

echo "✅ Environment configured"
echo ""
echo "🚀 Next steps:"
echo "1. Load environment variables: source .env (or use python-dotenv)"
echo "2. Start the worker: python3 workers/mds_evaluation_worker_real.py"
echo ""
echo "💡 For development/testing, you can disable SSL verification:"
echo "   export MCP_SERVER_VERIFY_SSL=false"
echo "   (NOT recommended for production!)"
