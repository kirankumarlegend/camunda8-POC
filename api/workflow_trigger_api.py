"""
REST API to trigger Camunda workflows via HTTP requests.
This allows external systems (like campaign managers) to start workflows.

Usage:
    python3 api/workflow_trigger_api.py

Then trigger workflows via:
    POST http://localhost:5000/api/workflows/push-notification
"""
import asyncio
import logging
from typing import Dict, List
from flask import Flask, request, jsonify
from pyzeebe import ZeebeClient, create_insecure_channel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ZEEBE_GATEWAY_ADDRESS = "localhost:26500"
WORKFLOW_BPMN_PROCESS_ID = "push-notification-workflow"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Zeebe Client Helper
# ---------------------------------------------------------------------------
async def start_workflow_instance(variables: Dict) -> Dict:
    """Start a new workflow instance in Zeebe."""
    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    client = ZeebeClient(channel)
    
    try:
        # Deploy workflow (idempotent)
        await client.deploy_resource("workflows/push-notification-workflow.bpmn")
        logger.info("✅ Workflow deployed")
        
        # Start instance
        workflow_instance = await client.run_process(
            bpmn_process_id=WORKFLOW_BPMN_PROCESS_ID,
            variables=variables
        )
        
        logger.info(f"✅ Workflow started: {workflow_instance}")
        
        return {
            "status": "success",
            "workflow_instance_key": str(workflow_instance),
            "bpmn_process_id": WORKFLOW_BPMN_PROCESS_ID,
            "variables": variables
        }
        
    except Exception as e:
        logger.error(f"❌ Workflow start failed: {e}", exc_info=True)
        raise

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "workflow-trigger-api"})


@app.route('/api/workflows/push-notification', methods=['POST'])
def trigger_push_notification_workflow():
    """
    Trigger push notification generation workflow.
    
    Request Body:
    {
        "workfrontProjectId": "69b18b90000050500e6247facdd92998",
        "pageUrl": "https://www.walmart.com/shop/deals/clearance",
        "messagingStrategy": "all",  // optional: "all", "value", "fomo", "newness"
        "emojiUsage": "medium",      // optional: "none", "light", "medium", "heavy"
        "numNotifications": 10,      // optional: default 10
        "modelName": "gpt-4.1-mini", // optional: default gpt-4.1-mini
        "recipientEmails": [         // optional: default team emails
            "user1@walmart.com",
            "user2@walmart.com"
        ]
    }
    
    Response:
    {
        "status": "success",
        "workflow_instance_key": "2251799813722087",
        "bpmn_process_id": "push-notification-workflow",
        "monitor_urls": {
            "operate": "http://localhost:8081",
            "tasklist": "http://localhost:8082"
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("workfrontProjectId"):
            return jsonify({
                "status": "error",
                "message": "workfrontProjectId is required"
            }), 400
        
        # Prepare workflow variables with defaults
        variables = {
            "workfrontProjectId": data["workfrontProjectId"],
            "pageUrl": data.get("pageUrl", "https://www.walmart.com/shop/deals/clearance"),
            "messagingStrategy": data.get("messagingStrategy", "all"),
            "emojiUsage": data.get("emojiUsage", "medium"),
            "numNotifications": data.get("numNotifications", 10),
            "modelName": data.get("modelName", "gpt-4.1-mini"),
            "recipientEmails": data.get("recipientEmails", [
                "anusha.naredla@walmart.com",
                "Nagateja.Chadalawada@walmart.com",
                "Manikandan.Narayanan@walmart.com"
            ]),
            "triggeredBy": data.get("triggeredBy", "api"),
            "triggeredAt": data.get("triggeredAt", "")
        }
        
        # Start workflow asynchronously
        result = asyncio.run(start_workflow_instance(variables))
        
        # Add monitoring URLs
        result["monitor_urls"] = {
            "operate": "http://localhost:8081",
            "tasklist": "http://localhost:8082"
        }
        
        return jsonify(result), 201
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error triggering workflow: {e}\n{error_details}")
        return jsonify({"status": "error", "message": str(e), "details": error_details}), 500


@app.route('/api/workflows/mds-evaluation', methods=['POST'])
def trigger_mds_evaluation_workflow():
    """
    Trigger MDS asset evaluation workflow.
    
    Request Body:
    {
        "assetFilePaths": [
            "/path/to/asset1.jpg",
            "/path/to/asset2.jpg"
        ],
        "aemFolderPath": "/content/dam/library/evaluation",  // optional
        "projectId": "7502741",                              // optional
        "uploadedBy": "user@walmart.com"                     // optional
    }
    """
    async def start_mds_workflow(variables):
        channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
        client = ZeebeClient(channel)
        
        await client.deploy_resource("workflows/mds-evaluation-workflow.bpmn")
        workflow_instance = await client.run_process(
            bpmn_process_id="mds-evaluation-workflow",
            variables=variables
        )
        return workflow_instance
    
    try:
        data = request.get_json()
        
        if not data.get("assetFilePaths"):
            return jsonify({
                "status": "error",
                "message": "assetFilePaths is required"
            }), 400
        
        variables = {
            "assetFilePaths": data["assetFilePaths"],
            "assetCount": len(data["assetFilePaths"]),
            "aemFolderPath": data.get("aemFolderPath", "/content/dam/library/evaluation"),
            "projectId": data.get("projectId", "unknown"),
            "uploadedBy": data.get("uploadedBy", "api")
        }
        
        # Start workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        workflow_instance = loop.run_until_complete(start_mds_workflow(variables))
        loop.close()
        
        return jsonify({
            "status": "success",
            "workflow_instance_key": str(workflow_instance),
            "bpmn_process_id": "mds-evaluation-workflow",
            "monitor_urls": {
                "operate": "http://localhost:8081",
                "tasklist": "http://localhost:8082"
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error triggering MDS workflow: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    logger.info("🚀 Starting Workflow Trigger API")
    logger.info(f"   Zeebe Gateway: {ZEEBE_GATEWAY_ADDRESS}")
    logger.info(f"   API Server: http://localhost:5000")
    logger.info("")
    logger.info("📋 Available Endpoints:")
    logger.info("   POST /api/workflows/push-notification")
    logger.info("   POST /api/workflows/mds-evaluation")
    logger.info("   GET  /health")
    logger.info("")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
