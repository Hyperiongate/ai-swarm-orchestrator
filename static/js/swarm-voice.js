/*
=============================================================================
SWARM-VOICE.JS - Voice Control Module for AI Swarm
Shiftwork Solutions LLC
=============================================================================

CHANGE LOG:
- January 23, 2026: Initial creation - Complete Voice Control System
  * Web Speech API integration for speech recognition
  * SpeechSynthesis API for text-to-speech responses
  * "Hey Swarm" wake word detection
  * Visual feedback: pulsing mic, waveform animation, status indicators
  * Toggle for voice responses on/off
  * Stop command support ("Stop" or "Cancel")
  * Direct voice input button (skip wake word)
  * Auto-send after voice input complete
  * Activation sound feedback
  * Browser compatibility checks
  * Integration with swarm-app.js sendMessage() function

FEATURES:
- Click "Activate Voice" to start listening for "Hey Swarm"
- Say "Hey Swarm" followed by your command
- AI responses are spoken aloud (toggleable)
- Say "Stop" to interrupt speech
- Click mic button in input area for direct voice input
- Visual status: inactive (gray), listening (blue pulse), recording (red), speaking (green)
- Works with existing conversation memory system

BROWSER SUPPORT:
- Chrome (recommended - best support)
- Edge (good support)
- Safari (partial support)
- Firefox (limited support)

DEPENDENCIES:
- swarm-app.js must be loaded (provides sendMessage, addMessage functions)
- swarm-styles.css must include voice-related styles

=============================================================================
*/

// =============================================================================
// 1. VOICE STATE VARIABLES
// =============================================================================

var voiceModeActive = false;      // Is voice mode turned on?
var isListening = false;          // Listening for wake word?
var isRecording = false;          // Recording user command?
var isSpeaking = false;           // Currently speaking response?
var wakeWordDetected = false;     // Wake word heard?
var voiceResponseEnabled = true;  // Should AI responses be spoken?

var speechRecognition = null;     // SpeechRecognition instance
var speechSynthesis = window.speechSynthesis;  // SpeechSynthesis API
var currentUtterance = null;      // Current speech utterance
var recognitionRestarting = false; // Prevent multiple restarts

// Configuration
var WAKE_WORD = 'hey swarm';
var STOP_WORDS = ['stop', 'cancel', 'quiet', 'shut up', 'be quiet'];

// =============================================================================
// 2. INITIALIZATION
// =============================================================================

/**
 * Initialize the voice control system
 * Called when DOM is ready
 */
function initVoice() {
    console.log('🎤 Initializing Voice Control System...');
    
    // Check browser support
    if (!checkVoiceSupport()) {
        console.warn('Voice control not fully supported in this browser');
        disableVoiceUI('Voice not supported in this browser. Use Chrome for best experience.');
        return;
    }
    
    // Pre-load voices for speech synthesis
    if (speechSynthesis) {
        // Chrome needs this to load voices
        speechSynthesis.getVoices();
        if (speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = function() {
                speechSynthesis.getVoices();
            };
        }
    }
    
    // Initialize speech recognition (but don't start yet)
    initSpeechRecognition();
    
    // Set initial UI state
    updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
    updateVoiceUI();
    
    console.log('✅ Voice Control System initialized');
}

/**
 * Check if browser supports required voice APIs
 */
function checkVoiceSupport() {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        console.error('SpeechRecognition API not supported');
        return false;
    }
    
    if (!window.speechSynthesis) {
        console.warn('SpeechSynthesis API not supported - voice responses disabled');
        voiceResponseEnabled = false;
    }
    
    return true;
}

/**
 * Disable voice UI when not supported
 */
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

/**
 * Initialize the SpeechRecognition object
 */
