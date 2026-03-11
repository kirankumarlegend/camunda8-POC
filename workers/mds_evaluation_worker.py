"""
MDS Evaluation Worker for Camunda 8
Handles all service tasks in the MDS evaluation workflow.

External I/O (GCS, AEM, MDS API, Postgres) is delegated to
the deployed Util Service via REST API calls (mocked here for design purposes).
"""
import asyncio
import logging
import os
import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import httpx
from pyzeebe import ZeebeWorker, ZeebeClient, Job, create_insecure_channel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ZEEBE_GATEWAY_ADDRESS = os.getenv("ZEEBE_GATEWAY_ADDRESS", "localhost:26500")

# The util service is a separately deployed repo that exposes HTTP endpoints
# for all "menial" infrastructure tasks.
UTIL_SERVICE_BASE_URL = os.getenv(
    "UTIL_SERVICE_BASE_URL", "https://util-service.internal.example.com"
)

MCP_SERVER_CALLBACK_URL = os.getenv(
    "MCP_SERVER_CALLBACK_URL",
    "https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/api/eval/callback",
)

GCS_BUCKET = os.getenv("GCS_BUCKET", "cbs-evaluation")

MDS_API_URL = os.getenv(
    "MDS_API_URL",
    "https://async-infer-platform.stage.walmart.com/job_publisher/submit_async_job",
)


