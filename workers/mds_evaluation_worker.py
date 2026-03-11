"""
MDS Evaluation Worker for Camunda 8
Handles all service tasks in the MDS evaluation workflow
"""
import asyncio
import logging
import os
import json
from typing import Dict, Any, List
from pyzeebe import ZeebeWorker, Job, create_insecure_channel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Zeebe configuration
ZEEBE_GATEWAY_ADDRESS = "localhost:26500"

# MCP Server configuration (for future integration)
MCP_SERVER_URL = "https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net"


# ============================================================================
# Task Handlers
# ============================================================================

async def validate_asset_filenames_handler(job: Job):
    """
    Task: validate-asset-filenames
    Validates asset filename format and extracts metadata
    
    Expected format: <projectId>-<DID>-<publisherId>-<platform>-<date>-<assetType>-<size>-<assetName>.<ext>
    Example: 7502741-5417-NULL-PMAX-NOV-DEALS-FY26-XCAT-EV2A-BFTG-DNAD-1200x1200-NULL-GM-AA-EL-25011430133EAW700.jpeg
    """
    asset_files = job.variables.get("assetFiles", [])
    
    logger.info(f"Validating {len(asset_files)} asset filenames...")
    
    valid_assets = []
    invalid_assets = []
    
    for filename in asset_files:
        parts = filename.split("-")
        
        # Minimum required parts: projectId, DID, publisherId, platform
        if len(parts) >= 4:
            asset_metadata = {
                "filename": filename,
                "projectId": parts[0],
                "did": parts[1],
                "publisherId": parts[2],
                "platform": parts[3],
                "valid": True
            }
            valid_assets.append(asset_metadata)
            logger.info(f"✅ Valid: {filename} (Project: {parts[0]}, DID: {parts[1]})")
        else:
            invalid_assets.append({
                "filename": filename,
                "reason": "Invalid format - expected <projectId>-<DID>-<publisherId>-<platform>-...",
                "valid": False
            })
            logger.warning(f"❌ Invalid: {filename}")
    
    logger.info(f"Validation complete: {len(valid_assets)} valid, {len(invalid_assets)} invalid")
    
    return {
        "validAssets": valid_assets,
        "invalidAssets": invalid_assets,
        "validCount": len(valid_assets),
        "invalidCount": len(invalid_assets)
    }


async def upload_assets_aem_gcs_handler(job: Job):
    """
    Task: upload-assets-aem-gcs
    Uploads assets to both AEM and GCS in parallel
    
    TODO: Integrate with actual AEM and GCS upload services
    """
    valid_assets = job.variables.get("validAssets", [])
    asset_file_paths = job.variables.get("assetFilePaths", [])
    aem_folder_path = job.variables.get("aemFolderPath", "/content/dam/cbs/evaluation/")
    
    logger.info(f"Uploading {len(valid_assets)} assets to AEM & GCS...")
    
    # TODO: Replace with actual upload logic
    # For now, simulate uploads
    uploaded_assets = []
    
    for i, asset in enumerate(valid_assets):
        filename = asset["filename"]
        file_path = asset_file_paths[i] if i < len(asset_file_paths) else None
        
        # Simulate AEM upload
        aem_path = f"{aem_folder_path}{filename}"
        
        # Simulate GCS upload (will use actual CBS job ID later)
        gcs_path = f"gs://cbs-evaluation/input/temp-job-id/{filename}"
        
        uploaded_assets.append({
            **asset,
            "aemPath": aem_path,
            "gcsInputPath": gcs_path,
            "uploaded": True
        })
        
        logger.info(f"✅ Uploaded: {filename}")
        logger.info(f"   AEM: {aem_path}")
        logger.info(f"   GCS: {gcs_path}")
    
    return {
        "uploadedAssets": uploaded_assets,
        "uploadedCount": len(uploaded_assets)
    }


async def store_job_metadata_handler(job: Job):
    """
    Task: store-job-metadata
    Stores job and asset metadata in Postgres
    
    TODO: Integrate with Postgres database
    """
    uploaded_assets = job.variables.get("uploadedAssets", [])
    project_id = job.variables.get("projectId", "unknown")
    
    logger.info(f"Storing job metadata for {len(uploaded_assets)} assets...")
    
    # Generate CBS Job ID (UUID in production)
    import uuid
    cbs_job_id = str(uuid.uuid4())
    
    # TODO: INSERT into eval_jobs table
    # TODO: INSERT into eval_assets table (one per asset)
    
    logger.info(f"✅ Job metadata stored: CBS Job ID = {cbs_job_id}")
    
    return {
        "cbsJobId": cbs_job_id,
        "storedAssetCount": len(uploaded_assets)
    }


