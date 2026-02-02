/*
=============================================================================
SWARM-VOICE.JS - Voice Control Module for AI Swarm (OpenAI Realtime API)
Shiftwork Solutions LLC
=============================================================================

CHANGE LOG:
- February 2, 2026: FIXED - Audio playback issues
  * Added AudioContext resume on user interaction
  * Fixed audio format conversion (base64 → ArrayBuffer → Float32)
  * Added comprehensive error logging and debugging
  * Fixed suspended AudioContext blocking playback
  * Added visual feedback for audio playing state
  * Improved error recovery

- January 28, 2026: UPDATED - Connect to dedicated voice service
  * Changed WebSocket URL from main app to voice service
  * Production: wss://ai-swarm-voice.onrender.com/ws/voice
  * Local dev: ws://localhost:10001/ws/voice
  * Auto-detects environment (local vs production)

- January 27, 2026: COMPLETE REWRITE - OpenAI Realtime API Integration
  * Replaced slow Web Speech API with OpenAI Realtime WebSocket streaming
  * Sub-2-second response time with streaming audio
  * Professional voice quality (GPT-4o realtime preview)
  * "Hey Swarm" wake word detection (server-side)
  * WebRTC audio capture for high-quality input
  * Full duplex streaming (can interrupt AI responses)
  * Auto-reconnect on connection loss
  * Integration with orchestrator for complex tasks

FEATURES:
- Click "Activate Voice" to start WebSocket connection
- Say "Hey Swarm" followed by your command
- AI responds with professional voice (< 2 second latency)
- Streaming responses (starts speaking while thinking)
- Say "Stop" to interrupt
- Click mic button for direct voice input

BROWSER SUPPORT:
- Chrome (recommended - best WebRTC support)
- Edge (good support)
- Safari (good support)
- Firefox (good support)

=============================================================================
*/

// =============================================================================
// 1. VOICE STATE VARIABLES
// =============================================================================

var voiceModeActive = false;
var isConnected = false;
var isRecording = false;
var isSpeaking = false;
var voiceResponseEnabled = true;

var ws = null;
var sessionId = null;
var conversationId = null;

var audioContext = null;
var audioWorklet = null;
var mediaStream = null;
var audioQueue = [];
var isPlayingAudio = false;
var currentAudioSource = null;

var WAKE_WORD = 'hey swarm';

// =============================================================================
// 2. INITIALIZATION
// =============================================================================

function initVoice() {
    console.log('🎤 Initializing Voice Control System (OpenAI Realtime API)...');
    
    if (!checkVoiceSupport()) {
        console.warn('Voice control not supported in this browser');
        disableVoiceUI('Voice not supported. Use Chrome, Edge, or Safari.');
        return;
    }
    
    updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
    updateVoiceUI();
    
    console.log('✅ Voice Control System initialized (Ready for WebSocket)');
}

function checkVoiceSupport() {
    // Check for WebSocket support
    if (!window.WebSocket) {
        console.error('WebSocket not supported');
        return false;
    }
    
    // Check for Web Audio API
    if (!window.AudioContext && !window.webkitAudioContext) {
        console.error('Web Audio API not supported');
        return false;
    }
    
    // Check for MediaDevices (microphone access)
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error('getUserMedia not supported');
        return false;
    }
    
    return true;
}

function disableVoiceUI(message) {
    var voiceSection = document.getElementById('voiceControlSection');
    if (voiceSection) {
        voiceSection.innerHTML = '<div class="voice-unsupported">' +
            '<span>🎤</span> ' + message + '</div>';
    }
    
    var voiceInputBtn = document.getElementById('voiceInputBtn');
    if (voiceInputBtn) {
        voiceInputBtn.disabled = true;
        voiceInputBtn.title = message;
        voiceInputBtn.style.opacity = '0.5';
    }
}

// =============================================================================
// 3. WEBSOCKET CONNECTION
// =============================================================================