# ---------------------------------------------------------------------------
# Util Service Client
# ---------------------------------------------------------------------------
class UtilServiceClient:
    """
    HTTP client for the shared Util Service.

    The Util Service is a separately-deployed microservice (or MCP server)
    that exposes REST endpoints for all infrastructure / menial tasks such as:

        POST /gcs/upload          – upload a file to GCS
        GET  /gcs/read            – read a file from GCS
        POST /aem/upload          – upload a file to AEM DAM
        POST /mds/submit          – submit an async job to MDS
        GET  /mds/status          – poll MDS job status
        POST /postgres/query      – query Postgres
        POST /postgres/upsert     – insert / update rows in Postgres
        POST /push-notification   – send push notification
        GET  /workfront/project   – get Workfront project metadata
        POST /image/create        – create an image from a template
        POST /image/assemble-psd  – assemble multiple images into a PSD

    THIS IMPLEMENTATION IS MOCKED – every method simulates a successful
    response and logs what the real call would look like.
    """

    def __init__(self, base_url: str = UTIL_SERVICE_BASE_URL):
        self.base_url = base_url.rstrip("/")
        # In production, replace with an httpx.AsyncClient configured with
        # service-account credentials, retries, timeouts, etc.
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # GCS helpers
    # ------------------------------------------------------------------

    async def gcs_upload(
        self,
        local_path_or_bytes: Any,
        gcs_path: str,
        content_type: str = "application/octet-stream",
    ) -> Dict:
        """
        Upload a file to GCS.

        Util Service endpoint:  POST /gcs/upload
        Payload: { gcs_path, content_type, data }
        """
        endpoint = f"{self.base_url}/gcs/upload"
        payload = {
            "gcs_path": gcs_path,
            "content_type": content_type,
        }
        logger.info("[UtilService] POST %s  payload=%s", endpoint, payload)
        # --- MOCK RESPONSE ---
        return {"gcs_path": gcs_path, "success": True}

    async def gcs_read_json(self, gcs_path: str) -> Dict:
        """
        Read a JSON file from GCS and return it as a dict.

        Util Service endpoint:  GET /gcs/read
        Query params: { gcs_path }
        """
        endpoint = f"{self.base_url}/gcs/read"
        logger.info("[UtilService] GET %s  params={gcs_path: %s}", endpoint, gcs_path)
        # --- MOCK RESPONSE – simulates the MDS output that would be in GCS ---
        return {
            "outputs": [
                {
                    "post_id": "req_eval_mock_001",
                    "media_id": "med_eval_mock_001",
                    "violations": [
                        {"name": "color-contrast", "score": 0.35},
                        {"name": "text-legibility", "score": 0.20},
                    ],
                },
                {
                    "post_id": "req_eval_mock_002",
                    "media_id": "med_eval_mock_002",
                    "violations": [
                        {"name": "spelling", "score": 0.10},
                    ],
                },
            ]
        }

    # ------------------------------------------------------------------
    # AEM helpers
    # ------------------------------------------------------------------

    async def aem_upload(self, gcs_path: str, aem_folder_path: str, filename: str) -> Dict:
        """
        Upload a file (already in GCS) to AEM DAM.

        Util Service endpoint:  POST /aem/upload
        Payload: { gcs_path, aem_folder_path, filename }
        """
        endpoint = f"{self.base_url}/aem/upload"
        aem_full_path = f"{aem_folder_path.rstrip('/')}/{filename}"
        payload = {
            "gcs_path": gcs_path,
            "aem_folder_path": aem_folder_path,
            "filename": filename,
        }
        logger.info("[UtilService] POST %s  payload=%s", endpoint, payload)
        # --- MOCK RESPONSE ---
        return {"aem_path": aem_full_path, "success": True}

    # ------------------------------------------------------------------
    # MDS helpers
    # ------------------------------------------------------------------

    async def mds_submit_job(
        self,
        gcs_input_path: str,
        gcs_output_base_path: str,
        callback_url: str,
    ) -> Dict:
        """
        Submit an async job to MDS via the Util Service.

        Util Service endpoint:  POST /mds/submit
        Payload: { input_path, output_path, callback_url }
        """
        endpoint = f"{self.base_url}/mds/submit"
        payload = {
            "model_name": "cbs_brand_safety",
            "model_version": -1,
            "input_path": gcs_input_path,
            "queue": "dev",
            "output_config": {"destination_folder_path": gcs_output_base_path},
            "callback_config": {
                "callback_type": "API",
                "callback_path": callback_url,
            },
        }
        logger.info("[UtilService] POST %s  payload=%s", endpoint, json.dumps(payload, indent=2))
        # --- MOCK RESPONSE ---
        simulated_mds_job_id = f"d6542ffc_{uuid.uuid4().hex[:8]}"
        return {"mds_job_id": simulated_mds_job_id, "success": True}

    # ------------------------------------------------------------------
    # Postgres helpers
    # ------------------------------------------------------------------

    async def postgres_upsert(self, table: str, record: Dict) -> Dict:
        """
        Insert or update a record in Postgres via the Util Service.

        Util Service endpoint:  POST /postgres/upsert
        Payload: { table, record }
        """
        endpoint = f"{self.base_url}/postgres/upsert"
        payload = {"table": table, "record": record}
        logger.info("[UtilService] POST %s  table=%s  keys=%s",
                    endpoint, table, list(record.keys()))
        # --- MOCK RESPONSE ---
        return {"affected_rows": 1, "table": table, "success": True}

    async def postgres_query(self, table: str, filters: Dict) -> List[Dict]:
        """
        Query rows from Postgres via the Util Service.

        Util Service endpoint:  POST /postgres/query
        Payload: { table, filters }
        """
        endpoint = f"{self.base_url}/postgres/query"
        payload = {"table": table, "filters": filters}
        logger.info("[UtilService] POST %s  table=%s  filters=%s", endpoint, table, filters)
        # --- MOCK RESPONSE ---
        return [{"id": str(uuid.uuid4()), **filters}]


# Shared singleton client
_util_client: Optional[UtilServiceClient] = None


def get_util_client() -> UtilServiceClient:
    global _util_client
    if _util_client is None:
        _util_client = UtilServiceClient(UTIL_SERVICE_BASE_URL)
    return _util_client


# ---------------------------------------------------------------------------
# Score Calculation Helpers
# ---------------------------------------------------------------------------
VIOLATION_CONFIG: Dict[str, Dict] = {
    "color-contrast":  {"weight": 2.0, "is_severe": False},
    "text-legibility": {"weight": 1.5, "is_severe": False},
    "explicit-content": {"weight": 5.0, "is_severe": True},
    "spelling":        {"weight": 1.0, "is_severe": False},
    "brand-logo":      {"weight": 3.0, "is_severe": False},
}