async def build_mds_input_json_handler(job: Job):
    """
    Task: build-mds-input-json
    Builds input.json file for MDS API submission
    """
    uploaded_assets = job.variables.get("uploadedAssets", [])
    cbs_job_id = job.variables.get("cbsJobId")
    
    logger.info(f"Building input.json for MDS submission...")
    
    import time
    timestamp = int(time.time())
    
    # Build MDS input.json structure
    inputs = []
    for i, asset in enumerate(uploaded_assets):
        post_id = f"req_eval_{cbs_job_id[:8]}_{i+1:03d}"
        media_id = f"med_eval_{cbs_job_id[:8]}_{i+1:03d}"
        
        inputs.append({
            "post_identifiers": {
                "post_id": post_id
            },
            "post_status": "active",
            "create_time": timestamp,
            "download_time": timestamp,
            "post_components": [],
            "media": [{
                "media_identifiers": {
                    "media_id": media_id
                },
                "type": "image",
                "media_components": [{
                    "name": "main",
                    "content": asset["gcsInputPath"]
                }]
            }]
        })
    
    input_json = {
        "publisher_identifiers": {
            "publisher_id": f"cbs-eval-{timestamp}",
            "platform_name": "manual_upload",
            "tenant": "martech",
            "download_time": timestamp,
            "create_time": timestamp
        },
        "publisher_status": "active",
        "download_time": timestamp,
        "create_time": timestamp,
        "inputs": inputs
    }
    
    # TODO: Upload input.json to GCS
    gcs_input_json_path = f"gs://cbs-evaluation/input/{cbs_job_id}/input.json"
    
    logger.info(f"✅ input.json built with {len(inputs)} assets")
    logger.info(f"   GCS path: {gcs_input_json_path}")
    
    return {
        "inputJson": input_json,
        "gcsInputJsonPath": gcs_input_json_path,
        "gcsInputPath": f"gs://cbs-evaluation/input/{cbs_job_id}/"
    }


async def submit_mds_job_handler(job: Job):
    """
    Task: submit-mds-job
    Submits async job to MDS API
    
    TODO: Integrate with actual MDS API
    """
    cbs_job_id = job.variables.get("cbsJobId")
    gcs_input_path = job.variables.get("gcsInputPath")
    
    logger.info(f"Submitting job to MDS API...")
    logger.info(f"   CBS Job ID: {cbs_job_id}")
    logger.info(f"   Input Path: {gcs_input_path}")
    
    # TODO: Call actual MDS API
    # For now, simulate
    mds_job_id = f"mds_{cbs_job_id[:8]}_simulated"
    gcs_output_base_path = f"gs://cbs-evaluation/output/{cbs_job_id}/"
    gcs_output_path = f"{gcs_output_base_path}{mds_job_id}/input.json"
    
    logger.info(f"✅ MDS job submitted")
    logger.info(f"   MDS Job ID: {mds_job_id}")
    logger.info(f"   Output will be at: {gcs_output_path}")
    logger.info(f"   Callback URL: {MCP_SERVER_URL}/api/eval/callback")
    
    # TODO: UPDATE eval_jobs with mds_job_id and gcs_output_path
    
    return {
        "mdsJobId": mds_job_id,
        "gcsOutputPath": gcs_output_path,
        "gcsOutputBasePath": gcs_output_base_path,
        "mdsSubmitted": True
    }


async def postprocess_mds_results_handler(job: Job):
    """
    Task: postprocess-mds-results
    Reads MDS output from GCS and calculates confidence scores
    
    TODO: Integrate with actual GCS and Postgres
    """
    cbs_job_id = job.variables.get("cbsJobId")
    mds_job_id = job.variables.get("mdsJobId")
    gcs_output_path = job.variables.get("gcsOutputPath")
    uploaded_assets = job.variables.get("uploadedAssets", [])
    
    logger.info(f"Postprocessing MDS results...")
    logger.info(f"   Reading from: {gcs_output_path}")
    
    # TODO: Read actual MDS output from GCS
    # For now, simulate results
    processed_assets = []
    
    for asset in uploaded_assets:
        # Simulate violations and scores
        violations = [
            {"name": "color-contrast", "score": 0.9},
            {"name": "spelling", "score": 0.85}
        ]
        
        # Calculate confidence (simplified)
        avg_score = sum(v["score"] for v in violations) / len(violations) if violations else 1.0
        confidence_score = 1.0 - (avg_score * 0.3)  # Simplified calculation
        
        # Determine status
        if confidence_score >= 0.85:
            status = "APPROVED"
        elif confidence_score >= 0.60:
            status = "NEEDS_REVIEW"
        else:
            status = "FLAGGED"
        
        processed_assets.append({
            **asset,
            "confidenceScore": round(confidence_score, 2),
            "status": status,
            "violations": violations,
            "flags": []
        })
        
        logger.info(f"✅ {asset['filename']}: {status} (confidence: {confidence_score:.2f})")
    
    # TODO: UPDATE eval_assets with scores and status
    
    return {
        "processedAssets": processed_assets,
        "processedCount": len(processed_assets)
    }


