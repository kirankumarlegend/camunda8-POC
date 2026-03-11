# Camunda 8 Orchestration Plan for Creative Brand System (CBS)

**Project**: CBS Content MCP Server Integration with Camunda 8  
**Date**: March 2026  
**Purpose**: Demonstrate Camunda 8 orchestration for AI-powered creative content workflows

---

## Executive Summary

This document outlines how Camunda 8 can orchestrate the 40+ MCP tools and APIs in the CBS Content MCP Server to create robust, human-supervised creative workflows. Camunda 8 brings enterprise-grade orchestration capabilities including BPMN workflows, DMN decision tables, human task management via Tasklist, and resilient microservices orchestration.

**Key Value Propositions:**
- **Visibility**: End-to-end tracking of creative content generation workflows
- **Human Oversight**: Strategic decision points for creative approval and quality control
- **Resilience**: Automatic retry logic and failure handling for external API calls
- **Compliance**: Audit trails for all content generation and approval decisions
- **Scalability**: Handle high-volume batch operations (e.g., 1000s of product images)
- **Decision Automation**: DMN tables for quality thresholds and routing logic

---

## Current System Analysis

### Existing CBS UI Features (creative-brand-system-cbs)

Based on the codebase analysis, the current system has these major capabilities:

1. **FAQ Generation & Evaluation** (`/content-generation`, API endpoints)
2. **CRM Push Notifications** (`/crm-push-notification/index.tsx`)
   - Headline and body copy generation
   - Multi-model evaluation
3. **Image Asset Evaluation** (`/evaluation/[did].tsx`)
   - Walmart image quality assessment
4. **Content Generation Hub** (`/generation.tsx`)
   - Image creation via Adobe Firefly/Gemini
   - PSD assembly with Photoshop API
   - Format conversion (PSD ↔ JPEG)
5. **Delivery/Upload** (`/delivery.tsx`)
   - Upload to AEM DAM
6. **Product Image Operations** (`/product-image-download.tsx`)
   - Search and scrape by product IDs
7. **A2A Agent Integration** (`/a2a-agent.tsx`)
   - AI agent with A2UI components

### Available MCP Tools (40+ tools)

**Content Generation Tools:**
- `generate_faqs` - FAQ generation with page context
- `generate_content` - Templated content (SEO titles, descriptions, copy blocks)
- `generate_push_notifications` - 3-stage pipeline (headlines → body → evaluation)
- `generate_image` - Adobe Firefly/Gemini image generation
- `generate_batch_images` - Bulk image generation
- `generate_image_description` - Vision AI for alt text

**Evaluation Tools:**
- `evaluate_faqs` - Multi-model consensus evaluation
- `evaluate_content` - General content quality assessment
- Multi-model approach (GPT, Gemini, Claude)

**AEM DAM Tools:**
- `aem_upload_asset` / `aem_upload_assets_bulk` - Asset upload
- `aem_dam_asset_download` / `aem_download_asset` - Asset retrieval
- `aem_list_assets` - Folder browsing
- `aem_dam_asset_search` - OData filtering
- `aem_search_assets` - QueryBuilder API

**Adobe Creative Tools:**
- `edit_image` - AI-powered image editing (Firefly/Gemini)
- `get_custom_models` - Custom Firefly models
- `azure_upload_file` - Presigned URL generation for Adobe APIs
- `azure_prepare_adobe_psd_urls` - PSD workflow preparation
- Photoshop API integration tools (PSD manipulation, layer editing, rendering)

**Data & Integration:**
- `scrape_url` - Walmart.com page scraping
- `workfront_get_metadata` - Project metadata retrieval
- `seo_mcp_bigquery` - Analytics queries
- Prompt versioning tools (`seed_prompt_to_gcs`, etc.)

---

## Camunda 8 Orchestration Opportunities

### 1. FAQ Generation & Approval Workflow 🌟

**Current Flow:** Linear - scrape → generate → evaluate → display  
**Camunda Enhancement:** Add human approval gate for quality control