def calculate_confidence_score(violations: List[Dict]) -> float:
    """Weighted confidence score: 1 - (weighted_sum / max_weight)."""
    weighted_sum = 0.0
    max_weight = 0.0
    for v in violations:
        cfg = VIOLATION_CONFIG.get(v["name"])
        if cfg:
            weighted_sum += v["score"] * cfg["weight"]
            max_weight += cfg["weight"]
    if max_weight == 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (weighted_sum / max_weight)))


def determine_asset_status(confidence_score: float, violations: List[Dict]) -> str:
    """Map confidence score and violation severity to an asset status."""
    for v in violations:
        cfg = VIOLATION_CONFIG.get(v["name"])
        if cfg and cfg.get("is_severe"):
            return "FLAGGED"
    if confidence_score >= 0.85:
        return "APPROVED"
    elif confidence_score >= 0.60:
        return "NEEDS_REVIEW"
    return "FLAGGED"


# ---------------------------------------------------------------------------
# Task Handlers
# ---------------------------------------------------------------------------

async def validate_asset_filenames_handler(job: Job):
    """
    Task: validate-asset-filenames
    Validates asset filename format and extracts metadata.
    Expected format: <projectId>-<DID>-<publisherId>-<platform>-...
    """
    asset_files: List[str] = job.variables.get("assetFiles", [])
    logger.info("Validating %d asset filenames...", len(asset_files))

    valid_assets, invalid_assets = [], []
    for filename in asset_files:
        parts = filename.split("-")
        if len(parts) >= 4:
            valid_assets.append({
                "filename": filename,
                "projectId": parts[0],
                "did": parts[1],
                "publisherId": parts[2],
                "platform": parts[3],
            })
            logger.info("✅ Valid: %s", filename)
        else:
            invalid_assets.append({
                "filename": filename,
                "reason": "Expected <projectId>-<DID>-<publisherId>-<platform>-...",
            })
            logger.warning("❌ Invalid: %s", filename)

    logger.info("Validation done: %d valid, %d invalid",
                len(valid_assets), len(invalid_assets))
    return {
        "validAssets": valid_assets,
        "invalidAssets": invalid_assets,
        "validCount": len(valid_assets),
        "invalidCount": len(invalid_assets),
    }


async def upload_assets_to_gcs_handler(job: Job):
    """
    Task: upload-assets-gcs
    Uploads validated assets to GCS via the Util Service.
    Returns the GCS paths needed for the rest of the workflow.
    """
    valid_assets: List[Dict] = job.variables.get("validAssets", [])
    cbs_job_id: str = job.variables.get("cbsJobId", str(uuid.uuid4()))
    util = get_util_client()

    logger.info("Uploading %d assets to GCS for job %s ...", len(valid_assets), cbs_job_id)

    uploaded_assets = []
    for asset in valid_assets:
        filename = asset["filename"]
        gcs_path = f"gs://{GCS_BUCKET}/input/{cbs_job_id}/{filename}"

        result = await util.gcs_upload(
            local_path_or_bytes=f"<binary content of {filename}>",
            gcs_path=gcs_path,
            content_type="image/jpeg",
        )

        uploaded_assets.append({
            **asset,
            "gcsInputPath": result["gcs_path"],
        })
        logger.info("  ✅ GCS uploaded: %s → %s", filename, result["gcs_path"])

    return {
        "uploadedAssets": uploaded_assets,
        "uploadedCount": len(uploaded_assets),
        "gcsInputFolder": f"gs://{GCS_BUCKET}/input/{cbs_job_id}/",
    }