function initSpeechRecognition() {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        return;
    }
    
    speechRecognition = new SpeechRecognition();
    speechRecognition.continuous = true;
    speechRecognition.interimResults = true;
    speechRecognition.lang = 'en-US';
    speechRecognition.maxAlternatives = 1;
    
    // Handle recognition results
    speechRecognition.onresult = function(event) {
        handleSpeechResult(event);
    };
    
    // Handle recognition start
    speechRecognition.onstart = function() {
        console.log('🎤 Speech recognition started');
        isListening = true;
        updateVoiceUI();
    };
    
    // Handle recognition end
    speechRecognition.onend = function() {
        console.log('🎤 Speech recognition ended');
        isListening = false;
        
        // Auto-restart if voice mode is still active and we're not recording
        if (voiceModeActive && !isRecording && !recognitionRestarting) {
            recognitionRestarting = true;
            setTimeout(function() {
                if (voiceModeActive && !isRecording) {
                    try {
                        speechRecognition.start();
                    } catch (e) {
                        console.log('Recognition restart error:', e);
                    }
                }
                recognitionRestarting = false;
            }, 100);
        }
        
        updateVoiceUI();
    };
    
    // Handle errors
    speechRecognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        
        if (event.error === 'not-allowed') {
            updateVoiceStatus('error', 'Microphone access denied. Please allow microphone access.');
            voiceModeActive = false;
        } else if (event.error === 'no-speech') {
            // Normal - just no speech detected, keep listening
            updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
        } else if (event.error === 'network') {
            updateVoiceStatus('error', 'Network error. Check your connection.');
        } else {
            updateVoiceStatus('warning', 'Voice error: ' + event.error);
        }
        
        updateVoiceUI();
    };
}

// =============================================================================
// 3. VOICE ACTIVATION CONTROLS
// =============================================================================

/**
 * Toggle voice mode on/off
 * Called when user clicks the main voice activation button
 */
function toggleVoiceMode() {
    if (voiceModeActive) {
        deactivateVoiceMode();
    } else {
        activateVoiceMode();
    }
}

/**
 * Activate voice listening mode
 */
function activateVoiceMode() {
    if (!speechRecognition) {
        initSpeechRecognition();
        if (!speechRecognition) {
            alert('Voice recognition not supported in this browser. Please use Chrome.');
            return;
        }
    }
    
    voiceModeActive = true;
    wakeWordDetected = false;
    
    // Play activation sound
    playActivationSound();
    
    // Start listening
    try {
        speechRecognition.start();
        updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
        console.log('🎤 Voice mode activated - listening for wake word');
    } catch (e) {
        console.error('Error starting speech recognition:', e);
        updateVoiceStatus('error', 'Could not start voice recognition');
        voiceModeActive = false;
    }
    
    updateVoiceUI();
}

/**
 * Deactivate voice listening mode
 */
function deactivateVoiceMode() {
    voiceModeActive = false;
    isListening = false;
    isRecording = false;
    wakeWordDetected = false;
    
    // Stop recognition
    if (speechRecognition) {
        try {
            speechRecognition.stop();
        } catch (e) {
            // Ignore - may not be running
        }
    }
    
    // Stop any ongoing speech
    stopSpeaking();
    
    updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
    updateVoiceUI();
    
    console.log('🎤 Voice mode deactivated');
}

/**
 * Start direct voice input (skip wake word)
 * Called when user clicks the mic button in the input area
 */
function startVoiceInput() {
    if (!speechRecognition) {
        initSpeechRecognition();
        if (!speechRecognition) {
            alert('Voice recognition not supported in this browser. Please use Chrome.');
            return;
        }
    }
    
    // If already speaking, stop
    if (isSpeaking) {
        stopSpeaking();
        return;
    }
    
    // If already recording, stop and send
    if (isRecording) {
        finishRecording();
        return;
    }
    
    // Start recording directly (skip wake word)
    playActivationSound();
    startRecording();
}

// =============================================================================
// 4. SPEECH RECOGNITION HANDLING
// =============================================================================

/**
 * Handle speech recognition results
 */