**BPMN Process:**
```
[Start] 
  → [Service Task: Scrape Page URL] 
  → [Service Task: Generate FAQs] 
  → [Service Task: Multi-Model Evaluation]
  → [DMN: Quality Gate Decision]
      ├─ Score >= 8.0 → [Auto-Approve]
      └─ Score < 8.0 → [User Task: Review FAQs in Tasklist]
          ├─ Approve → [Service Task: Publish to CMS]
          ├─ Reject → [Service Task: Regenerate with Feedback]
          └─ Edit → [User Task: Manual Editing] → [Publish]
  → [Service Task: Upload to AEM]
  → [End]
```

**Human-in-the-Loop Value:**
- Content quality review before publishing
- Brand voice alignment check
- Legal/compliance review for sensitive topics

**DMN Decision Table:**
| Evaluation Score | Model Consensus | Word Count | Action |
|-----------------|----------------|------------|--------|
| >= 8.5 | approved | >= 50 | Auto-Approve |
| >= 7.0, < 8.5 | approved | >= 50 | Human Review |
| < 7.0 | - | - | Auto-Reject |
| - | needs_revision | - | Regenerate |

**Tasklist Integration:**
- Assign to Content Reviewer role
- Display generated FAQs with evaluation feedback
- Inline editing capability
- Approval/Reject/Edit actions

---

### 2. CRM Push Notification Campaign Workflow 🔥

**Current Flow:** 3-stage pipeline (headlines → body → evaluation)  
**Camunda Enhancement:** Batch processing + A/B test variant generation + approval workflow

**BPMN Process:**
```
[Start: Campaign Brief Input]
  → [Service Task: Scrape Target Page(s)]
  → [Parallel Gateway: Generate Variants]
      ├─ [Generate Variant A - Value/Deal Strategy]
      ├─ [Generate Variant B - FOMO/Urgency Strategy]
      └─ [Generate Variant C - New/Restock Strategy]
  → [Converging Gateway: Collect All Variants]
  → [Service Task: Multi-Model Evaluation for Each]
  → [DMN: Auto-Approve vs Human Review]
      ├─ All variants score >= 8.0 → [User Task: Select Winning Variants]
      └─ Any variant < 8.0 → [User Task: Review & Edit Low-Scoring Variants]
  → [User Task: Schedule Campaign in Tasklist]
      - Set send time
      - Select target audience segments
      - Assign to Marketing Manager
  → [Service Task: Publish to CRM System]
  → [Timer Event: Wait until Send Time]
  → [Service Task: Trigger Campaign]
  → [End]
```

**Human-in-the-Loop Value:**
- Marketing manager approves messaging strategy
- A/B test variant selection
- Campaign timing and audience control
- Compliance review for promotional content

**DMN Decision Table (Variant Auto-Approval):**
| Consensus Verdict | Overall Score | Emoji Count | Has Brand Keywords | Action |
|------------------|---------------|-------------|-------------------|--------|
| approved | >= 8.5 | 1-3 | true | Auto-Approve |
| approved | >= 8.0, < 8.5 | 1-3 | true | Human Review |
| needs_revision | - | - | - | Regenerate |
| approved | - | > 5 | - | Human Review (too many emojis) |

**Parallel Processing Benefits:**
- Generate 3 variants simultaneously (faster)
- Independent evaluation of each variant
- Fault tolerance (if one fails, others continue)

---

### 3. Image Generation & PSD Assembly Pipeline 🎨

**Current Flow:** Generate → Edit → Assemble PSD → Convert → Upload  
**Camunda Enhancement:** Batch processing + error handling + version control

