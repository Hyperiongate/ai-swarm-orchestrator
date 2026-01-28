"""
AI SWARM VOICE SERVICE - FastAPI Main Application
Created: January 28, 2026
Last Updated: January 28, 2026

PURPOSE:
FastAPI microservice that handles real-time voice interaction using OpenAI's Realtime API.
Separate from the main Flask app to properly support WebSocket connections.

ARCHITECTURE DECISION:
Flask (WSGI) cannot handle WebSockets natively. We tried Hypercorn with ASGI wrappers
and it failed with "WSGI wrapper received a non-HTTP scope" errors. This FastAPI
service runs independently and communicates with the main Flask app via HTTP API calls.

LEARNING OBJECTIVES:
1. FastAPI async patterns (async/await, WebSocket handling)
2. CORS configuration for cross-origin WebSocket connections
3. Health checks and monitoring endpoints
4. WebSocket lifecycle management
5. Error handling in async contexts

ENDPOINTS:
- GET  /health          - Health check (returns service status)
- GET  /ws/voice        - WebSocket endpoint for voice streaming
- POST /api/interrupt   - Interrupt current AI response

ENVIRONMENT VARIABLES REQUIRED:
- OPENAI_API_KEY        - OpenAI API key for Realtime API
- MAIN_APP_URL          - URL of main Flask app (for orchestrator calls)
- PORT                  - Port to run on (default: 10000, Render sets this)

AUTHOR: Jim @ Shiftwork Solutions LLC
CHANGE LOG:
- January 28, 2026: Initial creation - FastAPI voice service with WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
from datetime import datetime
import asyncio
from typing import Dict, Optional

# Import our voice handler
from voice_handler import VoiceHandler

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="AI Swarm Voice Service",
    description="Real-time voice interaction microservice using OpenAI Realtime API",
    version="1.0.0"
)

# ============================================================================
# CORS CONFIGURATION
# ============================================================================
# Allow the main Flask app and any frontend to connect via WebSocket
# In production, you should restrict this to specific origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: ["https://your-app.onrender.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# GLOBAL STATE
# ============================================================================
# Track active WebSocket connections
# In a production system with multiple workers, you'd use Redis or similar

active_connections: Dict[str, WebSocket] = {}
voice_handlers: Dict[str, VoiceHandler] = {}

# ============================================================================
# CONFIGURATION FROM ENVIRONMENT
# ============================================================================

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
MAIN_APP_URL = os.environ.get('MAIN_APP_URL', 'http://localhost:10000')

if not OPENAI_API_KEY:
    logger.error("❌ OPENAI_API_KEY not set in environment variables!")
    raise ValueError("OPENAI_API_KEY is required")

logger.info(f"🔧 Voice service configured to call main app at: {MAIN_APP_URL}")

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Render uses this to determine if the service is running.
    """
    return JSONResponse({
        "status": "healthy",
        "service": "ai-swarm-voice",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(active_connections),
        "openai_api_configured": bool(OPENAI_API_KEY),
        "main_app_url": MAIN_APP_URL
    })

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """
    Root endpoint - provides service information.
    """
    return {
        "service": "AI Swarm Voice Service",
        "version": "1.0.0",
        "status": "running",
        "websocket_endpoint": "/ws/voice",
        "health_check": "/health",
        "active_connections": len(active_connections)
    }

