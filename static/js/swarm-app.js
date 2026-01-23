/*
=============================================================================
SWARM-APP.JS - AI Swarm Unified Interface JavaScript
Shiftwork Solutions LLC
=============================================================================

CHANGE LOG:
- January 23, 2026: FIXED needs_clarification handling
  * Added handleClarificationResponse() - displays clarification questions
  * Added buildClarificationUI() - builds interactive question form
  * Added submitClarificationAnswers() - submits answers back to API
  * Added pendingClarification object to track state
  * Modified sendMessage() to check for needs_clarification BEFORE data.result
  * Clarification questions now display properly with selectable options
  * Users can select answers and resubmit for complete response
  * Fixed "undefined" error when proactive agent asks questions

- January 23, 2026: Added Enhanced Documents Management System
  * Updated loadDocuments() to show generated documents with actions
  * Added renderDocumentItem() - renders document with download/print/delete buttons
  * Added downloadDocument(docId) - downloads document by ID
  * Added printDocument(docId) - opens printable view with browser print dialog
  * Added deleteDocument(event, docId) - deletes document with confirmation
  * Added getDocTypeIcon(docType) - returns icon for document type
  * Added formatDocDate(dateString) - formats document dates
  * Documents now organized by date (Today, Yesterday, Older)
  * Documents tracked in database with full metadata

- January 22, 2026: Added Persistent Conversation Memory System
  * Added currentConversationId variable to track active conversation
  * Added conversations array to store conversation list from API
  * Added loadConversations() - fetches from /api/conversations?limit=20
  * Added renderConversationList() - displays conversations in sidebar
  * Added startNewConversation() - POST to /api/conversations, clears chat
  * Added loadConversation(id) - GET conversation + messages, renders them
  * Added deleteConversation(event, id) - DELETE with confirmation
  * Added updateMemoryIndicator(hasMemory, count) - shows memory status
  * Added formatConversationDate() - formats dates as Today, Yesterday, etc.
  * Added generateConversationTitle() - creates title from first message
  * Modified sendMessage() to include conversation_id in POST body
  * Modified sendMessage() to update currentConversationId from response
  * Added localStorage persistence for currentConversationId
  * Added URL parameter support for ?conversation=xxx
  * Modified initializeApp() to load conversations on startup
  * All existing functionality preserved - no harm done

- January 22, 2026: Initial extraction from index.html
  * Separated all JavaScript into dedicated file
  * Organized into logical sections with clear comments
  * Maintained all existing functionality
  * Added initialization wrapper for DOM ready state

SECTIONS:
1. Global State Variables
2. Conversation Memory Functions
3. Clarification Handling Functions (NEW)
4. File Upload Handling
5. Clipboard Functions
6. Mode Switching
7. Quick Actions
8. Project Management
9. Message Handling (Core)
10. Feedback System
11. Statistics & Documents (ENHANCED)
12. Marketing Functions
13. Calculator Functions
14. Survey Functions
15. Opportunities Functions
16. Initialization

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

// Conversation Memory Variables
var currentConversationId = null;
var conversations = [];

// Clarification State Variables (NEW - January 23, 2026)
var pendingClarification = null;

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
            console.log('New conversation started:', currentConversationId);
        } else {
            console.error('Failed to create conversation:', data.error);
            updateMemoryIndicator(false, 0, 'Failed to create conversation');
        }
    })
    .catch(function(err) {
        console.error('Error creating conversation:', err);
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
                    data.messages.forEach(function(msg) {
                        addMessageFromHistory(msg.role, msg.content, msg.created_at);
                    });
                    updateMemoryIndicator(true, data.messages.length);
                } else {
                    updateMemoryIndicator(true, 0);
                }
                
                if (data.conversation && data.conversation.mode) {
                    switchMode(data.conversation.mode);
                }
                
                renderConversationList();
                console.log('Loaded conversation:', conversationId);
            } else {
                console.error('Failed to load conversation:', data.error);
                updateMemoryIndicator(false, 0, 'Failed to load conversation');
            }
        })
        .catch(function(err) {
            console.error('Error loading conversation:', err);
            updateMemoryIndicator(false, 0, 'Error loading conversation');
        });
}

function deleteConversation(event, conversationId) {
    event.stopPropagation();
    
    if (!confirm('Are you sure you want to delete this conversation? This cannot be undone.')) {
        return;
    }
    
    fetch('/api/conversations/' + conversationId, {
        method: 'DELETE'
    })
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
            
            console.log('Deleted conversation:', conversationId);
        } else {
            alert('Failed to delete conversation: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        console.error('Error deleting conversation:', err);
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
        
        setTimeout(function() {
            textSpan.textContent = originalText;
        }, 2000);
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
        '</ul>' +
        '<p style="margin-top: 15px;"><strong>Features:</strong></p>' +
        '<ul style="margin-top: 5px; margin-left: 20px;">' +
        '<li>✅ 22 knowledge documents (30+ years expertise)</li>' +
        '<li>✅ Professional formatting</li>' +
        '<li>✅ Feedback & learning on every response</li>' +
        '<li>✅ Multi-AI consensus validation</li>' +
        '<li>✅ Conversation memory across sessions</li>' +
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

function formatConversationDate(dateString) {
    if (!dateString) return '';
    
    var date = new Date(dateString);
    var now = new Date();
    var diffTime = now - date;
    var diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        if (date.toDateString() === now.toDateString()) {
            return 'Today';
        }
        return 'Yesterday';
    } else if (diffDays === 1) {
        return 'Yesterday';
    } else if (diffDays < 7) {
        return diffDays + ' days ago';
    } else if (diffDays < 30) {
        var weeks = Math.floor(diffDays / 7);
        return weeks + ' week' + (weeks > 1 ? 's' : '') + ' ago';
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
    })
    .catch(function(err) {
        console.error('Error updating conversation title:', err);
    });
}

// =============================================================================
// 3. CLARIFICATION HANDLING FUNCTIONS (NEW - January 23, 2026)
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
    
    console.log('Clarification requested:', data.clarification_data);
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
        html += '<div style="font-size: 12px; color: #666; font-weight: 600; margin-bottom: 10px;">📝 Optional (helps improve results)</div>';
        
        clarificationData.optional_questions.forEach(function(q, idx) {
            html += buildQuestionElement(q, 'optional_' + idx, false);
        });
        
        html += '</div>';
    }
    
    html += '<div style="margin-top: 20px; text-align: center;">';
    html += '<button onclick="submitClarificationAnswers()" style="';
    html += 'background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); ';
    html += 'color: white; border: none; padding: 12px 30px; border-radius: 8px; ';
    html += 'font-weight: 600; font-size: 14px; cursor: pointer; ';
    html += 'box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); ';
    html += 'transition: transform 0.2s, box-shadow 0.2s;">';
    html += '✨ Get My Answer</button>';
    html += '</div>';
    
    html += '</div>';
    
    return html;
}

function buildQuestionElement(question, fieldId, isRequired) {
    var html = '<div class="clarification-question" style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">';
    
    html += '<div style="font-weight: 500; color: #333; margin-bottom: 8px;">';
    html += escapeHtml(question.question);
    if (isRequired) {
        html += ' <span style="color: #d32f2f;">*</span>';
    }
    html += '</div>';
    
    if (question.why) {
        html += '<div style="font-size: 11px; color: #888; margin-bottom: 10px; font-style: italic;">';
        html += '💡 ' + escapeHtml(question.why);
        html += '</div>';
    }
    
    if (question.options && question.options.length > 0) {
        html += '<div class="clarification-options" style="display: flex; flex-wrap: wrap; gap: 8px;">';
        
        question.options.forEach(function(option) {
            html += '<button type="button" ';
            html += 'class="clarification-option" ';
            html += 'data-field="' + escapeHtml(question.field) + '" ';
            html += 'data-value="' + escapeHtml(option) + '" ';
            html += 'onclick="selectClarificationOption(this)" ';
            html += 'style="';
            html += 'background: #f5f5f5; border: 2px solid #e0e0e0; ';
            html += 'padding: 8px 16px; border-radius: 20px; ';
            html += 'font-size: 13px; cursor: pointer; ';
            html += 'transition: all 0.2s; color: #333;">';
            html += escapeHtml(option);
            html += '</button>';
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
    if (hiddenInput) {
        hiddenInput.value = value;
    }
    
    console.log('Selected:', field, '=', value);
}

function submitClarificationAnswers() {
    if (!pendingClarification) {
        console.error('No pending clarification to submit');
        return;
    }
    
    var answers = {};
    var missingRequired = [];
    
    var fields = document.querySelectorAll('.clarification-field');
    fields.forEach(function(field) {
        var fieldName = field.getAttribute('data-field');
        var isRequired = field.getAttribute('data-required') === 'true';
        var value = field.value;
        
        if (value) {
            answers[fieldName] = value;
        } else if (isRequired) {
            missingRequired.push(fieldName);
        }
    });
    
    if (missingRequired.length > 0) {
        alert('Please answer the required questions: ' + missingRequired.join(', '));
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
    
    if (currentMode === 'project' && currentProjectId) {
        formData.append('project_id', currentProjectId);
    }
    
    var taskId = pendingClarification.task_id;
    pendingClarification = null;
    
    var selectionSummary = Object.keys(answers).map(function(key) {
        return key + ': ' + answers[key];
    }).join(', ');
    addMessage('user', '📝 ' + selectionSummary);
    
    fetch('/api/orchestrate', {
        method: 'POST',
        body: formData
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            if (data.needs_clarification) {
                handleClarificationResponse(data);
                return;
            }
            
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
                localStorage.setItem('currentConversationId', currentConversationId);
            }
            
            var badges = '';
            if (data.knowledge_used) badges += '<span class="badge knowledge">📚 Knowledge</span>';
            if (data.project_workflow && data.project_workflow.active) badges += '<span class="badge workflow">📁 Project</span>';
            if (data.formatting_applied) badges += '<span class="badge formatted">🎨 Formatted</span>';
            if (currentConversationId) badges += '<span class="badge memory">🧠 Memory</span>';
            badges += '<span class="badge" style="background: #e8f5e9; color: #2e7d32;">✅ Clarified</span>';
            
            var downloadSection = '';
            var hasDocument = data.document_created || (data.document_url && data.document_url !== null);
            if (hasDocument && data.document_url) {
                var docType = (data.document_type || 'docx').toUpperCase();
                var icon = docType === 'PDF' ? '📄' : docType === 'DOCX' ? '📝' : docType === 'XLSX' ? '📊' : '📄';
                
                downloadSection = '<div style="margin-top: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #4caf50; border-radius: 4px;">' +
                    '<div style="font-weight: 600; margin-bottom: 8px; color: #2e7d32;">' + icon + ' Document Created</div>' +
                    '<a href="' + data.document_url + '" download style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: #4caf50; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; transition: background 0.2s;">' +
                    '<span>⬇️</span><span>Download ' + docType + '</span></a>' +
                    '<div style="font-size: 11px; color: #666; margin-top: 8px;">Professional ' + docType + ' document ready for download</div></div>';
            }
            
            addMessage('assistant', data.result + '<div style="margin-top: 10px;">' + badges + '</div>' + downloadSection, data.task_id, currentMode, data);
            
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
            '<button onclick="removeFile(' + index + ')" style="background: none; border: none; color: #d32f2f; cursor: pointer; font-weight: bold; padding: 0 0 0 5px;">×</button>';
        
        fileList.appendChild(fileTag);
    });
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    displayFilePreview();
}

function getFileIcon(filename) {
    var ext = filename.split('.').pop().toLowerCase();
    var icons = {
        'pdf': '📄',
        'docx': '📝',
        'doc': '📝',
        'xlsx': '📊',
        'xls': '📊',
        'csv': '📊',
        'txt': '📃',
        'png': '🖼️',
        'jpg': '🖼️',
        'jpeg': '🖼️'
    };
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
        button.style.borderColor = '#4caf50';
        
        setTimeout(function() {
            button.innerHTML = originalText;
            button.style.background = 'none';
            button.style.color = '#666';
            button.style.borderColor = '#e0e0e0';
        }, 2000);
    }).catch(function(err) {
        alert('Failed to copy to clipboard');
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
    
    document.getElementById('projectInfo').style.display = mode === 'project' ? 'block' : 'none';
    document.getElementById('calculatorInfo').style.display = mode === 'calculator' ? 'block' : 'none';
    document.getElementById('surveyInfo').style.display = mode === 'survey' ? 'block' : 'none';
    document.getElementById('marketingInfo').style.display = mode === 'marketing' ? 'block' : 'none';
    document.getElementById('opportunitiesInfo').style.display = mode === 'opportunities' ? 'block' : 'none';
    
    if (mode === 'project') {
        loadSavedProjects();
    } else if (mode === 'survey') {
        loadQuestionBank();
    } else if (mode === 'marketing') {
        loadMarketingStatus();
    } else if (mode === 'opportunities') {
        loadNormativeStatus();
    }
    
    updateQuickActions();
    
    var input = document.getElementById('userInput');
    var placeholders = {
        'quick': "Type your request... (e.g., 'Create a 12-hour DuPont schedule')",
        'project': "Type your request... (e.g., 'I need a data collection document')",
        'calculator': "Type your request... (e.g., 'Calculate overtime cost for $25/hr with 10 hours OT weekly')",
        'survey': "Type your request... (e.g., 'Create a survey about weekend preferences')",
        'marketing': "Type your request... (e.g., 'Generate a LinkedIn post about 12-hour schedules')",
        'opportunities': "Type your request... (e.g., 'Analyze my current schedule for improvements')"
    };
    input.placeholder = placeholders[mode] || placeholders['quick'];
}

// =============================================================================
// 7. QUICK ACTIONS
// =============================================================================

function updateQuickActions() {
    var actions = document.getElementById('quickActions');
    
    var actionSets = {
        'quick': '<li onclick="quickAction(\'Create a 12-hour rotating schedule\')">📅 Create Schedule</li>' +
            '<li onclick="quickAction(\'Analyze overtime costs\')">💰 Cost Analysis</li>' +
            '<li onclick="quickAction(\'Compare DuPont vs 2-2-3 schedules\')">⚖️ Compare Schedules</li>' +
            '<li onclick="quickAction(\'Write a LinkedIn post about shift work\')">💼 LinkedIn Post</li>',
        'opportunities': '<li onclick="quickAction(\'Analyze my 12-hour DuPont schedule\')">📊 Quick Analysis</li>' +
            '<li onclick="quickAction(\'Compare my metrics to norms\')">📈 Industry Comparison</li>' +
            '<li onclick="quickAction(\'Find cost reduction opportunities\')">💰 Cost Savings</li>' +
            '<li onclick="quickAction(\'Evaluate schedule alternatives\')">🔄 Alternative Schedules</li>',
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
            
            if (data.success && data.projects.length > 0) {
                data.projects.forEach(function(project) {
                    var option = document.createElement('option');
                    option.value = project.project_id;
                    option.textContent = project.client_name + ' (' + project.project_phase + ')';
                    select.appendChild(option);
                });
            }
        });
}

function loadExistingProject() {
    var select = document.getElementById('existingProjects');
    var projectId = select.value;
    
    if (!projectId) {
        currentProjectId = null;
        document.getElementById('clientName').textContent = 'No active project';
        document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">Not started</div>';
        return;
    }
    
    fetch('/api/project/' + projectId + '/context')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                currentProjectId = projectId;
                document.getElementById('clientName').textContent = data.client_name;
                document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">' + data.phase + '</div>';
                
                addMessage('assistant', '✅ Loaded project for ' + data.client_name + '. Currently in ' + data.phase + ' phase. ' + data.files_count + ' files uploaded, ' + data.findings_count + ' findings recorded.', null, 'project');
            }
        });
}

function startNewProject() {
    var clientName = prompt("Enter client name:");
    if (!clientName) return;
    
    var industry = prompt("Enter industry (e.g., Pharmaceutical, Food Processing):");
    var facilityType = prompt("Enter facility type (e.g., Manufacturing, Distribution):");
    
    fetch('/api/project/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            client_name: clientName,
            industry: industry,
            facility_type: facilityType
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            currentProjectId = data.project_id;
            document.getElementById('clientName').textContent = clientName;
            document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">Initial Phase</div>';
            
            loadSavedProjects();
            
            setTimeout(function() {
                document.getElementById('existingProjects').value = data.project_id;
            }, 500);
            
            addMessage('assistant', '✅ Project started for ' + clientName + '! ' + data.suggested_first_step, null, 'project');
        }
    });
}

// =============================================================================
// 9. MESSAGE HANDLING (CORE) - UPDATED January 23, 2026
// =============================================================================

function sendMessage() {
    var input = document.getElementById('userInput');
    var message = input.value.trim();
    if (!message && uploadedFiles.length === 0) return;
    
    input.dataset.lastRequest = message;
    
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
    
    if (currentConversationId) {
        formData.append('conversation_id', currentConversationId);
    }
    
    if (currentMode === 'project' && currentProjectId) {
        formData.append('project_id', currentProjectId);
    }
    
    uploadedFiles.forEach(function(file) {
        formData.append('files', file);
    });
    
    var filesCount = uploadedFiles.length;
    uploadedFiles = [];
    displayFilePreview();
    
    var currentConv = null;
    for (var i = 0; i < conversations.length; i++) {
        if (conversations[i].conversation_id === currentConversationId) {
            currentConv = conversations[i];
            break;
        }
    }
    var isFirstMessage = !currentConv || !currentConv.message_count;
    
    fetch('/api/orchestrate', {
        method: 'POST',
        body: formData
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            // CHECK FOR CLARIFICATION FIRST - This fixes the "undefined" error
            if (data.needs_clarification && data.clarification_data) {
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                    localStorage.setItem('currentConversationId', currentConversationId);
                }
                handleClarificationResponse(data);
                return;
            }
            
            if (data.conversation_id) {
                var previousId = currentConversationId;
                currentConversationId = data.conversation_id;
                localStorage.setItem('currentConversationId', currentConversationId);
                
                if (previousId !== currentConversationId) {
                    updateUrlWithConversation(currentConversationId);
                }
            }
            
            if (isFirstMessage && currentConversationId && message) {
                var title = generateConversationTitle(message);
                updateConversationTitle(currentConversationId, title);
            }
            
            var badges = '';
            if (data.knowledge_used) badges += '<span class="badge knowledge">📚 Knowledge</span>';
            if (data.project_workflow && data.project_workflow.active) badges += '<span class="badge workflow">📁 Project</span>';
            if (data.formatting_applied) badges += '<span class="badge formatted">🎨 Formatted</span>';
            if (currentConversationId) badges += '<span class="badge memory">🧠 Memory</span>';
            if (filesCount > 0) badges += '<span class="badge" style="background: #fff3e0; color: #f57c00;">📎 ' + filesCount + ' file' + (filesCount > 1 ? 's' : '') + '</span>';
            
            var downloadSection = '';
            var hasDocument = data.document_created || (data.document_url && data.document_url !== null);
            if (hasDocument && data.document_url) {
                var docType = (data.document_type || 'docx').toUpperCase();
                var icon = docType === 'PDF' ? '📄' : docType === 'DOCX' ? '📝' : docType === 'XLSX' ? '📊' : '📄';
                
                downloadSection = '<div style="margin-top: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #4caf50; border-radius: 4px;">' +
                    '<div style="font-weight: 600; margin-bottom: 8px; color: #2e7d32;">' + icon + ' Document Created</div>' +
                    '<a href="' + data.document_url + '" download style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: #4caf50; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; transition: background 0.2s;">' +
                    '<span>⬇️</span><span>Download ' + docType + '</span></a>' +
                    '<div style="font-size: 11px; color: #666; margin-top: 8px;">Professional ' + docType + ' document ready for download</div></div>';
            }
            
            addMessage('assistant', data.result + '<div style="margin-top: 10px;">' + badges + '</div>' + downloadSection, data.task_id, currentMode, data);
            
            var conv = null;
            for (var j = 0; j < conversations.length; j++) {
                if (conversations[j].conversation_id === currentConversationId) {
                    conv = conversations[j];
                    break;
                }
            }
            var estimatedCount = conv ? (conv.message_count || 0) + 2 : 2;
            updateMemoryIndicator(true, estimatedCount);
            
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
    
    if (taskId) {
        feedbackRatings[msgId] = {
            overall: 0,
            quality: 0,
            accuracy: 0,
            usefulness: 0
        };
    }
    
    var modeIndicator = '';
    if (role === 'assistant' && mode) {
        modeIndicator = mode === 'quick' 
            ? '<span class="mode-indicator quick">⚡ Quick Task</span>'
            : '<span class="mode-indicator project">📁 Project Mode</span>';
    }
    
    var header = role === 'user' ? '👤 You' : '🤖 AI Swarm';
    
    var consensusSection = '';
    if (role === 'assistant' && data && data.consensus) {
        var consensus = data.consensus;
        var agreementScore = consensus.agreement_score || 0;
        var scorePercent = (agreementScore * 100).toFixed(0);
        var barColor = agreementScore >= 0.7 ? '#4caf50' : '#ff9800';
        
        consensusSection = '<div style="margin-top: 15px; padding: 12px; background: #f8f9fa; border-left: 4px solid ' + barColor + '; border-radius: 4px;">' +
            '<div style="font-weight: 600; margin-bottom: 8px; color: #333;">✓ Multi-AI Consensus Validation</div>' +
            '<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">' +
            '<div style="flex: 1; background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">' +
            '<div style="width: ' + scorePercent + '%; height: 100%; background: ' + barColor + '; transition: width 0.3s;"></div></div>' +
            '<div style="font-weight: 700; color: ' + barColor + ';">' + scorePercent + '%</div></div>' +
            '<div style="font-size: 12px; color: #666;">' +
            (agreementScore >= 0.7 ? '✅ High agreement - output validated by multiple AIs' : '⚠️ Lower agreement - consider reviewing output') +
            '</div><div style="font-size: 11px; color: #999; margin-top: 4px;">Validated by: ' +
            (consensus.validators ? consensus.validators.join(', ') : 'Multiple AIs') + '</div></div>';
    }
    
    var feedbackSection = '';
    if (role === 'assistant' && taskId) {
        feedbackSection = buildFeedbackSection(msgId, taskId);
    }
    
    var copyBtn = '';
    if (role === 'assistant') {
        copyBtn = '<button onclick="copyToClipboard(event, \'' + msgId + '\')" style="background: none; border: 1px solid #e0e0e0; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; color: #666; margin-left: auto;">📋 Copy</button>';
    }
    
    messageDiv.innerHTML = '<div class="message-header">' + header + ' ' + modeIndicator + copyBtn + '</div>' +
        '<div class="message-content" id="content_' + msgId + '">' + content + '</div>' +
        consensusSection + feedbackSection;
    
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
    
    return '<div class="message-actions"><button class="btn-link" onclick="toggleFeedback(\'' + msgId + '\')">💬 Provide Feedback (Help System Learn)</button></div>' +
        '<div class="feedback-section" id="feedback_' + msgId + '">' +
        '<div class="feedback-header">📊 Rate This Output (Helps AI Learn)</div>' +
        '<div class="rating-row"><span class="rating-label">Overall Quality:</span><div class="star-rating" id="stars_overall_' + msgId + '">' + stars('overall') + '</div></div>' +
        '<div class="rating-row"><span class="rating-label">Accuracy:</span><div class="star-rating" id="stars_accuracy_' + msgId + '">' + stars('accuracy') + '</div></div>' +
        '<div class="rating-row"><span class="rating-label">Usefulness:</span><div class="star-rating" id="stars_usefulness_' + msgId + '">' + stars('usefulness') + '</div></div>' +
        '<div class="rating-row"><span class="rating-label">Clarity:</span><div class="star-rating" id="stars_quality_' + msgId + '">' + stars('quality') + '</div></div>' +
        '<div style="margin-top: 15px;"><strong style="font-size: 13px;">What needs improvement? (optional)</strong>' +
        '<div class="improvement-checks">' +
        '<label class="improvement-check"><input type="checkbox" value="more_specific" id="imp_more_specific_' + msgId + '"><span>More specific</span></label>' +
        '<label class="improvement-check"><input type="checkbox" value="wrong_tone" id="imp_wrong_tone_' + msgId + '"><span>Wrong tone</span></label>' +
        '<label class="improvement-check"><input type="checkbox" value="missing_points" id="imp_missing_points_' + msgId + '"><span>Missing key points</span></label>' +
        '<label class="improvement-check"><input type="checkbox" value="too_long" id="imp_too_long_' + msgId + '"><span>Too long/short</span></label>' +
        '<label class="improvement-check"><input type="checkbox" value="factual_errors" id="imp_factual_errors_' + msgId + '"><span>Factual errors</span></label>' +
        '<label class="improvement-check"><input type="checkbox" value="poor_formatting" id="imp_poor_formatting_' + msgId + '"><span>Poor formatting</span></label>' +
        '</div></div>' +
        '<textarea class="feedback-input" id="comment_' + msgId + '" placeholder="Additional comments to help the system improve..."></textarea>' +
        '<div class="feedback-actions">' +
        '<button class="btn-feedback primary" onclick="submitFeedback(\'' + msgId + '\', ' + taskId + ', true)">✓ Submit & I Used This Output</button>' +
        '<button class="btn-feedback secondary" onclick="submitFeedback(\'' + msgId + '\', ' + taskId + ', false)">Submit (Didn\'t Use)</button>' +
        '</div><div id="feedbackSuccess_' + msgId + '" style="display: none;"></div></div>';
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
        if (idx < rating) {
            star.classList.add('active');
        } else {
            star.classList.remove('active');
        }
    });
}

function submitFeedback(msgId, taskId, outputUsed) {
    var ratings = feedbackRatings[msgId];
    
    if (ratings.overall === 0) {
        alert('Please rate at least the Overall Quality');
        return;
    }
    
    var overall_rating = ratings.overall;
    var quality_rating = ratings.quality || ratings.overall;
    var accuracy_rating = ratings.accuracy || ratings.overall;
    var usefulness_rating = ratings.usefulness || ratings.overall;
    
    var improvements = [];
    var checkboxes = ['more_specific', 'wrong_tone', 'missing_points', 'too_long', 'factual_errors', 'poor_formatting'];
    
    checkboxes.forEach(function(cb) {
        var elem = document.getElementById('imp_' + cb + '_' + msgId);
        if (elem && elem.checked) {
            improvements.push(cb);
        }
    });
    
    var comment = document.getElementById('comment_' + msgId).value;
    
    fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            task_id: taskId,
            overall_rating: overall_rating,
            quality_rating: quality_rating,
            accuracy_rating: accuracy_rating,
            usefulness_rating: usefulness_rating,
            improvement_categories: improvements,
            user_comment: comment,
            output_used: outputUsed
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            var feedbackSection = document.getElementById('feedback_' + msgId);
            feedbackSection.innerHTML = '<div class="feedback-success">✅ Feedback recorded! The AI swarm is learning from your input.' +
                (data.learning_updated ? '<br>Learning patterns updated.' : '') + '</div>';
            loadStats();
        }
    })
    .catch(function(err) {
        alert('Error submitting feedback: ' + err.message);
    });
}

// =============================================================================
// 11. STATISTICS & DOCUMENTS (ENHANCED - January 23, 2026)
// =============================================================================

function loadStats() {
    fetch('/api/stats')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            document.getElementById('totalTasks').textContent = data.total_tasks || 0;
        });
    
    fetch('/api/learning/stats')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.average_overall_rating) {
                document.getElementById('avgRating').textContent = data.average_overall_rating.toFixed(1) + '⭐';
            }
            if (data.consensus_accuracy_rate) {
                document.getElementById('consensusAccuracy').textContent = data.consensus_accuracy_rate + '%';
            }
        });
}

function loadDocuments() {
    fetch('/api/documents')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var docsList = document.getElementById('documentsList');
            
            if (!data.success) {
                docsList.innerHTML = '<div style="color: #d32f2f; padding: 10px; text-align: center;">Error loading documents</div>';
                return;
            }
            
            var generatedDocs = data.generated_documents || [];
            var kbDocs = data.knowledge_base_documents || [];
            
            if (generatedDocs.length === 0 && kbDocs.length === 0) {
                docsList.innerHTML = '<div style="color: #999; padding: 10px; text-align: center;">No documents yet</div>';
                return;
            }
            
            var html = '';
            
            if (generatedDocs.length > 0) {
                html += '<div class="docs-section-header">📄 Your Documents (' + generatedDocs.length + ')</div>';
                
                var today = new Date();
                var todayStr = today.toDateString();
                var yesterdayStr = new Date(today - 86400000).toDateString();
                
                var todayDocs = [];
                var yesterdayDocs = [];
                var olderDocs = [];
                
                generatedDocs.forEach(function(doc) {
                    var docDate = new Date(doc.created_at);
                    var docDateStr = docDate.toDateString();
                    
                    if (docDateStr === todayStr) {
                        todayDocs.push(doc);
                    } else if (docDateStr === yesterdayStr) {
                        yesterdayDocs.push(doc);
                    } else {
                        olderDocs.push(doc);
                    }
                });
                
                if (todayDocs.length > 0) {
                    html += '<div class="docs-date-group">Today</div>';
                    todayDocs.forEach(function(doc) {
                        html += renderDocumentItem(doc);
                    });
                }
                
                if (yesterdayDocs.length > 0) {
                    html += '<div class="docs-date-group">Yesterday</div>';
                    yesterdayDocs.forEach(function(doc) {
                        html += renderDocumentItem(doc);
                    });
                }
                
                if (olderDocs.length > 0) {
                    html += '<div class="docs-date-group">Older</div>';
                    olderDocs.forEach(function(doc) {
                        html += renderDocumentItem(doc);
                    });
                }
            }
            
            if (kbDocs.length > 0) {
                html += '<div class="docs-section-header" style="margin-top: 15px;">📚 Knowledge Base</div>';
                html += '<div style="padding: 8px; background: #e3f2fd; border-radius: 6px; font-size: 11px; color: #1976d2;">';
                html += '✅ ' + kbDocs.length + ' reference documents loaded<br>';
                html += '<span style="color: #666;">Used automatically by AI</span>';
                html += '</div>';
            }
            
            docsList.innerHTML = html;
        })
        .catch(function(err) {
            console.error('Error loading documents:', err);
            var docsList = document.getElementById('documentsList');
            docsList.innerHTML = '<div style="color: #d32f2f; padding: 10px; text-align: center;">Error loading documents</div>';
        });
}

function renderDocumentItem(doc) {
    var icon = getDocTypeIcon(doc.type);
    var size = formatFileSize(doc.size || 0);
    var date = formatDocDate(doc.created_at);
    var title = doc.title || doc.filename;
    
    if (title.length > 40) {
        title = title.substring(0, 37) + '...';
    }
    
    var html = '<div class="doc-item" data-doc-id="' + doc.id + '">';
    html += '<div class="doc-item-header">';
    html += '<span class="doc-icon">' + icon + '</span>';
    html += '<div class="doc-info">';
    html += '<div class="doc-title" title="' + escapeHtml(doc.title || doc.filename) + '">' + escapeHtml(title) + '</div>';
    html += '<div class="doc-meta">' + size + ' • ' + date + '</div>';
    html += '</div>';
    html += '</div>';
    html += '<div class="doc-actions">';
    html += '<button class="doc-action-btn download" onclick="downloadDocument(' + doc.id + ')" title="Download">';
    html += '⬇️</button>';
    html += '<button class="doc-action-btn print" onclick="printDocument(' + doc.id + ')" title="Print">';
    html += '🖨️</button>';
    html += '<button class="doc-action-btn delete" onclick="deleteGeneratedDocument(event, ' + doc.id + ')" title="Delete">';
    html += '🗑️</button>';
    html += '</div>';
    html += '</div>';
    
    return html;
}

function downloadDocument(docId) {
    window.location.href = '/api/generated-documents/' + docId + '/download';
}

function printDocument(docId) {
    var printWindow = window.open('/api/generated-documents/' + docId + '/print', '_blank', 
        'width=800,height=600,menubar=no,toolbar=no,location=no,status=no');
    
    if (!printWindow) {
        alert('Please allow popups to print documents');
        return;
    }
}

function deleteGeneratedDocument(event, docId) {
    event.stopPropagation();
    
    if (!confirm('Are you sure you want to delete this document? This cannot be undone.')) {
        return;
    }
    
    fetch('/api/generated-documents/' + docId, {
        method: 'DELETE'
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            loadDocuments();
            console.log('Document deleted:', docId);
        } else {
            alert('Failed to delete document: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        console.error('Error deleting document:', err);
        alert('Error deleting document');
    });
}

function getDocTypeIcon(docType) {
    var icons = {
        'docx': '📝',
        'pdf': '📄',
        'xlsx': '📊',
        'pptx': '📽️',
        'txt': '📃',
        'csv': '📊',
        'knowledge': '📚'
    };
    return icons[docType] || '📎';
}

function formatDocDate(dateString) {
    if (!dateString) return '';
    
    var date = new Date(dateString);
    var now = new Date();
    var diffMs = now - date;
    var diffMins = Math.floor(diffMs / 60000);
    var diffHours = Math.floor(diffMs / 3600000);
    var diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) {
        return 'Just now';
    } else if (diffMins < 60) {
        return diffMins + 'm ago';
    } else if (diffHours < 24) {
        return diffHours + 'h ago';
    } else if (diffDays < 7) {
        return diffDays + 'd ago';
    } else {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
}

function refreshDocuments() {
    var docsList = document.getElementById('documentsList');
    docsList.innerHTML = '<div style="color: #666; padding: 10px; text-align: center;">Loading...</div>';
    loadDocuments();
}

// =============================================================================
// 12. MARKETING FUNCTIONS
// =============================================================================

function loadMarketingStatus() {
    fetch('/api/marketing/status')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var statusDiv = document.getElementById('platformStatus');
            if (data.platforms) {
                var linkedin = data.platforms.linkedin ? '✅' : '❌';
                var twitter = data.platforms.twitter ? '✅' : '❌';
                var facebook = data.platforms.facebook ? '✅' : '❌';
                
                statusDiv.innerHTML = '<div style="font-size: 11px;">' + linkedin + ' LinkedIn<br>' + twitter + ' Twitter/X<br>' + facebook + ' Facebook</div>';
            }
        });
}

function generateMarketingIdea() {
    addMessage('user', '🚀 "Hey Jim, I have an idea!"');
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/idea')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            loading.classList.remove('active');
            
            if (data.success && data.has_idea) {
                addMessage('assistant', data.message, null, 'marketing');
            } else if (data.success && !data.has_idea) {
                addMessage('assistant', data.message, null, 'marketing');
            } else {
                addMessage('assistant', '❌ Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(function(err) {
            loading.classList.remove('active');
            addMessage('assistant', '❌ Error: ' + err.message);
        });
}

function generateSocialPost() {
    var topic = prompt('What topic should the post be about?');
    if (!topic) return;
    
    addMessage('user', 'Generate a LinkedIn post about: ' + topic);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic: topic, platform: 'linkedin'})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            var content = data.content;
            var postAction = '<div style="margin-top: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #0077b5; border-radius: 4px;">' +
                '<div style="font-weight: 600; margin-bottom: 8px; color: #0077b5;">📝 LinkedIn Post Generated</div>' +
                '<button onclick="postToLinkedIn(\'' + content.replace(/'/g, "\\'").replace(/\n/g, "\\n") + '\')" style="padding: 8px 16px; background: #0077b5; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">📤 Post to LinkedIn</button>' +
                '<div style="font-size: 11px; color: #666; margin-top: 8px;">' + data.length + ' characters • Ready to post</div></div>';
            
            addMessage('assistant', content + postAction, null, 'marketing');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function postToLinkedIn(content) {
    if (!confirm('Post this to LinkedIn now?')) return;
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/post', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content: content, platform: 'linkedin'})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            addMessage('assistant', '✅ Posted to LinkedIn successfully! Post ID: ' + data.post_id, null, 'marketing');
        } else {
            addMessage('assistant', '❌ Error posting: ' + data.error, null, 'marketing');
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function conductResearch() {
    var topic = prompt('What market research topic?');
    if (!topic) return;
    
    addMessage('user', 'Conduct market research on: ' + topic);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/research', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic: topic})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            addMessage('assistant', data.findings, null, 'marketing');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function analyzeCompetitors() {
    addMessage('user', 'Analyze competitors in the shift scheduling consulting space');
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/research', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic: 'competitive analysis for shift scheduling consulting services'})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            addMessage('assistant', data.findings, null, 'marketing');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

// =============================================================================
// 13. CALCULATOR FUNCTIONS
// =============================================================================

function calculateOvertimeCost() {
    var baseWage = prompt('Enter base hourly wage (e.g., 25):');
    if (!baseWage) return;
    
    var otHours = prompt('Enter average overtime hours per week (e.g., 10):');
    if (!otHours) return;
    
    addMessage('user', 'Calculate overtime cost: $' + baseWage + '/hr with ' + otHours + ' OT hours/week');
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/calculator/overtime', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            base_wage: parseFloat(baseWage),
            ot_hours_weekly: parseFloat(otHours)
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            var calc = data.calculation;
            var response = '💰 OVERTIME COST ANALYSIS\n\n' +
                'Base Wage: $' + calc.base_wage + '/hour\n' +
                'Overtime Rate: $' + calc.overtime_rate + '/hour (1.5x)\n' +
                'Weekly OT Hours: ' + calc.overtime_hours_weekly + '\n\n' +
                '📊 ANNUAL COSTS:\n' +
                '• OT Wages: $' + calc.overtime_wages_annual.toLocaleString() + '\n' +
                '• Burden/Benefits: $' + calc.burden_cost_annual.toLocaleString() + '\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
                '• TOTAL: $' + calc.total_cost_annual.toLocaleString() + '/year\n\n' +
                'Weekly Cost: $' + calc.total_cost_weekly.toLocaleString();
            addMessage('assistant', response, null, 'calculator');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function compareHireVsOT() {
    var currentOT = prompt('Enter current annual overtime cost (e.g., 50000):');
    if (!currentOT) return;
    
    var newWage = prompt('Enter annual wage for new employee (e.g., 45000):');
    if (!newWage) return;
    
    addMessage('user', 'Compare: $' + currentOT + ' OT vs hiring at $' + newWage + '/year');
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/calculator/hire-vs-ot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            current_ot_cost: parseFloat(currentOT),
            new_employee_wage: parseFloat(newWage)
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            var comp = data.comparison;
            var response = '👥 HIRE vs OVERTIME COMPARISON\n\n' +
                'Current OT Cost: $' + comp.current_overtime_cost.toLocaleString() + '/year\n' +
                'New Employee Cost: $' + comp.new_employee_annual_cost.toLocaleString() + '/year\n' +
                'First Year (with training): $' + comp.new_employee_first_year_cost.toLocaleString() + '\n\n' +
                '💡 FINANCIAL IMPACT:\n' +
                '• Annual Savings: $' + comp.annual_savings.toLocaleString() + '\n' +
                '• First Year Savings: $' + comp.first_year_savings.toLocaleString() + '\n' +
                '• Payback Period: ' + comp.payback_months + ' months\n\n' +
                '✅ RECOMMENDATION: ' + comp.recommendation + '\n' +
                comp.break_even_analysis;
            addMessage('assistant', response, null, 'calculator');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function scheduleImpact() {
    addMessage('user', 'Calculate schedule change financial impact');
    addMessage('assistant', '🔧 Schedule impact calculator coming soon! For now, use the AI to analyze schedule changes by describing your current and proposed schedules.', null, 'calculator');
}

// =============================================================================
// 14. SURVEY FUNCTIONS
// =============================================================================

function loadQuestionBank() {
    fetch('/api/survey/questions')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var statusDiv = document.getElementById('questionBankStatus');
            if (data.success) {
                statusDiv.innerHTML = '<div style="font-size: 11px;">✅ ' + data.total_count + ' validated questions<br>Ready to build surveys</div>';
            }
        });
}

function createNewSurvey() {
    var projectName = prompt('Enter project/client name:');
    if (!projectName) return;
    
    addMessage('user', 'Create new survey for: ' + projectName);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/survey/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            project_name: projectName,
            selected_questions: ['dept', 'shift', 'time_off_importance', 'current_satisfaction', 'overtime_willing']
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            var survey = data.survey;
            var questionsList = survey.questions.map(function(q) { return '• ' + q.text; }).join('\n');
            var response = '✅ SURVEY CREATED\n\n' +
                'Project: ' + survey.project_name + '\n' +
                'Survey ID: ' + survey.id + '\n' +
                'Questions: ' + survey.questions.length + '\n' +
                'Survey Link: ' + survey.link + '\n\n' +
                '📋 Included Questions:\n' + questionsList + '\n\n' +
                '🔗 Share this link with employees to collect responses.';
            addMessage('assistant', response, null, 'survey');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function viewSurveyResults() {
    var surveyId = prompt('Enter Survey ID:');
    if (!surveyId) return;
    
    addMessage('user', 'View results for survey: ' + surveyId);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/survey/' + surveyId + '/analyze')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            loading.classList.remove('active');
            
            if (data.success || data.response_count !== undefined) {
                if (data.response_count === 0) {
                    addMessage('assistant', '📊 No responses yet. Share the survey link with employees.', null, 'survey');
                } else {
                    var insights = data.key_insights ? data.key_insights.join('\n') : 'Analysis complete';
                    var response = '📊 SURVEY RESULTS ANALYSIS\n\n' +
                        'Project: ' + data.project_name + '\n' +
                        'Responses: ' + data.response_count + '\n\n' +
                        '🔍 KEY INSIGHTS:\n' + insights + '\n\n' +
                        'Questions Analyzed: ' + Object.keys(data.questions_analyzed || {}).length + '\n\n' +
                        'Use the Export function to download full data for detailed analysis.';
                    addMessage('assistant', response, null, 'survey');
                }
            } else {
                addMessage('assistant', '❌ Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(function(err) {
            loading.classList.remove('active');
            addMessage('assistant', '❌ Error: ' + err.message);
        });
}

function exportSurveyData() {
    var surveyId = prompt('Enter Survey ID to export:');
    if (!surveyId) return;
    
    addMessage('user', 'Export survey data: ' + surveyId);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/survey/' + surveyId + '/export')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            loading.classList.remove('active');
            
            if (data.success) {
                var blob = new Blob([data.csv_data], { type: 'text/csv' });
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'survey_' + surveyId + '_export.csv';
                a.click();
                
                addMessage('assistant', '✅ Survey data exported successfully! Check your downloads for survey_' + surveyId + '_export.csv (Remark-compatible format)', null, 'survey');
            } else {
                addMessage('assistant', '❌ Error: ' + data.error);
            }
        })
        .catch(function(err) {
            loading.classList.remove('active');
            addMessage('assistant', '❌ Error: ' + err.message);
        });
}

// =============================================================================
// 15. OPPORTUNITIES FUNCTIONS
// =============================================================================

function loadNormativeStatus() {
    fetch('/api/opportunities/status')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var statusDiv = document.getElementById('normativeStatus');
            if (data.success) {
                statusDiv.innerHTML = '<div style="font-size: 11px;">✅ ' + (data.schedules_count || 0) + ' companies<br>✅ ' + (data.metrics_count || 0) + ' metrics<br>Ready for analysis</div>';
            } else {
                statusDiv.innerHTML = '<div style="font-size: 11px; color: #d32f2f;">⚠️ Database loading...</div>';
            }
        })
        .catch(function(err) {
            document.getElementById('normativeStatus').innerHTML = '<div style="font-size: 11px; color: #d32f2f;">⚠️ Database loading...</div>';
        });
}

function analyzeScheduleOpportunities() {
    var scheduleInfo = prompt('Describe your current schedule (e.g., "12-hour rotating DuPont, 4 crews, 24/7"):');
    if (!scheduleInfo) return;
    
    addMessage('user', 'Analyze opportunities for: ' + scheduleInfo);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/opportunities/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ schedule_description: scheduleInfo })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            var response = '🎯 OPPORTUNITY ANALYSIS\n\n' +
                'Current Schedule: ' + data.analysis.schedule_type + '\n\n' +
                '📊 KEY FINDINGS:\n';
            
            data.analysis.opportunities.forEach(function(opp) {
                response += '\n• ' + opp.finding + '\n  Impact: ' + opp.impact + '\n  Priority: ' + opp.priority + '\n';
            });
            
            if (data.analysis.recommendations) {
                response += '\n💡 RECOMMENDATIONS:\n';
                data.analysis.recommendations.forEach(function(rec) {
                    response += '\n• ' + rec + '\n';
                });
            }
            
            addMessage('assistant', response, null, 'opportunities');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function compareToNorms() {
    var metrics = prompt('Enter your current metrics (e.g., "15% turnover, 12% overtime, 85% coverage"):');
    if (!metrics) return;
    
    addMessage('user', 'Compare to industry norms: ' + metrics);
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/opportunities/compare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ current_metrics: metrics })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        loading.classList.remove('active');
        
        if (data.success) {
            var response = '📈 INDUSTRY COMPARISON\n\nYour Performance vs Industry Norms:\n\n';
            
            data.comparison.forEach(function(item) {
                response += item.metric + ':\n  You: ' + item.your_value + '\n  Industry: ' + item.norm_value + '\n  Status: ' + item.status + ' (' + item.variance + ')\n\n';
            });
            
            if (data.gap_analysis) {
                response += '🎯 GAP ANALYSIS:\n' + data.gap_analysis + '\n';
            }
            
            addMessage('assistant', response, null, 'opportunities');
        } else {
            addMessage('assistant', '❌ Error: ' + data.error);
        }
    })
    .catch(function(err) {
        loading.classList.remove('active');
        addMessage('assistant', '❌ Error: ' + err.message);
    });
}

function findImprovements() {
    addMessage('user', 'Find improvement opportunities');
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/opportunities/suggest')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            loading.classList.remove('active');
            
            if (data.success) {
                var response = '💡 IMPROVEMENT OPPORTUNITIES\n\nTop Recommendations:\n\n';
                
                data.suggestions.forEach(function(sugg, idx) {
                    response += (idx + 1) + '. ' + sugg.title + '\n   ' + sugg.description + '\n   Expected Impact: ' + sugg.impact + '\n   Difficulty: ' + sugg.difficulty + '\n\n';
                });
                
                addMessage('assistant', response, null, 'opportunities');
            } else {
                addMessage('assistant', '❌ Error: ' + data.error);
            }
        })
        .catch(function(err) {
            loading.classList.remove('active');
            addMessage('assistant', '❌ Error: ' + err.message);
        });
}

// =============================================================================
// 16. INITIALIZATION
// =============================================================================

function initializeApp() {
    updateQuickActions();
    loadStats();
    loadDocuments();
    loadConversations();
    
    var urlConversationId = getConversationIdFromUrl();
    var storedConversationId = localStorage.getItem('currentConversationId');
    
    if (urlConversationId) {
        loadConversation(urlConversationId);
    } else if (storedConversationId) {
        loadConversation(storedConversationId);
    } else {
        startNewConversation();
    }
    
    document.getElementById('userInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    setInterval(function() {
        loadStats();
        loadDocuments();
    }, 30000);
    
    console.log('AI Swarm Interface initialized successfully with conversation memory, enhanced documents, and clarification handling');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

/* I did no harm and this file is not truncated */