**BPMN Process (Product Image Kit Generation):**
```
[Start: Campaign Requirements]
  → [Service Task: Get Custom Firefly Models]
  → [Service Task: Retrieve Brand Assets from AEM]
  → [Multi-Instance Subprocess: For Each Product SKU]
      ├─ [Service Task: Generate Hero Image - Firefly]
      ├─ [Service Task: Generate Lifestyle Image - Gemini]
      ├─ [Service Task: Edit Images - Apply Brand Colors]
      │   → [Boundary Event: API Timeout]
      │       → [Service Task: Retry with Different Model]
      ├─ [Service Task: Upload Images to Azure Blob]
      ├─ [Service Task: Assemble PSD Template]
      │   → [Boundary Event: Assembly Failed]
      │       → [User Task: Manual PSD Fix in Tasklist]
      ├─ [Service Task: Render PSD to JPEG]
      └─ [Service Task: Generate Alt Text via Vision AI]
  → [Service Task: Bulk Upload All Assets to AEM DAM]
  → [User Task: QA Review in Tasklist]
      - View all generated images
      - Approve or request regeneration
  → [Service Task: Publish to Production DAM]
  → [End]
```

**Camunda Benefits:**
- **Parallel Processing**: Generate images for 100+ SKUs simultaneously
- **Retry Logic**: Automatic retry on Adobe API failures with exponential backoff
- **Error Boundary Events**: Catch PSD assembly failures and route to human
- **Multi-Instance**: Scalable batch processing with progress tracking
- **Visibility**: See which SKU failed in Operate dashboard

**Human-in-the-Loop Value:**
- QA review of generated images before publishing
- Manual fixes for complex PSD assembly issues
- Brand consistency verification
- Legal approval for product claims in images

**DMN Decision (Auto-Retry Strategy):**
| Error Type | Attempt Count | Service | Action |
|-----------|---------------|---------|--------|
| Timeout | < 3 | Adobe Firefly | Retry with Gemini |
| Invalid Base64 | 1 | Any | Strip data URI prefix, retry |
| Request Expired | 1 | Adobe | Re-upload to Azure, retry |
| Rate Limit | < 5 | Any | Wait 30s, retry |
| Any | >= 3 | Any | Human Task |

---

### 4. Asset Evaluation & Quality Control Workflow 📊

**Current Flow:** Upload → Evaluate → Display results  
**Camunda Enhancement:** Batch evaluation + approval routing + compliance checks

**BPMN Process:**
```
[Start: Asset Folder Selected]
  → [Service Task: List Assets from AEM Folder]
  → [Multi-Instance Subprocess: For Each Asset]
      ├─ [Service Task: Download Asset from AEM]
      ├─ [Service Task: Generate Image Description]
      ├─ [Service Task: Evaluate Content Quality]
      │   → Multi-model evaluation (GPT, Gemini, Claude)
      ├─ [DMN: Quality Threshold Check]
      │     ├─ Score >= 8.0 → Mark as Approved
      │     ├─ Score 6.0-7.9 → Mark for Review
      │     └─ Score < 6.0 → Mark as Rejected
      └─ [Service Task: Update Asset Metadata in AEM]
  → [Parallel Gateway: Route by Quality]
      ├─ [User Task: Review Medium-Quality Assets]
      ├─ [User Task: Re-generate Low-Quality Assets]
      └─ [Service Task: Auto-Publish High-Quality Assets]
  → [End]
```

**Human-in-the-Loop Value:**
- Manual review of borderline quality assets
- Subjective brand alignment checks
- Compliance verification (no inappropriate content)

**DMN Decision (Quality Routing):**
| Quality Score | AI Confidence | Asset Type | Routing |
|--------------|---------------|------------|---------|
| >= 8.0 | high | any | Auto-Approve |
| 6.0-7.9 | high | hero image | Human Review |
| 6.0-7.9 | low | any | Human Review |
| < 6.0 | any | any | Reject & Regenerate |

---

### 5. Content Production End-to-End Workflow 🚀

**The "Big Kahuna" - Full Creative Asset Production Pipeline**