async def upload_assets_to_aem_handler(job: Job):
    """
    Task: upload-assets-aem
    Uploads assets (from their GCS paths) to AEM DAM via the Util Service.
    This can run in parallel with GCS upload in the BPMN, or sequentially.
    """
    uploaded_assets: List[Dict] = job.variables.get("uploadedAssets", [])
    aem_folder_path: str = job.variables.get(
        "aemFolderPath", "/content/dam/cbs/evaluation/"
    )
    util = get_util_client()

    logger.info("Uploading %d assets to AEM folder: %s", len(uploaded_assets), aem_folder_path)

    aem_uploaded_assets = []
    for asset in uploaded_assets:
        filename = asset["filename"]
        result = await util.aem_upload(
            gcs_path=asset["gcsInputPath"],
            aem_folder_path=aem_folder_path,
            filename=filename,
        )
        aem_uploaded_assets.append({
            **asset,
            "aemPath": result["aem_path"],
        })
        logger.info("  ✅ AEM uploaded: %s → %s", filename, result["aem_path"])

    return {"uploadedAssets": aem_uploaded_assets}


async def store_job_metadata_handler(job: Job):
    """
    Task: store-job-metadata
    Generates a CBS Job ID and persists job + asset metadata to Postgres
    via the Util Service.
    """
    uploaded_assets: List[Dict] = job.variables.get("uploadedAssets", [])
    project_id: str = job.variables.get("projectId", "unknown")
    uploaded_by: str = job.variables.get("uploadedBy", "system")
    util = get_util_client()

    cbs_job_id = str(uuid.uuid4())
    ts = int(time.time())

    # Persist eval_jobs row
    await util.postgres_upsert("eval_jobs", {
        "cbs_job_id": cbs_job_id,
        "project_id": project_id,
        "status": "UPLOADED",
        "asset_count": len(uploaded_assets),
        "uploaded_by": uploaded_by,
        "created_at": ts,
    })

    # Persist one eval_assets row per asset
    for asset in uploaded_assets:
        asset_id = str(uuid.uuid4())
        await util.postgres_upsert("eval_assets", {
            "asset_id": asset_id,
            "cbs_job_id": cbs_job_id,
            "filename": asset["filename"],
            "gcs_input_path": asset.get("gcsInputPath", ""),
            "aem_path": asset.get("aemPath", ""),
            "project_id": asset.get("projectId", project_id),
            "did": asset.get("did", ""),
            "publisher_id": asset.get("publisherId", ""),
            "platform": asset.get("platform", ""),
            "status": "PENDING",
            "created_at": ts,
        })
        # Back-fill local record with asset_id for downstream tasks
        asset["assetId"] = asset_id

    logger.info("✅ Job metadata stored – cbsJobId=%s, assets=%d", cbs_job_id, len(uploaded_assets))
    return {
        "cbsJobId": cbs_job_id,
        "uploadedAssets": uploaded_assets,
        "storedAssetCount": len(uploaded_assets),
    }


async def build_and_upload_mds_input_handler(job: Job):
    """
    Task: build-mds-input-json
    Constructs the MDS input.json payload, then uploads it to GCS
    via the Util Service.
    """
    uploaded_assets: List[Dict] = job.variables.get("uploadedAssets", [])
    cbs_job_id: str = job.variables.get("cbsJobId")
    util = get_util_client()

    ts = int(time.time())

    inputs = []
    for i, asset in enumerate(uploaded_assets):
        post_id = f"req_eval_{cbs_job_id[:8]}_{i + 1:03d}"
        media_id = f"med_eval_{cbs_job_id[:8]}_{i + 1:03d}"
        inputs.append({
            "post_identifiers": {"post_id": post_id},
            "post_status": "active",
            "create_time": ts,
            "download_time": ts,
            "post_components": [],
            "media": [{
                "media_identifiers": {"media_id": media_id},
                "type": "image",
                "media_components": [{
                    "name": "main",
                    "content": asset["gcsInputPath"],
                }],
            }],
        })

    input_json = {
        "publisher_identifiers": {
            "publisher_id": f"cbs-eval-{ts}",
            "platform_name": "manual_upload",
            "tenant": "martech",
            "download_time": ts,
            "create_time": ts,
        },
        "publisher_status": "active",
        "download_time": ts,
        "create_time": ts,
        "inputs": inputs,
    }

    gcs_input_json_path = f"gs://{GCS_BUCKET}/input/{cbs_job_id}/input.json"

    # Upload input.json to GCS via Util Service
    await util.gcs_upload(
        local_path_or_bytes=json.dumps(input_json).encode(),
        gcs_path=gcs_input_json_path,
        content_type="application/json",
    )

    logger.info("✅ input.json built and uploaded to GCS: %s", gcs_input_json_path)
    return {
        "gcsInputJsonPath": gcs_input_json_path,
        "gcsInputFolder": f"gs://{GCS_BUCKET}/input/{cbs_job_id}/",
        "gcsOutputBasePath": f"gs://{GCS_BUCKET}/output/{cbs_job_id}/",
        "mdsInputAssetCount": len(inputs),
    }