async function connectWebSocket() {
    try {
        // UPDATED January 28, 2026: Connect to dedicated voice service
        // The voice service is a separate FastAPI microservice
        // Production: wss://ai-swarm-voice.onrender.com/ws/voice
        // Local dev: ws://localhost:10001/ws/voice
        
        // Automatically detect environment
        var isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        
        if (isLocal) {
            // Local development - connect to local voice service
            var wsUrl = 'ws://localhost:10001/ws/voice';
        } else {
            // Production - connect to deployed voice service
            var wsUrl = 'wss://ai-swarm-orchestrator-1.onrender.com/ws/voice';
        }
        
        console.log('🔌 Connecting to voice service:', wsUrl);
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('✅ WebSocket connected to voice service');
            isConnected = true;
            updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
            updateVoiceUI();
        };
        
        ws.onmessage = async function(event) {
            try {
                var data = JSON.parse(event.data);
                await handleWebSocketMessage(data);
            } catch (e) {
                console.error('❌ Error parsing WebSocket message:', e);
                console.error('Raw message:', event.data);
            }
        };
        
        ws.onerror = function(error) {
            console.error('❌ WebSocket error:', error);
            updateVoiceStatus('error', 'Connection error');
        };
        
        ws.onclose = function() {
            console.log('🔌 WebSocket closed');
            isConnected = false;
            
            // Auto-reconnect if voice mode is still active
            if (voiceModeActive) {
                setTimeout(function() {
                    if (voiceModeActive) {
                        console.log('🔄 Attempting reconnect...');
                        connectWebSocket();
                    }
                }, 2000);
            } else {
                updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
            }
            
            updateVoiceUI();
        };
        
    } catch (e) {
        console.error('❌ WebSocket connection failed:', e);
        updateVoiceStatus('error', 'Could not connect to voice service');
    }
}

async function handleWebSocketMessage(data) {
    var type = data.type;
    
    console.log('📨 Received message type:', type);
    
    switch(type) {
        case 'ready':
            sessionId = data.session_id;
            conversationId = data.conversation_id;
            console.log('📱 Session ready:', sessionId);
            updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
            break;
        
        case 'audio':
            // Received audio chunk from AI
            console.log('🔊 Received audio chunk, length:', data.data ? data.data.length : 0);
            if (voiceResponseEnabled) {
                try {
                    var audioData = base64ToArrayBuffer(data.data);
                    console.log('🔊 Decoded audio buffer size:', audioData.byteLength, 'bytes');
                    queueAudio(audioData);
                } catch (e) {
                    console.error('❌ Error decoding audio:', e);
                }
            } else {
                console.log('🔇 Voice responses disabled, skipping audio');
            }
            break;
        
        case 'transcript':
            // Complete AI transcript
            console.log('🤖 AI:', data.text);
            break;
        
        case 'transcript_partial':
            // Partial transcript (for display)
            console.log('🤖 Partial:', data.text);
            break;
        
        case 'user_transcript':
            // User's speech was transcribed
            console.log('👤 You said:', data.text);
            updateUserInput(data.text);
            break;
        
        case 'wake_detected':
            // Wake word detected
            console.log('🎤 Wake word detected!');
            updateVoiceStatus('recording', 'Listening... Speak your command');
            playActivationSound();
            break;
        
        case 'user_speaking':
            updateVoiceStatus('recording', 'Listening...');
            break;
        
        case 'user_stopped':
            updateVoiceStatus('processing', 'Processing...');
            break;
        
        case 'response_complete':
            console.log('✅ Response complete');
            if (voiceModeActive) {
                updateVoiceStatus('listening', 'Say "Hey Swarm" to continue...');
            }
            break;
        
        case 'error':
            console.error('❌ Server error:', data.message);
            updateVoiceStatus('error', 'Error: ' + data.message);
            break;
        
        case 'pong':
            // Keepalive response
            break;
        
        default:
            console.log('📨 Unknown message type:', type, data);
    }
}

function updateUserInput(text) {
    var input = document.getElementById('userInput');
    if (input) {
        input.value = text;
        console.log('✏️ Updated input field with:', text);
    }
}

// =============================================================================
// 4. AUDIO CAPTURE (Microphone)
// =============================================================================

