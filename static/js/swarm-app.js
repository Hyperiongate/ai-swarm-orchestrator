/*
=============================================================================
SWARM-APP.JS - AI Swarm Unified Interface JavaScript
Shiftwork Solutions LLC
=============================================================================
CHANGE LOG:

- February 18, 2026: FIXED AUTO-REFRESH AND PROGRESS INDICATOR
  * Fixed refreshConversationMessages() - was comparing DOM count to server
    count which was unreliable. Now uses lastKnownMessageCount variable that
    tracks the server-side message count properly.
  * Fixed startBackgroundJobPolling() - now injects a persistent animated
    progress banner into the conversation area so the user always knows
    analysis is running, even if they scroll or wait a long time.
  * Fixed stopBackgroundJobPolling() - now removes the progress banner when
    analysis completes so the UI is clean.
  * Fixed acceptLaborAnalysis() - sets lastKnownMessageCount from the
    current conversation state before polling starts, so the comparison
    baseline is correct from the first poll.
  * Loading spinner now hides immediately after "background started" message
    but progress banner remains visible throughout background processing.

- February 15, 2026: ADDED AUTO-REFRESH FOR LABOR ANALYSIS
  * Added startBackgroundJobPolling() function
  * Added stopBackgroundJobPolling() function
  * Added refreshConversationMessages() function
  * Added addMessageFromHistoryWithMetadata() function for download buttons
  * Updated acceptLaborAnalysis() to start auto-refresh polling

- February 5, 2026: ADDED PATTERN RECOGNITION DASHBOARD
  * Added loadPatternRecognition() function
  * Added generatePatternInsightsHTML() function
  * New Section 18: Pattern Recognition Dashboard
  * Dashboard shows interaction stats, top tasks, time patterns, communication style

- February 1, 2026: BULLETPROOF FILE BROWSER FIX
  * Added comprehensive debugging to file browser
  * Added safety checks for file.file_id vs file.id
  * Added validation before sending file_ids to backend
  * Added console logging for troubleshooting
  * Fixed undefined file ID bug in toggleFileSelection()

- January 31, 2026: FIXED PROJECT PERSISTENCE
  * Changed startNewProject() to use /api/projects/create endpoint (bulletproof backend)
  * Added description field to project creation request
  * Updated loadSavedProjects() to handle new response format with project_phase
  * Projects now persist across page refreshes with full bulletproof features
  * Added sessionStorage to remember selected project after creation

SECTIONS:
1. Global State Variables
2. Conversation Memory Functions
3. Clarification Handling Functions
4. File Upload Handling
5. Clipboard Functions
6. Mode Switching
7. Quick Actions
8. Project Management
9. Message Handling (Core)
10. Feedback System
11. Statistics & Documents
12. Marketing Functions
13. Calculator Functions
14. Survey Functions
15. Opportunities Functions
16. File Browser (BULLETPROOFED February 1, 2026)
17. Pattern Recognition Dashboard
18. Labor Analysis Functions (FIXED February 18, 2026)
19. Initialization

=============================================================================
*/

// =============================================================================
// 1. GLOBAL STATE VARIABLES
// =============================================================================

var currentMode = 'quick';
var currentProjectId = null;
var messageCounter = 0;
var feedbackRatings = {};
var uploadedFiles = [];
var currentConversationId = null;
var conversations = [];
var pendingClarification = null;
var backgroundJobPolling = null;

// FIX February 18, 2026: Tracks server-side message count so polling
// comparison is reliable (not based on DOM element count which is unpredictable)
var lastKnownMessageCount = 0;

// =============================================================================
// 2. CONVERSATION MEMORY FUNCTIONS
// =============================================================================

function loadConversations() {
    fetch('/api/conversations?limit=20')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success && data.conversations) {
                conversations = data.conversations;
                renderConversationList();
            } else {
                conversations = [];
                renderConversationList();
            }
        })
        .catch(function(err) {
            console.error('Error loading conversations:', err);
            conversations = [];
            renderConversationList();
        });
}

function renderConversationList() {
    var listContainer = document.getElementById('conversationsList');
    if (!listContainer) return;
    
    if (conversations.length === 0) {
        listContainer.innerHTML = '<div class="conversations-empty">No conversations yet.<br>Start chatting to create one!</div>';
        return;
    }
    
    var html = '';
    conversations.forEach(function(conv) {
        var isActive = conv.conversation_id === currentConversationId;
        var title = truncateTitle(conv.title || 'New Conversation', 50);
        var dateStr = formatConversationDate(conv.updated_at);
        var messageCount = conv.message_count || 0;
        
        html += '<div class="conversation-item ' + (isActive ? 'active' : '') + '" ';
        html += 'onclick="loadConversation(\'' + conv.conversation_id + '\')" ';
        html += 'data-id="' + conv.conversation_id + '">';
        html += '<div class="conversation-item-content">';
        html += '<div class="conversation-item-title" title="' + escapeHtml(conv.title || 'New Conversation') + '">';
        html += escapeHtml(title);
        html += '</div>';
        html += '<div class="conversation-item-meta">';
        html += '<span class="conversation-item-date">' + dateStr + '</span>';
        html += '<span class="conversation-item-count">' + messageCount + ' msg' + (messageCount !== 1 ? 's' : '') + '</span>';
        html += '</div>';
        html += '</div>';
        html += '<button class="conversation-delete-btn" ';
        html += 'onclick="deleteConversation(event, \'' + conv.conversation_id + '\')" ';
        html += 'title="Delete conversation">🗑️</button>';
        html += '</div>';
    });
    
    listContainer.innerHTML = html;
}

function startNewConversation() {
    updateMemoryIndicator(false, 0, 'Creating new conversation...');
    
    fetch('/api/conversations', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            mode: currentMode,
            title: 'New Conversation'
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success && data.conversation_id) {
            currentConversationId = data.conversation_id;
            localStorage.setItem('currentConversationId', currentConversationId);
            clearConversationArea();
            updateMemoryIndicator(true, 0);
            loadConversations();
            updateUrlWithConversation(currentConversationId);
        } else {
            updateMemoryIndicator(false, 0, 'Failed to create conversation');
        }
    })
    .catch(function(err) {
        updateMemoryIndicator(false, 0, 'Error creating conversation');
    });
}

function loadConversation(conversationId) {
    if (!conversationId) return;
    
    updateMemoryIndicator(false, 0, 'Loading conversation...');
    
    fetch('/api/conversations/' + conversationId)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                currentConversationId = conversationId;
                localStorage.setItem('currentConversationId', currentConversationId);
                updateUrlWithConversation(currentConversationId);
                clearConversationArea();
                
                if (data.messages && data.messages.length > 0) {
                    // FIX February 18, 2026: Update lastKnownMessageCount when loading a conversation
                    lastKnownMessageCount = data.messages.length;
                    data.messages.forEach(function(msg) {
                        addMessageFromHistory(msg.role, msg.content, msg.created_at);
                    });
                    updateMemoryIndicator(true, data.messages.length);
                } else {
                    lastKnownMessageCount = 0;
                    updateMemoryIndicator(true, 0);
                }
                
                if (data.conversation && data.conversation.mode) {
                    switchMode(data.conversation.mode);
                }
                
                renderConversationList();
            } else {
                updateMemoryIndicator(false, 0, 'Failed to load conversation');
            }
        })
        .catch(function(err) {
            updateMemoryIndicator(false, 0, 'Error loading conversation');
        });
}

function deleteConversation(event, conversationId) {
    event.stopPropagation();
    
    if (!confirm('Are you sure you want to delete this conversation? This cannot be undone.')) {
        return;
    }
    
    fetch('/api/conversations/' + conversationId, { method: 'DELETE' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            conversations = conversations.filter(function(c) { 
                return c.conversation_id !== conversationId; 
            });
            
            if (currentConversationId === conversationId) {
                currentConversationId = null;
                localStorage.removeItem('currentConversationId');
                
                if (conversations.length > 0) {
                    loadConversation(conversations[0].conversation_id);
                } else {
                    startNewConversation();
                }
            } else {
                renderConversationList();
            }
        } else {
            alert('Failed to delete conversation');
        }
    })
    .catch(function(err) {
        alert('Error deleting conversation');
    });
}

function updateMemoryIndicator(hasMemory, count, customMessage) {
    var indicator = document.getElementById('memoryStatus');
    if (!indicator) return;
    
    if (customMessage) {
        indicator.className = 'memory-status warning';
        indicator.innerHTML = '<span class="memory-icon">⏳</span><span class="memory-text">' + customMessage + '</span>';
        return;
    }
    
    if (hasMemory && currentConversationId) {
        indicator.className = 'memory-status active';
        indicator.innerHTML = '<span class="memory-icon">🧠</span>';
        indicator.innerHTML += '<span class="memory-text">Conversation memory active - ' + count + ' message' + (count !== 1 ? 's' : '') + ' in context</span>';
        indicator.innerHTML += '<span class="memory-link" onclick="copyConversationLink()" title="Copy link to this conversation">🔗 Share</span>';
    } else {
        indicator.className = 'memory-status warning';
        indicator.innerHTML = '<span class="memory-icon">⚠️</span><span class="memory-text">No conversation ID - memory disabled</span>';
    }
}

