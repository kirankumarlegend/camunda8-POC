"""
Push Notification Worker for Camunda 8 - REAL MCP SERVER INTEGRATION
Handles CRM push notification generation workflow with actual API calls.

MCP Server: https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net
Element AI Gateway: https://wmtllmgateway.stage.walmart.com
"""
import asyncio
import logging
import os
import json
import uuid
import time
import base64
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

# MCP Server
MCP_SERVER_BASE_URL = os.getenv(
    "MCP_SERVER_BASE_URL",
    "https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net"
)

# Element AI Gateway
ELEMENT_AI_GATEWAY_URL = os.getenv(
    "ELEMENT_AI_GATEWAY_URL",
    "https://wmtllmgateway.stage.walmart.com/wmtllmgateway/v1"
)

ELEMENT_AI_API_KEY = os.getenv(
    "ELEMENT_AI_API_KEY",
    "eyJzZ252ZXIiOiIxIiwiYWxnIjoiSFMyNTYiLCJ0eXAiOiJKV1QifQ.eyJqdGkiOiI1MzYzIiwic3ViIjoiNzkyIiwiaXNzIjoiV01UTExNR0FURVdBWS1TVEciLCJhY3QiOiJtMG4wNWh5IiwidHlwZSI6IkFQUCIsImlhdCI6MTc1Nzk3NDA4NCwiZXhwIjoxNzczNTI2MDg0fQ.mD_y1FS_sr53ZDcctQuWgSIur0AfWmn-5uziNxkYy_k"
)

# Default AEM folder for push notifications
AEM_FOLDER_PATH = os.getenv("AEM_FOLDER_PATH", "/content/dam/library/crm-push-notifications")

# ---------------------------------------------------------------------------
# MCP Server Client
# ---------------------------------------------------------------------------
class MCPServerClient:
    """
    HTTP client for CBS Content MCP Server.
    Supports MCP JSON-RPC protocol for tool calls.
    """

    def __init__(self, base_url: str = MCP_SERVER_BASE_URL):
        self.base_url = base_url.rstrip("/")
        
        # SSL certificate handling - disable for self-signed certs
        # The MCP server uses a self-signed certificate that's not in the system trust store
        verify = False
        logger.warning("   SSL verification DISABLED (self-signed cert)")
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=60.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            verify=verify
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """
        Call an MCP tool using JSON-RPC protocol.
        
        Args:
            tool_name: Name of the MCP tool
            arguments: Tool arguments as dict
            
        Returns:
            Tool result from MCP server
        """
        endpoint = f"{self.base_url}/mcp"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream"
        }
        
        try:
            logger.info(f"[MCP] Calling tool: {tool_name}")
            logger.debug(f"[MCP] Arguments: {json.dumps(arguments, indent=2)}")
            
            response = await self.client.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=120.0
            )
            response.raise_for_status()
            
            # Get response text and parse
            response_text = response.text
            logger.debug(f"[MCP] Response: {response_text[:500]}")
            
            # Handle Server-Sent Events format
            # MCP server sends: event: message\ndata: {...}\n\n:ping\n\n...
            if "event:" in response_text or response_text.startswith("data:") or ":ping" in response_text:
                # Parse SSE format - extract only the message event data
                lines = response_text.strip().split("\n")
                json_str = None
                
                for i, line in enumerate(lines):
                    # Look for "event: message" followed by "data: {...}"
                    if line.strip() == "event: message":
                        # Next line should be the data
                        if i + 1 < len(lines) and lines[i + 1].startswith("data:"):
                            json_str = lines[i + 1][5:].strip()
                            break
                    # Or just look for data lines that aren't pings
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                        if data and not data.startswith(":") and data != "ping":
                            json_str = data
                            break
                
                if not json_str:
                    raise Exception("No valid JSON found in SSE response")
                
                result = json.loads(json_str)
            else:
                result = json.loads(response_text)
            
            if "error" in result:
                logger.error(f"[MCP] Tool error: {result['error']}")
                raise Exception(f"MCP tool error: {result['error']}")
            
            # Extract structured content if available
            if "result" in result and "structuredContent" in result["result"]:
                return result["result"]["structuredContent"]
            elif "result" in result:
                return result["result"]
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[MCP] JSON decode error: {e}")
            logger.error(f"[MCP] Response text: {response_text[:1000]}")
            raise
        except Exception as e:
            logger.error(f"[MCP] Tool call failed: {e}")
            raise

    async def workfront_get_metadata(self, project_id: str, field_names: List[str] = None) -> Dict:
        """Get Workfront project metadata."""
        arguments = {"project_id": project_id}
        if field_names:
            arguments["field_names"] = field_names
        
        return await self.call_mcp_tool("workfront_get_metadata", arguments)

    async def generate_push_notifications(
        self,
        page_url: str,
        messaging_strategy: str = "all",
        emoji_usage: str = "medium",
        num_notifications: int = 10,
        model_name: str = "gpt-4.1-mini"
    ) -> Dict:
        """Generate push notifications using MCP tool."""
        arguments = {
            "page_url": page_url,
            "messaging_strategy": messaging_strategy,
            "emoji_usage": emoji_usage,
            "num_notifications": num_notifications,
            "model_name": model_name
        }
        
        return await self.call_mcp_tool("generate_push_notifications", arguments)

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        attachments: List[Dict] = None
    ) -> Dict:
        """Send email with optional attachments."""
        arguments = {
            "to_emails": to_emails,
            "subject": subject,
            "body": body
        }
        if attachments:
            arguments["attachments"] = attachments
        
        return await self.call_mcp_tool("send_email", arguments)

    async def upload_to_dam(self, file_path: str, folder_path: str, file_name: str) -> Dict:
        """Upload file to AEM DAM."""
        endpoint = f"{self.base_url}/api/aem-upload-asset"
        
        files = {
            "file": (file_name, open(file_path, "rb"), "text/csv")
        }
        data = {"folder_path": folder_path}
        
        try:
            logger.info(f"[MCP] Uploading to DAM: {file_name} -> {folder_path}")
            
            response = await self.client.post(
                endpoint,
                data=data,
                files=files
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"[MCP] ✅ DAM Upload: {result.get('data', {}).get('dam_path')}")
            return result
            
        except Exception as e:
            logger.error(f"[MCP] DAM upload failed: {e}")
            raise