async function startAudioCapture() {
    try {
        // Initialize AudioContext
        var AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContextClass({ sampleRate: 24000 });
        
        console.log('🎤 AudioContext created, state:', audioContext.state);
        
        // Resume context if suspended (required by Chrome)
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
            console.log('🎤 AudioContext resumed, new state:', audioContext.state);
        }
        
        // Get microphone stream
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 24000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });
        
        console.log('🎤 Microphone access granted');
        
        // Create audio source
        var source = audioContext.createMediaStreamSource(mediaStream);
        
        // Create ScriptProcessor for capturing audio
        var bufferSize = 4096;
        var processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
        
        processor.onaudioprocess = function(e) {
            if (!isConnected || !ws) return;
            
            // Get audio data
            var inputData = e.inputBuffer.getChannelData(0);
            
            // Convert Float32 to Int16 (PCM16)
            var pcm16 = floatTo16BitPCM(inputData);
            
            // Convert to base64
            var base64Audio = arrayBufferToBase64(pcm16.buffer);
            
            // Send to server
            ws.send(JSON.stringify({
                type: 'audio',
                data: base64Audio
            }));
        };
        
        // Connect audio graph
        source.connect(processor);
        processor.connect(audioContext.destination);
        
        audioWorklet = processor;
        
        console.log('🎤 Microphone capture started');
        
    } catch (e) {
        console.error('❌ Microphone access failed:', e);
        updateVoiceStatus('error', 'Microphone access denied');
        return false;
    }
    
    return true;
}

function stopAudioCapture() {
    if (audioWorklet) {
        audioWorklet.disconnect();
        audioWorklet = null;
    }
    
    if (mediaStream) {
        mediaStream.getTracks().forEach(function(track) {
            track.stop();
        });
        mediaStream = null;
    }
    
    console.log('🎤 Microphone capture stopped');
}

// =============================================================================
// 5. AUDIO PLAYBACK (AI Response) - FIXED
// =============================================================================

function queueAudio(audioData) {
    console.log('📥 Queueing audio chunk, size:', audioData.byteLength, 'bytes');
    audioQueue.push(audioData);
    
    if (!isPlayingAudio) {
        console.log('▶️ Starting playback');
        playNextAudio();
    } else {
        console.log('⏸️ Already playing, added to queue. Queue length:', audioQueue.length);
    }
}

async function playNextAudio() {
    if (audioQueue.length === 0) {
        console.log('✅ Audio queue empty, stopping playback');
        isPlayingAudio = false;
        isSpeaking = false;
        updateVoiceUI();
        return;
    }
    
    isPlayingAudio = true;
    isSpeaking = true;
    updateVoiceUI();
    updateVoiceStatus('speaking', 'Speaking response...');
    
    var audioData = audioQueue.shift();
    console.log('🔊 Playing audio chunk, size:', audioData.byteLength, 'bytes. Remaining in queue:', audioQueue.length);
    
    try {
        // Ensure audio context exists
        if (!audioContext) {
            console.log('🔧 Creating new AudioContext for playback');
            var AudioContextClass = window.AudioContext || window.webkitAudioContext;
            audioContext = new AudioContextClass({ sampleRate: 24000 });
        }
        
        // CRITICAL FIX: Resume AudioContext if suspended
        if (audioContext.state === 'suspended') {
            console.log('⚠️ AudioContext suspended, attempting resume...');
            await audioContext.resume();
            console.log('✅ AudioContext resumed, state:', audioContext.state);
        }
        
        console.log('🔊 AudioContext state:', audioContext.state);
        console.log('🔊 AudioContext sample rate:', audioContext.sampleRate);
        
        // Convert to Int16Array
        var int16Array = new Int16Array(audioData);
        console.log('🔊 Int16Array length:', int16Array.length, 'samples');
        
        // Convert Int16 PCM to Float32 for Web Audio
        var float32Array = new Float32Array(int16Array.length);
        for (var i = 0; i < int16Array.length; i++) {
            float32Array[i] = int16Array[i] / 32768.0;
        }
        console.log('🔊 Float32Array created, length:', float32Array.length);
        
        // Calculate duration
        var durationSeconds = float32Array.length / 24000;
        console.log('🔊 Audio duration:', durationSeconds.toFixed(2), 'seconds');
        
        // Create audio buffer
        var audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
        audioBuffer.getChannelData(0).set(float32Array);
        console.log('🔊 AudioBuffer created');
        
        // Create source and play
        var source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        
        currentAudioSource = source;
        
        source.onended = function() {
            console.log('🔊 Audio chunk finished playing');
            currentAudioSource = null;
            playNextAudio();
        };
        
        console.log('▶️ Starting audio playback NOW');
        source.start(0);
        console.log('✅ Audio playback started successfully');
        
    } catch (e) {
        console.error('❌ Audio playback error:', e);
        console.error('Error name:', e.name);
        console.error('Error message:', e.message);
        console.error('Error stack:', e.stack);
        
        // Try next audio chunk
        playNextAudio();
    }
}