function copyConversationLink() {
    if (!currentConversationId) {
        alert('No active conversation to share');
        return;
    }
    
    var url = window.location.origin + window.location.pathname + '?conversation=' + currentConversationId;
    
    navigator.clipboard.writeText(url).then(function() {
        var indicator = document.getElementById('memoryStatus');
        var textSpan = indicator.querySelector('.memory-text');
        var originalText = textSpan.textContent;
        textSpan.textContent = '✓ Link copied to clipboard!';
        setTimeout(function() { textSpan.textContent = originalText; }, 2000);
    }).catch(function(err) {
        alert('Failed to copy link');
    });
}

function clearConversationArea() {
    var conversation = document.getElementById('conversation');
    if (!conversation) return;
    
    conversation.innerHTML = '<div class="message assistant">' +
        '<div class="message-header">🤖 AI Swarm ' +
        '<span class="mode-indicator quick" id="initialModeIndicator">⚡ Quick Task Mode</span></div>' +
        '<div class="message-content">' +
        '<strong>Welcome to the unified AI Swarm interface!</strong>' +
        '<p style="margin-top: 10px;">Choose your mode:</p>' +
        '<ul style="margin-top: 10px; margin-left: 20px;">' +
        '<li><strong>⚡ Quick Task Mode:</strong> One-off requests, document creation, analysis</li>' +
        '<li><strong>📁 Project Mode:</strong> Full consulting engagements with context tracking</li>' +
        '<li><strong>🔬 Research Mode:</strong> Real-time industry intelligence and news</li>' +
        '<li><strong>🔔 Alerts Mode:</strong> Autonomous monitoring and notifications</li>' +
        '<li><strong>📊 Pipeline Mode:</strong> Lead scoring and sales pipeline management</li>' +
        '<li><strong>📝 Manuals Mode:</strong> Conversational implementation manual generation</li>' +
        '</ul></div></div>';
    
    messageCounter = 0;
}

function addMessageFromHistory(role, content, timestamp) {
    var conversation = document.getElementById('conversation');
    var messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + role;
    var msgId = 'msg_' + (++messageCounter);
    messageDiv.id = msgId;
    
    var header = role === 'user' ? '👤 You' : '🤖 AI Swarm';
    var timeStr = timestamp ? formatMessageTime(timestamp) : '';
    
    var copyBtn = '';
    if (role === 'assistant') {
        copyBtn = '<button onclick="copyToClipboard(event, \'' + msgId + '\')" style="background: none; border: 1px solid #e0e0e0; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; color: #666; margin-left: auto;">📋 Copy</button>';
    }
    
    messageDiv.innerHTML = '<div class="message-header">' + header + copyBtn + '</div>' +
        '<div class="message-content" id="content_' + msgId + '">' + content + '</div>' +
        (timeStr ? '<div class="message-timestamp">' + timeStr + '</div>' : '');
    
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
}

function addMessageFromHistoryWithMetadata(role, content, timestamp, metadata) {
    var conversation = document.getElementById('conversation');
    var messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + role;
    var msgId = 'msg_' + (++messageCounter);
    messageDiv.id = msgId;
    
    var header = role === 'user' ? '👤 You' : '🤖 AI Swarm';
    var timeStr = timestamp ? formatMessageTime(timestamp) : '';
    
    var copyBtn = '';
    if (role === 'assistant') {
        copyBtn = '<button onclick="copyToClipboard(event, \'' + msgId + '\')" style="background: none; border: 1px solid #e0e0e0; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; color: #666; margin-left: auto;">📋 Copy</button>';
    }
    
    var downloadSection = '';
    if (role === 'assistant' && metadata) {
        try {
            var meta = typeof metadata === 'string' ? JSON.parse(metadata) : metadata;
            
            if (meta.document_created && meta.document_id) {
                var docUrl = meta.document_url || '/api/generated-documents/' + meta.document_id + '/download';
                var docName = meta.document_name || 'Labor_Analysis_Report.xlsx';
                var docType = (meta.document_type || 'xlsx').toUpperCase();
                
                downloadSection = '<div style="margin-top: 20px; padding: 15px; background: linear-gradient(135deg, #e8f5e9 0%, #e3f2fd 100%); border-radius: 10px; border-left: 4px solid #4caf50;">';
                downloadSection += '<div style="font-size: 14px; font-weight: 600; color: #2e7d32; margin-bottom: 10px;">📊 Complete Analysis Report</div>';
                downloadSection += '<a href="' + docUrl + '" download="' + docName + '" style="display: inline-block; padding: 12px 24px; background: linear-gradient(135deg, #4caf50 0%, #66bb6a 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; box-shadow: 0 2px 8px rgba(76,175,80,0.3);">⬇️ Download ' + docType + ' Report</a>';
                downloadSection += '<div style="margin-top: 10px; font-size: 11px; color: #666;">File: ' + docName + '</div>';
                downloadSection += '</div>';
            }
        } catch (e) {
            console.error('Error parsing metadata:', e);
        }
    }
    
    messageDiv.innerHTML = '<div class="message-header">' + header + copyBtn + '</div>' +
        '<div class="message-content" id="content_' + msgId + '">' + content + downloadSection + '</div>' +
        (timeStr ? '<div class="message-timestamp">' + timeStr + '</div>' : '');
    
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
}

function formatConversationDate(dateString) {
    if (!dateString) return '';
    var date = new Date(dateString);
    var now = new Date();
    var diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        if (date.toDateString() === now.toDateString()) return 'Today';
        return 'Yesterday';
    } else if (diffDays === 1) {
        return 'Yesterday';
    } else if (diffDays < 7) {
        return diffDays + ' days ago';
    } else {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
}

function formatMessageTime(dateString) {
    if (!dateString) return '';
    var date = new Date(dateString);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function truncateTitle(title, maxLength) {
    if (!title) return 'New Conversation';
    if (title.length <= maxLength) return title;
    return title.substring(0, maxLength - 3) + '...';
}

function generateConversationTitle(message) {
    if (!message) return 'New Conversation';
    var title = message.trim().replace(/\s+/g, ' ');
    var prefixes = ['Please ', 'Can you ', 'Could you ', 'I need ', 'I want ', 'Help me '];
    for (var i = 0; i < prefixes.length; i++) {
        if (title.toLowerCase().indexOf(prefixes[i].toLowerCase()) === 0) {
            title = title.substring(prefixes[i].length);
            break;
        }
    }
    title = title.charAt(0).toUpperCase() + title.slice(1);
    return truncateTitle(title, 50);
}

function updateUrlWithConversation(conversationId) {
    var url = new URL(window.location);
    if (conversationId) {
        url.searchParams.set('conversation', conversationId);
    } else {
        url.searchParams.delete('conversation');
    }
    window.history.replaceState({}, '', url);
}

function getConversationIdFromUrl() {
    var urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('conversation');
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateConversationTitle(conversationId, title) {
    if (!conversationId || !title) return;
    
    fetch('/api/conversations/' + conversationId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ title: title })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            for (var i = 0; i < conversations.length; i++) {
                if (conversations[i].conversation_id === conversationId) {
                    conversations[i].title = title;
                    renderConversationList();
                    break;
                }
            }
        }
    });
}

// =============================================================================
// 3. CLARIFICATION HANDLING FUNCTIONS
// =============================================================================

function handleClarificationResponse(data) {
    pendingClarification = {
        task_id: data.task_id,
        conversation_id: data.conversation_id,
        clarification_data: data.clarification_data,
        original_request: document.getElementById('userInput').dataset.lastRequest || ''
    };
    
    var clarificationUI = buildClarificationUI(data.clarification_data);
    addMessage('assistant', clarificationUI, null, currentMode);
}

function buildClarificationUI(clarificationData) {
    var html = '<div class="clarification-container" style="background: linear-gradient(135deg, #e8f5e9 0%, #f3e5f5 100%); border-radius: 12px; padding: 20px; margin: 10px 0;">';
    
    html += '<div style="font-weight: 600; font-size: 16px; color: #333; margin-bottom: 15px;">';
    html += '🤔 ' + (clarificationData.message || 'I need a few details to give you the best result:');
    html += '</div>';
    
    if (clarificationData.required_questions && clarificationData.required_questions.length > 0) {
        html += '<div style="margin-bottom: 20px;">';
        html += '<div style="font-size: 12px; color: #d32f2f; font-weight: 600; margin-bottom: 10px;">⚡ Required</div>';
        clarificationData.required_questions.forEach(function(q, idx) {
            html += buildQuestionElement(q, 'required_' + idx, true);
        });
        html += '</div>';
    }
    
    if (clarificationData.optional_questions && clarificationData.optional_questions.length > 0) {
        html += '<div style="margin-bottom: 20px;">';
        html += '<div style="font-size: 12px; color: #666; font-weight: 600; margin-bottom: 10px;">📝 Optional</div>';
        clarificationData.optional_questions.forEach(function(q, idx) {
            html += buildQuestionElement(q, 'optional_' + idx, false);
        });
        html += '</div>';
    }
    
    html += '<div style="margin-top: 20px; text-align: center;">';
    html += '<button onclick="submitClarificationAnswers()" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 8px; font-weight: 600; cursor: pointer;">✨ Get My Answer</button>';
    html += '</div></div>';
    
    return html;
}