**BPMN Process (Walmart Campaign Launch):**
```
[Start: Workfront Project Created]
  → [Service Task: Get Project Metadata from Workfront]
      - Campaign theme
      - Target URLs
      - Asset requirements
      - Deadline
  → [Service Task: Scrape All Target Pages]
  → [Parallel Gateway: Multi-Track Production]
      ├─ [Track A: SEO Content]
      │   ├─ Generate FAQs
      │   ├─ Generate Meta Titles/Descriptions
      │   ├─ Evaluate Content
      │   └─ [User Task: SEO Approval]
      │
      ├─ [Track B: Push Notifications]
      │   ├─ Generate Headlines (3 variants)
      │   ├─ Generate Body Copy
      │   ├─ Evaluate Notifications
      │   └─ [User Task: Marketing Approval]
      │
      ├─ [Track C: Image Assets]
      │   ├─ Generate Product Images
      │   ├─ Assemble PSD Kits
      │   ├─ Generate Alt Text
      │   └─ [User Task: Creative Director Approval]
      │
      └─ [Track D: Analytics Setup]
          ├─ Query BigQuery for Historical Performance
          ├─ Generate Baseline Metrics
          └─ Set up Tracking
  → [Converging Gateway: All Tracks Complete]
  → [User Task: Final Campaign Review in Tasklist]
      - Assign to Campaign Manager
      - Review all assets together
      - Check cross-channel consistency
      - Form with approve/edit/reject options
  → [Decision Gateway: Launch Decision]
      ├─ Approved → [Service Task: Publish All Assets to Production]
      ├─ Needs Edits → [Loop Back to Edit Tasks]
      └─ Rejected → [Service Task: Notify Stakeholders] → [End]
  → [Service Task: Upload to AEM DAM]
  → [Service Task: Update Workfront Project Status]
  → [Service Task: Send Launch Notification]
  → [Timer Event: Wait for Campaign End Date]
  → [Service Task: Query BigQuery for Results]
  → [Service Task: Generate Performance Report]
  → [User Task: Review Campaign Results]
  → [End]
```

**This Workflow Showcases All Camunda 8 Features:**

1. **BPMN Orchestration**
   - Multi-track parallel execution
   - Complex decision gateways
   - Timer events for scheduling
   - Error boundary events
   - Multi-instance subprocesses

2. **Human Tasks via Tasklist**
   - SEO approval task
   - Marketing approval task
   - Creative director approval task
   - Final campaign review task
   - Results review task

3. **DMN Decisions**
   - Auto-approve high-quality content
   - Route to appropriate approver based on content type
   - Retry strategy for API failures
   - Quality threshold decisions

4. **Resilience & Fault Tolerance**
   - Retry logic for external API calls
   - Boundary error events for Adobe/Azure failures
   - Compensation activities (rollback if launch fails)
   - Saga pattern for distributed transactions

5. **Integration Points**
   - Workfront (project metadata)
   - MCP Server (40+ tools)
   - AEM DAM (asset storage)
   - BigQuery (analytics)
   - CRM system (push notifications)

6. **Visibility & Monitoring**
   - Track progress in Operate dashboard
   - See which track is blocking completion
   - Audit trail of all decisions
   - Performance metrics per subprocess

---

## Where Camunda 8 Shines

### 1. **Long-Running Workflows with External Dependencies**

**Example:** Image generation that depends on Adobe Firefly (which can take 30-60 seconds per image)

**Without Camunda:**
- HTTP timeout issues
- Lost state if server crashes
- No retry logic
- Manual tracking of progress

**With Camunda:**
- Zeebe persists workflow state
- Automatic retry on timeout
- Resume from last checkpoint after crash
- Progress visible in Operate

---

### 2. **Human-in-the-Loop at Scale**

**Example:** 500 product images need creative director approval before publishing

**Without Camunda:**
- Manual email notifications
- No tracking of who approved what
- No deadline enforcement
- Hard to see bottlenecks

**With Camunda Tasklist:**
- Tasks automatically assigned to role/user
- Deadline tracking and escalation
- Audit trail of approvals
- Batch approval capability
- Filter/search tasks by campaign

---

### 3. **Batch Processing with Fault Tolerance**

**Example:** Generate images for 1000 SKUs

