"""
Start Push Notification Workflow in Camunda 8
Triggers the workflow with a Workfront Project ID
"""
import asyncio
import json
import sys
from pyzeebe import ZeebeClient, create_insecure_channel

ZEEBE_GATEWAY_ADDRESS = "localhost:26500"
WORKFLOW_BPMN_PROCESS_ID = "push-notification-workflow"


async def deploy_workflow(client: ZeebeClient):
    """Deploy the BPMN workflow to Zeebe"""
    print("📦 Deploying workflow to Zeebe...")
    try:
        await client.deploy_resource("workflows/push-notification-workflow.bpmn")
        print("✅ Workflow deployed successfully")
        return True
    except Exception as e:
        print(f"⚠️  Workflow deployment failed (may already be deployed): {e}")
        return False


async def start_workflow(workfront_project_id: str):
    """Start a new workflow instance"""
    print(f"🚀 Starting Push Notification Workflow")
    print(f"   Workfront Project ID: {workfront_project_id}")
    print(f"   Zeebe Gateway: {ZEEBE_GATEWAY_ADDRESS}")
    print()
    
    # Create Zeebe client
    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    client = ZeebeClient(channel)
    
    # Deploy workflow (safe to call multiple times)
    await deploy_workflow(client)
    
    # Start workflow instance
    print(f"▶️  Creating workflow instance...")
    
    workflow_instance = await client.run_process(
        bpmn_process_id=WORKFLOW_BPMN_PROCESS_ID,
        variables={
            "workfrontProjectId": workfront_project_id
        }
    )
    
    print(f"✅ Workflow started successfully!")
    print(f"   Process Instance Key: {workflow_instance}")
    print()
    print("📊 Monitor progress:")
    print(f"   Operate: http://localhost:8081 (demo/demo)")
    print(f"   Tasklist: http://localhost:8082 (demo/demo)")
    print()
    print("⏳ The worker will process the tasks. Watch the logs!")
    
    return workflow_instance


async def main():
    """Main entry point"""
    # Get Workfront Project ID from command line or use default
    if len(sys.argv) > 1:
        workfront_project_id = sys.argv[1]
    else:
        # Default demo project ID
        workfront_project_id = "69010161000053b75f8d1b612b560578"
        print(f"ℹ️  No project ID provided, using demo ID: {workfront_project_id}")
        print(f"   Usage: python start_push_notification_workflow.py <workfront_project_id>")
        print()
    
    try:
        await start_workflow(workfront_project_id)
    except Exception as e:
        print(f"❌ Error starting workflow: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