function buildQuestionElement(question, fieldId, isRequired) {
    var html = '<div class="clarification-question" style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px;">';
    html += '<div style="font-weight: 500; color: #333; margin-bottom: 8px;">' + escapeHtml(question.question);
    if (isRequired) html += ' <span style="color: #d32f2f;">*</span>';
    html += '</div>';
    
    if (question.why) {
        html += '<div style="font-size: 11px; color: #888; margin-bottom: 10px;">💡 ' + escapeHtml(question.why) + '</div>';
    }
    
    if (question.options && question.options.length > 0) {
        html += '<div class="clarification-options" style="display: flex; flex-wrap: wrap; gap: 8px;">';
        question.options.forEach(function(option) {
            html += '<button type="button" class="clarification-option" data-field="' + escapeHtml(question.field) + '" data-value="' + escapeHtml(option) + '" onclick="selectClarificationOption(this)" style="background: #f5f5f5; border: 2px solid #e0e0e0; padding: 8px 16px; border-radius: 20px; cursor: pointer;">' + escapeHtml(option) + '</button>';
        });
        html += '</div>';
    }
    
    html += '<input type="hidden" class="clarification-field" data-field="' + escapeHtml(question.field) + '" data-required="' + isRequired + '" value="">';
    html += '</div>';
    return html;
}

function selectClarificationOption(button) {
    var field = button.getAttribute('data-field');
    var value = button.getAttribute('data-value');
    
    var allButtons = document.querySelectorAll('.clarification-option[data-field="' + field + '"]');
    allButtons.forEach(function(btn) {
        btn.style.background = '#f5f5f5';
        btn.style.borderColor = '#e0e0e0';
        btn.style.color = '#333';
    });
    
    button.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
    button.style.borderColor = '#667eea';
    button.style.color = 'white';
    
    var hiddenInput = document.querySelector('.clarification-field[data-field="' + field + '"]');
    if (hiddenInput) hiddenInput.value = value;
}

function submitClarificationAnswers() {
    if (!pendingClarification) return;
    
    var answers = {};
    var missingRequired = [];
    
    document.querySelectorAll('.clarification-field').forEach(function(field) {
        var fieldName = field.getAttribute('data-field');
        var isRequired = field.getAttribute('data-required') === 'true';
        var value = field.value;
        
        if (value) answers[fieldName] = value;
        else if (isRequired) missingRequired.push(fieldName);
    });
    
    if (missingRequired.length > 0) {
        alert('Please answer required questions: ' + missingRequired.join(', '));
        return;
    }
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    var formData = new FormData();
    formData.append('request', pendingClarification.original_request || 'Please provide the answer');
    formData.append('enable_consensus', 'true');
    formData.append('clarification_answers', JSON.stringify(answers));
    formData.append('task_id', pendingClarification.task_id);
    
    if (pendingClarification.conversation_id) {
        formData.append('conversation_id', pendingClarification.conversation_id);
    } else if (currentConversationId) {
        formData.append('conversation_id', currentConversationId);
    }
    
    pendingClarification = null;
    
    addMessage('user', '📝 ' + Object.keys(answers).map(function(k) { return k + ': ' + answers[k]; }).join(', '));
    
    fetch('/api/orchestrate', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        if (data.success) {
            if (data.needs_clarification) {
                handleClarificationResponse(data);
                return;
            }
            if (data.mode === 'analysis_offer' && data.session_id) {
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                    localStorage.setItem('currentConversationId', currentConversationId);
                    updateUrlWithConversation(currentConversationId);
                }
                sessionStorage.setItem('pending_labor_analysis', data.session_id);
                var offerHtml = data.response + '<div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">';
                offerHtml += '<button onclick="acceptLaborAnalysis(\'' + data.session_id + '\')" style="flex: 1; min-width: 150px; padding: 12px; background: linear-gradient(135deg, #4caf50 0%, #81c784 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">✅ Yes, analyze it</button>';
                offerHtml += '<button onclick="quickLaborSummary(\'' + data.session_id + '\')" style="flex: 1; min-width: 150px; padding: 12px; background: linear-gradient(135deg, #2196f3 0%, #64b5f6 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">📊 Quick summary</button>';
                offerHtml += '<button onclick="declineLaborAnalysis()" style="padding: 12px 20px; background: #f0f0f0; color: #666; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">Not now</button>';
                offerHtml += '</div>';
                addMessage('assistant', offerHtml, null, currentMode);
                updateMemoryIndicator(true, 2);
                loadConversations();
                return;
            }
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
                localStorage.setItem('currentConversationId', currentConversationId);
            }
            addMessage('assistant', data.result, data.task_id, currentMode, data);
            loadConversations();
            loadStats();
            loadDocuments();
        } else {
            addMessage('assistant', '❌ Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

// =============================================================================
// 4. FILE UPLOAD HANDLING
// =============================================================================

function handleFileUpload(event) {
    var files = Array.from(event.currentTarget.files);
    uploadedFiles = uploadedFiles.concat(files);
    displayFilePreview();
}

function displayFilePreview() {
    var preview = document.getElementById('filePreview');
    var fileList = document.getElementById('fileList');
    
    if (uploadedFiles.length === 0) {
        preview.style.display = 'none';
        return;
    }
    
    preview.style.display = 'block';
    fileList.innerHTML = '';
    
    uploadedFiles.forEach(function(file, index) {
        var fileTag = document.createElement('div');
        fileTag.style.cssText = 'display: inline-flex; align-items: center; gap: 5px; padding: 5px 10px; background: #e3f2fd; border-radius: 5px; font-size: 12px;';
        var icon = getFileIcon(file.name);
        fileTag.innerHTML = icon + ' ' + file.name + ' (' + formatFileSize(file.size) + ')' +
            '<button onclick="removeFile(' + index + ')" style="background: none; border: none; color: #d32f2f; cursor: pointer; margin-left: 5px; font-weight: bold;">×</button>';
        fileList.appendChild(fileTag);
    });
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    displayFilePreview();
}

function getFileIcon(filename) {
    var ext = filename.split('.').pop().toLowerCase();
    var icons = { 'pdf': '📄', 'docx': '📝', 'doc': '📝', 'xlsx': '📊', 'xls': '📊', 'csv': '📊', 'txt': '📃', 'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️' };
    return icons[ext] || '📎';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// =============================================================================
// 5. CLIPBOARD FUNCTIONS
// =============================================================================

function copyToClipboard(event, msgId) {
    var content = document.getElementById('content_' + msgId);
    if (!content) return;
    
    var text = content.innerText || content.textContent;
    
    navigator.clipboard.writeText(text).then(function() {
        var button = event.currentTarget;
        var originalText = button.innerHTML;
        button.innerHTML = '✓ Copied!';
        button.style.background = '#4caf50';
        button.style.color = 'white';
        setTimeout(function() {
            button.innerHTML = originalText;
            button.style.background = 'none';
            button.style.color = '#666';
        }, 2000);
    });
}

// =============================================================================
// 6. MODE SWITCHING
// =============================================================================

function switchMode(mode) {
    currentMode = mode;
    
    document.getElementById('quickModeBtn').classList.toggle('active', mode === 'quick');
    document.getElementById('projectModeBtn').classList.toggle('active', mode === 'project');
    document.getElementById('calculatorModeBtn').classList.toggle('active', mode === 'calculator');
    document.getElementById('surveyModeBtn').classList.toggle('active', mode === 'survey');
    document.getElementById('marketingModeBtn').classList.toggle('active', mode === 'marketing');
    document.getElementById('opportunitiesModeBtn').classList.toggle('active', mode === 'opportunities');
    
    var researchBtn = document.getElementById('researchModeBtn');
    if (researchBtn) researchBtn.classList.toggle('active', mode === 'research');
    
    var alertsBtn = document.getElementById('alertsModeBtn');
    if (alertsBtn) alertsBtn.classList.toggle('active', mode === 'alerts');
    
    var pipelineBtn = document.getElementById('pipelineModeBtn');
    if (pipelineBtn) pipelineBtn.classList.toggle('active', mode === 'pipeline');
    
    var manualsBtn = document.getElementById('manualsModeBtn');
    if (manualsBtn) manualsBtn.classList.toggle('active', mode === 'manuals');
    
    var casestudiesBtn = document.getElementById('casestudiesModeBtn');
    if (casestudiesBtn) casestudiesBtn.classList.toggle('active', mode === 'casestudies');
    
    document.getElementById('projectInfo').style.display = mode === 'project' ? 'block' : 'none';
    document.getElementById('calculatorInfo').style.display = mode === 'calculator' ? 'block' : 'none';
    document.getElementById('surveyInfo').style.display = mode === 'survey' ? 'block' : 'none';
    document.getElementById('marketingInfo').style.display = mode === 'marketing' ? 'block' : 'none';
    document.getElementById('opportunitiesInfo').style.display = mode === 'opportunities' ? 'block' : 'none';
    
    var researchInfo = document.getElementById('researchInfo');
    if (researchInfo) researchInfo.style.display = mode === 'research' ? 'block' : 'none';
    
    var alertsInfo = document.getElementById('alertsInfo');
    if (alertsInfo) alertsInfo.style.display = mode === 'alerts' ? 'block' : 'none';
    
    var pipelineInfo = document.getElementById('pipelineInfo');
    if (pipelineInfo) pipelineInfo.style.display = mode === 'pipeline' ? 'block' : 'none';
    
    var manualsInfo = document.getElementById('manualsInfo');
    if (manualsInfo) manualsInfo.style.display = mode === 'manuals' ? 'block' : 'none';
    
    var casestudiesInfo = document.getElementById('casestudiesInfo');
    if (casestudiesInfo) casestudiesInfo.style.display = mode === 'casestudies' ? 'block' : 'none';
    
    if (mode === 'project') loadSavedProjects();
    else if (mode === 'survey') loadQuestionBank();
    else if (mode === 'marketing') loadMarketingStatus();
    else if (mode === 'opportunities') loadNormativeStatus();
    else if (mode === 'research' && typeof checkResearchStatus === 'function') checkResearchStatus();
    else if (mode === 'alerts' && typeof checkAlertStatus === 'function') checkAlertStatus();
    else if (mode === 'pipeline' && typeof checkPipelineStatus === 'function') checkPipelineStatus();
    else if (mode === 'manuals' && typeof checkManualsStatus === 'function') checkManualsStatus();
    
    updateQuickActions();
    
    var input = document.getElementById('userInput');
    var placeholders = {
        'quick': "Type your request... (e.g., 'Create a schedule')",
        'project': "Type your request... (e.g., 'I need a data collection document')",
        'calculator': "Type your request... (e.g., 'Calculate overtime cost')",
        'survey': "Type your request... (e.g., 'Create a survey about weekend preferences')",
        'marketing': "Type your request... (e.g., 'Generate a LinkedIn post')",
        'opportunities': "Type your request... (e.g., 'Analyze my current schedule')",
        'research': "Type your research topic... (e.g., 'Latest OSHA fatigue regulations')",
        'alerts': "Type your request... (e.g., 'Add ABC Manufacturing to monitored clients')",
        'pipeline': "Type your request... (e.g., 'Show me high priority leads')",
        'manuals': "Type your request... (e.g., 'Create implementation manual for Acme Manufacturing')"
    };
    input.placeholder = placeholders[mode] || placeholders['quick'];
}

// =============================================================================
// 7. QUICK ACTIONS
// =============================================================================

function updateQuickActions() {
    var actions = document.getElementById('quickActions');
    
    var actionSets = {
        'quick': '<li onclick="quickAction(\'Analyze overtime costs\')">💰 Cost Analysis</li>' +
            '<li onclick="quickAction(\'Compare DuPont vs 2-2-3 schedules\')">⚖️ Compare Schedules</li>' +
            '<li onclick="quickAction(\'Write a LinkedIn post about shift work\')">💼 LinkedIn Post</li>',
        'research': '<li onclick="if(typeof searchIndustryNews===\'function\')searchIndustryNews()">📰 Industry News</li>' +
            '<li onclick="if(typeof searchRegulations===\'function\')searchRegulations()">⚖️ Regulations</li>' +
            '<li onclick="if(typeof searchStudies===\'function\')searchStudies()">🔬 Studies</li>' +
            '<li onclick="if(typeof getDailyBriefing===\'function\')getDailyBriefing()">📋 Daily Briefing</li>',
        'alerts': '<li onclick="if(typeof runLeadScan===\'function\')runLeadScan()">🎯 Run Lead Scan</li>' +
            '<li onclick="if(typeof viewScheduledJobs===\'function\')viewScheduledJobs()">📅 View Jobs</li>' +
            '<li onclick="if(typeof addMonitoredClient===\'function\')addMonitoredClient()">➕ Add Client</li>' +
            '<li onclick="if(typeof loadRecentAlerts===\'function\')loadRecentAlerts()">🔄 Refresh Alerts</li>',
        'pipeline': '<li onclick="if(typeof addNewLead===\'function\')addNewLead()">➕ Add Lead</li>' +
            '<li onclick="if(typeof importLeadsFromAlerts===\'function\')importLeadsFromAlerts()">📥 Import Alerts</li>' +
            '<li onclick="if(typeof viewAllLeads===\'function\')viewAllLeads()">👁️ View Pipeline</li>' +
            '<li onclick="quickAction(\'Show me high priority leads with score above 70\')">🔥 High Priority</li>',
        'manuals': '<li onclick="if(typeof startNewManual===\'function\')startNewManual()">➕ New Manual</li>' +
            '<li onclick="if(typeof viewAllManuals===\'function\')viewAllManuals()">👁️ All Manuals</li>' +
            '<li onclick="if(typeof viewLessons===\'function\')viewLessons()">💡 Lessons</li>' +
            '<li onclick="quickAction(\'Continue my manual for [client name]\')">📝 Continue</li>',
        'default': '<li onclick="quickAction(\'data collection\')">📋 Data Collection Doc</li>' +
            '<li onclick="quickAction(\'proposal\')">📄 Create Proposal</li>' +
            '<li onclick="quickAction(\'analyze files\')">📊 Analyze Files</li>' +
            '<li onclick="quickAction(\'linkedin post\')">💼 LinkedIn Post</li>'
    };
    
    actions.innerHTML = actionSets[currentMode] || actionSets['default'];
}

function quickAction(action) {
    document.getElementById('userInput').value = action;
    sendMessage();
}

// =============================================================================
// 8. PROJECT MANAGEMENT
// =============================================================================

function loadSavedProjects() {
    fetch('/api/projects')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var select = document.getElementById('existingProjects');
            if (!select) return;
            
            select.innerHTML = '<option value="">-- Select Project --</option>';
            
            var projects = [];
            if (data.success && data.projects) {
                projects = data.projects;
            } else if (Array.isArray(data)) {
                projects = data;
            }
            
            if (projects.length > 0) {
                projects.forEach(function(project) {
                    var option = document.createElement('option');
                    option.value = project.project_id;
                    var phase = project.project_phase || project.status || 'Active';
                    option.textContent = project.client_name + ' (' + phase + ')';
                    select.appendChild(option);
                });
                
                var lastProjectId = sessionStorage.getItem('lastSelectedProjectId');
                if (lastProjectId) {
                    select.value = lastProjectId;
                    if (select.value === lastProjectId) {
                        loadExistingProject();
                    }
                }
            }
        })
        .catch(function(err) {
            console.error('Error loading projects:', err);
        });
}

function loadExistingProject() {
    var select = document.getElementById('existingProjects');
    var projectId = select.value;
    
    if (!projectId) {
        currentProjectId = null;
        sessionStorage.removeItem('lastSelectedProjectId');
        document.getElementById('clientName').textContent = 'No active project';
        document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">Not started</div>';
        
        var fileList = document.getElementById('projectFilesList');
        if (fileList) {
            fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No project selected</div>';
        }
        updateFileCount(0);
        
        return;
    }
    
    sessionStorage.setItem('lastSelectedProjectId', projectId);
    
    fetch('/api/project/' + projectId + '/context')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                currentProjectId = projectId;
                document.getElementById('clientName').textContent = data.client_name;
                document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">' + data.phase + '</div>';
                addMessage('assistant', '✅ Loaded project for ' + data.client_name, null, 'project');
                loadProjectFiles();
            }
        });
}

