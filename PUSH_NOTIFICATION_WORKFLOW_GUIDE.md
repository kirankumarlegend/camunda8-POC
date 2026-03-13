# Push Notification Workflow - Complete Guide

## 🎯 Overview

This workflow automates CRM push notification generation using:
- **Workfront** for campaign metadata
- **MCP Server** for content generation and evaluation
- **Element AI Gateway** for LLM intelligence
- **AEM DAM** for asset storage
- **Email** for stakeholder notifications

## 🏗️ Architecture

```
Campaign Manager → REST API → Camunda Workflow → MCP Server → Element AI
                                     ↓
                              Human Review (Tasklist)
                                     ↓
                              Publish → AEM DAM + Email
```

## 🚀 Quick Start

### 1. Start the Worker

```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC

# Disable SSL verification for MCP server (dev only)
export MCP_SERVER_VERIFY_SSL=false

# Start the worker
python3 workers/push_notification_worker_real.py
```

### 2. Start the API Server (Optional)

```bash
# In another terminal
python3 api/workflow_trigger_api.py
```

### 3. Trigger the Workflow

**Option A: Via REST API (Recommended)**

```bash
curl --location 'http://localhost:5000/api/workflows/push-notification' \
--header 'Content-Type: application/json' \
--data '{
    "workfrontProjectId": "69b18b90000050500e6247facdd92998",
    "pageUrl": "https://www.walmart.com/shop/deals/clearance",
    "messagingStrategy": "all",
    "emojiUsage": "medium",
    "numNotifications": 10,
    "modelName": "gpt-4.1-mini",
    "recipientEmails": [
        "your.email@walmart.com"
    ]
}'
```

**Option B: Via Python Script**

```bash
python3 workflows/start_push_notification_workflow.py \
  --project-id 69b18b90000050500e6247facdd92998 \
  --page-url https://www.walmart.com/shop/deals/clearance \
  --num-notifications 10
```

## 📋 Workflow Steps

### Step 1: Get Workfront Metadata
**Task Type:** `get-workfront-metadata`

Retrieves campaign details from Workfront:
- Project name
- Copy direction/brief
- Campaign dates
- Stakeholders

**MCP Tool:** `workfront_get_metadata`

```bash
curl --location 'https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/mcp' \
--header 'Content-Type: application/json' \
--data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "workfront_get_metadata",
        "arguments": {
            "project_id": "69b18b90000050500e6247facdd92998"
        }
    }
}'
```

### Step 2: Generate Push Notifications
**Task Type:** `generate-push-notifications`

Generates push notifications using AI:
- Analyzes page URL
- Applies messaging strategy
- Evaluates against brand guidelines
- Returns approved/rejected notifications

**MCP Tool:** `generate_push_notifications`

```bash
curl --location 'https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/mcp' \
--header 'Content-Type: application/json' \
--data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "generate_push_notifications",
        "arguments": {
            "page_url": "https://www.walmart.com/shop/deals/clearance",
            "messaging_strategy": "all",
            "emoji_usage": "medium",
            "num_notifications": 10,
            "model_name": "gpt-4.1-mini"
        }
    }
}'
```

### Step 3: Human Review
**Task Type:** User Task

Reviewer sees:
- Generated notifications
- Evaluation scores
- Approval/rejection reasons

Actions:
- **Approve** → Proceed to publish
- **Regenerate** → Provide feedback and regenerate

### Step 4: Publish Notifications
**Task Type:** `publish-notifications`

1. Creates CSV file with notifications
2. Uploads to AEM DAM
3. Sends email to stakeholders

**MCP Tools:**
- `aem-upload-asset` (REST API)
- `send_email` (MCP tool)

## 📊 Workflow Variables

