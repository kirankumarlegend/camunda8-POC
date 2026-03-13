# MDS Evaluation Workflow - Real Endpoints Implementation

This implementation uses **real MCP server endpoints** for GCS upload, AEM upload, MDS job submission, and Postgres database operations.

## 🎯 Overview

This Camunda 8 workflow demonstrates enterprise-grade orchestration for asset evaluation:

1. **Asset Upload** → GCS and AEM DAM via MCP Server
2. **MDS Submission** → Async job to Moderation Service
3. **Callback Handling** → Resume workflow on MDS completion
4. **Postprocessing** → Parse violations and calculate scores
5. **Human Review** → Tasklist form for approval/rejection
6. **Publishing** → Export approved assets

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Camunda 8 Platform                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Zeebe   │  │ Operate  │  │ Tasklist │  │ Connectors│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
         ↕                                           ↕
┌─────────────────────┐                    ┌──────────────────┐
│  Python Workers     │                    │  MCP Server      │
│  (This Repo)        │←──────────────────→│  (CBS Content)   │
└─────────────────────┘                    └──────────────────┘
         ↕                                           ↕
┌─────────────────────┐                    ┌──────────────────┐
│  Postgres DB        │                    │  External APIs   │
│  (Metadata/Scores)  │                    │  • GCS           │
└─────────────────────┘                    │  • AEM           │
                                           │  • MDS           │
                                           └──────────────────┘
```

## 📋 Prerequisites

### 1. Camunda 8 Platform (Docker)
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
docker-compose up -d
```

### 2. Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file:

```bash
# Zeebe
ZEEBE_GATEWAY_ADDRESS=localhost:26500

# MCP Server
MCP_SERVER_BASE_URL=https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net

# MDS API
MDS_API_URL=https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job

# GCS
GCS_BUCKET=cbs-evaluation

# AEM
AEM_FOLDER_PATH=/content/dam/library/camunda-eval

# Postgres
DATABASE_URL=postgresql://martech_admin:sparktech_dev_OTgxNjU5@10.190.155.17:5432/martech?sslmode=disable
```

## 🚀 Quick Start

### Step 1: Start Camunda Platform
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
docker-compose up -d

# Wait for services to be ready (~30 seconds)
sleep 30
```

### Step 2: Start the Worker (Real Endpoints)
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC

# Activate virtual environment
source .venv/bin/activate

# Start the worker with real MCP server integration
python3 workers/mds_evaluation_worker_real.py
```

You should see:
```
🚀 Starting MDS Evaluation Worker (REAL ENDPOINTS)
   Zeebe Gateway:    localhost:26500
   MCP Server:       https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net
   MDS API:          https://async-infer-platform.stage.walmart.com/...
   GCS Bucket:       cbs-evaluation
   AEM Folder:       /content/dam/library/camunda-eval
   Postgres:         10.190.155.17:5432/martech
✅ All handlers registered. Listening for jobs...
```

### Step 3: Submit Assets for Evaluation
```bash
# Example with real asset files
python3 workflows/start_mds_evaluation.py \
  /Users/n0c082s/Downloads/OneDrive_1_2-10-2026/7688663-9169-NULL-IAB-STANDARD-BANNERS-LAST-MINUTE-GIFTS-FY26-XCAT-EXGT-XCAT-DNAD-300x250-NULL-GM-EL-25011430133PWW1073.jpg \
  /Users/n0c082s/Downloads/OneDrive_1_2-10-2026/7688663-9175-NULL-IAB-STANDARD-BANNERS-LAST-MINUTE-GIFTS-FY26-XCAT-EXGT-XCAT-DNAD-300x250-NULL-GM-EL-25011430133PWW1065.jpg
```

### Step 4: Monitor Progress

**Camunda Operate:** http://localhost:8081 (demo/demo)
- View workflow instances
- See task execution history
- Inspect variables

**Camunda Tasklist:** http://localhost:8082 (demo/demo)
- Review assets awaiting approval
- Fill out review form
- Approve/Reject/Request Changes

## 📊 Workflow Tasks

### Automated Tasks (Handled by Worker)

