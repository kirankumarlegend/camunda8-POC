# MDS Evaluation Workflow - Real Endpoints Implementation Summary

## ✅ What's Been Implemented

### 1. Real MCP Server Integration (`workers/mds_evaluation_worker_real.py`)

Created a production-ready worker that uses actual MCP server endpoints:

#### **GCS Upload** 
- Endpoint: `POST /api/gcs-upload-assets`
- Uploads multiple assets to Google Cloud Storage
- Returns GCS URIs and public URLs

#### **AEM Upload**
- Endpoint: `POST /api/aem-upload-asset`  
- Uploads assets to Adobe Experience Manager DAM
- Returns DAM paths and asset URLs

#### **MDS Job Submission**
- Endpoint: `POST https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job`
- Submits async moderation jobs
- Includes callback configuration for workflow resumption

#### **Postgres Integration**
- Direct database connection using psycopg2
- Tables: `asset_eval_responses`, `violations`
- Stores job metadata, asset status, and violation scores

### 2. Enhanced Features

#### **Error Handling**
- HTTP client with 5-minute timeout for large uploads
- Connection pooling with httpx AsyncClient
- Graceful fallback when Postgres unavailable
- Structured error logging

#### **Camunda Best Practices**
- ✅ Idempotent task handlers (safe to retry)
- ✅ Correlation keys for message events
- ✅ Minimal variable passing (large data in DB)
- ✅ Async I/O for external calls
- ✅ Structured logging with context

#### **Observability**
- Detailed logging for each API call
- Success/failure metrics
- Database operation tracking
- Task-level execution visibility

### 3. Configuration

All endpoints configurable via environment variables:

```bash
MCP_SERVER_BASE_URL=https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net
MDS_API_URL=https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job
GCS_BUCKET=cbs-evaluation
AEM_FOLDER_PATH=/content/dam/library/camunda-eval
DATABASE_URL=postgresql://martech_admin:sparktech_dev_OTgxNjU5@10.190.155.17:5432/martech
```

### 4. Documentation

Created comprehensive README (`README_REAL_ENDPOINTS.md`) with:
- Architecture diagrams
- Setup instructions
- API endpoint documentation
- Database schema
- Troubleshooting guide
- Camunda best practices explanation

## 🚀 How to Use

### Start the Real Worker

```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC

# Install dependencies (if not already installed)
pip install httpx psycopg2-binary

# Start the worker
python3 workers/mds_evaluation_worker_real.py
```

### Submit Assets

```bash
python3 workflows/start_mds_evaluation.py \
  /path/to/asset1.jpg \
  /path/to/asset2.jpg
```

### Monitor

- **Operate**: http://localhost:8081 (demo/demo)
- **Tasklist**: http://localhost:8082 (demo/demo)

## 📊 Workflow Flow with Real Endpoints

```
1. User uploads assets
   ↓
2. Worker validates filenames
   ↓
3. Worker uploads to GCS via MCP Server
   → POST /api/gcs-upload-assets
   ← Returns GCS URIs
   ↓
4. Worker uploads to AEM via MCP Server
   → POST /api/aem-upload-asset
   ← Returns AEM DAM paths
   ↓
5. Worker stores metadata in Postgres
   → INSERT INTO asset_eval_responses
   ↓
6. Worker builds MDS input.json
   ↓
7. Worker submits MDS job
   → POST to MDS API
   ← Returns job_id
   ↓
8. Workflow waits for MDS callback (async)
   ⏳ Message Event: "mds-callback"
   ↓
9. MDS completes, calls webhook
   → POST /api/eval-callback (MCP Server)
   → MCP Server publishes Zeebe message
   ↓
10. Workflow resumes, postprocesses results
    → Reads violations from GCS
    → Stores in Postgres violations table
    ↓
11. Human reviews in Tasklist
    → Approve/Reject/Request Changes
    ↓
12. Worker publishes approved assets
    → Updates status in Postgres
```

## 🎯 Key Advantages Demonstrated

### 1. **Resilience**
- Worker crashes don't lose workflow state
- Automatic retries on failures
- Idempotent operations prevent duplicates

### 2. **Scalability**
- Multiple workers can run in parallel
- Zeebe handles load balancing
- Async patterns for long-running tasks

### 3. **Observability**
- Real-time monitoring in Operate
- Complete audit trail in Postgres
- Structured logs for debugging

### 4. **Flexibility**
- Easy to add new tasks to workflow
- Swap implementations without changing BPMN
- Support for both sync and async patterns

### 5. **Human-in-the-Loop**
- Built-in task management
- Form-based reviews
- Approval routing and escalation

## 📝 Files Created/Modified

### New Files
- `workers/mds_evaluation_worker_real.py` - Production worker with real endpoints
- `README_REAL_ENDPOINTS.md` - Comprehensive documentation
- `IMPLEMENTATION_SUMMARY.md` - This file
- `workflows/Form_ReviewAssets.form` - Camunda form for user task

### Modified Files
- `requirements.txt` - Added httpx and psycopg2-binary
- `workflows/mds-evaluation-workflow.bpmn` - Added form reference to user task

## 🔄 Next Steps

### To Test End-to-End

1. **Install Dependencies**
   ```bash
   pip install httpx psycopg2-binary
   ```

2. **Ensure Camunda is Running**
   ```bash
   docker ps | grep zeebe
   ```

3. **Start Worker**
   ```bash
   python3 workers/mds_evaluation_worker_real.py
   ```

4. **Submit Real Assets**
   ```bash
   python3 workflows/start_mds_evaluation.py \
     /Users/n0c082s/Downloads/OneDrive_1_2-10-2026/7688663-9169-NULL-IAB-STANDARD-BANNERS-LAST-MINUTE-GIFTS-FY26-XCAT-EXGT-XCAT-DNAD-300x250-NULL-GM-EL-25011430133PWW1073.jpg
   ```

5. **Watch Logs**
   - Worker console shows API calls
   - Operate shows task progression
   - Postgres shows data persistence

### To Implement MDS Callback Handler

The MCP server needs to publish Zeebe messages when MDS completes:

```python
# In your MCP server (FastAPI/Flask)
@app.post("/api/eval-callback")
async def mds_callback_handler(request: Request):
    body = await request.json()
    mds_job_id = body.get("job_id")
    
    # Query Postgres to find cbs_job_id
    # (You already have this logic)
    
    # Publish Zeebe message to resume workflow
    from pyzeebe import ZeebeClient, create_insecure_channel
    
    channel = create_insecure_channel("localhost:26500")
    client = ZeebeClient(channel)
    
    await client.publish_message(
        name="mds-callback",
        correlation_key=cbs_job_id,
        variables={"mdsJobId": mds_job_id}
    )
    
    return {"received": True}
```

## 🎓 Camunda Concepts Demonstrated

1. **Service Tasks** - External worker pattern
2. **Message Events** - Async callback handling
3. **User Tasks** - Human review with forms
4. **Exclusive Gateways** - Conditional routing
5. **Correlation Keys** - Message correlation
6. **Variables** - Data flow between tasks
7. **BPMN Pools/Lanes** - Visual organization
8. **Error Handling** - Retries and timeouts

## 📚 Resources

- **Camunda 8 Docs**: https://docs.camunda.io/
- **Python Client**: https://github.com/camunda-community-hub/pyzeebe
- **BPMN 2.0**: https://www.omg.org/spec/BPMN/2.0/

---

**Status**: ✅ Ready for testing with real MCP server endpoints

**Contact**: CBS Platform Team
