/*
=============================================================================
SWARM-VOICE.JS - Voice Control Module for AI Swarm
Shiftwork Solutions LLC
=============================================================================

CHANGE LOG:
- January 23, 2026: FIXED "undefined" bug
  * Removed problematic addMessage override that caused "undefined" errors
  * Now uses MutationObserver to detect new assistant messages
  * Cleaner integration that doesn't interfere with swarm-app.js
  * Fixed timing issues with message detection

- January 23, 2026: Initial creation - Complete Voice Control System
  * Web Speech API integration for speech recognition
  * SpeechSynthesis API for text-to-speech responses
  * "Hey Swarm" wake word detection
  * Visual feedback: pulsing mic, waveform animation, status indicators
  * Toggle for voice responses on/off
  * Stop command support ("Stop" or "Cancel")
  * Direct voice input button (skip wake word)
  * Auto-send after voice input complete

FEATURES:
- Click "Activate Voice" to start listening for "Hey Swarm"
- Say "Hey Swarm" followed by your command
- AI responses are spoken aloud (toggleable)
- Say "Stop" to interrupt speech
- Click mic button in input area for direct voice input

BROWSER SUPPORT:
- Chrome (recommended - best support)
- Edge (good support)
- Safari (partial support)
- Firefox (limited support)

=============================================================================
*/

// =============================================================================
// 1. VOICE STATE VARIABLES
// =============================================================================

var voiceModeActive = false;
var isListening = false;
var isRecording = false;
var isSpeaking = false;
var wakeWordDetected = false;
var voiceResponseEnabled = true;

var speechRecognition = null;
var speechSynthesis = window.speechSynthesis;
var currentUtterance = null;
var recognitionRestarting = false;
var conversationObserver = null;
var lastSpokenMessageId = null;

var WAKE_WORD = 'hey swarm';
var STOP_WORDS = ['stop', 'cancel', 'quiet', 'shut up', 'be quiet'];

// =============================================================================
// 2. INITIALIZATION
// =============================================================================

function initVoice() {
    console.log('🎤 Initializing Voice Control System...');
    
    if (!checkVoiceSupport()) {
        console.warn('Voice control not fully supported in this browser');
        disableVoiceUI('Voice not supported in this browser. Use Chrome for best experience.');
        return;
    }
    
    if (speechSynthesis) {
        speechSynthesis.getVoices();
        if (speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = function() {
                speechSynthesis.getVoices();
            };
        }
    }
    
    initSpeechRecognition();
    setupMessageObserver();
    
    updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
    updateVoiceUI();
    
    console.log('✅ Voice Control System initialized');
}

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
    
    speechRecognition.onresult = function(event) {
        handleSpeechResult(event);
    };
    
    speechRecognition.onstart = function() {
        console.log('🎤 Speech recognition started');
        isListening = true;
        updateVoiceUI();
    };
    
    speechRecognition.onend = function() {
        console.log('🎤 Speech recognition ended');
        isListening = false;
        
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
    
    speechRecognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        
        if (event.error === 'not-allowed') {
            updateVoiceStatus('error', 'Microphone access denied. Please allow microphone access.');
            voiceModeActive = false;
        } else if (event.error === 'no-speech') {
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
// 3. MESSAGE OBSERVER (CLEAN INTEGRATION)
// =============================================================================

/**
 * Set up a MutationObserver to watch for new assistant messages
 * This is a clean way to detect when the AI responds without modifying swarm-app.js
 */
function setupMessageObserver() {
    var conversationDiv = document.getElementById('conversation');
    if (!conversationDiv) {
        // Try again after a short delay if DOM isn't ready
        setTimeout(setupMessageObserver, 500);
        return;
    }
    
    conversationObserver = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                // Check if this is an assistant message
                if (node.nodeType === 1 && node.classList && node.classList.contains('message') && node.classList.contains('assistant')) {
                    // Don't speak if voice mode is off or voice responses are disabled
                    if (!voiceModeActive || !voiceResponseEnabled) {
                        return;
                    }
                    
                    // Don't speak the same message twice
                    var msgId = node.id;
                    if (msgId && msgId === lastSpokenMessageId) {
                        return;
                    }
                    lastSpokenMessageId = msgId;
                    
                    // Get the message content
                    var contentDiv = node.querySelector('.message-content');
                    if (contentDiv) {
                        var text = contentDiv.innerText || contentDiv.textContent || '';
                        if (text && text.length > 0) {
                            // Small delay to let the UI finish updating
                            setTimeout(function() {
                                speakResponse(text);
                            }, 300);
                        }
                    }
                }
            });
        });
    });
    
    conversationObserver.observe(conversationDiv, {
        childList: true,
        subtree: false
    });
    
    console.log('🎤 Message observer set up');
}