**Without Camunda:**
- All-or-nothing processing
- If one fails, whole batch fails
- Hard to track which ones completed
- No partial retry

**With Camunda Multi-Instance:**
- Each SKU processed independently
- Failed SKUs can be retried individually
- Progress tracking (750/1000 complete)
- Continue processing others if one fails

---

### 4. **Complex Decision Logic**

**Example:** Route content to different approvers based on quality score, content type, and campaign sensitivity

**Without Camunda:**
- Decision logic scattered in code
- Hard to change rules
- No visibility into decision reasoning

**With Camunda DMN:**
- Decision tables in visual format
- Business users can update rules
- Test decision tables independently
- Audit trail shows which rule was applied

---

### 5. **Integration Orchestration**

**Example:** Coordinate between Workfront, MCP Server, Adobe APIs, AEM DAM, and BigQuery

**Without Camunda:**
- Point-to-point integrations
- Hard to track end-to-end flow
- Retry logic duplicated everywhere
- No central monitoring

**With Camunda:**
- Single orchestration layer
- Unified retry/error handling
- End-to-end visibility
- Saga pattern for consistency

---

## Camunda 8 Architecture for CBS

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CBS UI (Next.js)                        │
│  - FAQ Generation Page                                      │
│  - Push Notifications Page                                  │
│  - Image Generation Page                                    │
│  - Evaluation Page                                          │
│  - Tasklist Embedded Component (Human Tasks)               │
└────────────┬────────────────────────────────────────────────┘
             │
             │ REST API / WebSocket
             │
┌────────────▼────────────────────────────────────────────────┐
│              Camunda 8 Platform (Self-Managed)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Zeebe   │  │ Operate  │  │Tasklist  │  │Connectors│  │
│  │ :26500   │  │  :8081   │  │  :8082   │  │  :8085   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │             │             │             │          │
│       └─────────────┴─────────────┴─────────────┘          │
│                          │                                  │
│                   ┌──────▼──────┐                          │
│                   │Elasticsearch│                          │
│                   └─────────────┘                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ Job Workers (Python/Node.js)
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              CBS Content MCP Server Workers                 │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Worker 1: Content Generation                         │  │
│  │  - generate_faqs                                     │  │
│  │  - generate_content                                  │  │
│  │  - generate_push_notifications                       │  │
│  │  - scrape_url                                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Worker 2: Content Evaluation                         │  │
│  │  - evaluate_faqs                                     │  │
│  │  - evaluate_content                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Worker 3: Image Operations                           │  │
│  │  - generate_image                                    │  │
│  │  - edit_image                                        │  │
│  │  - generate_batch_images                             │  │
│  │  - azure_upload_file                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Worker 4: AEM DAM Operations                         │  │
│  │  - aem_upload_asset                                  │  │
│  │  - aem_dam_asset_download                            │  │
│  │  - aem_list_assets                                   │  │
│  │  - aem_dam_asset_search                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Worker 5: External Integrations                      │  │
│  │  - workfront_get_metadata                            │  │
│  │  - seo_mcp_bigquery                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────┬───────────────────────────────────────────────┘
              │
              │ Direct API Calls
              │
┌─────────────▼───────────────────────────────────────────────┐
│                  External Services                          │
│  - Adobe Firefly API                                        │
│  - Google Gemini API                                        │
│  - OpenAI API                                               │
│  - Anthropic Claude API                                     │
│  - AEM DAM                                                  │
│  - Azure Blob Storage                                       │
│  - Workfront API                                            │
│  - BigQuery                                                 │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**CBS UI:**
- Trigger workflows via REST API calls to Zeebe Gateway
- Embed Tasklist for human task management
- Display workflow status from Operate API
- Provide campaign configuration UI

**Zeebe (Workflow Engine):**
- Execute BPMN workflows
- Manage workflow state persistence
- Distribute jobs to workers
- Handle retries and timeouts

**Operate (Monitoring Dashboard):**
- Visualize running workflows
- Debug failed workflows
- View workflow history
- Performance metrics

