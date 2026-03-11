# Push Notification Workflow - Quick Start Guide

## Overview

This workflow orchestrates the generation of CRM push notifications using:
- **Workfront** for campaign metadata
- **MCP Server** for AI content generation and evaluation
- **Camunda 8** for workflow orchestration
- **Human-in-the-loop** for quality review and feedback

## Workflow Steps

```
1. Get Workfront Metadata → Extract campaign details
2. Generate Push Notifications → AI generates 10 notification variants
3. Evaluate Notifications → Multi-model quality assessment
4. Human Review Task → Review in Tasklist, provide feedback
5. Decision Gateway:
   - Approved → Publish to CRM
   - Needs Regeneration → Store feedback & regenerate
```

## Prerequisites

✅ **Camunda 8 running** (Zeebe, Operate, Tasklist)  
✅ **MCP Server running** at http://localhost:8080  
✅ **Python 3.10+** installed  
✅ **Workfront API access** configured in MCP Server

## Setup

### 1. Install Python Dependencies

```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
python3 -m pip install -r requirements.txt
```

### 2. Verify Services Are Running

```bash
# Check Camunda 8
curl http://localhost:8081  # Operate should respond
curl http://localhost:8082  # Tasklist should respond

# Check MCP Server
curl http://localhost:8080/health
# Should return: {"status":"healthy","version":"0.0.1"}
```

### 3. Configure MCP Server

Make sure the MCP Server has these environment variables set (in `.env`):

```bash
# Workfront API
WORKFRONT_API_KEY=your_workfront_api_key

# Element AI (for LLM calls)
ELEMENT_AI_API_KEY=your_element_ai_api_key

# Disable OAuth for local dev
DISABLE_OAUTH=true
```

## Running the Workflow

### Step 1: Start the Worker

In one terminal:

```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
python3 workers/push_notification_worker.py
```

You should see:
```
🚀 Starting Push Notification Worker...
   Zeebe Gateway: localhost:26500
   MCP Server: http://localhost:8080
✅ Worker registered all handlers. Listening for jobs...
```

### Step 2: Start the Workflow

In another terminal:

```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
python3 workflows/start_push_notification_workflow.py <WORKFRONT_PROJECT_ID>
```

Example:
```bash
python3 workflows/start_push_notification_workflow.py 69010161000053b75f8d1b612b560578
```

You should see:
```
🚀 Starting Push Notification Workflow
   Workfront Project ID: 69010161000053b75f8d1b612b560578
✅ Workflow started successfully!
   Process Instance Key: 2251799813685249
📊 Monitor progress:
   Operate: http://localhost:8081 (demo/demo)
   Tasklist: http://localhost:8082 (demo/demo)
```

### Step 3: Monitor Progress