function startNewProject() {
    var clientName = prompt("Enter client name:");
    if (!clientName) return;
    
    var industry = prompt("Enter industry (or press Cancel for default):");
    var facilityType = prompt("Enter facility type (or press Cancel for default):");
    
    fetch('/api/projects/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            client_name: clientName,
            industry: industry || 'Manufacturing',
            facility_type: facilityType || 'Production',
            description: 'Project for ' + clientName
        })
    })
    .then(function(r) {
        if (!r.ok && r.status === 500) {
            console.log('Bulletproof endpoint failed, trying legacy endpoint...');
            return fetch('/api/project/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    client_name: clientName,
                    industry: industry || 'Manufacturing',
                    facility_type: facilityType || 'Production'
                })
            });
        }
        return r;
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success && data.project_id) {
            currentProjectId = data.project_id;
            sessionStorage.setItem('lastSelectedProjectId', data.project_id);
            document.getElementById('clientName').textContent = clientName;
            document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">Initial Phase</div>';
            loadSavedProjects();
            
            var successMsg = '✅ <strong>Project created for ' + clientName + '!</strong><br><br>';
            successMsg += '📁 <strong>Project ID:</strong> ' + data.project_id + '<br><br>';
            successMsg += '<strong>Project features:</strong><br>';
            successMsg += '• ✅ Persistent storage<br>';
            successMsg += '• ✅ File management<br>';
            successMsg += '• ✅ Conversation tracking<br>';
            
            addMessage('assistant', successMsg, null, 'project');
        } else {
            addMessage('assistant', '❌ Error creating project: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

// =============================================================================
// 9. MESSAGE HANDLING (CORE)
// =============================================================================

function uploadFilesToProject(projectId, files) {
    return new Promise(function(resolve, reject) {
        var formData = new FormData();
        files.forEach(function(file) {
            formData.append('files', file);
        });
        
        fetch('/api/projects/' + projectId + '/files', {
            method: 'POST',
            body: formData
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                resolve(data.files);
            } else {
                reject(new Error(data.error || 'Upload failed'));
            }
        })
        .catch(reject);
    });
}

function sendMessage() {
    var input = document.getElementById('userInput');
    var message = input.value.trim();
    if (!message && uploadedFiles.length === 0) return;
    
    input.dataset.lastRequest = message;
    
    var hasFiles = uploadedFiles.length > 0;
    var inProjectMode = currentMode === 'project' && currentProjectId;
    
    if (hasFiles && inProjectMode) {
        var displayMessage = message || 'Uploading files to project';
        displayMessage += ' (' + uploadedFiles.length + ' file' + (uploadedFiles.length > 1 ? 's' : '') + ')';
        addMessage('user', displayMessage);
        
        input.value = '';
        var loading = document.getElementById('loadingIndicator');
        loading.classList.add('active');
        
        var filesToUpload = uploadedFiles.slice();
        uploadedFiles = [];
        displayFilePreview();
        
        var fileInput = document.getElementById('fileUpload');
        if (fileInput) fileInput.value = '';
        
        uploadFilesToProject(currentProjectId, filesToUpload)
            .then(function(uploadedFileInfo) {
                loading.classList.remove('active');
                
                var successMsg = '✅ <strong>Files saved to project!</strong><br><br>';
                uploadedFileInfo.forEach(function(file) {
                    successMsg += '📎 ' + file.original_filename + ' (' + formatFileSize(file.file_size) + ')<br>';
                });
                successMsg += '<br><div style="font-size: 11px; color: #666;">✓ Stored in project folder<br>✓ Available for future use<br>✓ Survives page refresh</div>';
                
                addMessage('assistant', successMsg, null, 'project');
                loadStats();
                loadDocuments();
                loadProjectFiles();
            })
            .catch(function(err) {
                loading.classList.remove('active');
                addMessage('assistant', '❌ Upload failed: ' + err.message);
            });
        
        return;
    }
    
    var displayMessage = message || 'Uploaded files for analysis';
    if (uploadedFiles.length > 0) {
        displayMessage += ' (' + uploadedFiles.length + ' file' + (uploadedFiles.length > 1 ? 's' : '') + ' attached)';
    }
    addMessage('user', displayMessage);
    
    input.value = '';
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    var formData = new FormData();
    formData.append('request', message || 'Please analyze the uploaded files');
    formData.append('enable_consensus', 'true');
    
    if (currentConversationId) formData.append('conversation_id', currentConversationId);
    if (currentMode === 'project' && currentProjectId) formData.append('project_id', currentProjectId);
    
    uploadedFiles.forEach(function(file) { formData.append('files', file); });
    
    var filesCount = uploadedFiles.length;
    uploadedFiles = [];
    displayFilePreview();
    
    var fileInput = document.getElementById('fileUpload');
    if (fileInput) fileInput.value = '';
    
    var isFirstMessage = !conversations.find(function(c) { return c.conversation_id === currentConversationId && c.message_count > 0; });
    
    fetch('/api/orchestrate', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            if (data.needs_clarification && data.clarification_data) {
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                    localStorage.setItem('currentConversationId', currentConversationId);
                }
                handleClarificationResponse(data);
                return;
            }
            if (data.mode === 'analysis_offer' && data.session_id) {
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                    localStorage.setItem('currentConversationId', currentConversationId);
                    updateUrlWithConversation(currentConversationId);
                }
                sessionStorage.setItem('pending_labor_analysis', data.session_id);
                var offerHtml = data.response + '<div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">';
                offerHtml += '<button onclick="acceptLaborAnalysis(\'' + data.session_id + '\')" style="flex: 1; min-width: 150px; padding: 12px; background: linear-gradient(135deg, #4caf50 0%, #81c784 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">✅ Yes, analyze it</button>';
                offerHtml += '<button onclick="quickLaborSummary(\'' + data.session_id + '\')" style="flex: 1; min-width: 150px; padding: 12px; background: linear-gradient(135deg, #2196f3 0%, #64b5f6 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">📊 Quick summary</button>';
                offerHtml += '<button onclick="declineLaborAnalysis()" style="padding: 12px 20px; background: #f0f0f0; color: #666; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">Not now</button>';
                offerHtml += '</div>';
                addMessage('assistant', offerHtml, null, currentMode);
                updateMemoryIndicator(true, 2);
                loadConversations();
                return;
            }
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
                localStorage.setItem('currentConversationId', currentConversationId);
                updateUrlWithConversation(currentConversationId);
            }
            
            if (isFirstMessage && currentConversationId && message) {
                updateConversationTitle(currentConversationId, generateConversationTitle(message));
            }
            
            var badges = '';
            if (data.knowledge_used) badges += '<span class="badge knowledge">📚 Knowledge</span>';
            if (currentConversationId) badges += '<span class="badge memory">🧠 Memory</span>';
            
            var downloadSection = '';
            
            if (data.document_url) {
                var docType = (data.document_type || 'docx').toUpperCase();
                downloadSection = '<div style="margin-top: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #4caf50; border-radius: 4px;">' +
                    '<a href="' + data.document_url + '" download style="padding: 8px 16px; background: #4caf50; color: white; text-decoration: none; border-radius: 6px;">⬇️ Download ' + docType + '</a></div>';
            }
            
            if (data.download_available && data.download_file) {
                var filename = data.download_filename || 'analysis.xlsx';
                downloadSection += '<div style="margin-top: 15px; padding: 12px; background: #e3f2fd; border-left: 4px solid #2196f3; border-radius: 4px;">' +
                    '<div style="margin-bottom: 8px; font-size: 13px; color: #1565c0; font-weight: 600;">📊 Complete Analysis Results</div>' +
                    '<a href="' + data.download_file + '" download="' + filename + '" style="padding: 8px 16px; background: #2196f3; color: white; text-decoration: none; border-radius: 6px; font-size: 14px;">⬇️ Download Excel (' + filename + ')</a>' +
                    '<div style="margin-top: 8px; font-size: 11px; color: #666;">Contains all rows from your analysis</div>' +
                    '</div>';
            }
            
            addMessage('assistant', data.result + '<div style="margin-top: 10px;">' + badges + '</div>' + downloadSection, data.task_id, currentMode, data);
            
            updateMemoryIndicator(true, 2);
            loadConversations();
            loadStats();
            loadDocuments(); 
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function addMessage(role, content, taskId, mode, data) {
    var conversation = document.getElementById('conversation');
    var messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + role;
    var msgId = 'msg_' + (++messageCounter);
    messageDiv.id = msgId;
    
    if (taskId) feedbackRatings[msgId] = { overall: 0, quality: 0, accuracy: 0, usefulness: 0 };
    
    var header = role === 'user' ? '👤 You' : '🤖 AI Swarm';
    
    var copyBtn = '';
    if (role === 'assistant') {
        copyBtn = '<button onclick="copyToClipboard(event, \'' + msgId + '\')" style="background: none; border: 1px solid #e0e0e0; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; color: #666; margin-left: auto;">📋 Copy</button>';
    }
    
    var feedbackSection = (role === 'assistant' && taskId) ? buildFeedbackSection(msgId, taskId) : '';
    
    messageDiv.innerHTML = '<div class="message-header">' + header + copyBtn + '</div>' +
        '<div class="message-content" id="content_' + msgId + '">' + content + '</div>' + feedbackSection;
    
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
}

