"""
Workflow Trigger & Callback API for Camunda 8
==============================================
Exposes REST endpoints so external systems (image upload tools, CI pipelines,
MCP servers) can start Camunda workflows and receive MDS callbacks.

Endpoints
---------
GET  /health                              – liveness probe
POST /api/workflows/mds-evaluation        – start MDS evaluation workflow
POST /api/workflows/push-notification     – start push-notification workflow
POST /api/eval/callback                   – MDS async callback (resumes workflow)

Run locally
-----------
    pip install flask pyzeebe
    python api/workflow_trigger_api.py

Deploy (Docker)
---------------
    docker build -t camunda-api .
    docker run -p 5000:5000 \\
      -e ZEEBE_GATEWAY_ADDRESS=<host>:26500 camunda-api

Environment variables
---------------------
    ZEEBE_GATEWAY_ADDRESS   default: localhost:26500
    API_PORT                default: 5000
    MCP_SERVER_URL          base URL shown in monitor_urls
"""
import asyncio
import logging
import os
import uuid
import time
from typing import Dict

from flask import Flask, request, jsonify
from pyzeebe import ZeebeClient, create_insecure_channel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ZEEBE_GATEWAY_ADDRESS = os.getenv("ZEEBE_GATEWAY_ADDRESS", "localhost:26500")
API_PORT              = int(os.getenv("API_PORT", 5000))
MCP_SERVER_URL        = os.getenv("MCP_SERVER_URL", f"http://localhost:{API_PORT}")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_zeebe_client() -> ZeebeClient:
    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    return ZeebeClient(channel)


async def _start_process(bpmn_id: str, bpmn_file: str, variables: Dict) -> str:
    """Deploy (idempotent) and start a workflow instance. Returns instance key."""
    client = _get_zeebe_client()
    await client.deploy_resource(bpmn_file)
    instance_key = await client.run_process(bpmn_process_id=bpmn_id, variables=variables)
    return str(instance_key)


async def _publish_message(name: str, correlation_key: str, variables: Dict):
    """Publish a Zeebe message to resume a waiting workflow instance."""
    client = _get_zeebe_client()
    await client.publish_message(
        name=name,
        correlation_key=correlation_key,
        variables=variables,
        time_to_live_in_milliseconds=60_000,
    )


def _monitor_urls() -> Dict:
    return {
        "operate":  "http://localhost:8081",
        "tasklist": "http://localhost:8082",
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "camunda-workflow-api",
        "zeebe": ZEEBE_GATEWAY_ADDRESS,
    })