// =============================================================================
// 4. VOICE ACTIVATION CONTROLS
// =============================================================================

function toggleVoiceMode() {
    if (voiceModeActive) {
        deactivateVoiceMode();
    } else {
        activateVoiceMode();
    }
}

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
    
    playActivationSound();
    
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

function deactivateVoiceMode() {
    voiceModeActive = false;
    isListening = false;
    isRecording = false;
    wakeWordDetected = false;
    
    if (speechRecognition) {
        try {
            speechRecognition.stop();
        } catch (e) {
            // Ignore
        }
    }
    
    stopSpeaking();
    
    updateVoiceStatus('inactive', 'Voice inactive - Click to activate');
    updateVoiceUI();
    
    console.log('🎤 Voice mode deactivated');
}

function startVoiceInput() {
    if (!speechRecognition) {
        initSpeechRecognition();
        if (!speechRecognition) {
            alert('Voice recognition not supported in this browser. Please use Chrome.');
            return;
        }
    }
    
    if (isSpeaking) {
        stopSpeaking();
        return;
    }
    
    if (isRecording) {
        finishRecording();
        return;
    }
    
    // Temporarily activate voice mode for direct input
    if (!voiceModeActive) {
        voiceModeActive = true;
        try {
            speechRecognition.start();
        } catch (e) {
            console.error('Error starting speech recognition:', e);
        }
    }
    
    playActivationSound();
    startRecording();
}

// =============================================================================
// 5. SPEECH RECOGNITION HANDLING
// =============================================================================

function handleSpeechResult(event) {
    var transcript = '';
    var isFinal = false;
    
    for (var i = event.resultIndex; i < event.results.length; i++) {
        var result = event.results[i];
        transcript += result[0].transcript;
        if (result.isFinal) {
            isFinal = true;
        }
    }
    
    transcript = transcript.toLowerCase().trim();
    console.log('🎤 Heard:', transcript, '(final:', isFinal, ')');
    
    if (isSpeaking && containsStopWord(transcript)) {
        stopSpeaking();
        return;
    }
    
    if (isRecording) {
        var input = document.getElementById('userInput');
        if (input) {
            var displayText = transcript.charAt(0).toUpperCase() + transcript.slice(1);
            input.value = displayText;
        }
        
        if (isFinal) {
            processVoiceCommand(transcript);
        }
        return;
    }
    
    if (!isRecording && transcript.indexOf(WAKE_WORD) !== -1) {
        console.log('🎤 Wake word detected!');
        wakeWordDetected = true;
        
        var wakeIndex = transcript.indexOf(WAKE_WORD);
        var afterWake = transcript.substring(wakeIndex + WAKE_WORD.length).trim();
        
        startRecording();
        
        if (afterWake && afterWake.length > 2) {
            var input = document.getElementById('userInput');
            if (input) {
                input.value = afterWake.charAt(0).toUpperCase() + afterWake.slice(1);
            }
        }
    }
}

function containsStopWord(transcript) {
    for (var i = 0; i < STOP_WORDS.length; i++) {
        if (transcript.indexOf(STOP_WORDS[i]) !== -1) {
            return true;
        }
    }
    return false;
}