function buildFeedbackSection(msgId, taskId) {
    var stars = function(type) {
        var html = '';
        for (var i = 1; i <= 5; i++) {
            html += '<span class="star" onclick="setRating(\'' + msgId + '\', \'' + type + '\', ' + i + ')">★</span>';
        }
        return html;
    };
    
    return '<div class="message-actions"><button class="btn-link" onclick="toggleFeedback(\'' + msgId + '\')">💬 Provide Feedback</button></div>' +
        '<div class="feedback-section" id="feedback_' + msgId + '">' +
        '<div class="feedback-header">📊 Rate This Output</div>' +
        '<div class="rating-row"><span class="rating-label">Overall:</span><div class="star-rating" id="stars_overall_' + msgId + '">' + stars('overall') + '</div></div>' +
        '<textarea class="feedback-input" id="comment_' + msgId + '" placeholder="Additional comments..."></textarea>' +
        '<div class="feedback-actions">' +
        '<button class="btn-feedback primary" onclick="submitFeedback(\'' + msgId + '\', ' + taskId + ', true)">✓ Submit</button>' +
        '</div></div>';
}

// =============================================================================
// 10. FEEDBACK SYSTEM
// =============================================================================

function toggleFeedback(msgId) {
    var feedback = document.getElementById('feedback_' + msgId);
    feedback.classList.toggle('active');
}

function setRating(msgId, type, rating) {
    feedbackRatings[msgId][type] = rating;
    var stars = document.querySelectorAll('#stars_' + type + '_' + msgId + ' .star');
    stars.forEach(function(star, idx) {
        star.classList.toggle('active', idx < rating);
    });
}

function submitFeedback(msgId, taskId, outputUsed) {
    var ratings = feedbackRatings[msgId];
    if (ratings.overall === 0) { alert('Please rate Overall Quality'); return; }
    
    var comment = document.getElementById('comment_' + msgId).value;
    
    fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            task_id: taskId,
            overall_rating: ratings.overall,
            quality_rating: ratings.quality || ratings.overall,
            accuracy_rating: ratings.accuracy || ratings.overall,
            usefulness_rating: ratings.usefulness || ratings.overall,
            user_comment: comment,
            output_used: outputUsed
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            document.getElementById('feedback_' + msgId).innerHTML = '<div class="feedback-success">✅ Feedback recorded!</div>';
            loadStats();
        }
    });
}

// =============================================================================
// 11. STATISTICS & DOCUMENTS
// =============================================================================

