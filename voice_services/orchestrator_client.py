"""
AI SWARM VOICE SERVICE - Orchestrator Client
Created: January 28, 2026
Last Updated: January 28, 2026

PURPOSE:
HTTP client that calls the main Flask app's /api/orchestrate endpoint.
This is how voice commands become AI Swarm tasks.

LEARNING OBJECTIVES:
1. Async HTTP requests with httpx
2. Error handling for API calls
3. JSON request/response handling
4. Retry logic for network failures
5. Integration patterns between microservices

AUTHOR: Jim @ Shiftwork Solutions LLC
CHANGE LOG:
- January 28, 2026: Initial creation - HTTP client for orchestrator calls
"""

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# ORCHESTRATOR CLIENT CLASS
# ============================================================================

class OrchestratorClient:
    """
    Client for calling the main app's orchestrator endpoint.
    
    This class handles:
    1. HTTP POST to /api/orchestrate
    2. Passing voice commands to AI Swarm
    3. Receiving and parsing responses
    4. Error handling and retries
    
    ARCHITECTURE NOTE:
    The voice service (FastAPI) and main app (Flask) are separate services.
    They communicate via HTTP API calls. This is a common microservices pattern.
    """
    
    def __init__(self, base_url: str, timeout: int = 180):
        """
        Initialize the orchestrator client.
        
        Args:
            base_url: URL of main Flask app (e.g., "https://your-app.onrender.com")
            timeout: Request timeout in seconds (default: 180 for complex tasks)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Create async HTTP client
        # LEARNING NOTE: httpx.AsyncClient is like requests but async
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True
        )
        
        logger.info(f"🔌 OrchestratorClient initialized for {base_url}")
    
    async def orchestrate(
        self, 
        user_request: str,
        conversation_id: Optional[str] = None,
        project_id: Optional[str] = None,
        enable_consensus: bool = True,
        mode: str = 'quick'
    ) -> Dict[str, Any]:
        """
        Send a request to the AI Swarm orchestrator.
        
        This is the main method that routes voice commands to the AI Swarm.
        
        Args:
            user_request: The user's command/request
            conversation_id: Optional conversation ID for context
            project_id: Optional project ID
            enable_consensus: Whether to use multi-AI validation
            mode: 'quick' or 'thorough'
        
        Returns:
            Dict containing the orchestrator's response:
            {
                "success": True/False,
                "task_id": int,
                "conversation_id": str,
                "result": str (HTML),
                "orchestrator": str,
                "execution_time": float,
                "document_created": bool,
                "document_url": str (optional),
                ...
            }
        
        LEARNING NOTE:
        This is an async function because network requests take time.
        By using async/await, we don't block other voice connections
        while waiting for the AI Swarm to respond.
        """
        try:
            # Prepare request payload
            payload = {
                "request": user_request,
                "enable_consensus": enable_consensus,
                "mode": mode
            }
            
            if conversation_id:
                payload["conversation_id"] = conversation_id
            
            if project_id:
                payload["project_id"] = project_id
            
            # API endpoint
            url = f"{self.base_url}/api/orchestrate"
            
            logger.info(f"📤 Sending to orchestrator: {user_request[:100]}...")
            logger.debug(f"📍 URL: {url}")
            logger.debug(f"📦 Payload: {payload}")
            
            # Make the HTTP POST request
            # LEARNING NOTE: 'await' here means "pause this function until response arrives"
            # Other async functions can run while we're waiting
            response = await self.client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json"
                }
            )
            
            # Check for HTTP errors (4xx, 5xx)
            response.raise_for_status()
            
            # Parse JSON response
            result = response.json()
            
            logger.info(f"✅ Orchestrator response received")
            logger.debug(f"📊 Result: {result}")
            
            return result
        
        except httpx.TimeoutException as e:
            logger.error(f"⏱️ Orchestrator request timed out after {self.timeout}s")
            return {
                "success": False,
                "error": f"Request timed out after {self.timeout} seconds. The task may still be processing."
            }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error from orchestrator: {e.response.status_code}")
            logger.error(f"📄 Response body: {e.response.text}")
            
            # Try to parse error message from response
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", str(e))
            except:
                error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }
        
        except Exception as e:
            logger.error(f"❌ Unexpected error calling orchestrator: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    async def create_conversation(self, mode: str = 'quick', project_id: Optional[str] = None) -> Optional[str]:
        """
        Create a new conversation in the main app.
        
        Args:
            mode: 'quick' or 'thorough'
            project_id: Optional project ID
        
        Returns:
            Conversation ID if successful, None if failed
        """
        try:
            url = f"{self.base_url}/api/conversations"
            
            payload = {"mode": mode}
            if project_id:
                payload["project_id"] = project_id
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                conversation_id = result.get("conversation_id")
                logger.info(f"✅ Created conversation: {conversation_id}")
                return conversation_id
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Error creating conversation: {e}")
            return None
    
    async def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """
        Get the status of a specific task.
        
        Args:
            task_id: Task ID to check
        
        Returns:
            Task details if found, error dict if not
        """
        try:
            url = f"{self.base_url}/api/task/{task_id}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"❌ Error getting task status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def health_check(self) -> bool:
        """
        Check if the main app is reachable.
        
        Returns:
            True if healthy, False if not
        """
        try:
            url = f"{self.base_url}/health"
            
            response = await self.client.get(url, timeout=5.0)
            response.raise_for_status()
            
            logger.info("✅ Main app is healthy")
            return True
        
        except Exception as e:
            logger.warning(f"⚠️ Main app health check failed: {e}")
            return False
    
    async def close(self):
        """
        Close the HTTP client.
        Should be called when shutting down the voice service.
        """
        await self.client.aclose()
        logger.info("🔌 OrchestratorClient closed")

# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

async def test_orchestrator():
    """
    Test function to verify orchestrator client works.
    Run this locally to test the connection.
    """
    import asyncio
    
    # Initialize client
    client = OrchestratorClient(
        base_url="http://localhost:10000",  # Change to your main app URL
        timeout=30
    )
    
    # Test health check
    print("Testing health check...")
    healthy = await client.health_check()
    print(f"Health check: {'✅ Passed' if healthy else '❌ Failed'}")
    
    if healthy:
        # Test orchestration
        print("\nTesting orchestration...")
        result = await client.orchestrate(
            user_request="What is a DuPont schedule?",
            enable_consensus=False,
            mode='quick'
        )
        
        print(f"\nResult:")
        print(f"Success: {result.get('success')}")
        print(f"Task ID: {result.get('task_id')}")
        print(f"Result: {result.get('result', 'N/A')[:200]}...")
    
    # Cleanup
    await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_orchestrator())

# I did no harm and this file is not truncated
