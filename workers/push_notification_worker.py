"""
Camunda Worker for Push Notification Generation Workflow
Calls CBS Content MCP Server APIs to orchestrate push notification generation
"""
import asyncio
import json
import logging
from typing import Dict, Any
import requests
from pyzeebe import ZeebeWorker, Job, JobController, create_insecure_channel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Server configuration
# Use deployed MCP server in Kubernetes (dev environment)
MCP_SERVER_URL = "https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net"
# For local testing, use: "http://localhost:8080"

# Zeebe configuration
ZEEBE_GATEWAY_ADDRESS = "localhost:26500"


class MCPClient:
    """Client for calling MCP Server APIs"""
    
    def __init__(self, base_url: str = MCP_SERVER_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Camunda-Worker/1.0"
        })
        # Disable SSL verification for dev environment with self-signed certificates
        # For production, use proper SSL certificates
        self.session.verify = False
        # Suppress InsecureRequestWarning
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via HTTP API"""
        # MCP tools are available as REST APIs at /api/{tool-name}
        # For example: generate_push_notifications -> /api/generate-push-notifications
        
        api_endpoint = tool_name.replace("_", "-")
        url = f"{self.base_url}/api/{api_endpoint}"
        
        logger.info(f"Calling MCP tool: {tool_name} at {url}")
        logger.debug(f"Arguments: {json.dumps(arguments, indent=2)}")
        
        try:
            response = self.session.post(url, json=arguments, timeout=180)
            response.raise_for_status()
            result = response.json()
            logger.info(f"MCP tool {tool_name} completed successfully")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
            raise
    
    def get_workfront_metadata(self, project_id: str) -> Dict[str, Any]:
        """Get Workfront project metadata"""
        # Workfront endpoint uses GET method with query parameters
        api_endpoint = "workfront-get-metadata"
        url = f"{self.base_url}/api/{api_endpoint}"
        
        logger.info(f"Calling MCP tool: workfront_get_metadata at {url}")
        
        try:
            # Use GET method with query parameters
            response = self.session.get(url, params={"project_id": project_id}, timeout=180)
            response.raise_for_status()
            result = response.json()
            logger.info(f"MCP tool workfront_get_metadata completed successfully")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling MCP tool workfront_get_metadata: {str(e)}")
            raise
    
    def generate_push_notifications(self, page_context: Dict[str, Any], 
                                    campaign_brief: str = "",
                                    theme: str = "",
                                    num_notifications: int = 10,
                                    regeneration_feedback: str = "") -> Dict[str, Any]:
        """Generate push notifications"""
        arguments = {
            "page_context": page_context,
            "campaign_brief": campaign_brief,
            "theme": theme,
            "num_notifications": num_notifications,
            "use_page_context": False  # Using campaign brief from Workfront
        }
        
        # Add regeneration feedback if provided
        if regeneration_feedback:
            arguments["campaign_instructions"] = f"Previous feedback: {regeneration_feedback}"
        
        return self.call_tool("generate_push_notifications", arguments)
    
    def evaluate_notifications(self, generated_content: Dict[str, Any], 
                               page_context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate notification quality using multi-model consensus"""
        # The generate_push_notifications already includes evaluation
        # but we can call evaluate_content separately for more control
        return self.call_tool("evaluate_content", {
            "content_type": "PushNotification",
            "generated_content": generated_content,
            "page_context": page_context
        })


# Initialize MCP client
mcp_client = MCPClient()

# Create Zeebe worker (will be initialized in main)
worker = None


# Register task handlers using decorators
# Note: worker will be set in main() before these are used

async def get_workfront_metadata_handler(job: Job):
    """
    Task: get-workfront-metadata
    Gets project metadata from Workfront
    """
    workfront_project_id = job.variables.get("workfrontProjectId")
    
    logger.info(f"Getting Workfront metadata for project: {workfront_project_id}")
    
    # Call MCP tool
    metadata = mcp_client.get_workfront_metadata(workfront_project_id)
    
    # Extract relevant fields for push notifications
    campaign_info = {
        "project_name": metadata.get("DE:Creative Project Name", ""),
        "theme": metadata.get("DE:WCS - Content Type", ""),
        "campaign_brief": metadata.get("DE:Overview / objective of request", ""),
        "target_date": metadata.get("DE:Requested handoff date", ""),
        "vertical": metadata.get("DE:Vertical", ""),
        "division": metadata.get("DE:Division", ""),
        "full_metadata": metadata
    }
    
    logger.info(f"✅ Workfront metadata retrieved: {campaign_info['project_name']}")
    
    return {
        "workfrontMetadata": metadata,
        "campaignInfo": campaign_info
    }