function loadStats() {
    fetch('/api/stats').then(function(r) { return r.json(); }).then(function(data) {
        document.getElementById('totalTasks').textContent = data.total_tasks || 0;
    });
    
    fetch('/api/learning/stats').then(function(r) { return r.json(); }).then(function(data) {
        if (data.average_overall_rating) document.getElementById('avgRating').textContent = data.average_overall_rating.toFixed(1) + '⭐';
        if (data.consensus_accuracy_rate) document.getElementById('consensusAccuracy').textContent = data.consensus_accuracy_rate + '%';
    });
}

function loadDocuments() {
    fetch('/api/documents')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var docsList = document.getElementById('documentsList');
            if (!data.success || (!data.generated_documents || data.generated_documents.length === 0)) {
                docsList.innerHTML = '<div style="color: #999; padding: 10px; text-align: center;">No documents yet</div>';
                return;
            }
            
            var html = '<div class="docs-section-header">📄 Your Documents</div>';
            data.generated_documents.forEach(function(doc) {
                html += '<div class="doc-item" style="padding: 8px; margin: 4px 0; background: #f9f9f9; border-radius: 6px; font-size: 11px;">';
                html += getDocTypeIcon(doc.type) + ' ' + escapeHtml(doc.title || doc.filename);
                html += ' <button onclick="downloadDocument(' + doc.id + ')" style="float: right; background: none; border: none; cursor: pointer;">⬇️</button>';
                html += '</div>';
            });
            docsList.innerHTML = html;
        });
}

function getDocTypeIcon(docType) {
    var icons = { 'docx': '📝', 'pdf': '📄', 'xlsx': '📊', 'pptx': '📽️' };
    return icons[docType] || '📎';
}

function downloadDocument(docId) {
    window.location.href = '/api/generated-documents/' + docId + '/download';
}

function refreshDocuments() {
    document.getElementById('documentsList').innerHTML = '<div style="color: #666; padding: 10px; text-align: center;">Loading...</div>';
    loadDocuments();
}

// =============================================================================
// 12-15. OTHER FUNCTIONS (Marketing, Calculator, Survey, Opportunities)
// =============================================================================

function loadMarketingStatus() {
    fetch('/api/marketing/status').then(function(r) { return r.json(); }).then(function(data) {
        var statusDiv = document.getElementById('platformStatus');
        if (data.platforms) statusDiv.innerHTML = '<div style="font-size: 11px;">✅ Marketing Hub Ready</div>';
    }).catch(function() {});
}

function generateMarketingIdea() { quickAction('🚀 Generate a marketing idea for shift work consulting'); }
function generateSocialPost() { var topic = prompt('What topic?'); if (topic) quickAction('Generate LinkedIn post about: ' + topic); }
function conductResearch() { var topic = prompt('Research topic?'); if (topic) quickAction('Market research on: ' + topic); }
function analyzeCompetitors() { quickAction('Analyze competitors in shift scheduling consulting'); }

function calculateOvertimeCost() { quickAction('Calculate overtime cost analysis'); }
function compareHireVsOT() { quickAction('Compare hiring vs overtime costs'); }
function scheduleImpact() { quickAction('Calculate schedule change financial impact'); }

function loadQuestionBank() {
    fetch('/api/survey/questions').then(function(r) { return r.json(); }).then(function(data) {
        var statusDiv = document.getElementById('questionBankStatus');
        if (data.success) statusDiv.innerHTML = '<div style="font-size: 11px;">✅ ' + data.total_count + ' questions ready</div>';
    }).catch(function() {});
}

function createNewSurvey() { var name = prompt('Project name?'); if (name) quickAction('Create survey for: ' + name); }
function viewSurveyResults() { var id = prompt('Survey ID?'); if (id) quickAction('View results for survey: ' + id); }
function exportSurveyData() { var id = prompt('Survey ID?'); if (id) quickAction('Export survey data: ' + id); }

function loadNormativeStatus() {
    fetch('/api/opportunities/status').then(function(r) { return r.json(); }).then(function(data) {
        var statusDiv = document.getElementById('normativeStatus');
        if (data.success) statusDiv.innerHTML = '<div style="font-size: 11px;">✅ Database ready</div>';
    }).catch(function() {});
}

function analyzeScheduleOpportunities() { var info = prompt('Describe your schedule:'); if (info) quickAction('Analyze: ' + info); }
function compareToNorms() { var metrics = prompt('Enter metrics:'); if (metrics) quickAction('Compare to norms: ' + metrics); }
function findImprovements() { quickAction('Find improvement opportunities'); }

// =============================================================================
// 16. FILE BROWSER FOR PROJECT MODE
// =============================================================================

var selectedFiles = [];

function loadProjectFiles() {
    if (!currentProjectId) {
        var fileList = document.getElementById('projectFilesList');
        if (fileList) {
            fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No project selected</div>';
        }
        updateFileCount(0);
        return;
    }
    
    console.log('🔍 Loading files for project:', currentProjectId);
    
    fetch('/api/projects/' + currentProjectId + '/files')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            console.log('📡 API Response:', data);
            
            if (data.success && data.files) {
                console.log('✅ Loaded', data.files.length, 'files');
                
                if (data.files.length > 0) {
                    console.log('📋 Sample file structure:', data.files[0]);
                }
                
                displayProjectFiles(data.files);
                updateFileCount(data.files.length);
            } else {
                var fileList = document.getElementById('projectFilesList');
                if (fileList) {
                    fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No files uploaded yet</div>';
                }
                updateFileCount(0);
            }
        })
        .catch(function(err) {
            console.error('❌ Error loading files:', err);
            var fileList = document.getElementById('projectFilesList');
            if (fileList) {
                fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #d32f2f;">Error loading files</div>';
            }
        });
}

function displayProjectFiles(files) {
    var fileList = document.getElementById('projectFilesList');
    if (!fileList) {
        console.warn('⚠️ projectFilesList element not found');
        return;
    }
    
    if (files.length === 0) {
        fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No files uploaded yet</div>';
        return;
    }
    
    var html = '';
    files.forEach(function(file, index) {
        var fileId = file.filename || file.id;
        
        if (!fileId) {
            console.error('❌ File missing ID at index', index, ':', file);
            return;
        }
        
        console.log('✅ Processing file:', fileId, '-', file.original_filename);
        
        var isSelected = selectedFiles.indexOf(fileId) !== -1;
        var icon = getFileIcon(file.original_filename || file.filename || '');
        var sizeStr = formatFileSize(file.file_size || 0);
        var dateStr = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : '';
        
        html += '<div class="file-item" data-file-id="' + escapeHtml(fileId) + '">';
        html += '  <input type="checkbox" class="file-checkbox" ' + (isSelected ? 'checked' : '') + ' onchange="toggleFileSelection(\'' + escapeHtml(fileId) + '\')">';
        html += '  <span class="file-icon">' + icon + '</span>';
        html += '  <div class="file-info">';
        html += '    <div class="file-name">' + escapeHtml(file.original_filename || file.filename || 'Unknown') + '</div>';
        html += '    <div class="file-meta">' + sizeStr + ' • ' + dateStr + '</div>';
        html += '  </div>';
        html += '  <div class="file-actions">';
        html += '    <button onclick="downloadProjectFile(\'' + escapeHtml(fileId) + '\', \'' + escapeHtml(file.original_filename || file.filename) + '\')" class="file-action-btn">⬇️</button>';
        html += '    <button onclick="deleteProjectFile(\'' + escapeHtml(fileId) + '\')" class="file-action-btn">🗑️</button>';
        html += '  </div>';
        html += '</div>';
    });
    
    fileList.innerHTML = html;
    console.log('✅ Rendered', files.length, 'files in browser');
}

function toggleFileSelection(fileId) {
    if (!fileId || fileId === 'undefined') {
        console.error('❌ Invalid fileId passed to toggleFileSelection:', fileId);
        return;
    }
    
    console.log('🔘 Toggling selection for:', fileId);
    
    var index = selectedFiles.indexOf(fileId);
    if (index === -1) {
        selectedFiles.push(fileId);
        console.log('✅ Selected:', fileId);
    } else {
        selectedFiles.splice(index, 1);
        console.log('❌ Deselected:', fileId);
    }
    
    console.log('📊 Currently selected files:', selectedFiles);
    updateSelectedCount();
}

function selectAllFiles() {
    var checkboxes = document.querySelectorAll('.file-checkbox');
    selectedFiles = [];
    checkboxes.forEach(function(cb) {
        cb.checked = true;
        var fileId = cb.closest('.file-item').getAttribute('data-file-id');
        if (fileId && fileId !== 'undefined') {
            selectedFiles.push(fileId);
        }
    });
    console.log('✅ Selected all files:', selectedFiles);
    updateSelectedCount();
}

function clearFileSelection() {
    var checkboxes = document.querySelectorAll('.file-checkbox');
    checkboxes.forEach(function(cb) {
        cb.checked = false;
    });
    selectedFiles = [];
    console.log('🔄 Cleared selection');
    updateSelectedCount();
}

function updateSelectedCount() {
    var countEl = document.getElementById('selectedFileCount');
    if (countEl) {
        countEl.textContent = selectedFiles.length + ' file' + (selectedFiles.length !== 1 ? 's' : '') + ' selected';
    }
    
    var actionBtns = document.querySelectorAll('.file-action-group button');
    actionBtns.forEach(function(btn) {
        btn.disabled = selectedFiles.length === 0;
    });
}