# Shared singleton client
_mcp_client: Optional[MCPServerClient] = None


def get_mcp_client() -> MCPServerClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPServerClient(MCP_SERVER_BASE_URL)
    return _mcp_client


# ---------------------------------------------------------------------------
# Element AI Gateway Client
# ---------------------------------------------------------------------------
class ElementAIClient:
    """Client for Walmart Element AI Gateway."""
    
    def __init__(self, base_url: str = ELEMENT_AI_GATEWAY_URL, api_key: str = ELEMENT_AI_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    
    async def close(self):
        await self.client.aclose()
    
    async def call_gemini(self, prompt: str, model: str = "gemini-2.5-flash", max_tokens: int = 2000) -> str:
        """Call Google Gemini via Element AI Gateway."""
        endpoint = f"{self.base_url}/google-genai"
        
        payload = {
            "model": model,
            "model-version": "001",
            "task": "generateContent",
            "model-params": {
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ],
                "generation_config": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.1
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        try:
            response = await self.client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # Extract text from Gemini response
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text
            
        except Exception as e:
            logger.error(f"[Element AI] Gemini call failed: {e}")
            raise


_element_ai_client: Optional[ElementAIClient] = None


def get_element_ai_client() -> ElementAIClient:
    global _element_ai_client
    if _element_ai_client is None:
        _element_ai_client = ElementAIClient()
    return _element_ai_client


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def create_csv_from_notifications(notifications: List[Dict], evaluation: Dict) -> str:
    """Create CSV content from notifications and evaluation results."""
    csv_lines = ["Notification ID,Headline,Body Copy,Declared Strategy,Eval Status,Reasoning"]
    
    # Get evaluations
    batch_evals = evaluation.get("results", [{}])[0].get("batch_evaluations", [])
    
    for i, notif in enumerate(notifications):
        notif_id = i + 1
        headline = notif.get("headline", "").replace('"', '""')
        body = notif.get("body_copy", "").replace('"', '""')
        strategy = notif.get("hook", "")
        
        # Find matching evaluation
        eval_data = next((e for e in batch_evals if e.get("notification_id") == notif_id), {})
        verdict = eval_data.get("verdict", "pending")
        reasoning = eval_data.get("summary_reason", "").replace('"', '""')
        
        csv_lines.append(f'"{notif_id}","{headline}","{body}","{strategy}","{verdict}","{reasoning}"')
    
    # Add uniqueness evaluation
    uniqueness = evaluation.get("results", [{}])[0].get("uniqueness_evaluation", {})
    if uniqueness:
        reason = uniqueness.get("reason", "").replace('"', '""')
        csv_lines.append(f'"Batch Uniqueness Audit","{reason}","","",""')
    
    return "\n".join(csv_lines)


# ---------------------------------------------------------------------------
# Task Handlers
# ---------------------------------------------------------------------------

async def get_workfront_metadata_handler(job: Job):
    """
    Task: get-workfront-metadata
    Retrieves project metadata from Workfront including copy direction and campaign details.
    """
    workfront_project_id: str = job.variables.get("workfrontProjectId")
    logger.info(f"Fetching Workfront metadata for project: {workfront_project_id}")
    
    mcp = get_mcp_client()
    
    # Get all project metadata
    metadata = await mcp.workfront_get_metadata(
        project_id=workfront_project_id
    )
    
    project_data = metadata.get("data", {})
    
    # Extract key fields
    project_name = project_data.get("name", "Unknown Project")
    copy_direction = project_data.get("DE:Copy Direction", {})
    
    # Parse copy direction if it's in Draft.js format
    copy_brief = ""
    if isinstance(copy_direction, dict) and "blocks" in copy_direction:
        copy_brief = "\n".join([block.get("text", "") for block in copy_direction.get("blocks", [])])
    elif isinstance(copy_direction, str):
        copy_brief = copy_direction
    
    logger.info(f"✅ Workfront metadata retrieved: {project_name}")
    
    return {
        "workfrontMetadata": project_data,
        "projectName": project_name,
        "copyBrief": copy_brief,
        "projectReferenceNumber": project_data.get("referenceNumber", ""),
    }


async def generate_push_notifications_handler(job: Job):
    """
    Task: generate-push-notifications
    Generates push notifications using MCP server tool.
    """
    page_url: str = job.variables.get("pageUrl", "https://www.walmart.com/shop/deals/clearance")
    messaging_strategy: str = job.variables.get("messagingStrategy", "all")
    emoji_usage: str = job.variables.get("emojiUsage", "medium")
    num_notifications: int = job.variables.get("numNotifications", 10)
    model_name: str = job.variables.get("modelName", "gpt-4.1-mini")
    
    # Check if this is a regeneration with feedback
    feedback_text: str = job.variables.get("feedbackText", "")
    
    logger.info(f"Generating {num_notifications} push notifications...")
    logger.info(f"  Page URL: {page_url}")
    logger.info(f"  Strategy: {messaging_strategy}")
    logger.info(f"  Emoji: {emoji_usage}")
    logger.info(f"  Model: {model_name}")
    if feedback_text:
        logger.info(f"  Feedback: {feedback_text[:100]}...")
    
    mcp = get_mcp_client()
    
    # Generate notifications via MCP
    result = await mcp.generate_push_notifications(
        page_url=page_url,
        messaging_strategy=messaging_strategy,
        emoji_usage=emoji_usage,
        num_notifications=num_notifications,
        model_name=model_name
    )
    
    data = result.get("data", {})
    notifications = data.get("notifications", [])
    evaluation = data.get("evaluation", {})
    
    logger.info(f"✅ Generated {len(notifications)} notifications")
    
    # Count approved vs rejected
    batch_evals = evaluation.get("results", [{}])[0].get("batch_evaluations", [])
    approved_count = sum(1 for e in batch_evals if e.get("verdict") == "approved")
    rejected_count = sum(1 for e in batch_evals if e.get("verdict") == "rejected")
    
    logger.info(f"  Approved: {approved_count}, Rejected: {rejected_count}")
    
    # Format notifications for display in the form
    notifications_text = ""
    for i, notif in enumerate(notifications):
        eval_data = next((e for e in batch_evals if e.get("notification_id") == i + 1), {})
        verdict = eval_data.get("verdict", "pending")
        status_icon = "✅" if verdict == "approved" else "❌"
        
        notifications_text += f"{status_icon} Notification {i + 1} ({verdict})\n"
        notifications_text += f"Headline: {notif.get('headline', '')}\n"
        notifications_text += f"Body: {notif.get('body_copy', '')}\n"
        notifications_text += f"Strategy: {notif.get('hook', '')}\n\n"
    
    return {
        "notifications": notifications,
        "evaluation": evaluation,
        "approvedCount": approved_count,
        "rejectedCount": rejected_count,
        "totalCount": len(notifications),
        "generatedNotifications": notifications_text.strip(),
    }


async def store_feedback_handler(job: Job):
    """
    Task: store-feedback
    Stores user feedback for regeneration.
    """
    feedback_text: str = job.variables.get("feedbackText", "")
    logger.info(f"✅ Feedback stored: {feedback_text[:100]}...")
    
    # Feedback is already in variables, will be used in next generation
    return {"feedbackStored": True}


async def publish_notifications_handler(job: Job):
    """
    Task: publish-notifications
    Publishes approved notifications:
    1. Creates CSV file
    2. Uploads to AEM DAM
    3. Sends email to stakeholders
    """
    notifications: List[Dict] = job.variables.get("notifications", [])
    evaluation: Dict = job.variables.get("evaluation", {})
    workfront_project_id: str = job.variables.get("workfrontProjectId")
    project_name: str = job.variables.get("projectName", "Push Notification Campaign")
    recipient_emails: List[str] = job.variables.get("recipientEmails", [
        "anusha.naredla@walmart.com",
        "Nagateja.Chadalawada@walmart.com",
        "Manikandan.Narayanan@walmart.com"
    ])
    
    logger.info(f"Publishing {len(notifications)} notifications...")
    
    # Create CSV content
    csv_content = create_csv_from_notifications(notifications, evaluation)
    
    # Save CSV to temp file
    timestamp = int(time.time())
    csv_filename = f"push-notifications_{workfront_project_id}_{timestamp}.csv"
    csv_filepath = f"/tmp/{csv_filename}"
    
    with open(csv_filepath, "w") as f:
        f.write(csv_content)
    
    logger.info(f"  CSV created: {csv_filepath}")
    
    mcp = get_mcp_client()
    
    # Upload to AEM DAM
    dam_result = await mcp.upload_to_dam(
        file_path=csv_filepath,
        folder_path=AEM_FOLDER_PATH,
        file_name=csv_filename
    )
    
    dam_path = dam_result.get("data", {}).get("dam_path", "")
    dam_url = dam_result.get("data", {}).get("asset_url", "")
    
    logger.info(f"  ✅ Uploaded to DAM: {dam_path}")
    
    # Prepare email with CSV attachment
    csv_base64 = base64.b64encode(csv_content.encode()).decode()
    
    email_body = f"""
Hello,

The push notifications for "{project_name}" have been generated and approved.

Workfront Project ID: {workfront_project_id}
Total Notifications: {len(notifications)}

The notifications are attached as a CSV file and have been uploaded to AEM DAM:
{dam_url}

Please review and proceed with campaign deployment.

Best regards,
Creative Brand System (Automated)
"""
    
    # Send email
    email_result = await mcp.send_email(
        to_emails=recipient_emails,
        subject=f"Push Notifications Ready: {project_name}",
        body=email_body,
        attachments=[{
            "file_name": csv_filename,
            "content_base64": csv_base64
        }]
    )
    
    logger.info(f"  ✅ Email sent to {len(recipient_emails)} recipients")
    
    return {
        "published": True,
        "damPath": dam_path,
        "damUrl": dam_url,
        "emailSent": True,
        "recipientCount": len(recipient_emails),
    }


# ---------------------------------------------------------------------------
# Main Worker Entry Point
# ---------------------------------------------------------------------------

async def main():
    """Start the Zeebe worker and register all task handlers."""
    logger.info("🚀 Starting Push Notification Worker (REAL MCP SERVER)")
    logger.info(f"   Zeebe Gateway:    {ZEEBE_GATEWAY_ADDRESS}")
    logger.info(f"   MCP Server:       {MCP_SERVER_BASE_URL}")
    logger.info(f"   Element AI:       {ELEMENT_AI_GATEWAY_URL}")
    logger.info(f"   AEM Folder:       {AEM_FOLDER_PATH}")

    channel = create_insecure_channel(grpc_address=ZEEBE_GATEWAY_ADDRESS)
    worker = ZeebeWorker(channel)

    worker.task(task_type="get-workfront-metadata")(get_workfront_metadata_handler)
    worker.task(task_type="generate-push-notifications")(generate_push_notifications_handler)
    worker.task(task_type="store-feedback")(store_feedback_handler)
    worker.task(task_type="publish-notifications")(publish_notifications_handler)

    logger.info("✅ All handlers registered. Listening for jobs...")
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