async def submit_mds_job_handler(job: Job):
    """
    Task: submit-mds-job
    Calls the Util Service to submit an async MDS job.
    The Util Service handles the actual MDS REST call with auth headers.
    On completion MDS will POST to our callback URL.
    """
    cbs_job_id: str = job.variables.get("cbsJobId")
    gcs_input_folder: str = job.variables.get("gcsInputFolder")
    gcs_output_base_path: str = job.variables.get("gcsOutputBasePath")
    util = get_util_client()

    logger.info("Submitting MDS job – cbsJobId=%s, input=%s", cbs_job_id, gcs_input_folder)

    result = await util.mds_submit_job(
        gcs_input_path=gcs_input_folder,
        gcs_output_base_path=gcs_output_base_path,
        callback_url=MCP_SERVER_CALLBACK_URL,
    )

    mds_job_id: str = result["mds_job_id"]
    gcs_output_path = f"{gcs_output_base_path}{mds_job_id}/input.json"

    # Record the MDS job ID so the callback handler can correlate
    await util.postgres_upsert("eval_jobs", {
        "cbs_job_id": cbs_job_id,
        "mds_job_id": mds_job_id,
        "gcs_output_path": gcs_output_path,
        "status": "MDS_SUBMITTED",
    })

    logger.info("✅ MDS job submitted – mdsJobId=%s", mds_job_id)
    logger.info("   Callback URL: %s", MCP_SERVER_CALLBACK_URL)
    logger.info("   Output will be at: %s", gcs_output_path)

    return {
        "mdsJobId": mds_job_id,
        "gcsOutputPath": gcs_output_path,
        "gcsOutputBasePath": gcs_output_base_path,
    }


async def postprocess_mds_results_handler(job: Job):
    """
    Task: postprocess-mds-results
    Called after the MDS callback is received (Zeebe message correlation).

    1. Reads the MDS output JSON from GCS via the Util Service
    2. Computes weighted confidence scores for each asset
    3. Persists scores, violations and status back to Postgres
    """
    cbs_job_id: str = job.variables.get("cbsJobId")
    mds_job_id: str = job.variables.get("mdsJobId")       # injected by Zeebe message
    gcs_output_path: str = job.variables.get("gcsOutputPath")
    uploaded_assets: List[Dict] = job.variables.get("uploadedAssets", [])
    util = get_util_client()

    logger.info("Postprocessing MDS results – cbsJobId=%s, mdsJobId=%s", cbs_job_id, mds_job_id)
    logger.info("  Reading MDS output from GCS: %s", gcs_output_path)

    # Step 1 – Read MDS output from GCS
    mds_output: Dict = await util.gcs_read_json(gcs_output_path)
    outputs_by_index = mds_output.get("outputs", [])

    # Step 2 – Process each asset
    processed_assets = []
    ts = int(time.time())

    for i, asset in enumerate(uploaded_assets):
        # Try to match output by index (real impl would match by post_id / media_id)
        output = outputs_by_index[i] if i < len(outputs_by_index) else {}
        violations = output.get("violations", [])

        confidence_score = calculate_confidence_score(violations)
        status = determine_asset_status(confidence_score, violations)

        processed_asset = {
            **asset,
            "confidenceScore": round(confidence_score, 4),
            "status": status,
            "violations": violations,
        }
        processed_assets.append(processed_asset)

        # Step 3 – Persist results to Postgres via Util Service
        await util.postgres_upsert("eval_assets", {
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "mds_job_id": mds_job_id,
            "confidence_score": round(confidence_score, 4),
            "violations": json.dumps(violations),
            "status": status,
            "postprocessed_at": ts,
        })

        logger.info(
            "  ✅ %s → status=%s, confidence=%.2f, violations=%d",
            asset["filename"], status, confidence_score, len(violations),
        )

    # Update job status
    await util.postgres_upsert("eval_jobs", {
        "cbs_job_id": cbs_job_id,
        "status": "POSTPROCESSED",
        "postprocessed_at": ts,
    })

    logger.info("✅ Postprocessing complete – %d assets processed", len(processed_assets))
    return {
        "processedAssets": processed_assets,
        "processedCount": len(processed_assets),
    }