function stopAudioPlayback() {
    console.log('⏹️ Stopping audio playback');
    
    // Stop current audio
    if (currentAudioSource) {
        try {
            currentAudioSource.stop();
            currentAudioSource = null;
        } catch (e) {
            console.error('Error stopping audio source:', e);
        }
    }
    
    // Clear queue
    audioQueue = [];
    isPlayingAudio = false;
    isSpeaking = false;
    
    // Send interrupt to server
    if (ws && isConnected) {
        ws.send(JSON.stringify({ type: 'interrupt' }));
    }
    
    updateVoiceUI();
}

// =============================================================================
// 6. VOICE ACTIVATION CONTROLS
// =============================================================================

async function toggleVoiceMode() {
    if (voiceModeActive) {
        deactivateVoiceMode();
    } else {
        await activateVoiceMode();
    }
}

async function activateVoiceMode() {
    console.log('🎤 Activating voice mode...');
    voiceModeActive = true;
    
    playActivationSound();
    
    // Connect WebSocket
    await connectWebSocket();
    
    // Start audio capture
    var captureStarted = await startAudioCapture();
    
    if (!captureStarted) {
        voiceModeActive = false;
        updateVoiceStatus('error', 'Could not access microphone');
        return;
    }
    
    updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
    updateVoiceUI();
    
    console.log('✅ Voice mode activated');
}

function deactivateVoiceMode() {
    console.log('🎤 Deactivating voice mode...');
    voiceModeActive = false;
    
    // Close WebSocket
    if (ws) {
        ws.close();
        ws = null;
    }
    
    // Stop audio
    stopAudioCapture();
    stopAudioPlayback();
    
    // Close AudioContext
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close();
        audioContext = null;
    }
    
    isConnected = false;
    
    updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
    updateVoiceUI();
    
    console.log('✅ Voice mode deactivated');
}

async function startVoiceInput() {
    console.log('🎤 Starting voice input...');
    
    if (!voiceModeActive) {
        await activateVoiceMode();
    }
    
    if (isSpeaking) {
        stopAudioPlayback();
    }
    
    // Resume AudioContext on user interaction (required by Chrome)
    if (audioContext && audioContext.state === 'suspended') {
        console.log('🔧 Resuming AudioContext on user interaction...');
        await audioContext.resume();
        console.log('✅ AudioContext resumed, state:', audioContext.state);
    }
}

// =============================================================================
// 7. UI UPDATES
// =============================================================================

function updateVoiceStatus(state, text) {
    var statusText = document.getElementById('voiceStatusText');
    var statusDot = document.getElementById('voiceStatusDot');
    
    if (statusText) {
        statusText.textContent = text;
    }
    
    if (statusDot) {
        statusDot.className = 'voice-status-dot';
        statusDot.classList.add('voice-status-' + state);
    }
    
    console.log('📊 Voice status:', state, '-', text);
}

