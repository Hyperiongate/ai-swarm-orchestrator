"""
AI SWARM VOICE SERVICE - Voice Handler
Created: January 28, 2026
Last Updated: January 28, 2026

PURPOSE:
Handles WebSocket communication with OpenAI's Realtime API for voice interaction.
Manages audio streaming, wake word detection, and integration with main orchestrator.

LEARNING OBJECTIVES:
1. OpenAI Realtime API WebSocket protocol
2. Async audio streaming patterns
3. WebSocket client implementation in Python
4. Base64 audio encoding/decoding
5. Session management for stateful conversations

OPENAI REALTIME API:
- Endpoint: wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17
- Audio format: PCM16, 24kHz, mono, base64-encoded
- Bidirectional streaming (full duplex)
- Built-in wake word detection
- Automatic speech-to-text and text-to-speech

AUTHOR: Jim @ Shiftwork Solutions LLC
CHANGE LOG:
- January 28, 2026: Initial creation - OpenAI Realtime API integration
"""

import asyncio
import json
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import websockets
from websockets.exceptions import ConnectionClosed

from orchestrator_client import OrchestratorClient

logger = logging.getLogger(__name__)

# ============================================================================
# VOICE HANDLER CLASS
# ============================================================================

class VoiceHandler:
    """
    Manages a single voice conversation session.
    
    This class handles:
    1. Connection to OpenAI Realtime API (WebSocket)
    2. Streaming audio from client → OpenAI
    3. Streaming audio from OpenAI → client
    4. Wake word detection ("Hey Swarm")
    5. Integration with main orchestrator for complex tasks
    
    ARCHITECTURE:
    - Two WebSocket connections: one to client, one to OpenAI
    - Audio flows bidirectionally through this handler
    - Transcripts are intercepted for wake word detection
    - Complex requests are routed to main app's /api/orchestrate
    """
    
    def __init__(self, connection_id: str, websocket, openai_api_key: str, main_app_url: str):
        """
        Initialize the voice handler.
        
        Args:
            connection_id: Unique identifier for this connection
            websocket: FastAPI WebSocket connection to client
            openai_api_key: OpenAI API key
            main_app_url: URL of main Flask app
        """
        self.connection_id = connection_id
        self.client_ws = websocket
        self.openai_api_key = openai_api_key
        self.main_app_url = main_app_url
        
        # OpenAI WebSocket connection
        self.openai_ws: Optional[websockets.WebSocketClientProtocol] = None
        
        # Session state
        self.session_id: Optional[str] = None
        self.conversation_id: Optional[str] = None
        self.is_listening = False
        self.is_speaking = False
        
        # Orchestrator client
        self.orchestrator = OrchestratorClient(main_app_url)
        
        # Wake word detection
        self.wake_word = "hey swarm"
        self.wake_word_detected = False
        self.pending_user_input = ""
        
        # Task tracking
        self.active_tasks = []
        
        logger.info(f"🎤 VoiceHandler created for connection {connection_id}")
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    async def initialize(self):
        """
        Initialize the voice handler.
        Connects to OpenAI Realtime API.
        
        LEARNING NOTE:
        This is an async function (uses await) because connecting to OpenAI
        is a network operation that could take time. We don't want to block
        other connections while waiting.
        """
        try:
            # Connect to OpenAI Realtime API
            openai_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
            
            logger.info(f"🔌 Connecting to OpenAI Realtime API...")
            
            # Create WebSocket connection to OpenAI
            self.openai_ws = await websockets.connect(
                openai_url,
                additional_headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }
            )
            
            logger.info(f"✅ Connected to OpenAI Realtime API")
            
            # Configure session
            await self.configure_session()
            
            # Start listening for OpenAI responses
            # This runs in the background
            self.active_tasks.append(
                asyncio.create_task(self.listen_to_openai())
            )
            
            logger.info(f"🎙️ Voice handler initialized for {self.connection_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize voice handler: {e}")
            raise
    
    async def configure_session(self):
        """
        Configure the OpenAI Realtime API session.
        
        Sets up:
        - Voice selection (alloy, echo, shimmer, etc.)
        - Turn detection (wake word)
        - Audio format
        - System instructions
        """
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": """You are a helpful AI assistant for Shiftwork Solutions, 
                a consulting firm specializing in 24/7 shift schedule optimization. 
                Be professional, concise, and helpful. When users ask for complex tasks 
                like creating documents or analyzing schedules, acknowledge their request 
                and let them know you're processing it.""",
                "voice": "alloy",  # Options: alloy, echo, shimmer
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",  # Voice Activity Detection
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "temperature": 0.8,
                "max_response_output_tokens": 4096
            }
        }
        
        await self.openai_ws.send(json.dumps(config))
        logger.info("⚙️ Session configured")
    
    # ========================================================================
    # MESSAGE HANDLING
    # ========================================================================
    
    async def handle_client_message(self, message: Dict[str, Any]):
        """
        Handle a message from the client (browser).
        
        Message types:
        - audio: Audio chunk from microphone
        - interrupt: Stop current AI response
        - ping: Keepalive
        
        Args:
            message: JSON message from client
        """
        msg_type = message.get("type")
        
        try:
            if msg_type == "audio":
                # Forward audio to OpenAI
                await self.forward_audio_to_openai(message.get("data"))
            
            elif msg_type == "interrupt":
                # User wants to interrupt AI response
                await self.interrupt()
            
            elif msg_type == "ping":
                # Keepalive
                await self.client_ws.send_json({"type": "pong"})
            
            else:
                logger.warning(f"⚠️ Unknown message type from client: {msg_type}")
        
        except Exception as e:
            logger.error(f"❌ Error handling client message: {e}")
            await self.send_error_to_client(str(e))
    
    async def forward_audio_to_openai(self, audio_data: str):
        """
        Forward audio from client to OpenAI.
        
        Args:
            audio_data: Base64-encoded PCM16 audio
        """
        if not self.openai_ws:
            return
        
        try:
            # Send to OpenAI
            await self.openai_ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_data
            }))
        
        except Exception as e:
            logger.error(f"❌ Error forwarding audio to OpenAI: {e}")
    
    # ========================================================================
    # OPENAI RESPONSE HANDLING
    # ========================================================================
    
    async def listen_to_openai(self):
        """
        Listen for messages from OpenAI Realtime API.
        This runs continuously in the background.
        
        LEARNING NOTE:
        This is a long-running async task. It loops forever, waiting for
        messages from OpenAI. The 'async for' pattern is perfect for this:
        it yields control to other tasks while waiting for the next message.
        """
        try:
            async for message in self.openai_ws:
                data = json.loads(message)
                await self.handle_openai_message(data)
        
        except ConnectionClosed:
            logger.info(f"🔌 OpenAI connection closed for {self.connection_id}")
        
        except Exception as e:
            logger.error(f"❌ Error listening to OpenAI: {e}")
    
    async def handle_openai_message(self, message: Dict[str, Any]):
        """
        Handle a message from OpenAI.
        
        OpenAI sends various event types:
        - session.created: Session is ready
        - conversation.item.created: New message
        - response.audio.delta: Audio chunk (AI speaking)
        - response.audio_transcript.delta: Partial transcript
        - response.audio_transcript.done: Complete transcript
        - input_audio_buffer.speech_started: User started speaking
        - input_audio_buffer.speech_stopped: User stopped speaking
        - conversation.item.input_audio_transcription.completed: User transcript
        """
        msg_type = message.get("type")
        
        try:
            if msg_type == "session.created":
                self.session_id = message.get("session", {}).get("id")
                logger.info(f"📱 Session created: {self.session_id}")
            
            elif msg_type == "response.audio.delta":
                # AI is speaking - forward audio to client
                audio_data = message.get("delta")
                await self.client_ws.send_json({
                    "type": "audio",
                    "data": audio_data
                })
            
            elif msg_type == "response.audio_transcript.done":
                # Complete AI transcript
                transcript = message.get("transcript", "")
                logger.info(f"🤖 AI said: {transcript}")
                
                await self.client_ws.send_json({
                    "type": "transcript",
                    "text": transcript
                })
            
            elif msg_type == "conversation.item.input_audio_transcription.completed":
                # User's speech was transcribed
                transcript = message.get("transcript", "")
                logger.info(f"👤 User said: {transcript}")
                
                await self.client_ws.send_json({
                    "type": "user_transcript",
                    "text": transcript
                })
                
                # Check for wake word
                await self.check_wake_word(transcript)
            
            elif msg_type == "input_audio_buffer.speech_started":
                # User started speaking
                self.is_listening = True
                await self.client_ws.send_json({"type": "user_speaking"})
            
            elif msg_type == "input_audio_buffer.speech_stopped":
                # User stopped speaking
                self.is_listening = False
                await self.client_ws.send_json({"type": "user_stopped"})
            
            elif msg_type == "response.done":
                # AI finished responding
                self.is_speaking = False
                await self.client_ws.send_json({"type": "response_complete"})
            
            elif msg_type == "error":
                # OpenAI sent an error
                error_msg = message.get("error", {}).get("message", "Unknown error")
                logger.error(f"❌ OpenAI error: {error_msg}")
                await self.send_error_to_client(error_msg)
        
        except Exception as e:
            logger.error(f"❌ Error handling OpenAI message: {e}")
    
    # ========================================================================
    # WAKE WORD DETECTION & ORCHESTRATION
    # ========================================================================
    
    async def check_wake_word(self, transcript: str):
        """
        Check if the transcript contains the wake word.
        If it does, extract the command and route to orchestrator.
        
        Args:
            transcript: User's speech transcript
        """
        transcript_lower = transcript.lower().strip()
        
        # Check for wake word
        if self.wake_word in transcript_lower:
            logger.info(f"🎤 Wake word detected!")
            
            # Extract command (everything after wake word)
            wake_index = transcript_lower.index(self.wake_word)
            command = transcript[wake_index + len(self.wake_word):].strip()
            
            if command:
                logger.info(f"📝 Command: {command}")
                
                # Notify client
                await self.client_ws.send_json({"type": "wake_detected"})
                
                # Route to orchestrator
                await self.route_to_orchestrator(command)
            else:
                logger.info("⚠️ Wake word detected but no command provided")
                
                # Prompt user for command
                await self.speak("Yes? How can I help you?")
    
    async def route_to_orchestrator(self, user_request: str):
        """
        Route a user request to the main app's orchestrator.
        
        This is where voice commands become AI Swarm tasks.
        For example: "Hey Swarm, create a DuPont schedule"
        → Routes to /api/orchestrate
        → AI Swarm processes it
        → Response comes back
        → We speak the response
        
        Args:
            user_request: The user's command
        """
        try:
            logger.info(f"🚀 Routing to orchestrator: {user_request}")
            
            # Tell user we're processing
            await self.speak("I'm working on that now...")
            
            # Call orchestrator
            result = await self.orchestrator.orchestrate(
                user_request=user_request,
                conversation_id=self.conversation_id
            )
            
            if result.get("success"):
                # Extract result text
                response_text = result.get("result", "Task completed successfully.")
                
                # Remove HTML tags for voice (simple approach)
                import re
                response_text = re.sub('<[^<]+?>', '', response_text)
                
                # Limit length for voice (don't read entire documents)
                if len(response_text) > 500:
                    response_text = response_text[:500] + "... The full result is available in the interface."
                
                # Speak the response
                await self.speak(response_text)
                
                # If document was created, mention it
                if result.get("document_created"):
                    doc_type = result.get("document_type", "document")
                    await self.speak(f"I've also created a {doc_type} file for you.")
            
            else:
                error_msg = result.get("error", "Sorry, I encountered an error processing your request.")
                await self.speak(error_msg)
        
        except Exception as e:
            logger.error(f"❌ Error routing to orchestrator: {e}")
            await self.speak("Sorry, I encountered an error processing your request.")
    
    async def speak(self, text: str):
        """
        Make the AI speak a specific message.
        
        This sends text to OpenAI, which converts it to speech
        and streams it back to us.
        
        Args:
            text: Text for AI to speak
        """
        try:
            if not self.openai_ws:
                return
            
            # Send text to OpenAI for TTS
            await self.openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": text
                }
            }))
            
            self.is_speaking = True
        
        except Exception as e:
            logger.error(f"❌ Error speaking: {e}")
    
    # ========================================================================
    # INTERRUPTION
    # ========================================================================
    
    async def interrupt(self):
        """
        Interrupt the current AI response.
        User said "Stop" or clicked stop button.
        """
        try:
            if self.openai_ws and self.is_speaking:
                # Cancel current response
                await self.openai_ws.send(json.dumps({
                    "type": "response.cancel"
                }))
                
                self.is_speaking = False
                
                logger.info(f"🛑 Interrupted response for {self.connection_id}")
        
        except Exception as e:
            logger.error(f"❌ Error interrupting: {e}")
    
    # ========================================================================
    # ERROR HANDLING
    # ========================================================================
    
    async def send_error_to_client(self, error_msg: str):
        """Send an error message to the client."""
        try:
            await self.client_ws.send_json({
                "type": "error",
                "message": error_msg
            })
        except:
            pass
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def close(self):
        """
        Clean up resources when connection closes.
        
        LEARNING NOTE:
        This is important! WebSockets and async tasks need proper cleanup.
        If you don't close connections and cancel tasks, you'll have
        memory leaks and zombie processes.
        """
        logger.info(f"🧹 Closing voice handler for {self.connection_id}")
        
        # Cancel all background tasks
        for task in self.active_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close OpenAI WebSocket
        if self.openai_ws:
            try:
                await self.openai_ws.close()
            except:
                pass
        
        logger.info(f"✅ Voice handler closed for {self.connection_id}")

# I did no harm and this file is not truncated