# ---------------------------------------------------------------------------
# Review-phase handlers (unchanged in logic, updated Postgres calls)
# ---------------------------------------------------------------------------

async def approve_assets_handler(job: Job):
    """Task: approve-assets — mark assets APPROVED in Postgres."""
    processed_assets: List[Dict] = job.variables.get("processedAssets", [])
    cbs_job_id: str = job.variables.get("cbsJobId")
    util = get_util_client()
    ts = int(time.time())

    for asset in processed_assets:
        await util.postgres_upsert("eval_assets", {
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "status": "APPROVED",
            "reviewed_at": ts,
        })
        await util.postgres_upsert("eval_asset_history", {
            "id": str(uuid.uuid4()),
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "action": "APPROVED",
            "timestamp": ts,
        })

    await util.postgres_upsert("eval_jobs", {
        "cbs_job_id": cbs_job_id,
        "status": "APPROVED",
        "updated_at": ts,
    })

    logger.info("✅ %d assets approved", len(processed_assets))
    return {"approvedCount": len(processed_assets), "approvedAt": ts}


async def reject_assets_handler(job: Job):
    """Task: reject-assets — mark assets REJECTED in Postgres."""
    processed_assets: List[Dict] = job.variables.get("processedAssets", [])
    cbs_job_id: str = job.variables.get("cbsJobId")
    util = get_util_client()
    ts = int(time.time())

    for asset in processed_assets:
        await util.postgres_upsert("eval_assets", {
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "status": "REJECTED",
            "reviewed_at": ts,
        })
        await util.postgres_upsert("eval_asset_history", {
            "id": str(uuid.uuid4()),
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "action": "REJECTED",
            "timestamp": ts,
        })

    await util.postgres_upsert("eval_jobs", {
        "cbs_job_id": cbs_job_id,
        "status": "REJECTED",
        "updated_at": ts,
    })

    logger.info("✅ %d assets rejected", len(processed_assets))
    return {"rejectedCount": len(processed_assets), "rejectedAt": ts}


async def store_asset_feedback_handler(job: Job):
    """Task: store-asset-feedback — store reviewer comments and loop back."""
    feedback_text: str = job.variables.get("feedbackText", "")
    processed_assets: List[Dict] = job.variables.get("processedAssets", [])
    cbs_job_id: str = job.variables.get("cbsJobId")
    util = get_util_client()
    ts = int(time.time())

    for asset in processed_assets:
        await util.postgres_upsert("eval_feedback", {
            "id": str(uuid.uuid4()),
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "feedback_text": feedback_text,
            "created_at": ts,
        })
        await util.postgres_upsert("eval_asset_history", {
            "id": str(uuid.uuid4()),
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "action": "FEEDBACK",
            "notes": feedback_text[:200],
            "timestamp": ts,
        })

    logger.info("✅ Feedback stored for %d assets", len(processed_assets))
    return {"feedbackStored": True, "feedbackCount": len(processed_assets)}


