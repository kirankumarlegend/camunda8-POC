# Camunda 8 Concepts - Quick Guide

## 🏗️ Core Components

### 1. **Zeebe** (Workflow Engine)
- The "brain" that executes your BPMN workflows
- Runs on `localhost:26500`
- Stores workflow state, manages job distribution

### 2. **Operate** (Monitoring Dashboard)
- **URL:** http://localhost:8081 (demo/demo)
- **Purpose:** Monitor and troubleshoot workflow instances
- **For:** DevOps, Technical users, Debugging

### 3. **Tasklist** (Human Task Interface)
- **URL:** http://localhost:8082 (demo/demo)
- **Purpose:** Complete human tasks (User Tasks in BPMN)
- **For:** Business users, Reviewers, Approvers

---

## 📊 Operate vs Tasklist

### **Operate** - Technical Monitoring
What you see:
- **All workflow instances** (running, completed, failed)
- **Process visualization** - See the BPMN diagram with current state
- **Incidents** - Failed tasks, errors, retry information
- **Variables** - Data flowing through the workflow
- **Performance metrics** - Duration, bottlenecks

**Example in your workflow:**
```
Push Notification Generation Workflow
├── ✅ Start with Workfront Project ID
├── ✅ Get Workfront Metadata
├── ✅ Generate Push Notifications  
├── ✅ Evaluate Notification Quality
└── ⏸️  Review & Provide Feedback (WAITING)
```

You can:
- See which tasks completed successfully (green checkmarks)
- View error messages if tasks fail
- Inspect variables like `workfrontProjectId`, `generatedNotifications`, `evaluation`
- Cancel or retry failed instances
- View incident details

---

### **Tasklist** - User Actions
What you see:
- **Only YOUR assigned tasks** (filtered by user)
- **Forms to complete** - Input fields, checkboxes, etc.
- **Task details** - Context and instructions

**Example in your workflow:**
```
Task: Review & Provide Feedback
Assignee: demo
Variables visible:
- generatedNotifications: [10 push notifications]
- evaluationSummary: {verdict: "approved", score: 8.5}
- campaignInfo: {project_name: "CBS CRM Test Project"}

Actions:
[Approve] or [Request Regeneration with Feedback]
```

You can:
- Complete assigned tasks
- Fill out forms
- Make approval decisions
- Provide feedback for regeneration

---

## 🎯 What is a "Task"?

A **task** is a step in your workflow. There are different types:

### 1. **Service Task** (Automated)
- Executed by **Workers** (Python scripts in your case)
- No human interaction
- Examples from your workflow:
  - `Get Workfront Metadata` → Worker calls MCP API
  - `Generate Push Notifications` → Worker calls MCP API
  - `Evaluate Notifications` → Worker processes data
  - `Store Feedback` → Worker stores to database
  - `Publish Notifications` → Worker publishes to CRM

**How it works:**
```
Zeebe: "Hey workers, I have a job: get-workfront-metadata"
Worker: "I'll take it!" (claims the job)
Worker: Calls MCP API, gets data
Worker: "Done! Here's the result: {metadata...}"
Zeebe: "Great! Moving to next task..."
```

### 2. **User Task** (Manual)
- Requires **human action** in Tasklist
- Workflow pauses until someone completes it
- Example from your workflow:
  - `Review & Provide Feedback` → Appears in Tasklist

**How it works:**
```
Zeebe: "Creating user task for 'demo' user"
(Task appears in Tasklist for demo user)
Human: Reviews notifications, clicks [Approve]
Zeebe: "Task completed! Continuing workflow..."
```

### 3. **Gateway** (Decision Point)
- Routes workflow based on conditions
- Example from your workflow:
  - `Review Decision` gateway:
    - If `reviewDecision = "approved"` → Go to Publish
    - If `reviewDecision = "regenerate"` → Go back to Generate

---

## 🚀 How to Trigger a New Workflow

### Method 1: Using the Start Script (What you've been doing)
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC

# Start with a Workfront Project ID
python3 workflows/start_push_notification_workflow.py 698e0f500000e2ed2f7dfe0afff7aced
```

**What happens:**
1. Script deploys the BPMN workflow to Zeebe
2. Creates a new process instance with variables: `{workfrontProjectId: "..."}`
3. Returns the process instance key
4. Workers immediately start picking up tasks

### Method 2: Using Zeebe Client Programmatically
```python
from pyzeebe import ZeebeClient, create_insecure_channel
import asyncio

async def start_workflow():
    channel = create_insecure_channel(grpc_address="localhost:26500")
    client = ZeebeClient(channel)
    
    # Start workflow with variables
    result = await client.run_process(
        bpmn_process_id="push-notification-workflow",
        variables={
            "workfrontProjectId": "698e0f500000e2ed2f7dfe0afff7aced"
        }
    )
    print(f"Started workflow: {result}")

