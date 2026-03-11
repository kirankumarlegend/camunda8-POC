# MCP Server Configuration Requirements

## Issue: CREATIONAGENT_PRIVATE_KEY Error

When calling the Workfront metadata endpoint, the MCP Server returns:
```json
{"status":"error","message":"CREATIONAGENT_PRIVATE_KEY or CREATIONAGENT_PRIVATE_KEY_PATH is required"}
```

## Root Cause

The MCP Server requires the `CREATIONAGENT_PRIVATE_KEY` environment variable to authenticate with Workfront. This is set up in the server's environment configuration.

## MCP Server Endpoints

### Deployed Server (Kubernetes - Dev)
```
Base URL: https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net
```

### Local Server
```
Base URL: http://localhost:8080
```

## Workfront Metadata API

**Endpoint:** `GET /api/workfront-get-metadata`

**Query Parameters:**
- `project_id` (required): Workfront project ID

**Example:**
```bash
curl --location 'https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/api/workfront-get-metadata?project_id=698e0f500000e2ed2f7dfe0afff7aced' \
--header 'Content-Type: application/json'
```

## Required Environment Variables for MCP Server

The MCP Server needs these environment variables configured:

### Workfront Integration
- `WORKFRONT_API_KEY` - Workfront API key for authentication
- `CREATIONAGENT_PRIVATE_KEY` - Private key for Workfront CreationAgent authentication
  - OR `CREATIONAGENT_PRIVATE_KEY_PATH` - Path to file containing the private key

### LLM Gateway (Element AI)
- `ELEMENT_AI_API_KEY` - API key for Element AI LLM Gateway

### Other Optional Services
- `adobe_firefly_clientId` - Adobe Firefly client ID
- `adobe_firefly_clientSecret` - Adobe Firefly client secret
- `AZURE_SAS_SIGNATURE` - Azure storage SAS token
- `AEM_BASIC_AUTH` - AEM DAM authentication
- `GCS_BUCKET_NAME` - Google Cloud Storage bucket name
- `GCS_CREDENTIALS_PATH` - Path to GCS service account JSON key

## Fixing the Error

### Option 1: Configure Kubernetes Secret (Production)

The MCP Server in Kubernetes should have secrets configured via Akeyless:

1. Add secret to Akeyless: `/secrets/creationagent_private_key.txt`
2. Mount it in the Kubernetes deployment
3. The server will automatically load it from `/etc/secrets/creationagent_private_key.txt`

### Option 2: Local .env File (Development)

For local MCP server testing:

```bash
cd /path/to/cbs-content-mcp-server

# Create .env file
cat > .env <<EOF
CREATIONAGENT_PRIVATE_KEY=your_private_key_here
WORKFRONT_API_KEY=your_workfront_api_key
ELEMENT_AI_API_KEY=your_element_ai_key
DISABLE_OAUTH=true
EOF

# Start server
cbs-content-mcp-server
```

## Worker Configuration

The Camunda worker is configured to use the deployed MCP Server:

**File:** `/Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC/workers/push_notification_worker.py`

```python
# MCP Server configuration
MCP_SERVER_URL = "https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net"
```

To use local MCP server instead:
```python
MCP_SERVER_URL = "http://localhost:8080"
```

## Testing Workfront Integration

### Test 1: Health Check
```bash
curl https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/health
```

Expected:
```json
{"status":"healthy","version":"0.0.1"}
```

### Test 2: Workfront Metadata
```bash
curl 'https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/api/workfront-get-metadata?project_id=698e0f500000e2ed2f7dfe0afff7aced'
```

Expected (if configured correctly):
```json
{
  "status": "success",
  "data": {
    "project_id": "698e0f500000e2ed2f7dfe0afff7aced",
    "DE:Creative Project Name": "Valentine's Day Campaign",
    "DE:Overview / objective of request": "...",
    ...
  }
}
```

Error (if missing CREATIONAGENT_PRIVATE_KEY):
```json
{
  "status": "error",
  "message": "CREATIONAGENT_PRIVATE_KEY or CREATIONAGENT_PRIVATE_KEY_PATH is required"
}
```

## Next Steps

1. **Contact MCP Server Team** to ensure `CREATIONAGENT_PRIVATE_KEY` is configured in the Kubernetes deployment
2. **Verify Secret Mounting** in the pod: `kubectl exec <pod-name> -- ls -la /etc/secrets/`
3. **Check Server Logs** for any secret loading errors
4. **Use Valid Project ID** - The example project ID `69010161000053b75f8d1b612b560578` may not exist. Use a valid one like `698e0f500000e2ed2f7dfe0afff7aced`

## Alternative: Mock Mode for Testing

If you want to test the workflow without Workfront integration, you can:

1. Modify the worker to use mock data for Workfront responses
2. Skip the Workfront step in the BPMN workflow
3. Use the MCP Server's other endpoints that don't require Workfront (e.g., generate-push-notifications with manual campaign_brief)