**In Operate (http://localhost:8081):**
- Login with `demo` / `demo`
- See the workflow instance running
- Watch each service task complete
- Debug any failures

**In Worker Logs:**
- See real-time MCP tool calls
- View generated notifications
- See evaluation scores

### Step 4: Complete Human Review Task

**In Tasklist (http://localhost:8082):**
- Login with `demo` / `demo`
- You'll see a task: "Review & Provide Feedback"
- Click on it to see:
  - Generated notifications (headlines + body copy)
  - Evaluation results (consensus verdict, scores)
  - Recommendations from AI evaluators

**Review Options:**
1. **Approve** → Workflow continues to publish
2. **Request Regeneration** → Provide feedback, workflow loops back to generation

**Provide Feedback:**
- Click the feedback form in Tasklist
- Enter comments like:
  - "Make tone more casual"
  - "Add more urgency"
  - "Remove emoji, too many"
  - "Focus on value proposition"
- This feedback is stored and used in regeneration

### Step 5: View Results

After approval, check:
- **Worker logs** - See "Published" message
- **Operate** - Workflow completed successfully
- **Generated content** - Available in workflow variables

## Workflow Variables

The workflow maintains these key variables:

```json
{
  "workfrontProjectId": "690101...",
  "workfrontMetadata": {
    "project_name": "Valentine's Day Campaign",
    "theme": "Romance & Gifts",
    "campaign_brief": "Promote Valentine's gifts..."
  },
  "generatedNotifications": [
    {
      "headline": "💝 Valentine's Day Deals...",
      "body_copy": "Show your love with...",
      "hook": "Value/Deal"
    }
  ],
  "evaluation": {
    "consensus_verdict": "approved",
    "overall_score": 8.5,
    "model_evaluations": [...]
  },
  "userFeedback": "Make more romantic, less commercial",
  "reviewDecision": "approved" | "regenerate"
}
```

## Troubleshooting

### Worker not connecting to Zeebe
```
Error: Failed to connect to localhost:26500
```
**Solution:** Make sure Camunda 8 is running:
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
docker-compose ps
```

### MCP Server not responding
```
Error calling MCP tool workfront_get_metadata: Connection refused
```
**Solution:** Start MCP Server:
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/cbs-content-mcp-server
cbs-content-mcp-server
```

### Workfront API errors
```
Error: Workfront metadata not found
```
**Solution:** Check Workfront API key in MCP Server `.env`:
```bash
WORKFRONT_API_KEY=your_actual_key
```

### Task not appearing in Tasklist
- Wait 30 seconds for Tasklist to sync with Zeebe
- Refresh the Tasklist page
- Check Operate to see if workflow is waiting at the user task

## Workflow Customization

### Change Number of Notifications

Edit `push_notification_worker.py`:
```python
result = mcp_client.generate_push_notifications(
    ...
    num_notifications=25,  # Change from 10 to 25
)
```

### Add Auto-Approval Logic

Modify workflow to add DMN decision before human task:
- Score >= 9.0 → Auto-approve
- Score < 9.0 → Human review

### Store Feedback to Database

In `store_feedback_handler`, add:
```python
# Store to PostgreSQL
db.execute("""
    INSERT INTO feedback (project_id, feedback, score)
    VALUES (?, ?, ?)
""", (project_id, feedback, score))

# Update prompts in GCS
mcp_client.call_tool("update_prompt_version", {
    "prompt_name": "push_notification_headline",
    "improvements": feedback
})
```

## Next Steps

1. **Add DMN decision table** for auto-approval thresholds
2. **Integrate with real CRM API** in publish step
3. **Add batch processing** for multiple campaigns
4. **Build dashboard** to visualize feedback trends
5. **A/B test tracking** - compare notification performance

## API Endpoints Reference

All MCP tools are available as REST APIs:

```bash
# Get Workfront metadata
curl -X POST http://localhost:8080/api/workfront-get-metadata \
  -H "Content-Type: application/json" \
  -d '{"project_id": "6901016..."}'

# Generate push notifications
curl -X POST http://localhost:8080/api/generate-push-notifications \
  -H "Content-Type: application/json" \
  -d '{
    "page_context": {...},
    "campaign_brief": "Valentine campaign",
    "num_notifications": 10
  }'

# Evaluate content
curl -X POST http://localhost:8080/api/evaluate-content \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "PushNotification",
    "generated_content": {...},
    "page_context": {...}
  }'
```

## Demo Video Script

**For stakeholders:**

1. Show Workfront project with campaign requirements
2. Run workflow start script with project ID
3. Show Operate dashboard - tasks progressing automatically
4. Show worker logs - MCP tools being called
5. Show generated notifications in logs (10 variants)
6. Show evaluation results (consensus verdict, scores)
7. Switch to Tasklist - human review task waiting
8. Open task - show generated content and evaluation
9. Provide feedback: "Make more urgent, add scarcity"
10. Select "Request Regeneration"
11. Show workflow looping back in Operate
12. Show new generation with feedback applied
13. This time, approve
14. Show workflow completing
15. Show "Published to CRM" message

**Wow factor:** Real-time orchestration + Human feedback loop + Quality gates
