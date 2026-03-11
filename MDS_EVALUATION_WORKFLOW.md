# MDS Evaluation Workflow - Camunda 8 Implementation

## 📋 Overview

This workflow orchestrates the **MDS (Moderation Service) Asset Evaluation** process for the CBS Playground Evaluation tab. It handles:
- Asset upload to AEM and GCS
- MDS API submission for brand safety evaluation
- Postprocessing of violation scores
- Human review and approval workflow

## 🔄 Workflow Process

```
1. User Uploads Assets
   ↓
2. Validate Asset Filenames
   (format: <projectId>-<DID>-<publisherId>-<platform>-...)
   ↓
3. Upload to AEM & GCS
   (parallel fan-out to both storage systems)
   ↓
4. Store Job Metadata (Postgres)
   (eval_jobs + eval_assets tables)
   ↓
5. Build input.json for MDS
   (CBS-generated post_id, media_id)
   ↓
6. Submit Async Job to MDS
   (returns mds_job_id, stores CBS↔MDS mapping)
   ↓
7. Wait for MDS Callback ⏸️
   (Message Correlation: cbsJobId)
   ↓
8. Postprocess & Calculate Scores
   (read GCS output, compute weighted confidence, determine status)
   ↓
9. Human Review & Approve Assets 👤
   (Tasklist: view violations, confidence scores)
   ↓
10. Gateway: Decision
    ├─ Approved → Mark as Approved → Publish
    ├─ Needs Changes → Store Feedback → Loop to Review
    └─ Rejected → Mark as Rejected → End
```

## 🎯 Key Design Decisions

### 1. **Message Correlation for MDS Callback**
- MDS calls webhook `/api/eval/callback` when job completes
- Callback includes `mds_job_id` in payload
- Lookup `cbs_job_id` from `eval_jobs` table via `mds_job_id`
- **Publish message** to Zeebe with correlation key `cbsJobId`
- Workflow instance waiting at `Event_WaitMDSCallback` resumes automatically

### 2. **Postgres as Source of Truth**
Tables created:
- `eval_jobs` - Job tracking (CBS↔MDS ID mapping, GCS paths, status)
- `eval_assets` - Asset metadata (filename, paths, scores, violations, status)
- `eval_callback_responses` - Raw MDS responses
- `eval_violations_config` - Violation weights and thresholds
- `eval_asset_history` - Audit trail
- `eval_feedback` - Reviewer comments

### 3. **Worker Task Types**
| Task Type | Worker Action |
|-----------|---------------|
| `validate-asset-filenames` | Parse filenames, extract projectId/DID/publisher/platform |
| `upload-assets-aem-gcs` | Fan-out upload to AEM + GCS in parallel |
| `store-job-metadata` | INSERT to `eval_jobs` and `eval_assets` |
| `build-mds-input-json` | Construct MDS `input.json`, upload to GCS |
| `submit-mds-job` | POST to MDS API, store `mds_job_id` |
| `postprocess-mds-results` | Read GCS output, calculate scores, update DB |
| `approve-assets` | UPDATE `eval_assets.status = 'APPROVED'` |
| `reject-assets` | UPDATE `eval_assets.status = 'REJECTED'` |
| `store-asset-feedback` | INSERT to `eval_feedback` + `eval_asset_history` |
| `publish-approved-assets` | Export to downstream systems |

## 📊 Workflow Variables

### Input Variables (Start)
```json
{
  "assetFiles": ["file1.jpg", "file2.jpg", ...],
  "aemFolderPath": "/content/dam/cbs/evaluation/project-7502741/",
  "uploadedBy": "user@walmart.com"
}
```

### Process Variables (throughout)
```json
{
  "cbsJobId": "uuid",
  "mdsJobId": "d6542ffc_e94a_44dd_a62e_f437146b9429",
  "assetCount": 6,
  "validAssets": [...],
  "invalidAssets": [...],
  "gcsInputPath": "gs://cbs-evaluation/input/<cbsJobId>/",
  "gcsOutputPath": "gs://cbs-evaluation/output/<cbsJobId>/<mdsJobId>/input.json",
  "processedAssets": [
    {
      "assetId": "uuid",
      "assetName": "7502741-5417-NULL-PMAX-...",
      "confidenceScore": 0.73,
      "status": "NEEDS_REVIEW",
      "violations": [...]
    }
  ],
  "reviewDecision": "approved" | "feedback" | "rejected",
  "feedbackText": "Color logo violation is false positive"
}
```