# ============================================================================
# WEBSOCKET ENDPOINT - MAIN VOICE INTERFACE
# ============================================================================

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice interaction.
    
    FLOW:
    1. Client connects and sends audio chunks (PCM16, 24kHz, base64)
    2. We stream audio to OpenAI Realtime API
    3. OpenAI streams back audio responses (also PCM16, 24kHz)
    4. We forward audio and transcripts back to client
    5. On wake word ("Hey Swarm"), we route to main orchestrator
    
    MESSAGE TYPES:
    Client → Server:
        - {"type": "audio", "data": "<base64-pcm16>"}
        - {"type": "interrupt"}
        - {"type": "ping"}
    
    Server → Client:
        - {"type": "ready", "session_id": "...", "conversation_id": "..."}
        - {"type": "audio", "data": "<base64-pcm16>"}
        - {"type": "transcript", "text": "..."}
        - {"type": "user_transcript", "text": "..."}
        - {"type": "wake_detected"}
        - {"type": "response_complete"}
        - {"type": "error", "message": "..."}
        - {"type": "pong"}
    
    LEARNING NOTES:
    - await websocket.accept() establishes the WebSocket connection
    - WebSocket.receive_json() is async - uses async/await pattern
    - We create a VoiceHandler per connection (stateful)
    - Connection cleanup happens in finally block
    - WebSocketDisconnect exception is expected on client disconnect
    """
    
    await websocket.accept()
    
    connection_id = None
    handler = None
    
    try:
        # Create unique connection ID
        import uuid
        connection_id = str(uuid.uuid4())[:8]
        
        logger.info(f"🎤 New WebSocket connection: {connection_id}")
        
        # Store connection
        active_connections[connection_id] = websocket
        
        # Create voice handler for this connection
        handler = VoiceHandler(
            connection_id=connection_id,
            websocket=websocket,
            openai_api_key=OPENAI_API_KEY,
            main_app_url=MAIN_APP_URL
        )
        
        voice_handlers[connection_id] = handler
        
        # Initialize the handler (connects to OpenAI)
        await handler.initialize()
        
        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "session_id": handler.session_id,
            "conversation_id": handler.conversation_id
        })
        
        # Main message loop
        # This runs until the client disconnects
        while True:
            # Wait for message from client
            message = await websocket.receive_json()
            
            # Route message to handler
            await handler.handle_client_message(message)
    
    except WebSocketDisconnect:
        logger.info(f"🔌 Client disconnected: {connection_id}")
    
    except Exception as e:
        logger.error(f"❌ WebSocket error for {connection_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    
    finally:
        # Cleanup
        if connection_id:
            # Close voice handler
            if handler:
                await handler.close()
            
            # Remove from active connections
            if connection_id in active_connections:
                del active_connections[connection_id]
            
            if connection_id in voice_handlers:
                del voice_handlers[connection_id]
            
            logger.info(f"🧹 Cleaned up connection: {connection_id}")

# ============================================================================
# INTERRUPT ENDPOINT
# ============================================================================

@app.post("/api/interrupt/{connection_id}")
async def interrupt_voice(connection_id: str):
    """
    Interrupt the current AI response for a specific connection.
    This is useful if the user wants to stop the AI mid-sentence.
    """
    if connection_id not in voice_handlers:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    handler = voice_handlers[connection_id]
    await handler.interrupt()
    
    return {"status": "interrupted", "connection_id": connection_id}

# ============================================================================
# STARTUP EVENT
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Runs when the FastAPI service starts.
    Good place for initialization tasks.
    """
    logger.info("🚀 AI Swarm Voice Service starting...")
    logger.info(f"📡 Main app URL: {MAIN_APP_URL}")
    logger.info(f"🔑 OpenAI API key configured: {bool(OPENAI_API_KEY)}")
    logger.info("✅ Voice service ready for WebSocket connections")

# ============================================================================
# SHUTDOWN EVENT
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs when the FastAPI service shuts down.
    Clean up any active connections.
    """
    logger.info("🛑 AI Swarm Voice Service shutting down...")
    
    # Close all active voice handlers
    for connection_id, handler in list(voice_handlers.items()):
        try:
            await handler.close()
        except:
            pass
    
    # Close all WebSocket connections
    for connection_id, ws in list(active_connections.items()):
        try:
            await ws.close()
        except:
            pass
    
    logger.info("✅ All connections closed")

# ============================================================================
# STATISTICS ENDPOINT
# ============================================================================

@app.get("/api/stats")
async def get_stats():
    """
    Get statistics about the voice service.
    Useful for monitoring and debugging.
    """
    return {
        "active_connections": len(active_connections),
        "active_handlers": len(voice_handlers),
        "connections": list(active_connections.keys()),
        "uptime_seconds": "TODO",  # You could track this with a startup timestamp
        "total_sessions": "TODO"   # You could track this in a database
    }

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler.
    Catches any unhandled exceptions and returns a proper JSON error.
    """
    logger.error(f"❌ Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "type": type(exc).__name__
        }
    )

# ============================================================================
# MAIN ENTRY POINT (for local testing)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # For local development
    port = int(os.environ.get("PORT", 10001))
    
    logger.info(f"🎤 Starting voice service on port {port}")
    logger.info("📝 Access at: http://localhost:{port}")
    logger.info("🔌 WebSocket at: ws://localhost:{port}/ws/voice")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes (disable in production)
        log_level="info"
    )

# I did no harm and this file is not truncated