function handleSpeechResult(event) {
    var transcript = '';
    var isFinal = false;
    
    // Get the transcript from results
    for (var i = event.resultIndex; i < event.results.length; i++) {
        var result = event.results[i];
        transcript += result[0].transcript;
        if (result.isFinal) {
            isFinal = true;
        }
    }
    
    transcript = transcript.toLowerCase().trim();
    console.log('🎤 Heard:', transcript, '(final:', isFinal, ')');
    
    // Check for stop commands first
    if (isSpeaking && containsStopWord(transcript)) {
        stopSpeaking();
        return;
    }
    
    // If we're recording a command
    if (isRecording) {
        // Update the input field with interim results
        var input = document.getElementById('userInput');
        if (input) {
            // Capitalize first letter
            var displayText = transcript.charAt(0).toUpperCase() + transcript.slice(1);
            input.value = displayText;
        }
        
        // If this is a final result, process the command
        if (isFinal) {
            processVoiceCommand(transcript);
        }
        return;
    }
    
    // Check for wake word
    if (!isRecording && transcript.indexOf(WAKE_WORD) !== -1) {
        console.log('🎤 Wake word detected!');
        wakeWordDetected = true;
        
        // Extract any command after the wake word
        var wakeIndex = transcript.indexOf(WAKE_WORD);
        var afterWake = transcript.substring(wakeIndex + WAKE_WORD.length).trim();
        
        // Start recording
        startRecording();
        
        // If there was text after the wake word, use it as initial input
        if (afterWake && afterWake.length > 2) {
            var input = document.getElementById('userInput');
            if (input) {
                input.value = afterWake.charAt(0).toUpperCase() + afterWake.slice(1);
            }
        }
    }
}

/**
 * Check if transcript contains a stop word
 */
function containsStopWord(transcript) {
    for (var i = 0; i < STOP_WORDS.length; i++) {
        if (transcript.indexOf(STOP_WORDS[i]) !== -1) {
            return true;
        }
    }
    return false;
}

/**
 * Start recording user command
 */
function startRecording() {
    isRecording = true;
    wakeWordDetected = true;
    
    // Play a beep to indicate recording started
    playBeep(600, 100);
    
    updateVoiceStatus('recording', 'Listening... Speak your command');
    updateVoiceUI();
    
    // Clear input field
    var input = document.getElementById('userInput');
    if (input) {
        input.value = '';
        input.placeholder = 'Listening...';
    }
    
    // Set a timeout to auto-finish if no speech
    setTimeout(function() {
        if (isRecording) {
            var input = document.getElementById('userInput');
            if (input && input.value.trim().length > 0) {
                finishRecording();
            }
        }
    }, 5000);
    
    console.log('🎤 Recording started');
}

/**
 * Finish recording and send the command
 */
function finishRecording() {
    isRecording = false;
    
    var input = document.getElementById('userInput');
    var command = input ? input.value.trim() : '';
    
    if (command.length > 0) {
        // Play completion beep
        playBeep(800, 100);
        
        // Send the message
        if (typeof sendMessage === 'function') {
            sendMessage();
        }
        
        updateVoiceStatus('processing', 'Processing your request...');
    } else {
        updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
    }
    
    // Reset placeholder
    if (input) {
        input.placeholder = "Type your request here... or say 'Hey Swarm'";
    }
    
    wakeWordDetected = false;
    updateVoiceUI();
    
    console.log('🎤 Recording finished');
}

/**
 * Process a voice command
 */
function processVoiceCommand(transcript) {
    // Clean up the transcript
    var command = transcript.trim();
    
    // Remove wake word if present
    if (command.toLowerCase().indexOf(WAKE_WORD) === 0) {
        command = command.substring(WAKE_WORD.length).trim();
    }
    
    if (command.length < 2) {
        // Too short, wait for more input
        return;
    }
    
    // Capitalize first letter
    command = command.charAt(0).toUpperCase() + command.slice(1);
    
    // Update input field
    var input = document.getElementById('userInput');
    if (input) {
        input.value = command;
    }
    
    // Finish recording and send
    finishRecording();
}

// =============================================================================
// 5. TEXT-TO-SPEECH (RESPONSE SPEAKING)
// =============================================================================

/**
 * Speak an AI response
 * Called automatically when AI responds (if voice responses enabled)
 */