## 🔧 MDS API Integration

### Submit Job
```bash
curl 'https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job' \
  --header 'WM_SVC.NAME: BRAND_SAFETY_TEST' \
  --header 'WM_SVC.ENV: dev' \
  --header 'WM_CONSUMER.ID: 123e4567-e89b-12d3-a456-426614174000' \
  --data '{
    "model_name": "cbs_brand_safety",
    "model_version": -1,
    "input_path": "gs://cbs-evaluation/input/<cbsJobId>/",
    "queue": "dev",
    "output_config": {
      "destination_folder_path": "gs://cbs-evaluation/output/<cbsJobId>/"
    },
    "callback_config": {
      "callback_type": "API",
      "callback_path": "https://cbs-content-mcp-server.../api/eval/callback"
    }
  }'
```

### Callback Handler (MCP Server)
```python
@mcp.custom_route("/api/eval/callback", methods=["POST"])
async def mds_callback_handler(request):
    body = await request.json()
    mds_job_id = body.get("job_id")
    
    # Store raw response
    await db.insert("eval_callback_responses", {
        "mds_job_id": mds_job_id,
        "response_body": body
    })
    
    # Lookup CBS job ID
    job = await db.query("eval_jobs", mds_job_id=mds_job_id)
    cbs_job_id = job["cbs_job_id"]
    
    # Update status
    await db.update("eval_jobs", 
        where={"cbs_job_id": cbs_job_id},
        set={"status": "CALLBACK_RECEIVED"}
    )
    
    # Publish message to Zeebe to resume workflow
    await zeebe_client.publish_message(
        name="mds-callback",
        correlation_key=cbs_job_id,
        variables={"mdsJobId": mds_job_id}
    )
    
    return {"received": True}
```

## 📈 Postprocessing Logic

### Score Calculation
```python
def calculate_confidence_score(violations, violation_config):
    """
    Calculate weighted confidence score from MDS violations.
    
    confidence = 1 - (weighted_score / max_possible_weight)
    """
    weighted_sum = 0
    max_weight = 0
    
    for violation in violations:
        config = violation_config.get(violation["name"])
        if config:
            weighted_sum += violation["score"] * config["weight"]
            max_weight += config["weight"]
    
    if max_weight == 0:
        return 1.0  # No violations
    
    normalized = 1 - (weighted_sum / max_weight)
    return max(0.0, min(1.0, normalized))  # Clamp to [0, 1]
```

### Status Determination
```python
def determine_asset_status(confidence_score, violations, violation_config):
    """
    Determine asset status based on confidence and severe violations.
    """
    # Check for severe violations
    for violation in violations:
        config = violation_config.get(violation["name"])
        if config and config["is_severe"]:
            return "FLAGGED"
    
    # Thresholds (configurable)
    if confidence_score >= 0.85:
        return "APPROVED"
    elif confidence_score >= 0.60:
        return "NEEDS_REVIEW"
    else:
        return "FLAGGED"
```

## 🚀 Running the Workflow

### 1. Start Worker
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
python3 workers/mds_evaluation_worker.py
```

### 2. Trigger Workflow
```bash
# Upload 6 assets for evaluation
python3 workflows/start_mds_evaluation.py \
  --assets asset1.jpg asset2.jpg asset3.jpg asset4.jpg asset5.jpg asset6.jpg \
  --aem-folder /content/dam/cbs/evaluation/project-7502741/
```

### 3. Monitor in Operate
```
http://localhost:8081 (demo/demo)
```
- View workflow instance progress
- Check variables: `cbsJobId`, `mdsJobId`, `processedAssets`
- Monitor waiting at `Event_WaitMDSCallback`

### 4. Complete Review in Tasklist
```
http://localhost:8082 (demo/demo)
```
- Task: "Review & Approve Assets"
- View violations and confidence scores
- Decision: Approve / Needs Changes / Reject

## 🔄 Message Correlation Deep Dive

### Why Message Correlation?

MDS API is **asynchronous**:
1. We submit job → get `mds_job_id`
2. MDS processes (takes minutes/hours)
3. MDS calls our callback webhook
4. Workflow needs to **resume** from waiting state

**Problem**: Workflow instance is paused. How does callback know which instance to resume?

**Solution**: Message Correlation with `cbsJobId`

### How It Works

**Step 1: Workflow waits**
```xml
<bpmn:intermediateCatchEvent id="Event_WaitMDSCallback">
  <bpmn:messageEventDefinition messageRef="Message_MDSCallback" />
