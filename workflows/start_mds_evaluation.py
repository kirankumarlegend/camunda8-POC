"""
Start MDS Evaluation Workflow in Camunda 8
Triggers the workflow with asset files for evaluation
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from pyzeebe import ZeebeClient, create_insecure_channel

ZEEBE_GATEWAY_ADDRESS = "localhost:26500"
WORKFLOW_BPMN_PROCESS_ID = "mds-evaluation-workflow"


async def deploy_workflow(client: ZeebeClient):
    """Deploy the BPMN workflow to Zeebe"""
    print("📦 Deploying MDS Evaluation workflow to Zeebe...")
    try:
        await client.deploy_resource("workflows/mds-evaluation-workflow.bpmn")
        print("✅ Workflow deployed successfully")
        return True
    except Exception as e:
        print(f"⚠️  Workflow deployment failed (may already be deployed): {e}")
        return False


async def start_workflow(asset_files: list, aem_folder_path: str = None):
    """Start a new MDS evaluation workflow instance"""
    print(f"🚀 Starting MDS Evaluation Workflow")
    print(f"   Asset Files: {len(asset_files)} files")
    print(f"   Zeebe Gateway: {ZEEBE_GATEWAY_ADDRESS}")
    print()
    
    # Validate files exist
    valid_files = []
    invalid_files = []
    
    for file_path in asset_files:
        if os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            valid_files.append({
                "path": file_path,
                "name": file_name,
                "size": file_size
            })
            print(f"   ✅ {file_name} ({file_size} bytes)")
        else:
            invalid_files.append(file_path)
            print(f"   ❌ {file_path} (not found)")
    
    if not valid_files:
        print("\n❌ No valid asset files found!")
        return None
    
    if invalid_files:
        print(f"\n⚠️  {len(invalid_files)} files not found (skipped)")
    
    print()
    
    # Extract project ID from first file (format: <projectId>-<DID>-...)
    first_file_name = valid_files[0]["name"]
    parts = first_file_name.split("-")
    project_id = parts[0] if len(parts) > 0 else "unknown"
    
    # Default AEM folder path if not provided
    if not aem_folder_path:
        aem_folder_path = f"/content/dam/cbs/evaluation/project-{project_id}/"
    
    # Create Zeebe client
    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    client = ZeebeClient(channel)
    
    # Deploy workflow (safe to call multiple times)
    await deploy_workflow(client)
    
    # Start workflow instance
    print(f"▶️  Creating workflow instance...")
    
    # Prepare workflow variables
    variables = {
        "assetFiles": [f["name"] for f in valid_files],
        "assetFilePaths": [f["path"] for f in valid_files],
        "assetCount": len(valid_files),
        "aemFolderPath": aem_folder_path,
        "projectId": project_id,
        "uploadedBy": "demo-user"
    }
    
    workflow_instance = await client.run_process(
        bpmn_process_id=WORKFLOW_BPMN_PROCESS_ID,
        variables=variables
    )
    
    print(f"✅ Workflow started successfully!")
    print(f"   Process Instance Key: {workflow_instance}")
    print()
    print("📊 Monitor progress:")
    print(f"   Operate: http://localhost:8081 (demo/demo)")
    print(f"   Tasklist: http://localhost:8082 (demo/demo)")
    print()
    print("⏳ The worker will process the tasks. Watch the logs!")
    print()
    print("💡 Note: This workflow will:")
    print("   1. Validate asset filenames")
    print("   2. Upload to AEM & GCS")
    print("   3. Submit to MDS API")
    print("   4. Wait for MDS callback (async)")
    print("   5. Postprocess scores")
    print("   6. Wait for human review in Tasklist")
    
    return workflow_instance


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 start_mds_evaluation.py <asset1.jpg> [asset2.jpg] [asset3.jpg] ...")
        print()
        print("Example:")
        print("  python3 workflows/start_mds_evaluation.py \\")
        print("    /Users/n0c082s/Downloads/asset_eval_1.jpg \\")
        print("    /Users/n0c082s/Downloads/asset_eval_2.jpg \\")
        print("    /Users/n0c082s/Downloads/asset_eval_3.jpg")
        print()
        print("Asset filename format:")
        print("  <projectId>-<DID>-<publisherId>-<platform>-<date>-<assetType>-<size>-<assetName>.<ext>")
        print("  Example: 7502741-5417-NULL-PMAX-NOV-DEALS-FY26-XCAT-1200x1200-NULL-GM.jpg")
        sys.exit(1)
    
    asset_files = sys.argv[1:]
    
    # Optional: specify AEM folder path as environment variable
    aem_folder_path = os.environ.get("AEM_FOLDER_PATH")
    
    asyncio.run(start_workflow(asset_files, aem_folder_path))


if __name__ == "__main__":
    main()