async def publish_approved_assets_handler(job: Job):
    """Task: publish-approved-assets — export to downstream systems."""
    processed_assets: List[Dict] = job.variables.get("processedAssets", [])
    cbs_job_id: str = job.variables.get("cbsJobId")
    util = get_util_client()
    ts = int(time.time())

    logger.info("Publishing %d approved assets...", len(processed_assets))

    for asset in processed_assets:
        # Example downstream task – could be AEM publish, CDN invalidation, etc.
        # All delegated to Util Service:
        # await util.aem_publish(asset["aemPath"])
        logger.info("  📤 Publishing %s (AEM: %s)", asset["filename"], asset.get("aemPath"))

        await util.postgres_upsert("eval_assets", {
            "asset_id": asset.get("assetId"),
            "cbs_job_id": cbs_job_id,
            "status": "PUBLISHED",
            "published_at": ts,
        })

    await util.postgres_upsert("eval_jobs", {
        "cbs_job_id": cbs_job_id,
        "status": "PUBLISHED",
        "updated_at": ts,
    })

    logger.info("✅ %d assets published", len(processed_assets))
    return {"publishedCount": len(processed_assets), "publishedAt": ts}


# ---------------------------------------------------------------------------
# MCP Server: Callback handler (Zeebe message publisher)
# ---------------------------------------------------------------------------
# This runs inside your MCP / FastAPI server, NOT inside the Zeebe worker.
# Shown here for reference and colocation with the rest of the eval logic.
#
# @app.post("/api/eval/callback")
# async def mds_callback_handler(request: Request):
#     body = await request.json()
#     mds_job_id = body["job_id"]
#
#     util = get_util_client()
#     rows = await util.postgres_query("eval_jobs", {"mds_job_id": mds_job_id})
#     cbs_job_id = rows[0]["cbs_job_id"]
#
#     await util.postgres_upsert("eval_jobs", {
#         "cbs_job_id": cbs_job_id,
#         "status": "CALLBACK_RECEIVED",
#     })
#     await util.postgres_upsert("eval_callback_responses", {
#         "id": str(uuid.uuid4()),
#         "mds_job_id": mds_job_id,
#         "cbs_job_id": cbs_job_id,
#         "response_body": json.dumps(body),
#         "received_at": int(time.time()),
#     })
#
#     # Resume the waiting Zeebe workflow instance
#     channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
#     zeebe_client = ZeebeClient(channel)
#     await zeebe_client.publish_message(
#         name="mds-callback",
#         correlation_key=cbs_job_id,
#         variables={"mdsJobId": mds_job_id},
#     )
#
#     return {"received": True}


# ---------------------------------------------------------------------------
# Main Worker Entry Point
# ---------------------------------------------------------------------------

async def main():
    """Start the Zeebe worker and register all task handlers."""
    logger.info("🚀 Starting MDS Evaluation Worker")
    logger.info("   Zeebe Gateway:    %s", ZEEBE_GATEWAY_ADDRESS)
    logger.info("   Util Service URL: %s", UTIL_SERVICE_BASE_URL)
    logger.info("   GCS Bucket:       %s", GCS_BUCKET)
    logger.info("   MDS Callback URL: %s", MCP_SERVER_CALLBACK_URL)

    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    worker = ZeebeWorker(channel)

    worker.task(task_type="validate-asset-filenames")(validate_asset_filenames_handler)
    worker.task(task_type="upload-assets-gcs")(upload_assets_to_gcs_handler)
    worker.task(task_type="upload-assets-aem")(upload_assets_to_aem_handler)
    worker.task(task_type="store-job-metadata")(store_job_metadata_handler)
    worker.task(task_type="build-mds-input-json")(build_and_upload_mds_input_handler)
    worker.task(task_type="submit-mds-job")(submit_mds_job_handler)
    worker.task(task_type="postprocess-mds-results")(postprocess_mds_results_handler)
    worker.task(task_type="approve-assets")(approve_assets_handler)
    worker.task(task_type="reject-assets")(reject_assets_handler)
    worker.task(task_type="store-asset-feedback")(store_asset_feedback_handler)
    worker.task(task_type="publish-approved-assets")(publish_approved_assets_handler)

    logger.info("✅ All handlers registered. Listening for jobs...")
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