asyncio.run(start_workflow())
```

### Method 3: Using HTTP API (External Systems)
```bash
curl -X POST http://localhost:26500/v1/process-instances \
  -H "Content-Type: application/json" \
  -d '{
    "bpmnProcessId": "push-notification-workflow",
    "variables": {
      "workfrontProjectId": "698e0f500000e2ed2f7dfe0afff7aced"
    }
  }'
```

### Method 4: Via Operate UI (Manual Testing)
Not available in Community Edition. Enterprise only.

---

## 🔄 Your Workflow Lifecycle

```
1. START
   ↓
2. Get Workfront Metadata (Service Task)
   Worker → MCP API → Returns project details
   ↓
3. Generate Push Notifications (Service Task)
   Worker → MCP API → Returns 10 notifications
   ↓
4. Evaluate Notifications (Service Task)
   Worker → Processes evaluation data
   ↓
5. Review & Provide Feedback (User Task) ← YOU ARE HERE
   Human → Opens Tasklist → Reviews → Makes decision
   ↓
6. Review Decision (Gateway)
   ├─ Approved → Publish to CRM
   └─ Regenerate → Store Feedback → Loop back to #2
   ↓
7. Publish Notifications (Service Task)
   Worker → Publishes to CRM system
   ↓
8. END
```

---

## 🎮 Common Actions

### View Running Workflows
**Operate:** http://localhost:8081
- Click on "Push Notification Generation Workflow"
- See all instances
- Filter by status: Running, Completed, Incident

### Complete a Task
**Tasklist:** http://localhost:8082
- See tasks assigned to you
- Click on "Review & Provide Feedback"
- Fill out form, click Complete

### Debug a Failed Task
**Operate:**
1. Look for incidents (red exclamation mark)
2. Click on the incident
3. See error message: "500 Server Error: Internal Server Error..."
4. Fix the issue (update API key, fix URL, etc.)
5. Click "Retry" on the incident

### Monitor Worker Health
**Terminal:**
```bash
# Watch worker logs
tail -f logs/push_notification_worker.log

# Or check running worker
ps aux | grep push_notification_worker.py
```

### Start Multiple Workflow Instances
```bash
# Project 1
python3 workflows/start_push_notification_workflow.py 698e0f500000e2ed2f7dfe0afff7aced

# Project 2
python3 workflows/start_push_notification_workflow.py 69010161000053b75f8d1b612b560578

# Both run in parallel!
# Each gets its own process instance key
# Workers handle both concurrently
```

---

## 📈 Monitoring Best Practices

### 1. **Check Operate for Health**
- Are workflows completing successfully?
- Any incidents that need attention?
- Are tasks taking too long?

### 2. **Check Worker Logs**
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
tail -f logs/push_notification_worker.log  # If you set up logging

# Or watch real-time in terminal where worker is running
```

### 3. **Check Tasklist for Pending Tasks**
- Tasks waiting for human action
- Age of oldest task
- Who is it assigned to?

### 4. **Performance Metrics**
Operate shows:
- Average workflow duration
- Task durations
- Bottlenecks (which tasks take longest)

---

## 🔧 Troubleshooting

### "Worker not picking up jobs"
**Check:**
1. Is worker running? `ps aux | grep push_notification_worker.py`
2. Is it connected to Zeebe? Check logs for "Starting to listen for jobs"
3. Task type matches? Worker registers "get-workfront-metadata", BPMN uses "get-workfront-metadata"

### "Task failing with incident"
**Steps:**
1. Open Operate → Click on failed instance
2. See error message in incident
3. Fix the issue (API error, missing data, etc.)
4. Click "Retry" or update incident count

### "Can't see my task in Tasklist"
**Check:**
1. Is task assigned to you? (Check `zeebe:assignmentDefinition` in BPMN)
2. Is workflow at that step? (Check Operate to see current state)
3. Logged in as correct user? (demo/demo)

---

## 🎯 Quick Reference

| Component | URL | Purpose | Users |
|-----------|-----|---------|-------|
| **Zeebe** | localhost:26500 | Workflow engine | Workers, API |
| **Operate** | localhost:8081 | Monitor workflows | DevOps, Debugging |
| **Tasklist** | localhost:8082 | Complete user tasks | Business users |

| Task Type | Execution | Visible In | Completes By |
|-----------|-----------|------------|--------------|
| Service Task | Automated | Operate only | Worker |
| User Task | Manual | Operate + Tasklist | Human |
| Gateway | Automatic | Operate only | Zeebe |

---

## 🚀 Next Steps

1. **Complete the user task** in Tasklist (http://localhost:8082)
2. **Watch the workflow finish** in Operate
3. **Try triggering another instance** with a different project ID
4. **Experiment with regeneration loop** - Request regeneration with feedback
5. **Add more workers** for different task types
6. **Create new workflows** for other content types (FAQs, copy blocks, etc.)

**Your workflow is production-ready!** 🎉
