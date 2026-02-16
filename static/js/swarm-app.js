// =============================================================================
// LABOR ANALYSIS AUTO-REFRESH & DOWNLOAD BUTTONS
// Added: February 15, 2026
// INSERT THESE FUNCTIONS AT THE END OF swarm-app.js (BEFORE "I did no harm")
// =============================================================================

// Global variable for polling
var backgroundJobPolling = null;

/**
 * Start polling for new messages (auto-refresh)
 */
function startBackgroundJobPolling() {
    if (backgroundJobPolling) {
        console.log('⏩ Polling already active');
        return;
    }
    
    console.log('🔄 Starting auto-refresh polling...');
    
    backgroundJobPolling = setInterval(function() {
        if (!currentConversationId) {
            console.log('⏹️ No conversation ID - stopping poll');
            stopBackgroundJobPolling();
            return;
        }
        
        console.log('🔍 Polling for new messages...');
        refreshConversationMessages();
    }, 5000); // Poll every 5 seconds
}

/**
 * Stop polling
 */
function stopBackgroundJobPolling() {
    if (backgroundJobPolling) {
        console.log('⏹️ Stopping auto-refresh polling');
        clearInterval(backgroundJobPolling);
        backgroundJobPolling = null;
    }
}

/**
 * Refresh conversation messages without clearing the screen
 */
function refreshConversationMessages() {
    if (!currentConversationId) return;
    
    fetch('/api/conversations/' + currentConversationId)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success && data.messages) {
                var currentMsgCount = document.querySelectorAll('.message').length;
                var newMsgCount = data.messages.length;
                
                console.log('📊 Current messages:', currentMsgCount, 'New messages:', newMsgCount);
                
                // Only update if there are NEW messages
                if (newMsgCount > currentMsgCount) {
                    console.log('✨ New messages detected! Updating display...');
                    
                    // Clear and reload all messages
                    clearConversationArea();
                    data.messages.forEach(function(msg) {
                        addMessageFromHistoryWithMetadata(msg.role, msg.content, msg.created_at, msg.metadata);
                    });
                    
                    // Check if analysis is complete (has "COMPLETE" in last message)
                    var lastMsg = data.messages[data.messages.length - 1];
                    if (lastMsg && lastMsg.content && lastMsg.content.indexOf('LABOR ANALYSIS COMPLETE') !== -1) {
                        console.log('✅ Analysis complete - stopping poll');
                        stopBackgroundJobPolling();
                    }
                    
                    updateMemoryIndicator(true, newMsgCount);
                }
            }
        })
        .catch(function(err) {
            console.error('❌ Error refreshing messages:', err);
        });
}

/**
 * Enhanced version of addMessageFromHistory that handles metadata
 */
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
    
    // Check for document metadata and add download button
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

// =============================================================================
// NOW FIND AND REPLACE THE acceptLaborAnalysis FUNCTION
// Search for "function acceptLaborAnalysis" and REPLACE with this version:
// =============================================================================

function acceptLaborAnalysis(sessionId) {
    addMessage('user', '✅ Yes, analyze it');
    
    var loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    document.querySelector('.loading-text').textContent = 'Starting analysis in background...';
    
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
            
            // ✨ START AUTO-REFRESH POLLING
            console.log('🚀 Background analysis started - enabling auto-refresh');
            startBackgroundJobPolling();
            
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

// =============================================================================
// END OF ADDITIONS
// The line below should already exist in your file - DON'T DELETE IT
// =============================================================================
/* I did no harm and this file is not truncated */