function speakResponse(text) {
    if (!voiceResponseEnabled || !speechSynthesis) {
        return;
    }
    
    // Clean the text for speech
    var cleanText = cleanTextForSpeech(text);
    
    if (!cleanText || cleanText.length === 0) {
        return;
    }
    
    // Stop any current speech
    stopSpeaking();
    
    // Create utterance
    currentUtterance = new SpeechSynthesisUtterance(cleanText);
    currentUtterance.rate = 1.0;
    currentUtterance.pitch = 1.0;
    currentUtterance.volume = 1.0;
    
    // Try to get a good voice
    var voices = speechSynthesis.getVoices();
    var preferredVoice = null;
    
    // Prefer Google or Microsoft voices
    for (var i = 0; i < voices.length; i++) {
        var voice = voices[i];
        if (voice.lang.indexOf('en') === 0) {
            if (voice.name.indexOf('Google') !== -1 || voice.name.indexOf('Microsoft') !== -1) {
                preferredVoice = voice;
                break;
            }
            if (!preferredVoice) {
                preferredVoice = voice;
            }
        }
    }
    
    if (preferredVoice) {
        currentUtterance.voice = preferredVoice;
    }
    
    // Handle speech events
    currentUtterance.onstart = function() {
        isSpeaking = true;
        updateVoiceStatus('speaking', 'Speaking response...');
        updateVoiceUI();
        console.log('🔊 Started speaking');
    };
    
    currentUtterance.onend = function() {
        isSpeaking = false;
        currentUtterance = null;
        
        if (voiceModeActive) {
            updateVoiceStatus('listening', 'Say "Hey Swarm" to continue...');
        } else {
            updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
        }
        
        updateVoiceUI();
        console.log('🔊 Finished speaking');
    };
    
    currentUtterance.onerror = function(event) {
        console.error('Speech synthesis error:', event.error);
        isSpeaking = false;
        currentUtterance = null;
        updateVoiceUI();
    };
    
    // Start speaking
    isSpeaking = true;
    updateVoiceUI();
    speechSynthesis.speak(currentUtterance);
}

/**
 * Clean text for speech synthesis
 * Removes HTML, markdown, special characters, etc.
 */