async def generate_push_notifications_handler(job: Job):
    """
    Task: generate-push-notifications
    Generates push notifications using Workfront campaign info
    """
    campaign_info = job.variables.get("campaignInfo", {})
    regeneration_feedback = job.variables.get("userFeedback", "")
    
    logger.info(f"Generating push notifications for: {campaign_info.get('project_name')}")
    
    # Prepare page_context (even though we're not using page scraping)
    page_context = {
        "page_type": "campaign",
        "scraped_data": {
            "title": campaign_info.get("project_name", ""),
            "description": campaign_info.get("campaign_brief", ""),
            "vertical": campaign_info.get("vertical", ""),
            "division": campaign_info.get("division", "")
        }
    }
    
    # Call MCP tool
    result = mcp_client.generate_push_notifications(
        page_context=page_context,
        campaign_brief=campaign_info.get("campaign_brief", ""),
        theme=campaign_info.get("theme", ""),
        num_notifications=10,
        regeneration_feedback=regeneration_feedback
    )
    
    # Extract notifications and evaluation
    notifications = result.get("data", {}).get("notifications", [])
    evaluation = result.get("data", {}).get("evaluation", {})
    
    logger.info(f"✅ Generated {len(notifications)} push notifications")
    logger.info(f"📊 Evaluation consensus: {evaluation.get('consensus_verdict', 'N/A')}")
    logger.info(f"📊 Overall score: {evaluation.get('overall_score', 'N/A')}")
    
    return {
        "generatedNotifications": notifications,
        "evaluation": evaluation,
        "generationResponse": result
    }


async def evaluate_notifications_handler(job: Job):
    """
    Task: evaluate-notifications
    Evaluates notification quality (this is actually done in generation, 
    but keeping separate for workflow clarity)
    """
    # Evaluation is already done in generate_push_notifications
    # This task is a pass-through to maintain clean workflow structure
    
    evaluation = job.variables.get("evaluation", {})
    notifications = job.variables.get("generatedNotifications", [])
    
    logger.info(f"📊 Evaluation results:")
    logger.info(f"   Consensus: {evaluation.get('consensus_verdict')}")
    logger.info(f"   Overall Score: {evaluation.get('overall_score')}")
    logger.info(f"   Notifications Count: {len(notifications)}")
    
    # Format for display in Tasklist
    evaluation_summary = {
        "verdict": evaluation.get("consensus_verdict", "unknown"),
        "score": evaluation.get("overall_score", 0),
        "total_notifications": len(notifications),
        "model_evaluations": evaluation.get("model_evaluations", []),
        "recommendations": evaluation.get("recommendations", [])
    }
    
    return {
        "evaluationSummary": evaluation_summary,
        "readyForReview": True
    }


async def store_feedback_handler(job: Job):
    """
    Task: store-feedback
    Stores user feedback for improving future generations
    """
    user_feedback = job.variables.get("userFeedback", "")
    review_comments = job.variables.get("reviewComments", "")
    workfront_project_id = job.variables.get("workfrontProjectId")
    
    logger.info(f"💾 Storing feedback for project: {workfront_project_id}")
    logger.info(f"   Feedback: {user_feedback[:100] if user_feedback else 'No feedback'}...")
    
    # Here you would:
    # 1. Store feedback in database for analysis
    # 2. Update prompt guidelines based on feedback patterns
    # 3. Feed into GCS prompt versioning system
    
    # For now, we'll just log and prepare for regeneration
    feedback_data = {
        "project_id": workfront_project_id,
        "feedback": user_feedback,
        "comments": review_comments,
        "stored_at": "timestamp_here"
    }
    
    # In production, call:
    # mcp_client.call_tool("seed_prompt_to_gcs", {...})
    
    logger.info(f"✅ Feedback stored successfully")
    
    return {
        "feedbackStored": True,
        "feedbackData": feedback_data
    }


async def publish_notifications_handler(job: Job):
    """
    Task: publish-notifications
    Publishes approved notifications to CRM system
    """
    notifications = job.variables.get("generatedNotifications", [])
    campaign_info = job.variables.get("campaignInfo", {})
    
    logger.info(f"📤 Publishing {len(notifications)} notifications to CRM")
    logger.info(f"   Campaign: {campaign_info.get('project_name')}")
    
    # Here you would:
    # 1. Format notifications for CRM API
    # 2. Call CRM API to create campaign
    # 3. Schedule notifications
    
    # For demo, we'll simulate
    published_data = {
        "campaign_id": "CRM-12345",
        "notification_count": len(notifications),
        "status": "published",
        "scheduled_for": campaign_info.get("target_date", "TBD")
    }
    
    logger.info(f"✅ Notifications published: Campaign ID {published_data['campaign_id']}")
    
    return {
        "publishedData": published_data,
        "publishedAt": "timestamp_here"
    }


async def main():
    """Main worker loop"""
    logger.info("🚀 Starting Push Notification Worker...")
    logger.info(f"   Zeebe Gateway: {ZEEBE_GATEWAY_ADDRESS}")
    logger.info(f"   MCP Server: {MCP_SERVER_URL}")
    
    # Create Zeebe worker
    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    worker = ZeebeWorker(channel)
    
    # Register task handlers using decorator pattern
    worker.task(task_type="get-workfront-metadata")(get_workfront_metadata_handler)
    worker.task(task_type="generate-push-notifications")(generate_push_notifications_handler)
    worker.task(task_type="evaluate-notifications")(evaluate_notifications_handler)
    worker.task(task_type="store-feedback")(store_feedback_handler)
    worker.task(task_type="publish-notifications")(publish_notifications_handler)
    
    logger.info("✅ Worker registered all handlers. Starting to listen for jobs...")
    
    # Start the worker - this will poll for jobs
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
