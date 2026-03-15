# Deployment Guide — Camunda 8 Workflow API

## 1. How the pieces fit together

```
External System / Webhook caller
         │
         │  POST /api/workflows/mds-evaluation
         ▼
┌─────────────────────────┐      gRPC :26500
│  workflow_trigger_api   │ ──────────────────► Zeebe (Camunda 8)
│  (Flask – port 5000)    │                        │
└─────────────────────────┘                        │ runs workflow
         ▲                                         │
         │  POST /api/eval/callback                ▼
         └──────────────────────── MDS Async Service
                                  (calls back when job done)
```

---

## 2. Run locally (fastest)

```bash
# 1. Start Camunda stack
docker-compose up -d

# 2. Start workers (separate terminal)
python workers/mds_evaluation_worker.py

# 3. Start the API server
python api/workflow_trigger_api.py
```

The API is now live at `http://localhost:5000`.

---

## 3. Start a workflow via webhook

### Trigger MDS Evaluation
```bash
curl -X POST http://localhost:5000/api/workflows/mds-evaluation \
  -H "Content-Type: application/json" \
  -d '{
    "assetFiles": [
      "7502741-5417-NULL-PMAX-NOV-DEALS-1200x1200.jpg",
      "7502741-5417-NULL-PMAX-NOV-DEALS-800x800.jpg"
    ],
    "uploadedBy": "teja@example.com"
  }'
```

**Response:**
```json
{
  "status": "success",
  "workflow_instance_key": "2251799813722087",
  "bpmn_process_id": "mds-evaluation-workflow",
  "asset_count": 2,
  "monitor_urls": {
    "operate":  "http://localhost:8081",
    "tasklist": "http://localhost:8082"
  }
}
```

---

## 4. Simulate MDS callback (resume waiting workflow)

When MDS finishes processing, it POSTs to your callback URL.
For local testing, simulate it manually:

```bash
# Get cbsJobId from Camunda Operate → Variables tab
CBS_JOB_ID="paste-cbsJobId-here"

curl -X POST http://localhost:5000/api/eval/callback \
  -H "Content-Type: application/json" \
  -d "{
    \"job_id\": \"mds_test_job_001\",
    \"cbs_job_id\": \"$CBS_JOB_ID\",
    \"status\": \"completed\",
    \"output_path\": \"gs://cbs-evaluation/output/$CBS_JOB_ID/mds_test_job_001/\"
  }"
```

The workflow will immediately resume from the waiting state.

---

## 5. Deploy via Docker

```bash
# Build image
docker build -t camunda-workflow-api .

# Run (point at your Zeebe cluster)
docker run -d \
  -p 5000:5000 \
  -e ZEEBE_GATEWAY_ADDRESS=<your-zeebe-host>:26500 \
  --name camunda-api \
  camunda-workflow-api
```

---

## 6. Add to docker-compose (run everything together)

Add this service to your existing `docker-compose.yml`:

```yaml
  workflow-api:
    build: .
    ports:
      - "5000:5000"
    environment:
      ZEEBE_GATEWAY_ADDRESS: zeebe:26500
      API_PORT: "5000"
    depends_on:
      - zeebe
    restart: unless-stopped
```

Then run:
```bash
docker-compose up -d workflow-api
```

---

## 7. Configure MDS to call your webhook

In `submit-mds-job` task, the callback URL is:
```
https://<your-public-host>:5000/api/eval/callback
```

Set via environment variable when running the API:
```bash
MCP_SERVER_CALLBACK_URL=https://yourserver.com/api/eval/callback \
  python api/workflow_trigger_api.py
```

---

## 8. Health check

```bash
curl http://localhost:5000/health
# → {"status": "healthy", "service": "camunda-workflow-api", "zeebe": "localhost:26500"}
```

---

## 9. Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZEEBE_GATEWAY_ADDRESS` | `localhost:26500` | Zeebe gRPC address |
| `API_PORT` | `5000` | Flask listen port |
| `MCP_SERVER_CALLBACK_URL` | `http://localhost:5000/api/eval/callback` | Callback URL sent to MDS |
