# Fix BPMN Diagram Visualization

## Problem
The BPMN files execute correctly but show blank diagrams in Operate because they're missing `<bpmndi:BPMNShape>` and `<bpmndi:BPMNEdge>` coordinates.

## Solution: Use bpmn.io Online

### Step 1: Open bpmn.io
Go to: **https://demo.bpmn.io/new**

### Step 2: Load Your BPMN
1. Click the **XML** icon (top right corner, looks like `</>`)
2. Copy the entire contents of your BPMN file
3. Paste into the XML editor
4. Click back to the diagram view (click the diagram icon)

### Step 3: Auto-Layout
The diagram will automatically render with proper coordinates!

### Step 4: Download
1. Click **File → Download File** (or the download icon)
2. Save as `mds-evaluation-workflow.bpmn`
3. Replace your local file

### Step 5: Re-deploy
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC
python3 deploy_workflow.py
```

### Step 6: View in Operate
Refresh http://localhost:8081 - the diagram will now appear!

---

## Alternative: Manual Fix (Advanced)

If you prefer to manually add coordinates, here's the pattern:

```xml
<bpmndi:BPMNDiagram id="BPMNDiagram_1">
  <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="mds-evaluation-workflow">
    
    <!-- Start Event -->
    <bpmndi:BPMNShape id="Shape_StartEvent_Upload" bpmnElement="StartEvent_Upload">
      <dc:Bounds x="180" y="120" width="36" height="36" />
      <bpmndi:BPMNLabel>
        <dc:Bounds x="156" y="163" width="84" height="27" />
      </bpmndi:BPMNLabel>
    </bpmndi:BPMNShape>
    
    <!-- Task 1 -->
    <bpmndi:BPMNShape id="Shape_Task_ValidateAssets" bpmnElement="Task_ValidateAssets">
      <dc:Bounds x="270" y="98" width="100" height="80" />
    </bpmndi:BPMNShape>
    
    <!-- Flow 1 -->
    <bpmndi:BPMNEdge id="Edge_Flow_ToValidate" bpmnElement="Flow_ToValidate">
      <di:waypoint x="216" y="138" />
      <di:waypoint x="270" y="138" />
    </bpmndi:BPMNEdge>
    
    <!-- Repeat for all elements... -->
    
  </bpmndi:BPMNPlane>
</bpmndi:BPMNDiagram>
```

But this is tedious - use bpmn.io instead!

---

## Files to Fix
- `workflows/mds-evaluation-workflow.bpmn`
- `workflows/push-notification-workflow.bpmn`

Both need diagram coordinates added.