# ---------------------------------------------------------------------------
# MDS Evaluation Workflow  –  POST /api/workflows/mds-evaluation
# ---------------------------------------------------------------------------
@app.route("/api/workflows/mds-evaluation", methods=["POST"])
def trigger_mds_evaluation():
    """
    Start the MDS Asset Evaluation workflow.

    Request body (JSON)
    -------------------
    {
        "assetFiles": ["7502741-5417-NULL-PMAX-...", ...],   # REQUIRED
        "aemFolderPath": "/content/dam/cbs/evaluation/...",  # optional
        "projectId": "7502741",                              # optional
        "uploadedBy": "user@example.com"                     # optional
    }

    Response 201
    ------------
    {
        "status": "success",
        "workflow_instance_key": "2251799813722087",
        "cbsJobId": "<uuid>",
        "bpmn_process_id": "mds-evaluation-workflow",
        "monitor_urls": { "operate": "...", "tasklist": "..." }
    }
    """
    data = request.get_json(silent=True) or {}

    asset_files = data.get("assetFiles", [])
    if not asset_files:
        return jsonify({"status": "error",
                        "message": "assetFiles (list of filenames) is required"}), 400

    # Infer projectId from first filename if not supplied
    first_file = asset_files[0] if asset_files else ""
    inferred_project = first_file.split("-")[0] if first_file else "unknown"

    variables = {
        "assetFiles":    asset_files,
        "assetCount":    len(asset_files),
        "aemFolderPath": data.get("aemFolderPath",
                                  f"/content/dam/cbs/evaluation/project-{inferred_project}/"),
        "projectId":     data.get("projectId", inferred_project),
        "uploadedBy":    data.get("uploadedBy", "api"),
    }

    try:
        instance_key = asyncio.run(_start_process(
            bpmn_id="mds-evaluation-workflow",
            bpmn_file="workflows/mds-evaluation-workflow.bpmn",
            variables=variables,
        ))
        logger.info("✅ MDS workflow started – instance=%s assets=%d",
                    instance_key, len(asset_files))
        return jsonify({
            "status": "success",
            "workflow_instance_key": instance_key,
            "bpmn_process_id": "mds-evaluation-workflow",
            "asset_count": len(asset_files),
            "monitor_urls": _monitor_urls(),
        }), 201

    except Exception as exc:
        logger.error("❌ Failed to start MDS workflow: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# MDS Callback  –  POST /api/eval/callback
# ---------------------------------------------------------------------------
@app.route("/api/eval/callback", methods=["POST"])
def mds_callback():
    """
    MDS calls this webhook when an async evaluation job is complete.

    MDS posts something like:
    {
        "job_id": "d6542ffc_e94a_...",
        "status": "completed",
        "output_path": "gs://cbs-evaluation/output/<cbsJobId>/<mdsJobId>/..."
    }

    This handler:
    1. Extracts the mds_job_id
    2. Looks up the cbs_job_id from Postgres (via Util Service — mocked here)
    3. Publishes a Zeebe message "mds-callback" with correlationKey = cbsJobId
       → this resumes the workflow waiting at Event_WaitMDSCallback
    """
    body = request.get_json(silent=True) or {}
    mds_job_id = body.get("job_id") or body.get("mds_job_id")

    if not mds_job_id:
        return jsonify({"status": "error",
                        "message": "job_id is required in callback body"}), 400

    logger.info("📥 MDS callback received – mdsJobId=%s", mds_job_id)

    # ── Step 1: Look up cbs_job_id from Postgres via Util Service ────────────
    # In production:
    #   rows = util_client.postgres_query("eval_jobs", {"mds_job_id": mds_job_id})
    #   cbs_job_id = rows[0]["cbs_job_id"]
    #
    # For the POC we accept cbs_job_id directly in the callback body as a fallback:
    cbs_job_id = body.get("cbs_job_id")
    if not cbs_job_id:
        logger.warning("cbs_job_id not in callback body – Util Service lookup would "
                       "resolve this in production. Using mds_job_id as fallback.")
        cbs_job_id = mds_job_id   # POC fallback

    # ── Step 2: Publish Zeebe message to resume the workflow ─────────────────
    try:
        asyncio.run(_publish_message(
            name="mds-callback",
            correlation_key=cbs_job_id,
            variables={
                "mdsJobId":      mds_job_id,
                "mdsStatus":     body.get("status", "completed"),
                "gcsOutputPath": body.get("output_path", ""),
            },
        ))
        logger.info("✅ Zeebe message published – name=mds-callback correlationKey=%s",
                    cbs_job_id)
        return jsonify({
            "received":         True,
            "mds_job_id":       mds_job_id,
            "cbs_job_id":       cbs_job_id,
            "workflow_resumed": True,
        }), 200

    except Exception as exc:
        logger.error("❌ Failed to publish Zeebe message: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# Push Notification Workflow  –  POST /api/workflows/push-notification
# ---------------------------------------------------------------------------
@app.route("/api/workflows/push-notification", methods=["POST"])
def trigger_push_notification():
    """
    Start the Push Notification Generation workflow.

    Request body (JSON)
    -------------------
    {
        "workfrontProjectId": "69b18b90000050500e6247facdd92998",  # REQUIRED
        "pageUrl": "https://www.walmart.com/shop/deals/clearance",
        "messagingStrategy": "all",     // "all" | "value" | "fomo" | "newness"
        "emojiUsage": "medium",         // "none" | "light" | "medium" | "heavy"
        "numNotifications": 10,
        "modelName": "gpt-4.1-mini",
        "recipientEmails": ["user@example.com"]
    }
    """
    data = request.get_json(silent=True) or {}

    if not data.get("workfrontProjectId"):
        return jsonify({"status": "error",
                        "message": "workfrontProjectId is required"}), 400

    variables = {
        "workfrontProjectId": data["workfrontProjectId"],
        "pageUrl":            data.get("pageUrl",
                                       "https://www.walmart.com/shop/deals/clearance"),
        "messagingStrategy":  data.get("messagingStrategy", "all"),
        "emojiUsage":         data.get("emojiUsage", "medium"),
        "numNotifications":   data.get("numNotifications", 10),
        "modelName":          data.get("modelName", "gpt-4.1-mini"),
        "recipientEmails":    data.get("recipientEmails",
                                       ["Nagateja.Chadalawada@walmart.com"]),
        "triggeredBy":        data.get("triggeredBy", "api"),
    }

    try:
        instance_key = asyncio.run(_start_process(
            bpmn_id="push-notification-workflow",
            bpmn_file="workflows/push-notification-workflow.bpmn",
            variables=variables,
        ))
        logger.info("✅ Push-notification workflow started – instance=%s", instance_key)
        return jsonify({
            "status": "success",
            "workflow_instance_key": instance_key,
            "bpmn_process_id": "push-notification-workflow",
            "monitor_urls": _monitor_urls(),
        }), 201

    except Exception as exc:
        logger.error("❌ Failed to start push-notification workflow: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 Camunda Workflow Trigger API")
    logger.info("   Zeebe Gateway:  %s", ZEEBE_GATEWAY_ADDRESS)
    logger.info("   API Port:       %s", API_PORT)
    logger.info("")
    logger.info("📋 Endpoints:")
    logger.info("   GET  /health")
    logger.info("   POST /api/workflows/mds-evaluation")
    logger.info("   POST /api/workflows/push-notification")
    logger.info("   POST /api/eval/callback          ← MDS webhook target")
    logger.info("")

    app.run(host="0.0.0.0", port=API_PORT, debug=False)