function startRecording() {
    isRecording = true;
    wakeWordDetected = true;
    
    playBeep(600, 100);
    
    updateVoiceStatus('recording', 'Listening... Speak your command');
    updateVoiceUI();
    
    var input = document.getElementById('userInput');
    if (input) {
        input.value = '';
        input.placeholder = 'Listening...';
    }
    
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

function finishRecording() {
    isRecording = false;
    
    var input = document.getElementById('userInput');
    var command = input ? input.value.trim() : '';
    
    if (command.length > 0) {
        playBeep(800, 100);
        
        // Call the sendMessage function from swarm-app.js
        if (typeof sendMessage === 'function') {
            sendMessage();
        } else {
            console.error('sendMessage function not found');
        }
        
        updateVoiceStatus('processing', 'Processing your request...');
    } else {
        updateVoiceStatus('listening', 'Say "Hey Swarm" to begin...');
    }
    
    if (input) {
        input.placeholder = "Type your request here... or say 'Hey Swarm'";
    }
    
    wakeWordDetected = false;
    updateVoiceUI();
    
    console.log('🎤 Recording finished');
}

function processVoiceCommand(transcript) {
    var command = transcript.trim();
    
    if (command.toLowerCase().indexOf(WAKE_WORD) === 0) {
        command = command.substring(WAKE_WORD.length).trim();
    }
    
    if (command.length < 2) {
        return;
    }
    
    command = command.charAt(0).toUpperCase() + command.slice(1);
    
    var input = document.getElementById('userInput');
    if (input) {
        input.value = command;
    }
    
    finishRecording();
}

// =============================================================================
// 6. TEXT-TO-SPEECH
// =============================================================================

function speakResponse(text) {
    if (!voiceResponseEnabled || !speechSynthesis) {
        return;
    }
    
    if (!text || typeof text !== 'string') {
        console.log('🔊 No valid text to speak');
        return;
    }
    
    var cleanText = cleanTextForSpeech(text);
    
    if (!cleanText || cleanText.length === 0) {
        console.log('🔊 Text empty after cleaning');
        return;
    }
    
    stopSpeaking();
    
    currentUtterance = new SpeechSynthesisUtterance(cleanText);
    currentUtterance.rate = 1.0;
    currentUtterance.pitch = 1.0;
    currentUtterance.volume = 1.0;
    
    var voices = speechSynthesis.getVoices();
    var preferredVoice = null;
    
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
    
    isSpeaking = true;
    updateVoiceUI();
    speechSynthesis.speak(currentUtterance);
}

function cleanTextForSpeech(text) {
    if (!text) return '';
    
    // Remove HTML tags
    var cleaned = text.replace(/<[^>]*>/g, ' ');
    
    // Remove markdown formatting
    cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
    cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
    cleaned = cleaned.replace(/#{1,6}\s*/g, '');
    cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
    cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    
    // Remove emojis and special characters
    cleaned = cleaned.replace(/[•●○◦▪▫]/g, '');
    cleaned = cleaned.replace(/━+/g, '');
    cleaned = cleaned.replace(/─+/g, '');
    cleaned = cleaned.replace(/[📊📋📄📁💰💡✅❌⚠️🎯🔍📝📈📉🧮🤖👤🧠📎🎨📚🔗⬇️]/g, '');
    
    // Remove badge text
    cleaned = cleaned.replace(/Knowledge|Memory|Formatted|Project|Quick Task/gi, '');
    
    // Clean up whitespace
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    
    // Limit length
    if (cleaned.length > 800) {
        cleaned = cleaned.substring(0, 800);
        var lastSentence = cleaned.lastIndexOf('.');
        if (lastSentence > 400) {
            cleaned = cleaned.substring(0, lastSentence + 1);
        }
        cleaned += ' For more details, please see the full response on screen.';
    }
    
    return cleaned;
}

function stopSpeaking() {
    if (speechSynthesis) {
        speechSynthesis.cancel();
    }
    isSpeaking = false;
    currentUtterance = null;
    updateVoiceUI();
    console.log('🔊 Speech stopped');
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

function speakMessage(msgId) {
    var content = document.getElementById('content_' + msgId);
    if (content) {
        var text = content.innerText || content.textContent;
        if (text) {
            speakResponse(text);
        }
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
        } else if (voiceModeActive) {
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

// =============================================================================
// 8. AUDIO FEEDBACK
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
        // Audio not supported
    }
}

// =============================================================================
// 9. INITIALIZATION
// =============================================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoice);
} else {
    initVoice();
}

/* I did no harm and this file is not truncated */