async def approve_assets_handler(job: Job):
    """
    Task: approve-assets
    Marks assets as approved in database
    """
    processed_assets = job.variables.get("processedAssets", [])
    
    logger.info(f"Approving {len(processed_assets)} assets...")
    
    # TODO: UPDATE eval_assets SET status='APPROVED'
    # TODO: INSERT into eval_asset_history
    
    logger.info(f"✅ Assets approved")
    
    return {
        "approvedCount": len(processed_assets),
        "approvedAt": "timestamp_here"
    }


async def reject_assets_handler(job: Job):
    """
    Task: reject-assets
    Marks assets as rejected in database
    """
    processed_assets = job.variables.get("processedAssets", [])
    
    logger.info(f"Rejecting {len(processed_assets)} assets...")
    
    # TODO: UPDATE eval_assets SET status='REJECTED'
    # TODO: INSERT into eval_asset_history
    
    logger.info(f"✅ Assets rejected")
    
    return {
        "rejectedCount": len(processed_assets),
        "rejectedAt": "timestamp_here"
    }


async def store_asset_feedback_handler(job: Job):
    """
    Task: store-asset-feedback
    Stores reviewer feedback for assets
    """
    feedback_text = job.variables.get("feedbackText", "")
    processed_assets = job.variables.get("processedAssets", [])
    
    logger.info(f"Storing feedback for {len(processed_assets)} assets...")
    logger.info(f"   Feedback: {feedback_text[:100]}...")
    
    # TODO: INSERT into eval_feedback
    # TODO: INSERT into eval_asset_history
    
    logger.info(f"✅ Feedback stored")
    
    return {
        "feedbackStored": True,
        "feedbackCount": len(processed_assets)
    }


async def publish_approved_assets_handler(job: Job):
    """
    Task: publish-approved-assets
    Publishes approved assets to downstream systems
    """
    processed_assets = job.variables.get("processedAssets", [])
    
    logger.info(f"Publishing {len(processed_assets)} approved assets...")
    
    # TODO: Export to downstream systems
    # TODO: Update status to PUBLISHED
    
    logger.info(f"✅ Assets published")
    
    return {
        "publishedCount": len(processed_assets),
        "publishedAt": "timestamp_here"
    }


# ============================================================================
# Main Worker
# ============================================================================

async def main():
    """Main worker loop"""
    logger.info("🚀 Starting MDS Evaluation Worker...")
    logger.info(f"   Zeebe Gateway: {ZEEBE_GATEWAY_ADDRESS}")
    logger.info(f"   MCP Server: {MCP_SERVER_URL}")
    
    # Create Zeebe worker
    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    worker = ZeebeWorker(channel)
    
    # Register task handlers
    worker.task(task_type="validate-asset-filenames")(validate_asset_filenames_handler)
    worker.task(task_type="upload-assets-aem-gcs")(upload_assets_aem_gcs_handler)
    worker.task(task_type="store-job-metadata")(store_job_metadata_handler)
    worker.task(task_type="build-mds-input-json")(build_mds_input_json_handler)
    worker.task(task_type="submit-mds-job")(submit_mds_job_handler)
    worker.task(task_type="postprocess-mds-results")(postprocess_mds_results_handler)
    worker.task(task_type="approve-assets")(approve_assets_handler)
    worker.task(task_type="reject-assets")(reject_assets_handler)
    worker.task(task_type="store-asset-feedback")(store_asset_feedback_handler)
    worker.task(task_type="publish-approved-assets")(publish_approved_assets_handler)
    
    logger.info("✅ Worker registered all handlers. Starting to listen for jobs...")
    
    # Start the worker - this will poll for jobs
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