| Task | Type | Description | MCP Endpoint |
|------|------|-------------|--------------|
| **Validate Asset Filenames** | Service Task | Parse filename metadata | N/A |
| **Upload to GCS** | Service Task | Upload to Google Cloud Storage | `POST /api/gcs-upload-assets` |
| **Upload to AEM** | Service Task | Upload to Adobe Experience Manager | `POST /api/aem-upload-asset` |
| **Store Job Metadata** | Service Task | Save to Postgres | Direct DB |
| **Build MDS Input** | Service Task | Create input.json | N/A |
| **Submit MDS Job** | Service Task | Submit to Moderation Service | MDS API |
| **Wait for Callback** | Message Event | Async wait for MDS completion | N/A |
| **Postprocess Results** | Service Task | Parse violations, calculate scores | N/A |
| **Approve Assets** | Service Task | Mark as approved in DB | Direct DB |
| **Reject Assets** | Service Task | Mark as rejected in DB | Direct DB |
| **Store Feedback** | Service Task | Save reviewer comments | Direct DB |
| **Publish Assets** | Service Task | Export to downstream systems | N/A |

### Human Tasks

| Task | Type | Description |
|------|------|-------------|
| **Review & Approve Assets** | User Task | Human review with Camunda form |

## 🔄 Real API Integrations

### 1. GCS Upload
```python
# MCP Server Endpoint
POST https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/api/gcs-upload-assets

# Request (multipart/form-data)
{
  "target_location": "cbs-evaluation/input",
  "folder_name": "<job_id>",
  "image1": <file>,
  "image2": <file>
}

# Response
{
  "status": "success",
  "bucket": "cbs-evaluation",
  "upload_path": "input/<job_id>",
  "total_assets": 2,
  "successful_uploads": 2,
  "assets": [
    {
      "status": "success",
      "blob_path": "input/<job_id>/asset.jpg",
      "gs_uri": "gs://cbs-evaluation/input/<job_id>/asset.jpg",
      "public_url": "https://storage.googleapis.com/...",
      "size_bytes": 96425
    }
  ]
}
```

### 2. AEM Upload
```python
# MCP Server Endpoint
POST https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/api/aem-upload-asset

# Request (multipart/form-data)
{
  "folder_path": "/content/dam/library/camunda-eval",
  "file1": <file>,
  "file2": <file>
}

# Response
{
  "status": "success",
  "data": {
    "total_files": 2,
    "successful_uploads": 2,
    "results": [
      {
        "file_name": "asset.jpg",
        "result": {
          "status": "success",
          "data": {
            "dam_path": "/content/dam/library/camunda-eval/asset.jpg",
            "asset_url": "https://author-p120867-e1855908.adobeaemcloud.com/...",
            "asset_details_url": "https://author-p120867-e1855908.adobeaemcloud.com/assetdetails.html/..."
          }
        }
      }
    ]
  }
}
```

### 3. MDS Job Submission
```python
# MDS API Endpoint
POST https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job

# Headers
{
  "Content-Type": "application/json",
  "WM_SVC.NAME": "BRAND_SAFETY_TEST",
  "WM_SVC.ENV": "dev"
}

# Request
{
  "model_name": "cbs_brand_safety",
  "model_version": -1,
  "input_path": "gs://cbs-evaluation/input/<job_id>/",
  "queue": "dev",
  "output_config": {
    "destination_folder_path": "gs://cbs-evaluation/output/"
  },
  "callback_config": {
    "callback_type": "API",
    "callback_path": "https://cbs-content-mcp-server.../api/eval-callback"
  }
}

# Response
{
  "job_id": "2b3c865c_c3b9_49f6_a671_b612fea2e54a",
  "request_id": "8b80778d_336c_451a_98bb_304a0674afff"
}
```

### 4. MDS Callback
```python
# Callback from MDS to MCP Server
POST https://cbs-content-mcp-server.../api/eval-callback

# Request Body
{
  "status": "Succeeded",
  "success_ratio": 1.0,
  "failure_threshold": 0.0,
  "output_folder_path": "gs://cbs-evaluation/output/<mds_job_id>"
}

# MCP Server Action:
# 1. Store callback in Postgres
# 2. Publish Zeebe message to resume workflow
```

## 🗄️ Database Schema

### Postgres Tables

```sql
-- Asset evaluation responses
CREATE TABLE asset_eval_responses (
    job_id VARCHAR(255),
    asset_filename VARCHAR(500),
    gcs_path TEXT,
    aem_path TEXT,
    mds_job_id VARCHAR(255),
    status VARCHAR(50),
    created_at BIGINT,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (job_id, asset_filename)
);

-- Violations
CREATE TABLE violations (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255),
    asset_filename VARCHAR(500),
    violation_name VARCHAR(200),
    violation_score FLOAT,
    created_at BIGINT
);
```