**Tasklist (Human Task Management):**
- Assign tasks to users/roles
- Task forms for data entry
- Approval workflows
- Deadline tracking

**Python Workers:**
- Subscribe to Zeebe job types
- Call MCP Server tools
- Handle errors and return results
- Implement retry logic

**MCP Server:**
- Provide 40+ tools as REST API
- Handle LLM orchestration
- Manage external service calls
- Activity logging to PostgreSQL

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2) ✅ DONE
- [x] Set up Camunda 8 locally
- [x] Deploy basic "Hello World" workflow
- [x] Create simple Python worker

### Phase 2: Single Workflow POC (Week 3-4)
**Goal:** Demonstrate FAQ Generation with Human Approval

**Deliverables:**
1. BPMN workflow: FAQ Generation & Approval
2. DMN table: Quality gate decision
3. Python worker: Call `scrape_url`, `generate_faqs`, `evaluate_faqs`
4. Tasklist integration: Review task with approval form
5. Demo video: End-to-end flow

**Success Metrics:**
- Workflow completes successfully
- Human task appears in Tasklist
- Approval decision routes correctly
- All steps visible in Operate

### Phase 3: Multi-Workflow Integration (Week 5-8)
**Goal:** Add Push Notifications and Image Generation workflows

**Deliverables:**
1. Push Notification workflow with A/B variants
2. Image Generation workflow with batch processing
3. Shared DMN decision tables
4. Worker pool (3-5 workers for different task types)
5. CBS UI integration: Trigger workflows from existing pages

**Success Metrics:**
- 3 workflows running in production
- Parallel processing working (3+ simultaneous workflows)
- Human tasks integrated into existing CBS UI
- Error handling and retry working

### Phase 4: Advanced Features (Week 9-12)
**Goal:** Full production-grade orchestration

**Deliverables:**
1. End-to-End campaign workflow
2. Multi-instance batch processing (100+ SKUs)
3. Timer events for scheduled campaigns
4. Saga pattern for distributed transactions
5. Performance monitoring dashboard
6. User documentation and training

**Success Metrics:**
- Process 100+ images in single workflow
- Timer events trigger correctly
- Compensation activities work on failure
- 95%+ workflow completion rate
- < 5min average approval task completion

---

## Demo Scenarios for Stakeholders

### Demo 1: "The Magic of Human-in-the-Loop"
**Scenario:** FAQ Generation with Quality Control

**Story:**
"Let's generate FAQs for the Valentine's Day Electronics page. Watch as Camunda orchestrates the scraping, generation, and evaluation... and now it's waiting for Karen from Content Team to review because the quality score was 7.8. She can approve, reject, or edit inline. Once she clicks approve, it automatically publishes to AEM. No emails, no spreadsheets, just a task in her queue."

**Demo Steps:**
1. Show CBS UI - click "Generate FAQs"
2. Show Operate dashboard - workflow progressing
3. Show evaluation service task completing
4. Show DMN decision routing to human task
5. Switch to Tasklist - Karen's review task
6. Show FAQ content with evaluation feedback
7. Karen clicks "Approve"
8. Switch back to Operate - workflow continues to publish
9. Show AEM DAM - FAQs are there

**Wow Factor:** Real-time visibility + human control

---

### Demo 2: "Batch Processing at Scale"
**Scenario:** Generate 100 Product Images for Holiday Campaign

**Story:**
"We need 100 product hero images for Black Friday. In the old world, this would take days of manual work. Watch Camunda process all 100 in parallel. See how it handles failures gracefully - if Adobe Firefly times out, it automatically retries with Gemini. And the creative director only needs to review the 5 images that scored below 8.0."

**Demo Steps:**
1. Show CBS UI - upload CSV of 100 SKUs
2. Show Operate - multi-instance subprocess running
3. Show progress: 45/100 completed
4. Show failed instance in Operate
5. Show automatic retry with different model
6. Show successful completion
7. Show Tasklist - 5 review tasks for low-scoring images
8. Show bulk approval in Tasklist
9. Show all 100 images in AEM DAM

