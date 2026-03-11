"""
Simple script to deploy the BPMN workflow to Zeebe
"""
import asyncio
from pyzeebe import ZeebeClient, create_insecure_channel

async def deploy():
    channel = create_insecure_channel(grpc_address="localhost:26500")
    client = ZeebeClient(channel)
    
    print("Deploying workflow...")
    result = await client.deploy_resource("/Users/n0c082s/Documents/repo/metamorphosis/Camunda8-POC/workflows/push-notification-workflow.bpmn")
    print(f"✅ Deployed successfully!")
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(deploy())