| Variable | Type | Description | Default |
|----------|------|-------------|---------|
| `workfrontProjectId` | string | Workfront project ID | **Required** |
| `pageUrl` | string | Landing page URL | clearance page |
| `messagingStrategy` | string | Strategy: all/value/fomo/newness | `all` |
| `emojiUsage` | string | Emoji level: none/light/medium/heavy | `medium` |
| `numNotifications` | int | Number to generate | `10` |
| `modelName` | string | LLM model to use | `gpt-4.1-mini` |
| `recipientEmails` | array | Email recipients | Team emails |

## 🔧 Configuration

### Environment Variables

```bash
# Zeebe
export ZEEBE_GATEWAY_ADDRESS=localhost:26500

# MCP Server
export MCP_SERVER_BASE_URL=https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net
export MCP_SERVER_VERIFY_SSL=false  # Dev only

# Element AI Gateway
export ELEMENT_AI_GATEWAY_URL=https://wmtllmgateway.stage.walmart.com/wmtllmgateway/v1
export ELEMENT_AI_API_KEY=eyJzZ252ZXIiOiIxIiwiYWxnIjoiSFMyNTYiLCJ0eXAiOiJKV1QifQ...

# AEM
export AEM_FOLDER_PATH=/content/dam/library/crm-push-notifications
```

## 📝 API Reference

### Trigger Workflow

**Endpoint:** `POST /api/workflows/push-notification`

**Request:**
```json
{
    "workfrontProjectId": "69b18b90000050500e6247facdd92998",
    "pageUrl": "https://www.walmart.com/shop/deals/clearance",
    "messagingStrategy": "all",
    "emojiUsage": "medium",
    "numNotifications": 10,
    "modelName": "gpt-4.1-mini",
    "recipientEmails": ["user@walmart.com"]
}
```

**Response:**
```json
{
    "status": "success",
    "workflow_instance_key": "2251799813722087",
    "bpmn_process_id": "push-notification-workflow",
    "variables": {...},
    "monitor_urls": {
        "operate": "http://localhost:8081",
        "tasklist": "http://localhost:8082"
    }
}
```

## 🎨 MCP Server Tools Used

### 1. workfront_get_metadata
Retrieves Workfront project metadata.

**Arguments:**
- `project_id` (string): Workfront project ID
- `field_names` (array, optional): Specific fields to retrieve

**Returns:**
```json
{
    "status": "success",
    "data": {
        "project_id": "...",
        "name": "CBS CRM Test Project",
        "DE:Copy Direction": {...},
        "referenceNumber": "8509251"
    }
}
```

### 2. generate_push_notifications
Generates and evaluates push notifications.

**Arguments:**
- `page_url` (string): Landing page URL
- `messaging_strategy` (string): all/value/fomo/newness
- `emoji_usage` (string): none/light/medium/heavy
- `num_notifications` (int): Number to generate
- `model_name` (string): LLM model

**Returns:**
```json
{
    "status": "success",
    "data": {
        "notifications": [
            {
                "headline": "Clearance: low home prices 🏷️",
                "body_copy": "Low prices on home décor & furniture. Tap to browse clearance.",
                "hook": "Value/Deal"
            }
        ],
        "evaluation": {
            "results": [{
                "batch_evaluations": [{
                    "notification_id": 1,
                    "verdict": "approved",
                    "metrics": {...}
                }]
            }]
        }
    }
}
```

### 3. send_email
Sends email with attachments.

**Arguments:**
- `to_emails` (array): Recipient emails
- `subject` (string): Email subject
- `body` (string): Email body
- `attachments` (array, optional): File attachments

**Returns:**
```json
{
    "status": "success",
    "recipients": ["user@walmart.com"],
    "subject": "Generated Push Notifications"
}
```

### 4. aem-upload-asset (REST API)
Uploads files to AEM DAM.

**Endpoint:** `POST /api/aem-upload-asset`

**Form Data:**
- `folder_path`: DAM folder path
- `file`: File to upload