**Wow Factor:** Parallel processing + automatic retry + selective human review

---

### Demo 3: "The Full Monty - End-to-End Campaign"
**Scenario:** Valentine's Day Campaign Launch

**Story:**
"Let's launch the Valentine's Day campaign. One click starts the entire pipeline: FAQs, push notifications, and product images - all in parallel. The SEO team reviews FAQs, marketing reviews push notifications, and the creative director reviews images. Everyone works in their Tasklist queue. Once all three approve, the campaign manager gets a final review task to launch everything together. After launch, Camunda waits for the campaign end date, then automatically generates a performance report from BigQuery."

**Demo Steps:**
1. Show Workfront project with campaign requirements
2. Show CBS UI - click "Launch Campaign"
3. Show Operate - 3 parallel tracks running
4. Show multiple Tasklist users with different tasks
5. Show Track A (SEO) completing first
6. Show Track B (Marketing) in progress
7. Show Track C (Creative) waiting for approval
8. Show converging gateway waiting for all tracks
9. Show campaign manager's final review task
10. Show timer event scheduled for campaign end
11. Fast-forward time (for demo)
12. Show automated BigQuery report generation
13. Show results dashboard

**Wow Factor:** Multi-team coordination + automated scheduling + analytics integration

---

## Technical Considerations

### Worker Implementation Strategy

**Option A: Monolithic Worker (Simpler for POC)**
- One Python worker handles all MCP tool calls
- Switch based on job type
- Easier to debug
- Good for MVP

**Option B: Specialized Workers (Better for Production)**
- Content Worker (FAQs, push notifications)
- Image Worker (Firefly, Gemini, editing)
- AEM Worker (upload, download, search)
- Evaluation Worker (multi-model consensus)
- Integration Worker (Workfront, BigQuery)
- Better isolation and scalability
- Independent deployment

**Recommendation:** Start with Option A, migrate to Option B in Phase 3

---

### Error Handling Patterns

**1. Retry with Backoff**
```
Service Task: Generate Image via Firefly
  → Error Boundary Event: Timeout
      → Timer Event: Wait 10s
      → Retry: Generate Image
```

**2. Fallback to Alternative Service**
```
Service Task: Generate Image via Firefly
  → Error Boundary Event: Rate Limited
      → Service Task: Generate Image via Gemini
```

**3. Human Intervention**
```
Service Task: Assemble PSD
  → Error Boundary Event: Assembly Failed
      → User Task: Manual PSD Fix
          → Service Task: Continue with Manual PSD
```

**4. Compensation (Rollback)**
```
Service Task: Publish to Production
  → Error Event: Publish Failed
      → Compensation Handler: Delete from Staging
      → Compensation Handler: Revert AEM Metadata
      → Compensation Handler: Send Rollback Notification
```

---

### Performance Optimization

**1. Use Camunda Connectors for Simple HTTP Calls**
- Pre-built HTTP REST connector
- No custom worker code needed
- Good for simple MCP tool calls

**2. Batch Variable Updates**
- Update workflow variables in batch
- Reduces Zeebe Gateway calls
- Improves throughput

**3. Worker Pooling**
- Run 3-5 worker instances per task type
- Horizontal scaling
- Load balancing by Zeebe

**4. Async Patterns**
- Use async Python workers (asyncio)
- Non-blocking I/O
- Better resource utilization

---

## Integration with CBS UI

### Approach 1: Embedded Tasklist (Recommended)
Embed Camunda Tasklist directly into CBS UI using iframe or API

**Pros:**
- Users stay in CBS UI
- Unified experience
- SSO integration

**Implementation:**
```jsx
// In CBS UI component
<TasklistEmbed 
  workflowId={workflowId}
  userId={currentUser.id}
  apiUrl="http://localhost:8082"
/>
```

### Approach 2: Custom Task UI
Build custom task forms in CBS UI, communicate with Tasklist API