function updateFileCount(count) {
    var countEl = document.getElementById('projectFileCount');
    if (countEl) {
        countEl.textContent = count + ' file' + (count !== 1 ? 's' : '');
    }
}

function downloadProjectFile(fileId, filename) {
    console.log('⬇️ Downloading file:', fileId, filename);
    window.open('/api/projects/' + currentProjectId + '/files/' + fileId, '_blank');
}

function deleteProjectFile(fileId) {
    if (!confirm('Delete this file? This cannot be undone.')) return;
    
    console.log('🗑️ Deleting file:', fileId);
    
    fetch('/api/projects/' + currentProjectId + '/files/' + fileId, {
        method: 'DELETE'
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            console.log('✅ File deleted successfully');
            loadProjectFiles();
            addMessage('assistant', '✅ File deleted successfully');
        } else {
            console.error('❌ Failed to delete file:', data.error);
            addMessage('assistant', '❌ Failed to delete file: ' + data.error);
        }
    })
    .catch(function(err) {
        console.error('❌ Delete error:', err);
        addMessage('assistant', '❌ Error deleting file: ' + err.message);
    });
}

function performFileAction(action) {
    console.log('🎬 Performing action:', action);
    console.log('📋 Selected files:', selectedFiles);
    
    if (selectedFiles.length === 0) {
        alert('Please select at least one file');
        console.warn('⚠️ No files selected');
        return;
    }
    
    var invalidFiles = selectedFiles.filter(function(id) { return !id || id === 'undefined'; });
    if (invalidFiles.length > 0) {
        console.error('❌ Invalid file IDs detected:', invalidFiles);
        alert('Error: Some file IDs are invalid. Please refresh the page and try again.');
        return;
    }
    
    if (!currentProjectId) {
        console.error('❌ No project ID');
        alert('Error: No project selected');
        return;
    }
    
    var messages = {
        'analyze': 'Analyze these files and provide insights',
        'summarize': 'Summarize the key points from these files',
        'extract': 'Extract all data from these files into a structured format',
        'compare': 'Compare these files and highlight the differences'
    };
    
    var message = messages[action] || 'Process these files';
    
    console.log('📤 Sending request to AI with file_ids:', selectedFiles);
    
    fetch('/api/projects/' + currentProjectId + '/files')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                var selectedFileInfo = data.files.filter(function(f) {
                    var fileId = f.filename || f.id;
                    return selectedFiles.indexOf(fileId) !== -1;
                });
                
                var fileNames = selectedFileInfo.map(function(f) { 
                    return f.original_filename || f.filename || 'Unknown'; 
                }).join(', ');
                
                console.log('📝 File names:', fileNames);
                
                addMessage('user', message + ' (' + selectedFiles.length + ' file' + (selectedFiles.length !== 1 ? 's' : '') + ': ' + fileNames + ')');
                
                var formData = new FormData();
                formData.append('request', message);
                formData.append('project_id', currentProjectId);
                formData.append('file_ids', JSON.stringify(selectedFiles));
                
                console.log('📦 FormData prepared:');
                console.log('  - request:', message);
                console.log('  - project_id:', currentProjectId);
                console.log('  - file_ids:', JSON.stringify(selectedFiles));
                
                var loading = document.getElementById('loadingIndicator');
                loading.classList.add('active');
                
                fetch('/api/orchestrate', {
                    method: 'POST',
                    body: formData
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    loading.classList.remove('active');
                    console.log('✅ AI Response:', data);
                    
                    if (data.success) {
                        addMessage('assistant', data.result, data.task_id, 'project');
                    } else {
                        console.error('❌ AI Error:', data.error);
                        addMessage('assistant', '❌ Error: ' + data.error);
                    }
                })
                .catch(function(err) {
                    loading.classList.remove('active');
                    console.error('❌ Request error:', err);
                    addMessage('assistant', '❌ Error: ' + err.message);
                });
                
                clearFileSelection();
            }
        })
        .catch(function(err) {
            console.error('❌ Failed to get file info:', err);
            addMessage('assistant', '❌ Error: ' + err.message);
        });
}

// =============================================================================
// 17. PATTERN RECOGNITION DASHBOARD
// =============================================================================

function loadPatternRecognition() {
    fetch('/api/intelligence/patterns/dashboard')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                var dashboardHtml = generatePatternInsightsHTML(data);
                addMessage('assistant', dashboardHtml, null, currentMode);
            } else {
                addMessage('assistant', '⚠️ Pattern recognition data not available yet. Keep using the swarm to build your pattern profile!');
            }
        })
        .catch(function(err) {
            console.error('Error loading patterns:', err);
            addMessage('assistant', '❌ Error loading pattern insights: ' + err.message);
        });
}

function generatePatternInsightsHTML(data) {
    var summary = data.summary || {};
    var topTasks = data.top_task_types || [];
    var timePatterns = data.time_patterns || [];
    var commStyle = data.communication_style || {};
    
    var html = `
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 12px; color: white; margin: 15px 0;">
    <h2 style="margin: 0 0 10px 0; font-size: 22px;">🧠 Your AI Swarm Pattern Recognition Dashboard</h2>
    <p style="margin: 0; opacity: 0.9; font-size: 13px;">Based on ${summary.total_interactions || 0} interactions</p>
</div>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0;">
    <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #667eea;">
        <div style="font-size: 28px; font-weight: bold; color: #667eea;">${summary.total_interactions || 0}</div>
        <div style="font-size: 12px; color: #666; margin-top: 5px;">Total Interactions</div>
    </div>
    
    <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #4caf50;">
        <div style="font-size: 28px; font-weight: bold; color: #4caf50;">${summary.success_rate || 0}%</div>
        <div style="font-size: 12px; color: #666; margin-top: 5px;">Success Rate</div>
    </div>
    
    <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #ff9800;">
        <div style="font-size: 28px; font-weight: bold; color: #ff9800;">${summary.avg_response_time || 0}s</div>
        <div style="font-size: 12px; color: #666; margin-top: 5px;">Avg Response Time</div>
    </div>
    
    <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #e91e63;">
        <div style="font-size: 28px; font-weight: bold; color: #e91e63;">${summary.consensus_used || 0}%</div>
        <div style="font-size: 12px; color: #666; margin-top: 5px;">Consensus Mode</div>
    </div>
</div>

${topTasks.length > 0 ? `
<div style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
    <h3 style="margin: 0 0 15px 0; color: #667eea; font-size: 16px;">📊 Your Top Task Types</h3>
    <div style="display: flex; flex-direction: column; gap: 10px;">
        ${topTasks.slice(0, 5).map(function(task) {
            var percentage = task.percentage || 0;
            return `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="min-width: 150px; font-size: 13px; font-weight: 500;">${task.task_type || 'Unknown'}</div>
                    <div style="flex: 1; background: #f0f0f0; border-radius: 10px; height: 20px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #667eea, #764ba2); height: 100%; width: ${percentage}%; border-radius: 10px;"></div>
                    </div>
                    <div style="min-width: 40px; text-align: right; font-size: 12px; color: #666;">${task.count} (${percentage}%)</div>
                </div>
            `;
        }).join('')}
    </div>
</div>
` : ''}

${timePatterns.length > 0 ? `
<div style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
    <h3 style="margin: 0 0 15px 0; color: #4caf50; font-size: 16px;">⏰ Work Patterns</h3>
    <div style="border-left: 4px solid #4caf50; padding-left: 15px;">
        ${timePatterns.slice(0, 3).map(function(t) {
            return `
                <div style="margin: 10px 0;">
                    <span style="font-size: 14px;">✓ Most active on <strong>${t.day}s</strong> (${t.percentage}% of tasks)</span>
                </div>
            `;
        }).join('')}
    </div>
</div>
` : ''}

<div style="background: white; padding: 20px; border-radius: 10px;">
    <h3 style="margin: 0 0 15px 0; color: #ff9800; font-size: 16px;">💬 Communication Style</h3>
    <div style="border-left: 4px solid #ff9800; padding-left: 15px;">
        <div style="margin: 10px 0; font-size: 14px;">✓ Average message length: <strong>${commStyle.avg_message_length || 0} characters</strong></div>
        <div style="margin: 10px 0; font-size: 14px;">✓ Communication style: <strong>${commStyle.style || 'Unknown'}</strong></div>
    </div>
</div>

${summary.total_interactions === 0 ? `
<div style="background: #fff3cd; padding: 20px; border-radius: 10px; margin-top: 20px; border-left: 4px solid #ffc107;">
    <strong>Not enough data yet!</strong><br>
    Keep using the AI Swarm and I'll learn your patterns over time.
</div>
` : ''}
`;
    
    return html;
}

// =============================================================================
// 18. LABOR ANALYSIS FUNCTIONS - FIXED February 18, 2026
// =============================================================================

/**
 * Injects a persistent animated progress banner into the conversation area.
 * This stays visible throughout background processing so the user always
 * knows something is working, regardless of how long it takes.
 * FIX: February 18, 2026 - replaces the unreliable loading spinner approach.
 */