**Returns:**
```json
{
    "status": "success",
    "data": {
        "dam_path": "/content/dam/library/crm-push-notifications/push-notifications.csv",
        "asset_url": "https://author-p120867-e1855908.adobeaemcloud.com/...",
        "asset_details_url": "https://author-p120867-e1855908.adobeaemcloud.com/assetdetails.html/..."
    }
}
```

## 🔄 Workflow Regeneration Loop

If reviewer requests changes:

1. User provides feedback in Tasklist
2. Workflow stores feedback
3. Loops back to generation step
4. Feedback is included in next generation prompt
5. New notifications generated with improvements

## 📊 Monitoring

### Camunda Operate
**URL:** http://localhost:8081 (demo/demo)

View:
- Workflow instances
- Task execution history
- Variables at each step
- Error details

### Camunda Tasklist
**URL:** http://localhost:8082 (demo/demo)

Actions:
- Review generated notifications
- Approve or request regeneration
- Provide feedback

## 🐛 Troubleshooting

### Worker Not Processing Tasks

```bash
# Check Zeebe connection
docker ps | grep zeebe

# Check worker logs
# Should see: "✅ All handlers registered. Listening for jobs..."
```

### MCP Server SSL Errors

```bash
# Disable SSL verification (dev only)
export MCP_SERVER_VERIFY_SSL=false
```

### Workflow Stuck

```bash
# Check Operate for error details
# Check worker logs for exceptions
# Verify MCP server is accessible
```

## 📚 Example Scenarios

### Scenario 1: Flash Sale Campaign

```bash
curl -X POST http://localhost:5000/api/workflows/push-notification \
-H 'Content-Type: application/json' \
-d '{
    "workfrontProjectId": "69b18b90000050500e6247facdd92998",
    "pageUrl": "https://www.walmart.com/shop/deals/flash-deals",
    "messagingStrategy": "fomo",
    "emojiUsage": "heavy",
    "numNotifications": 15
}'
```

### Scenario 2: New Product Launch

```bash
curl -X POST http://localhost:5000/api/workflows/push-notification \
-H 'Content-Type: application/json' \
-d '{
    "workfrontProjectId": "69b18b90000050500e6247facdd92998",
    "pageUrl": "https://www.walmart.com/shop/new-arrivals",
    "messagingStrategy": "newness",
    "emojiUsage": "light",
    "numNotifications": 8
}'
```

### Scenario 3: Value Campaign

```bash
curl -X POST http://localhost:5000/api/workflows/push-notification \
-H 'Content-Type: application/json' \
-d '{
    "workfrontProjectId": "69b18b90000050500e6247facdd92998",
    "pageUrl": "https://www.walmart.com/shop/rollbacks",
    "messagingStrategy": "value",
    "emojiUsage": "medium",
    "numNotifications": 12
}'
```

## 🎯 Integration with Campaign Manager

Campaign managers can trigger this workflow when campaign status changes:

```javascript
// Campaign Manager Integration Example
async function onCampaignStatusChange(campaign) {
    if (campaign.status === 'READY_FOR_CONTENT') {
        const response = await fetch('http://camunda-api:5000/api/workflows/push-notification', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                workfrontProjectId: campaign.workfrontId,
                pageUrl: campaign.landingPageUrl,
                messagingStrategy: campaign.strategy,
                recipientEmails: campaign.stakeholders
            })
        });
        
        const result = await response.json();
        console.log('Workflow started:', result.workflow_instance_key);
    }
}
```

## 📦 Dependencies

```bash
pip install flask pyzeebe httpx
```

## 🔐 Security Notes

- API key for Element AI Gateway is required
- MCP server uses self-signed cert (disable SSL verification for dev)
- Production: Use proper SSL certificates and API authentication

## 📖 Additional Resources

- **MCP Server Tools:** https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/mcp
- **Camunda Docs:** https://docs.camunda.io/
- **Element AI Gateway:** Internal Walmart documentation

---

**Questions?** Contact the CBS Platform team