**Pros:**
- Full design control
- Match CBS design system exactly
- Custom validation

**Cons:**
- More development effort

### Approach 3: Hybrid
Use embedded Tasklist for most tasks, custom forms for special workflows

**Best of Both Worlds**

---

## Decision Matrix: Which Workflows to Orchestrate?

| Workflow | Camunda Value | Priority | Complexity |
|----------|--------------|----------|------------|
| FAQ Generation & Approval | High (human approval) | High | Low |
| Push Notification Campaigns | High (multi-variant, scheduling) | High | Medium |
| Image Generation Batch | Very High (scale, retry) | High | Medium |
| PSD Assembly Pipeline | High (error handling) | Medium | High |
| Asset Evaluation | Medium (batch processing) | Medium | Low |
| End-to-End Campaign | Very High (coordination) | High | High |
| Single Image Edit | Low (simple API call) | Low | Low |
| Asset Upload | Low (simple operation) | Low | Low |
| Workfront Sync | Medium (polling, state) | Low | Medium |

**Start With:** FAQ Generation (quick win) → Push Notifications (business impact) → Image Batch (technical showcase)

---

## Risks & Mitigations

### Risk 1: Learning Curve
**Impact:** Team unfamiliar with BPMN/Camunda  
**Mitigation:**
- Start with simple workflows
- Training sessions on BPMN basics
- Use Camunda Modeler templates
- Pair programming for first workers

### Risk 2: Performance Overhead
**Impact:** Zeebe adds latency compared to direct API calls  
**Mitigation:**
- Use Camunda for long-running workflows (> 1 min)
- Keep synchronous, fast operations outside Camunda
- Optimize worker polling intervals
- Use async patterns

### Risk 3: External Service Failures
**Impact:** Adobe/AEM/OpenAI APIs go down  
**Mitigation:**
- Implement retry boundaries with exponential backoff
- Fallback to alternative services (Firefly → Gemini)
- Clear error messages in Tasklist
- Manual intervention tasks

### Risk 4: State Management
**Impact:** Large workflow variables (image base64) hit size limits  
**Mitigation:**
- Store large data in Azure Blob, pass URLs
- Use workflow variables for metadata only
- Clean up old workflow instances
- Archive completed workflows

---

## Success Metrics

### Technical Metrics
- Workflow completion rate: > 95%
- Average workflow duration: < 5 minutes for standard flows
- Worker availability: > 99%
- Error rate: < 5%
- Retry success rate: > 80%

### Business Metrics
- Time-to-publish reduced by 50%
- Human approval SLA: < 2 hours
- Batch processing: 100+ assets in single workflow
- Campaign launch coordination: 3+ teams synchronized
- Audit compliance: 100% tracked

### User Metrics
- Task completion time: < 5 minutes average
- User satisfaction with Tasklist: > 4/5
- Number of manual escalations: < 10%
- Self-service workflow trigger rate: > 80%

---

## Conclusion

Camunda 8 brings **enterprise-grade orchestration** to the CBS creative workflows. The key differentiators are:

1. **Visibility**: See every workflow step in Operate dashboard
2. **Human Oversight**: Strategic approval gates via Tasklist
3. **Resilience**: Automatic retry and error handling
4. **Scale**: Parallel batch processing for 100+ assets
5. **Compliance**: Audit trails for all decisions
6. **Flexibility**: Business users can modify DMN tables

**The POC should focus on demonstrating these 3 scenarios:**
1. FAQ Generation with Human Approval (simplest)
2. Push Notification Campaign with A/B Variants (business impact)
3. Batch Image Generation with Error Handling (technical depth)

**Next Steps:**
1. Refine BPMN diagrams in Camunda Modeler
2. Build Python workers for core MCP tools
3. Create DMN tables for quality gates
4. Integrate Tasklist into CBS UI
5. Record demo videos for stakeholders

---

**Document Version:** 1.0  
**Last Updated:** March 9, 2026  
**Author:** AI Architect  
**Reviewers:** CBS Engineering Team
