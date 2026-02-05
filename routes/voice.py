"""
Voice Routes - WebSocket API for Real-Time Voice
Created: January 27, 2026
Last Updated: January 27, 2026

CHANGES IN THIS VERSION:
- January 27, 2026: Initial creation
  * WebSocket endpoint for real-time voice streaming
  * Integration with OpenAI Realtime API
  * Orchestrator routing for complex tasks
  * Conversation memory integration
  * Session management

FEATURES:
- /api/voice/stream - WebSocket endpoint for voice streaming
- /api/voice/status - Check voice system status
- Full duplex audio streaming
- Wake word detection server-side
- Orchestrator integration for task processing

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from flask_sock import Sock
import asyncio
import json
import base64
from voice_realtime_handler import get_voice_handler
from database import create_conversation, add_message, get_conversation
from config import OPENAI_API_KEY
from voice_learning_integration import get_voice_learning_integration  # Phase 1: Voice Learning

voice_bp = Blueprint('voice', __name__)
sock = Sock()

# Store active voice sessions
active_sessions = {}


@voice_bp.route('/api/voice/status', methods=['GET'])
def voice_status():
    """Check if voice system is available and configured."""
    try:
        available = OPENAI_API_KEY is not None and len(OPENAI_API_KEY) > 0
        
        return jsonify({
            'success': True,
            'available': available,
            'provider': 'openai_realtime' if available else None,
            'model': 'gpt-4o-realtime-preview-2024-12-17' if available else None,
            'features': {
                'streaming': True,
                'wake_word': True,
                'natural_voice': True,
                'low_latency': True
            } if available else {},
            'active_sessions': len(active_sessions)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def register_voice_websocket(app):
    """
    Register WebSocket routes with the Flask app.
    Must be called from app.py with the main Flask app instance.
    """
    sock.init_app(app)
    
    @sock.route('/api/voice/stream')
    async def voice_stream(ws):
        """
        WebSocket endpoint for real-time voice streaming.
        
        Protocol:
        - Client sends: {"type": "audio", "data": "<base64-encoded-pcm16>"}
        - Client sends: {"type": "text", "text": "user message"}
        - Client sends: {"type": "commit"} to finalize audio buffer
        - Client sends: {"type": "interrupt"} to stop AI response
        - Client receives: {"type": "audio", "data": "<base64-encoded-pcm16>"}
        - Client receives: {"type": "transcript", "text": "ai response"}
        - Client receives: {"type": "status", "message": "..."}
        """
        
        session_id = None
        handler = None
        conversation_id = None
        
        try:
            print(f"🎤 New voice session started")
            
            # Create async orchestrator callback
            async def orchestrator_callback(text: str, conv_id: str) -> str:
                """Route to orchestrator and return response."""
                try:
                    # Import here to avoid circular dependency
                    from orchestration import analyze_task_with_sonnet
                    from orchestration.ai_clients import call_claude_sonnet
                    
                    # Analyze and execute
                    analysis = analyze_task_with_sonnet(text, knowledge_base=None)
                    
                    # Get quick response (for voice, keep it short)
                    prompt = f"""The user asked via voice: "{text}"

Provide a BRIEF spoken response (2-3 sentences max). Be conversational.
If this is a complex task that requires detailed work, acknowledge it and say you'll process it.