function showAnalysisProgressBanner() {
    // Remove any existing banner first to avoid duplicates
    removeAnalysisProgressBanner();

    var conversation = document.getElementById('conversation');
    if (!conversation) return;

    var banner = document.createElement('div');
    banner.id = 'analysisProgressBanner';
    banner.style.cssText = [
        'margin: 15px 0',
        'padding: 20px 25px',
        'background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #303f9f 100%)',
        'border-radius: 12px',
        'color: white',
        'border-left: 5px solid #7986cb',
        'box-shadow: 0 4px 20px rgba(26,35,126,0.4)'
    ].join(';');

    banner.innerHTML = [
        '<div style="display:flex;align-items:center;gap:15px;margin-bottom:12px;">',
            '<div id="analysisPulse" style="',
                'width:18px;height:18px;border-radius:50%;',
                'background:#7986cb;flex-shrink:0;',
                'animation:analysisPulse 1.4s ease-in-out infinite;',
            '"></div>',
            '<div style="font-size:16px;font-weight:700;">⚙️ Labor Analysis Running in Background</div>',
        '</div>',
        '<div style="font-size:13px;opacity:0.9;line-height:1.6;margin-bottom:14px;">',
            'Your data is being analyzed. This typically takes <strong>3–8 minutes</strong> for large files.<br>',
            'The results will appear here automatically when complete — no refresh needed.',
        '</div>',
        '<div style="background:rgba(255,255,255,0.12);border-radius:8px;padding:12px;">',
            '<div style="font-size:12px;font-weight:600;margin-bottom:8px;opacity:0.8;">What\'s being analyzed:</div>',
            '<div style="font-size:12px;opacity:0.9;line-height:1.8;">',
                '⏱ Overtime patterns &amp; cost exposure<br>',
                '👥 Staffing distribution by department<br>',
                '🔄 Shift balance &amp; coverage gaps<br>',
                '📅 Day-of-week &amp; monthly trends<br>',
                '💰 Headcount efficiency metrics',
            '</div>',
        '</div>',
        '<div style="margin-top:12px;font-size:11px;opacity:0.7;text-align:center;">',
            '🔄 Checking for results every 5 seconds...',
        '</div>'
    ].join('');

    // Inject the pulse keyframe animation if not already present
    if (!document.getElementById('analysisPulseStyle')) {
        var style = document.createElement('style');
        style.id = 'analysisPulseStyle';
        style.textContent = '@keyframes analysisPulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:0.4;transform:scale(1.3);}}';
        document.head.appendChild(style);
    }

    conversation.appendChild(banner);
    conversation.scrollTop = conversation.scrollHeight;
}

/**
 * Removes the progress banner when analysis completes.
 */
function removeAnalysisProgressBanner() {
    var banner = document.getElementById('analysisProgressBanner');
    if (banner) {
        banner.parentNode.removeChild(banner);
    }
}

/**
 * Starts polling the conversation for new messages every 5 seconds.
 * Uses lastKnownMessageCount (server count) for reliable comparison —
 * NOT DOM element count which is unpredictable.
 * FIX: February 18, 2026
 */
function startBackgroundJobPolling() {
    if (backgroundJobPolling) {
        console.log('⏩ Polling already active');
        return;
    }

    console.log('🔄 Starting auto-refresh polling (baseline message count: ' + lastKnownMessageCount + ')');

    showAnalysisProgressBanner();

    backgroundJobPolling = setInterval(function() {
        if (!currentConversationId) {
            console.log('⏹️ No conversation ID - stopping poll');
            stopBackgroundJobPolling();
            return;
        }

        console.log('🔍 Polling for new messages (known count: ' + lastKnownMessageCount + ')...');
        refreshConversationMessages();
    }, 5000);
}

/**
 * Stops polling and cleans up the progress banner.
 * FIX: February 18, 2026 - now also removes the banner.
 */
function stopBackgroundJobPolling() {
    if (backgroundJobPolling) {
        console.log('⏹️ Stopping auto-refresh polling');
        clearInterval(backgroundJobPolling);
        backgroundJobPolling = null;
    }
    removeAnalysisProgressBanner();
}

/**
 * Fetches the current conversation from the server and compares the
 * server message count to lastKnownMessageCount. If new messages exist,
 * redraws the conversation and updates the counter.
 *
 * FIX: February 18, 2026 - Previous version compared DOM element count
 * to server count which was always mismatched (welcome message, banners,
 * etc. inflated DOM count). Now uses a dedicated JS variable that tracks
 * only the server-side message count.
 */
function refreshConversationMessages() {
    if (!currentConversationId) return;

    fetch('/api/conversations/' + currentConversationId)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success && data.messages) {
                var serverMsgCount = data.messages.length;

                console.log('📊 Server messages: ' + serverMsgCount + ' | Last known: ' + lastKnownMessageCount);

                if (serverMsgCount > lastKnownMessageCount) {
                    console.log('✨ New messages detected! Updating display...');

                    // Update our baseline before redrawing
                    lastKnownMessageCount = serverMsgCount;

                    // Remove the progress banner before redrawing so it doesn't
                    // get caught inside clearConversationArea()
                    removeAnalysisProgressBanner();

                    // Redraw all messages
                    clearConversationArea();
                    data.messages.forEach(function(msg) {
                        addMessageFromHistoryWithMetadata(msg.role, msg.content, msg.created_at, msg.metadata);
                    });

                    // Check if analysis is complete
                    var lastMsg = data.messages[data.messages.length - 1];
                    if (lastMsg && lastMsg.content && lastMsg.content.indexOf('LABOR ANALYSIS COMPLETE') !== -1) {
                        console.log('✅ Analysis complete - stopping poll');
                        stopBackgroundJobPolling();
                    } else {
                        // Analysis still running - re-show the banner after redraw
                        showAnalysisProgressBanner();
                    }

                    updateMemoryIndicator(true, serverMsgCount);
                    loadConversations();
                }
            }
        })
        .catch(function(err) {
            console.error('❌ Error refreshing messages:', err);
        });
}

/**
 * Handles user clicking "Yes, analyze it".
 * Sets lastKnownMessageCount from the current conversation state so the
 * polling baseline is correct from the very first poll.
 * FIX: February 18, 2026
 */
function acceptLaborAnalysis(sessionId) {
    addMessage('user', '✅ Yes, analyze it');

    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    document.querySelector('.loading-text').textContent = 'Submitting analysis job...';

    fetch('/api/orchestrate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            request: 'yes analyze it',
            conversation_id: currentConversationId,
            labor_analysis_response: 'full',
            session_id: sessionId
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');

        if (data.success) {
            sessionStorage.removeItem('pending_labor_analysis');
            addMessage('assistant', data.result, data.task_id, currentMode);

            // FIX: Set baseline message count BEFORE starting the poll.
            // Fetch current message count from server so we know exactly
            // how many messages exist right now. Poll will fire when count exceeds this.
            if (currentConversationId) {
                fetch('/api/conversations/' + currentConversationId)
                    .then(function(r) { return r.json(); })
                    .then(function(convData) {
                        if (convData.success && convData.messages) {
                            lastKnownMessageCount = convData.messages.length;
                            console.log('🎯 Polling baseline set to ' + lastKnownMessageCount + ' messages');
                        }
                        console.log('🚀 Background analysis started - enabling auto-refresh');
                        startBackgroundJobPolling();
                    })
                    .catch(function() {
                        // Fallback: estimate count from DOM messages (better than 0)
                        lastKnownMessageCount = document.querySelectorAll('.message').length;
                        console.log('⚠️ Could not fetch count - using DOM estimate: ' + lastKnownMessageCount);
                        startBackgroundJobPolling();
                    });
            } else {
                startBackgroundJobPolling();
            }

            loadStats();
            loadDocuments();
        } else {
            addMessage('assistant', '❌ Error: ' + (data.error || 'Analysis failed'));
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function quickLaborSummary(sessionId) {
    addMessage('user', '📊 Just give me a quick summary');
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    fetch('/api/orchestrate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({request: 'quick summary', conversation_id: currentConversationId, labor_analysis_response: 'summary', session_id: sessionId})})
    .then(function(r) { return r.json(); }).then(function(data) { loading.classList.remove('active'); if (data.success) { sessionStorage.removeItem('pending_labor_analysis'); addMessage('assistant', data.result, data.task_id, currentMode); } else { addMessage('assistant', '❌ Error: ' + (data.error || 'Summary failed')); }}).catch(function(err) { loading.classList.remove('active'); addMessage('assistant', '❌ Error: ' + err.message); });
}

function declineLaborAnalysis() {
    addMessage('user', 'Not now');
    sessionStorage.removeItem('pending_labor_analysis');
    addMessage('assistant', '✅ File saved. You can ask me to analyze it later.');
}

// =============================================================================
// 19. INITIALIZATION
// =============================================================================

function initializeApp() {
    updateQuickActions();
    loadStats();
    loadDocuments();
    loadConversations();
    
    var urlConversationId = getConversationIdFromUrl();
    var storedConversationId = localStorage.getItem('currentConversationId');
    
    if (urlConversationId) loadConversation(urlConversationId);
    else if (storedConversationId) loadConversation(storedConversationId);
    else startNewConversation();
    
    document.getElementById('userInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    
    setInterval(function() { loadStats(); loadDocuments(); }, 30000);
    
    console.log('🚀 AI Swarm Interface initialized - Auto-refresh fixed - February 18, 2026');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

/* I did no harm and this file is not truncated */