function cleanTextForSpeech(text) {
    if (!text) return '';
    
    // Remove HTML tags
    var cleaned = text.replace(/<[^>]*>/g, '');
    
    // Remove markdown formatting
    cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');  // Bold
    cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');       // Italic
    cleaned = cleaned.replace(/#{1,6}\s*/g, '');           // Headers
    cleaned = cleaned.replace(/`([^`]+)`/g, '$1');         // Code
    cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // Links
    
    // Remove special characters that don't speak well
    cleaned = cleaned.replace(/[•●○◦▪▫]/g, '');
    cleaned = cleaned.replace(/━+/g, '');
    cleaned = cleaned.replace(/─+/g, '');
    cleaned = cleaned.replace(/[📊📋📄📁💰💡✅❌⚠️🎯🔍📝📈📉🧮]/g, '');
    
    // Clean up whitespace
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    
    // Limit length to avoid very long speeches
    if (cleaned.length > 1000) {
        cleaned = cleaned.substring(0, 1000);
        var lastSentence = cleaned.lastIndexOf('.');
        if (lastSentence > 500) {
            cleaned = cleaned.substring(0, lastSentence + 1);
        }
        cleaned += ' For more details, please see the full response on screen.';
    }
    
    return cleaned;
}

/**
 * Stop current speech
 */
function stopSpeaking() {
    if (speechSynthesis) {
        speechSynthesis.cancel();
    }
    isSpeaking = false;
    currentUtterance = null;
    updateVoiceUI();
    console.log('🔊 Speech stopped');
}

/**
 * Toggle voice response on/off
 */
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

/**
 * Speak a specific message (for manual speak buttons)
 */
function speakMessage(msgId) {
    var content = document.getElementById('content_' + msgId);
    if (content) {
        var text = content.innerText || content.textContent;
        speakResponse(text);
    }
}

// =============================================================================
// 6. UI UPDATES
// =============================================================================

/**
 * Update the voice status display
 */
function updateVoiceStatus(state, text) {
    var statusText = document.getElementById('voiceStatusText');
    var statusDot = document.getElementById('voiceStatusDot');
    
    if (statusText) {
        statusText.textContent = text;
    }
    
    if (statusDot) {
        // Remove all state classes
        statusDot.className = 'voice-status-dot';
        // Add the current state class
        statusDot.classList.add('voice-status-' + state);
    }
}

/**
 * Update all voice UI elements based on current state
 */
function updateVoiceUI() {
    // Update main activation button
    var activateBtn = document.getElementById('voiceActivateBtn');
    if (activateBtn) {
        activateBtn.classList.remove('active', 'listening', 'recording', 'speaking');
        
        if (isSpeaking) {
            activateBtn.classList.add('speaking');
            activateBtn.innerHTML = '🔊 Speaking...';
        } else if (isRecording) {
            activateBtn.classList.add('recording');
            activateBtn.innerHTML = '🎤 Recording...';
        } else if (voiceModeActive) {
            activateBtn.classList.add('active', 'listening');
            activateBtn.innerHTML = '🎤 Listening...';
        } else {
            activateBtn.innerHTML = '🎤 Activate Voice';
        }
    }
    
    // Update waveform
    var waveform = document.getElementById('voiceWaveform');
    if (waveform) {
        if (isSpeaking || isRecording) {
            waveform.classList.add('active');
        } else {
            waveform.classList.remove('active');
        }
    }
    
    // Update voice input button in input area
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
    
    // Update hint text
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

// =============================================================================
// 7. AUDIO FEEDBACK
// =============================================================================

/**
 * Play activation sound
 */
function playActivationSound() {
    playBeep(523, 100);  // C5
    setTimeout(function() {
        playBeep(659, 100);  // E5
    }, 100);
    setTimeout(function() {
        playBeep(784, 150);  // G5
    }, 200);
}

/**
 * Play a simple beep sound
 */
function playBeep(frequency, duration) {
    try {
        var AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        
        var ctx = new AudioContext();
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
        // Audio not supported, ignore
    }
}

// =============================================================================
// 8. INTEGRATION WITH SWARM-APP.JS
// =============================================================================

/**
 * Hook into the addMessage function to auto-speak AI responses
 * This overrides/extends the original addMessage if voice is enabled
 */
(function() {
    // Wait for swarm-app.js to load
    var checkInterval = setInterval(function() {
        if (typeof addMessage === 'function') {
            clearInterval(checkInterval);
            
            // Store reference to original function
            var originalAddMessage = addMessage;
            
            // Override with voice-enabled version
            window.addMessage = function(role, content, taskId, mode, data) {
                // Call original function
                originalAddMessage(role, content, taskId, mode, data);
                
                // If it's an assistant message and voice responses are enabled, speak it
                if (role === 'assistant' && voiceModeActive && voiceResponseEnabled) {
                    // Extract just the text content (remove badges, etc.)
                    var textContent = content;
                    
                    // Remove download sections and badges from speech
                    textContent = textContent.replace(/<div[^>]*>.*?<\/div>/gs, ' ');
                    
                    // Small delay to let the UI update first
                    setTimeout(function() {
                        speakResponse(textContent);
                    }, 500);
                }
                
                // Add speak button to assistant messages
                if (role === 'assistant' && taskId) {
                    var msgId = 'msg_' + messageCounter;
                    addSpeakButton(msgId);
                }
            };
            
            console.log('🎤 Voice integration with addMessage complete');
        }
    }, 100);
})();

/**
 * Add a speak button to a message
 */
function addSpeakButton(msgId) {
    var messageDiv = document.getElementById(msgId);
    if (!messageDiv) return;
    
    var header = messageDiv.querySelector('.message-header');
    if (!header) return;
    
    // Check if speak button already exists
    if (header.querySelector('.speak-btn')) return;
    
    var speakBtn = document.createElement('button');
    speakBtn.className = 'speak-btn';
    speakBtn.innerHTML = '🔊';
    speakBtn.title = 'Speak this message';
    speakBtn.style.cssText = 'background: none; border: 1px solid #e0e0e0; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; color: #666; margin-left: 5px;';
    speakBtn.onclick = function() {
        speakMessage(msgId);
    };
    
    header.appendChild(speakBtn);
}

// =============================================================================
// 9. INITIALIZATION ON DOM READY
// =============================================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoice);
} else {
    initVoice();
}

/* I did no harm and this file is not truncated */