## 🎨 Camunda Best Practices Implemented

### 1. **Idempotency**
- All task handlers can be safely retried
- Database upserts prevent duplicate records
- File uploads check for existing files

### 2. **Error Handling**
```python
# Automatic retries with exponential backoff
worker.task(
    task_type="upload-assets-gcs",
    max_jobs_to_activate=3,
    timeout_ms=300000,  # 5 minutes
    request_timeout_ms=60000
)(upload_assets_to_gcs_handler)
```

### 3. **Correlation Keys**
- MDS callback uses `cbsJobId` as correlation key
- Ensures callback resumes correct workflow instance

### 4. **Variable Scoping**
- Minimal variables passed between tasks
- Large data (violations) stored in Postgres, not workflow variables

### 5. **Async Patterns**
- Message events for long-running external processes (MDS)
- Non-blocking I/O with httpx AsyncClient

### 6. **Observability**
- Structured logging with timestamps
- Task-level metrics in Operate
- Database audit trail

## 📈 Monitoring & Debugging

### View Workflow Instances
```bash
# Camunda Operate
open http://localhost:8081
```

### Check Worker Logs
```bash
# Worker console output shows:
# - Task activations
# - API calls to MCP server
# - Database operations
# - Errors and retries
```

### Query Database
```bash
# Connect to Postgres
psql postgresql://martech_admin:sparktech_dev_OTgxNjU5@10.190.155.17:5432/martech

# Check asset status
SELECT * FROM asset_eval_responses ORDER BY created_at DESC LIMIT 10;

# Check violations
SELECT * FROM violations WHERE job_id = '<your_job_id>';
```

### Zeebe Logs
```bash
docker logs zeebe -f
```

## 🔧 Troubleshooting

### Worker Not Connecting to Zeebe
```bash
# Check Zeebe is running
docker ps | grep zeebe

# Check port is accessible
nc -zv localhost 26500
```

### MCP Server Connection Issues
```bash
# Test MCP server connectivity
curl -I https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/health

# Check VPN/network access
```

### Postgres Connection Issues
```bash
# Test database connection
psql postgresql://martech_admin:sparktech_dev_OTgxNjU5@10.190.155.17:5432/martech -c "SELECT 1"
```

### Workflow Stuck at Message Event
```bash
# Manually publish message to resume workflow
python3 -c "
from pyzeebe import ZeebeClient, create_insecure_channel
import asyncio

async def publish():
    channel = create_insecure_channel('localhost:26500')
    client = ZeebeClient(channel)
    await client.publish_message(
        name='mds-callback',
        correlation_key='<your_cbs_job_id>',
        variables={'mdsJobId': '<your_mds_job_id>'}
    )

asyncio.run(publish())
"
```

## 🎯 Advantages of Camunda for This Use Case

### 1. **Visual Process Modeling**
- BPMN diagram serves as living documentation
- Business stakeholders can understand the flow
- Easy to modify and version control

### 2. **Resilience & Reliability**
- Automatic retries on task failures
- State persistence (survives worker crashes)
- Guaranteed message delivery

### 3. **Scalability**
- Horizontal scaling of workers
- Load balancing across worker instances
- Handles thousands of concurrent workflows

### 4. **Human-in-the-Loop**
- Built-in task management (Tasklist)
- Form-based user interactions
- Audit trail of all decisions

### 5. **Observability**
- Real-time monitoring in Operate
- Historical analytics
- SLA tracking and alerting

### 6. **Integration Flexibility**
- Easy to add new external services
- Supports sync and async patterns
- Message correlation for callbacks

## 📚 Next Steps

1. **Add Error Boundaries** - Implement BPMN error events for graceful degradation
2. **Metrics & Alerts** - Export Zeebe metrics to Prometheus/Grafana
3. **Multi-tenancy** - Add tenant isolation for different business units
4. **Approval Routing** - Dynamic assignment based on violation severity
5. **Batch Processing** - Parallel processing of multiple asset batches

## 📝 License

Internal use only - Walmart Global Tech

---

**Questions?** Contact the CBS Platform team or check the [Camunda 8 Documentation](https://docs.camunda.io/)