</bpmn:intermediateCatchEvent>

<bpmn:message id="Message_MDSCallback" name="mds-callback">
  <zeebe:subscription correlationKey="=cbsJobId" />
</bpmn:message>
```

When workflow reaches this event:
- Zeebe creates a **message subscription**
- Subscription key: value of `cbsJobId` variable (e.g., "abc-123")
- Workflow instance pauses

**Step 2: MDS calls back**
```python
# MCP Server callback handler
cbs_job_id = lookup_cbs_job_id_from_mds_job_id(mds_job_id)

# Publish message to Zeebe
zeebe_client.publish_message(
    name="mds-callback",           # Must match message name in BPMN
    correlation_key=cbs_job_id,    # Match the waiting subscription
    variables={"mdsJobId": mds_job_id}
)
```

**Step 3: Zeebe correlates**
- Zeebe receives message with name `"mds-callback"` and key `"abc-123"`
- Finds subscription with matching name and key
- Resumes that specific workflow instance
- Injects `mdsJobId` variable into process

### Alternative: Polling (Not Recommended)
```xml
<!-- DON'T DO THIS -->
<bpmn:serviceTask id="PollMDSStatus">
  <bpmn:multiInstanceLoopCharacteristics>
    <!-- Poll every 30 seconds for 1 hour -->
  </bpmn:multiInstanceLoopCharacteristics>
</bpmn:serviceTask>
```

Problems:
- Wastes resources
- Delays detection
- Hard to tune (too fast = spam, too slow = latency)

Message correlation is **event-driven** and instant.

## 🎨 Workflow vs REST API

### When to use Camunda workflow:
✅ **Multi-step orchestration** (upload → MDS → postprocess → review)  
✅ **Human-in-the-loop** (review task in Tasklist)  
✅ **Long-running async** (MDS takes minutes/hours)  
✅ **Audit trail** (Operate shows every step)  
✅ **Retry/recovery** (automatic retry on failures)  
✅ **Conditional routing** (approve vs reject vs feedback)

### When to use simple REST API:
✅ **Single synchronous action** (e.g., GET asset details)  
✅ **No workflow state** (stateless CRUD)  
✅ **Immediate response** (milliseconds)

**This MDS use case is PERFECT for Camunda** because:
- Multi-step (9 tasks)
- Async (MDS callback)
- Human review required
- Complex routing (approve/reject/feedback loop)

## 📝 Next Steps

1. **Create Worker** → `workers/mds_evaluation_worker.py`
2. **Create Start Script** → `workflows/start_mds_evaluation.py`
3. **Test with Sample Assets** → 6 JPGs with correct naming format
4. **Monitor Execution** → Operate + Tasklist
5. **Simulate MDS Callback** → Manual curl to test correlation
6. **Integrate with MCP Server** → Add `/api/eval/*` endpoints
7. **Connect to Postgres** → Create tables and repositories

## 🐛 Troubleshooting

### Workflow stuck at "Wait for MDS Callback"
**Check:**
1. Is message name correct? (`"mds-callback"`)
2. Is correlation key correct? (use actual `cbsJobId` value)
3. Did callback handler publish message?
4. Check Zeebe logs for correlation errors

**Test manually:**
```bash
# Get cbsJobId from Operate
CBS_JOB_ID="abc-123"

# Publish message via zbctl
zbctl publish message "mds-callback" \
  --correlationKey "$CBS_JOB_ID" \
  --variables '{"mdsJobId": "test-mds-job-123"}'
```

### BPMN Diagram Not Showing in Operate
**Cause:** Missing diagram layout coordinates in BPMN XML

**Fix:** Use Camunda Modeler to open BPMN file and re-export. Or add this to see task list view:
- Operate shows task names even without diagram
- Click on tasks to see details

**Workaround:** The workflow **executes correctly** even without visual diagram. You'll see:
- Instance History (list of task names)
- Variables
- Incidents
- Just not the pretty flowchart

---

**Your workflow is ready to implement! Start with the worker next.** 🚀