Keep your response SHORT and NATURAL for spoken delivery."""
                    
                    response = call_claude_sonnet(prompt)
                    
                    if isinstance(response, dict):
                        return response.get('content', 'I can help with that.')
                    return str(response)
                    
                except Exception as e:
                    print(f"❌ Orchestrator error: {e}")
                    return "I encountered an error. Let me try that again."
            
            # Initialize voice handler
            handler = get_voice_handler(orchestrator_callback=orchestrator_callback)
            
            # Connect to OpenAI Realtime API
            connected = await handler.connect()
            if not connected:
                await ws.send(json.dumps({
                    'type': 'error',
                    'message': 'Failed to connect to voice service'
                }))
                return
            
            # Create conversation for this session
            conversation_id = create_conversation(mode='voice', title='Voice Conversation')
            handler.set_conversation_id(conversation_id)
            
            # Store session
            session_id = handler.session_id
            active_sessions[session_id] = {
                'handler': handler,
                'conversation_id': conversation_id,
                'websocket': ws
            }
            
            # Send ready status
            await ws.send(json.dumps({
                'type': 'ready',
                'session_id': session_id,
                'conversation_id': conversation_id
            }))
            
            # Message handler for OpenAI events
            async def handle_openai_event(event_type: str, data: dict):
                """Forward events from OpenAI to the client."""
                try:
                    if event_type == "audio.delta":
                        # Forward audio chunk to client
                        audio_b64 = base64.b64encode(data['audio']).decode('utf-8')
                        await ws.send(json.dumps({
                            'type': 'audio',
                            'data': audio_b64
                        }))
                    
                    elif event_type == "transcript.delta":
                        # Partial transcript
                        await ws.send(json.dumps({
                            'type': 'transcript_partial',
                            'text': data['text']
                        }))
                    
                    elif event_type == "transcript.done":
                        # Complete transcript
                        text = data['text']
                        await ws.send(json.dumps({
                            'type': 'transcript',
                            'text': text
                        }))
                        
                        # Save to conversation
                        add_message(conversation_id, 'assistant', text)
                    
                    elif event_type == "user.transcript":
                        # User's speech transcribed
                        text = data['text']
                        await ws.send(json.dumps({
                            'type': 'user_transcript',
                            'text': text
                        }))
                        
                        # Save to conversation
                        add_message(conversation_id, 'user', text)
                        
                        # ============================================================
                        # PHASE 1: VOICE LEARNING INTEGRATION - February 5, 2026
                        # Learn from voice conversations (tone, urgency, engagement)
                        # ============================================================
                        try:
                            # Get the last assistant message for learning
                            from database import get_messages
                            messages = get_messages(conversation_id, limit=2)
                            
                            if len(messages) >= 2:
                                # Find user and assistant messages
                                user_msg = None
                                assistant_msg = None
                                
                                for msg in messages:
                                    if msg['role'] == 'user':
                                        user_msg = msg['content']
                                    elif msg['role'] == 'assistant':
                                        assistant_msg = msg['content']
                                
                                if user_msg and assistant_msg:
                                    voice_learning = get_voice_learning_integration()
                                    learned = voice_learning.learn_from_voice_exchange(
                                        user_msg,
                                        assistant_msg,
                                        {
                                            'conversation_id': conversation_id,
                                            'session_id': session_id,
                                            'wake_word_used': True  # Assume wake word was used in voice mode
                                        }
                                    )
                                    
                                    if learned:
                                        print(f"🎤 Learned from voice conversation")
                        
                        except Exception as voice_learn_error:
                            print(f"⚠️ Voice learning failed (non-critical): {voice_learn_error}")
                        # ============================================================
                    
                    elif event_type == "wake.command":
                        # Wake word detected with command
                        await ws.send(json.dumps({
                            'type': 'wake_detected',
                            'command': data['command']
                        }))
                    
                    elif event_type == "speech.started":
                        await ws.send(json.dumps({'type': 'user_speaking'}))
                    
                    elif event_type == "speech.stopped":
                        await ws.send(json.dumps({'type': 'user_stopped'}))
                    
                    elif event_type == "response.done":
                        await ws.send(json.dumps({'type': 'response_complete'}))
                    
                    elif event_type == "error":
                        await ws.send(json.dumps({
                            'type': 'error',
                            'message': data.get('message', 'Unknown error')
                        }))
                    
                except Exception as e:
                    print(f"❌ Event handling error: {e}")
            
            # Start listening to OpenAI messages
            openai_task = asyncio.create_task(
                handler.handle_messages(handle_openai_event)
            )
            
            # Handle client messages
            while True:
                try:
                    # Receive message from client
                    message = await ws.receive()
                    
                    if message is None:
                        break
                    
                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'audio':
                        # Audio data from client (base64 PCM16)
                        audio_b64 = data.get('data', '')
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await handler.send_audio(audio_bytes)
                    
                    elif msg_type == 'commit':
                        # Commit audio buffer
                        await handler.commit_audio()
                    
                    elif msg_type == 'text':
                        # Text fallback
                        text = data.get('text', '')
                        if text:
                            await handler.send_text(text)
                    
                    elif msg_type == 'interrupt':
                        # Stop current response
                        await handler.interrupt_response()
                    
                    elif msg_type == 'ping':
                        # Keepalive
                        await ws.send(json.dumps({'type': 'pong'}))
                
                except Exception as e:
                    print(f"❌ Client message error: {e}")
                    break
            
            # Cleanup
            openai_task.cancel()
            
        except Exception as e:
            print(f"❌ Voice session error: {e}")
            try:
                await ws.send(json.dumps({
                    'type': 'error',
                    'message': str(e)
                }))
            except:
                pass
        
        finally:
            # Cleanup
            if handler:
                await handler.disconnect()
            
            if session_id and session_id in active_sessions:
                del active_sessions[session_id]
            
            print(f"👋 Voice session ended")


# I did no harm and this file is not truncated