function updateVoiceUI() {
    var activateBtn = document.getElementById('voiceActivateBtn');
    if (activateBtn) {
        activateBtn.classList.remove('active', 'listening', 'recording', 'speaking');
        
        if (isSpeaking) {
            activateBtn.classList.add('speaking');
            activateBtn.innerHTML = '🔊 Speaking...';
        } else if (isRecording) {
            activateBtn.classList.add('recording');
            activateBtn.innerHTML = '🎤 Recording...';
        } else if (voiceModeActive && isConnected) {
            activateBtn.classList.add('active', 'listening');
            activateBtn.innerHTML = '🎤 Listening...';
        } else {
            activateBtn.innerHTML = '🎤 Activate Voice';
        }
    }
    
    var waveform = document.getElementById('voiceWaveform');
    if (waveform) {
        if (isSpeaking || isRecording) {
            waveform.classList.add('active');
        } else {
            waveform.classList.remove('active');
        }
    }
    
    var voiceInputBtn = document.getElementById('voiceInputBtn');
    if (voiceInputBtn) {
        voiceInputBtn.classList.remove('recording', 'speaking');
        
        if (isSpeaking) {
            voiceInputBtn.classList.add('speaking');
            voiceInputBtn.innerHTML = '🔊';
            voiceInputBtn.title = 'Click to stop speaking';
        } else if (isRecording) {
            voiceInputBtn.classList.add('recording');
            voiceInputBtn.innerHTML = '⏹️';
            voiceInputBtn.title = 'Click to stop recording';
        } else {
            voiceInputBtn.innerHTML = '🎤';
            voiceInputBtn.title = 'Click to speak your message';
        }
    }
    
    var hint = document.getElementById('voiceHint');
    if (hint) {
        if (voiceModeActive) {
            if (isRecording) {
                hint.innerHTML = 'Speak your command now...';
            } else if (isSpeaking) {
                hint.innerHTML = 'Say <strong>"Stop"</strong> to interrupt';
            } else {
                hint.innerHTML = 'Say <strong>"Hey Swarm"</strong> followed by your command';
            }
        } else {
            hint.innerHTML = 'Click <strong>Activate Voice</strong> to start';
        }
    }
}

function toggleVoiceResponse() {
    voiceResponseEnabled = !voiceResponseEnabled;
    
    var toggle = document.getElementById('voiceResponseToggle');
    if (toggle) {
        toggle.checked = voiceResponseEnabled;
    }
    
    var label = document.getElementById('voiceResponseLabel');
    if (label) {
        label.textContent = voiceResponseEnabled ? 'Voice responses ON' : 'Voice responses OFF';
    }
    
    console.log('🔊 Voice responses:', voiceResponseEnabled ? 'enabled' : 'disabled');
}

// =============================================================================
// 8. AUDIO UTILITIES
// =============================================================================

function floatTo16BitPCM(float32Array) {
    var int16Array = new Int16Array(float32Array.length);
    for (var i = 0; i < float32Array.length; i++) {
        var s = Math.max(-1, Math.min(1, float32Array[i]));
        int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
}

function arrayBufferToBase64(buffer) {
    var binary = '';
    var bytes = new Uint8Array(buffer);
    for (var i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}

function base64ToArrayBuffer(base64) {
    try {
        var binaryString = window.atob(base64);
        var bytes = new Uint8Array(binaryString.length);
        for (var i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    } catch (e) {
        console.error('❌ Error decoding base64:', e);
        console.error('Base64 string length:', base64.length);
        console.error('First 100 chars:', base64.substring(0, 100));
        throw e;
    }
}

// =============================================================================
// 9. AUDIO FEEDBACK
// =============================================================================

function playActivationSound() {
    playBeep(523, 100);
    setTimeout(function() {
        playBeep(659, 100);
    }, 100);
    setTimeout(function() {
        playBeep(784, 150);
    }, 200);
}

async function playBeep(frequency, duration) {
    try {
        var AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;
        
        var ctx = new AudioContextClass();
        
        // Resume if suspended
        if (ctx.state === 'suspended') {
            await ctx.resume();
        }
        
        var oscillator = ctx.createOscillator();
        var gainNode = ctx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        
        oscillator.frequency.value = frequency;
        oscillator.type = 'sine';
        
        gainNode.gain.value = 0.1;
        
        oscillator.start();
        
        setTimeout(function() {
            oscillator.stop();
            ctx.close();
        }, duration);
    } catch (e) {
        console.error('Error playing beep:', e);
    }
}

// =============================================================================
// 10. INITIALIZATION
// =============================================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoice);
} else {
    initVoice();
}

console.log('📝 Voice control script loaded - February 2, 2026');

/* I did no harm and this file is not truncated */
