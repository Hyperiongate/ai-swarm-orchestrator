/*
=============================================================================
SWARM-APP.JS - AI Swarm Unified Interface JavaScript
Shiftwork Solutions LLC
=============================================================================

CHANGE LOG:
- January 22, 2026: Initial extraction from index.html
  * Separated all JavaScript into dedicated file
  * Organized into logical sections with clear comments
  * Maintained all existing functionality
  * Added initialization wrapper for DOM ready state

SECTIONS:
1. Global State Variables
2. File Upload Handling
3. Clipboard Functions
4. Mode Switching
5. Quick Actions
6. Project Management
7. Message Handling (Core)
8. Feedback System
9. Statistics & Documents
10. Marketing Functions
11. Calculator Functions
12. Survey Functions
13. Opportunities Functions
14. Initialization

=============================================================================
*/

// =============================================================================
// 1. GLOBAL STATE VARIABLES
// =============================================================================

let currentMode = 'quick';  // 'quick', 'project', 'calculator', 'survey', 'marketing', 'opportunities'
let currentProjectId = null;
let messageCounter = 0;
let feedbackRatings = {};  // Store ratings for each message
let uploadedFiles = [];    // Store uploaded files

// =============================================================================
// 2. FILE UPLOAD HANDLING
// =============================================================================

function handleFileUpload(event) {
    const files = Array.from(event.currentTarget.files);
    uploadedFiles = uploadedFiles.concat(files);
    displayFilePreview();
}

function displayFilePreview() {
    const preview = document.getElementById('filePreview');
    const fileList = document.getElementById('fileList');
    
    if (uploadedFiles.length === 0) {
        preview.style.display = 'none';
        return;
    }
    
    preview.style.display = 'block';
    fileList.innerHTML = '';
    
    uploadedFiles.forEach((file, index) => {
        const fileTag = document.createElement('div');
        fileTag.style.cssText = 'display: inline-flex; align-items: center; gap: 5px; padding: 5px 10px; background: #e3f2fd; border-radius: 5px; font-size: 12px;';
        
        const icon = getFileIcon(file.name);
        fileTag.innerHTML = `
            ${icon} ${file.name} (${formatFileSize(file.size)})
            <button onclick="removeFile(${index})" style="background: none; border: none; color: #d32f2f; cursor: pointer; font-weight: bold; padding: 0 0 0 5px;">×</button>
        `;
        
        fileList.appendChild(fileTag);
    });
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    displayFilePreview();
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
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
// 3. CLIPBOARD FUNCTIONS
// =============================================================================

function copyToClipboard(event, msgId) {
    const content = document.getElementById(`content_${msgId}`);
    if (!content) return;
    
    // Get text content without HTML
    const text = content.innerText || content.textContent;
    
    // Copy to clipboard
    navigator.clipboard.writeText(text).then(() => {
        // Show success feedback
        const button = event.currentTarget;
        const originalText = button.innerHTML;
        button.innerHTML = '✓ Copied!';
        button.style.background = '#4caf50';
        button.style.color = 'white';
        button.style.borderColor = '#4caf50';
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.background = 'none';
            button.style.color = '#666';
            button.style.borderColor = '#e0e0e0';
        }, 2000);
    }).catch(err => {
        alert('Failed to copy to clipboard');
    });
}

// =============================================================================
// 4. MODE SWITCHING
// =============================================================================

function switchMode(mode) {
    currentMode = mode;
    
    // Update button states
    document.getElementById('quickModeBtn').classList.toggle('active', mode === 'quick');
    document.getElementById('projectModeBtn').classList.toggle('active', mode === 'project');
    document.getElementById('calculatorModeBtn').classList.toggle('active', mode === 'calculator');
    document.getElementById('surveyModeBtn').classList.toggle('active', mode === 'survey');
    document.getElementById('marketingModeBtn').classList.toggle('active', mode === 'marketing');
    document.getElementById('opportunitiesModeBtn').classList.toggle('active', mode === 'opportunities');
    
    // Show/hide panels
    document.getElementById('projectInfo').style.display = mode === 'project' ? 'block' : 'none';
    document.getElementById('calculatorInfo').style.display = mode === 'calculator' ? 'block' : 'none';
    document.getElementById('surveyInfo').style.display = mode === 'survey' ? 'block' : 'none';
    document.getElementById('marketingInfo').style.display = mode === 'marketing' ? 'block' : 'none';
    document.getElementById('opportunitiesInfo').style.display = mode === 'opportunities' ? 'block' : 'none';
    
    // Load data for specific modes
    if (mode === 'project') {
        loadSavedProjects();
    } else if (mode === 'calculator') {
        // Calculator mode ready
    } else if (mode === 'survey') {
        loadQuestionBank();
    } else if (mode === 'marketing') {
        loadMarketingStatus();
    } else if (mode === 'opportunities') {
        loadNormativeStatus();
    }
    
    // Update quick actions
    updateQuickActions();
    
    // Update input placeholder
    const input = document.getElementById('userInput');
    const placeholders = {
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
// 5. QUICK ACTIONS
// =============================================================================

function updateQuickActions() {
    const actions = document.getElementById('quickActions');
    
    const actionSets = {
        'quick': `
            <li onclick="quickAction('Create a 12-hour rotating schedule')">📅 Create Schedule</li>
            <li onclick="quickAction('Analyze overtime costs')">💰 Cost Analysis</li>
            <li onclick="quickAction('Compare DuPont vs 2-2-3 schedules')">⚖️ Compare Schedules</li>
            <li onclick="quickAction('Write a LinkedIn post about shift work')">💼 LinkedIn Post</li>
        `,
        'opportunities': `
            <li onclick="quickAction('Analyze my 12-hour DuPont schedule')">📊 Quick Analysis</li>
            <li onclick="quickAction('Compare my metrics to norms')">📈 Industry Comparison</li>
            <li onclick="quickAction('Find cost reduction opportunities')">💰 Cost Savings</li>
            <li onclick="quickAction('Evaluate schedule alternatives')">🔄 Alternative Schedules</li>
        `,
        'default': `
            <li onclick="quickAction('data collection')">📋 Data Collection Doc</li>
            <li onclick="quickAction('proposal')">📄 Create Proposal</li>
            <li onclick="quickAction('analyze files')">📊 Analyze Files</li>
            <li onclick="quickAction('linkedin post')">💼 LinkedIn Post</li>
        `
    };
    
    actions.innerHTML = actionSets[currentMode] || actionSets['default'];
}

function quickAction(action) {
    document.getElementById('userInput').value = action;
    sendMessage();
}

// =============================================================================
// 6. PROJECT MANAGEMENT
// =============================================================================

function loadSavedProjects() {
    fetch('/api/projects')
        .then(r => r.json())
        .then(data => {
            const select = document.getElementById('existingProjects');
            if (!select) return;
            
            // Keep the first option
            select.innerHTML = '<option value="">-- Select Project --</option>';
            
            if (data.success && data.projects.length > 0) {
                data.projects.forEach(project => {
                    const option = document.createElement('option');
                    option.value = project.project_id;
                    option.textContent = `${project.client_name} (${project.project_phase})`;
                    select.appendChild(option);
                });
            }
        });
}

function loadExistingProject() {
    const select = document.getElementById('existingProjects');
    const projectId = select.value;
    
    if (!projectId) {
        currentProjectId = null;
        document.getElementById('clientName').textContent = 'No active project';
        document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">Not started</div>';
        return;
    }
    
    // Load project details
    fetch(`/api/project/${projectId}/context`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                currentProjectId = projectId;
                document.getElementById('clientName').textContent = data.client_name;
                document.getElementById('projectPhase').innerHTML = `<div class="phase-indicator">${data.phase}</div>`;
                
                addMessage('assistant', `✅ Loaded project for ${data.client_name}. Currently in ${data.phase} phase. ${data.files_count} files uploaded, ${data.findings_count} findings recorded.`, null, 'project');
            }
        });
}

function startNewProject() {
    const clientName = prompt("Enter client name:");
    if (!clientName) return;
    
    const industry = prompt("Enter industry (e.g., Pharmaceutical, Food Processing):");
    const facilityType = prompt("Enter facility type (e.g., Manufacturing, Distribution):");
    
    fetch('/api/project/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            client_name: clientName,
            industry: industry,
            facility_type: facilityType
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            currentProjectId = data.project_id;
            document.getElementById('clientName').textContent = clientName;
            document.getElementById('projectPhase').innerHTML = '<div class="phase-indicator">Initial Phase</div>';
            
            // Refresh projects list
            loadSavedProjects();
            
            // Select the new project
            setTimeout(() => {
                document.getElementById('existingProjects').value = data.project_id;
            }, 500);
            
            addMessage('assistant', `✅ Project started for ${clientName}! ${data.suggested_first_step}`, null, 'project');
        }
    });
}

// =============================================================================
// 7. MESSAGE HANDLING (CORE)
// =============================================================================

function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    if (!message && uploadedFiles.length === 0) return;
    
    // Add user message
    let displayMessage = message || 'Uploaded files for analysis';
    if (uploadedFiles.length > 0) {
        displayMessage += ` (${uploadedFiles.length} file${uploadedFiles.length > 1 ? 's' : ''} attached)`;
    }
    addMessage('user', displayMessage);
    
    input.value = '';
    
    // Show loading
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    // Prepare request
    const formData = new FormData();
    formData.append('request', message || 'Please analyze the uploaded files');
    formData.append('enable_consensus', 'true');
    if (currentMode === 'project' && currentProjectId) {
        formData.append('project_id', currentProjectId);
    }
    
    // Add files
    uploadedFiles.forEach((file) => {
        formData.append('files', file);
    });
    
    // Clear uploaded files
    const filesCount = uploadedFiles.length;
    uploadedFiles = [];
    displayFilePreview();
    
    // Send to swarm
    fetch('/api/orchestrate', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            let badges = '';
            if (data.knowledge_used) badges += '<span class="badge knowledge">📚 Knowledge</span>';
            if (data.project_workflow && data.project_workflow.active) badges += '<span class="badge workflow">📁 Project</span>';
            if (data.formatting_applied) badges += '<span class="badge formatted">🎨 Formatted</span>';
            if (filesCount > 0) badges += `<span class="badge" style="background: #fff3e0; color: #f57c00;">📎 ${filesCount} file${filesCount > 1 ? 's' : ''}</span>`;
            
            // Add download button if document was created
            let downloadSection = '';
            const hasDocument = data.document_created || (data.document_url && data.document_url !== null);
            if (hasDocument && data.document_url) {
                const docType = (data.document_type || 'docx').toUpperCase();
                const icon = docType === 'PDF' ? '📄' : docType === 'DOCX' ? '📝' : docType === 'XLSX' ? '📊' : '📄';
                
                downloadSection = `
                    <div style="margin-top: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #4caf50; border-radius: 4px;">
                        <div style="font-weight: 600; margin-bottom: 8px; color: #2e7d32;">
                            ${icon} Document Created
                        </div>
                        <a href="${data.document_url}" download style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: #4caf50; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; transition: background 0.2s;">
                            <span>⬇️</span>
                            <span>Download ${docType}</span>
                        </a>
                        <div style="font-size: 11px; color: #666; margin-top: 8px;">
                            Professional ${docType} document ready for download
                        </div>
                    </div>
                `;
            }
            
            addMessage('assistant', data.result + '<div style="margin-top: 10px;">' + badges + '</div>' + downloadSection, data.task_id, currentMode, data);
            
            // Refresh stats
            loadStats();
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function addMessage(role, content, taskId = null, mode = null, data = null) {
    const conversation = document.getElementById('conversation');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    const msgId = `msg_${++messageCounter}`;
    messageDiv.id = msgId;
    
    // Initialize ratings storage for this message
    if (taskId) {
        feedbackRatings[msgId] = {
            overall: 0,
            quality: 0,
            accuracy: 0,
            usefulness: 0
        };
    }
    
    let modeIndicator = '';
    if (role === 'assistant' && mode) {
        modeIndicator = mode === 'quick' 
            ? '<span class="mode-indicator quick">⚡ Quick Task</span>'
            : '<span class="mode-indicator project">📁 Project Mode</span>';
    }
    
    const header = role === 'user' ? '👤 You' : '🤖 AI Swarm';
    
    // Add consensus validation display if available
    let consensusSection = '';
    if (role === 'assistant' && data && data.consensus) {
        const consensus = data.consensus;
        const agreementScore = consensus.agreement_score || 0;
        const scorePercent = (agreementScore * 100).toFixed(0);
        
        consensusSection = `
            <div style="margin-top: 15px; padding: 12px; background: #f8f9fa; border-left: 4px solid ${agreementScore >= 0.7 ? '#4caf50' : '#ff9800'}; border-radius: 4px;">
                <div style="font-weight: 600; margin-bottom: 8px; color: #333;">
                    ✓ Multi-AI Consensus Validation
                </div>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <div style="flex: 1; background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">
                        <div style="width: ${scorePercent}%; height: 100%; background: ${agreementScore >= 0.7 ? '#4caf50' : '#ff9800'}; transition: width 0.3s;"></div>
                    </div>
                    <div style="font-weight: 700; color: ${agreementScore >= 0.7 ? '#4caf50' : '#ff9800'};">${scorePercent}%</div>
                </div>
                <div style="font-size: 12px; color: #666;">
                    ${agreementScore >= 0.7 
                        ? '✅ High agreement - output validated by multiple AIs' 
                        : '⚠️ Lower agreement - consider reviewing output'}
                </div>
                <div style="font-size: 11px; color: #999; margin-top: 4px;">
                    Validated by: ${consensus.validators ? consensus.validators.join(', ') : 'Multiple AIs'}
                </div>
            </div>
        `;
    }
    
    let feedbackSection = '';
    if (role === 'assistant' && taskId) {
        feedbackSection = buildFeedbackSection(msgId, taskId);
    }
    
    messageDiv.innerHTML = `
        <div class="message-header">
            ${header} ${modeIndicator}
            ${role === 'assistant' ? `<button onclick="copyToClipboard(event, '${msgId}')" style="background: none; border: 1px solid #e0e0e0; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; color: #666; margin-left: auto;">📋 Copy</button>` : ''}
        </div>
        <div class="message-content" id="content_${msgId}">${content}</div>
        ${consensusSection}
        ${feedbackSection}
    `;
    
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
}

function buildFeedbackSection(msgId, taskId) {
    return `
        <div class="message-actions">
            <button class="btn-link" onclick="toggleFeedback('${msgId}')">💬 Provide Feedback (Help System Learn)</button>
        </div>
        <div class="feedback-section" id="feedback_${msgId}">
            <div class="feedback-header">📊 Rate This Output (Helps AI Learn)</div>
            
            <div class="rating-row">
                <span class="rating-label">Overall Quality:</span>
                <div class="star-rating" id="stars_overall_${msgId}">
                    ${[1,2,3,4,5].map(i => `<span class="star" onclick="setRating('${msgId}', 'overall', ${i})">★</span>`).join('')}
                </div>
            </div>
            
            <div class="rating-row">
                <span class="rating-label">Accuracy:</span>
                <div class="star-rating" id="stars_accuracy_${msgId}">
                    ${[1,2,3,4,5].map(i => `<span class="star" onclick="setRating('${msgId}', 'accuracy', ${i})">★</span>`).join('')}
                </div>
            </div>
            
            <div class="rating-row">
                <span class="rating-label">Usefulness:</span>
                <div class="star-rating" id="stars_usefulness_${msgId}">
                    ${[1,2,3,4,5].map(i => `<span class="star" onclick="setRating('${msgId}', 'usefulness', ${i})">★</span>`).join('')}
                </div>
            </div>
            
            <div class="rating-row">
                <span class="rating-label">Clarity:</span>
                <div class="star-rating" id="stars_quality_${msgId}">
                    ${[1,2,3,4,5].map(i => `<span class="star" onclick="setRating('${msgId}', 'quality', ${i})">★</span>`).join('')}
                </div>
            </div>
            
            <div style="margin-top: 15px;">
                <strong style="font-size: 13px;">What needs improvement? (optional)</strong>
                <div class="improvement-checks">
                    <label class="improvement-check">
                        <input type="checkbox" value="more_specific" id="imp_more_specific_${msgId}">
                        <span>More specific</span>
                    </label>
                    <label class="improvement-check">
                        <input type="checkbox" value="wrong_tone" id="imp_wrong_tone_${msgId}">
                        <span>Wrong tone</span>
                    </label>
                    <label class="improvement-check">
                        <input type="checkbox" value="missing_points" id="imp_missing_points_${msgId}">
                        <span>Missing key points</span>
                    </label>
                    <label class="improvement-check">
                        <input type="checkbox" value="too_long" id="imp_too_long_${msgId}">
                        <span>Too long/short</span>
                    </label>
                    <label class="improvement-check">
                        <input type="checkbox" value="factual_errors" id="imp_factual_errors_${msgId}">
                        <span>Factual errors</span>
                    </label>
                    <label class="improvement-check">
                        <input type="checkbox" value="poor_formatting" id="imp_poor_formatting_${msgId}">
                        <span>Poor formatting</span>
                    </label>
                </div>
            </div>
            
            <textarea class="feedback-input" id="comment_${msgId}" placeholder="Additional comments to help the system improve..."></textarea>
            
            <div class="feedback-actions">
                <button class="btn-feedback primary" onclick="submitFeedback('${msgId}', ${taskId}, true)">
                    ✓ Submit & I Used This Output
                </button>
                <button class="btn-feedback secondary" onclick="submitFeedback('${msgId}', ${taskId}, false)">
                    Submit (Didn't Use)
                </button>
            </div>
            
            <div id="feedbackSuccess_${msgId}" style="display: none;"></div>
        </div>
    `;
}

// =============================================================================
// 8. FEEDBACK SYSTEM
// =============================================================================

function toggleFeedback(msgId) {
    const feedback = document.getElementById(`feedback_${msgId}`);
    feedback.classList.toggle('active');
}

function setRating(msgId, type, rating) {
    // Store the rating
    feedbackRatings[msgId][type] = rating;
    
    // Update star display
    const stars = document.querySelectorAll(`#stars_${type}_${msgId} .star`);
    stars.forEach((star, idx) => {
        if (idx < rating) {
            star.classList.add('active');
        } else {
            star.classList.remove('active');
        }
    });
}

function submitFeedback(msgId, taskId, outputUsed) {
    const ratings = feedbackRatings[msgId];
    
    // Validate that at least overall rating is set
    if (ratings.overall === 0) {
        alert('Please rate at least the Overall Quality');
        return;
    }
    
    // Default other ratings to overall if not set
    const overall_rating = ratings.overall;
    const quality_rating = ratings.quality || ratings.overall;
    const accuracy_rating = ratings.accuracy || ratings.overall;
    const usefulness_rating = ratings.usefulness || ratings.overall;
    
    // Get improvement categories
    const improvements = [];
    const checkboxes = [
        'more_specific', 'wrong_tone', 'missing_points', 
        'too_long', 'factual_errors', 'poor_formatting'
    ];
    
    checkboxes.forEach(cb => {
        const elem = document.getElementById(`imp_${cb}_${msgId}`);
        if (elem && elem.checked) {
            improvements.push(cb);
        }
    });
    
    // Get comment
    const comment = document.getElementById(`comment_${msgId}`).value;
    
    // Submit to backend
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
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Hide feedback form, show success
            const feedbackSection = document.getElementById(`feedback_${msgId}`);
            
            feedbackSection.innerHTML = `
                <div class="feedback-success">
                    ✅ Feedback recorded! The AI swarm is learning from your input.
                    ${data.learning_updated ? '<br>Learning patterns updated.' : ''}
                </div>
            `;
            
            // Refresh stats
            loadStats();
        }
    })
    .catch(err => {
        alert('Error submitting feedback: ' + err.message);
    });
}

// =============================================================================
// 9. STATISTICS & DOCUMENTS
// =============================================================================

function loadStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            document.getElementById('totalTasks').textContent = data.total_tasks || 0;
        });
    
    fetch('/api/learning/stats')
        .then(r => r.json())
        .then(data => {
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
        .then(r => r.json())
        .then(data => {
            const docsList = document.getElementById('documentsList');
            
            if (!data.success || data.documents.length === 0) {
                docsList.innerHTML = '<div style="color: #999; padding: 10px; text-align: center;">No documents yet</div>';
                return;
            }
            
            docsList.innerHTML = '';
            
            data.documents.forEach(doc => {
                const docItem = document.createElement('div');
                docItem.style.cssText = 'padding: 8px; margin: 4px 0; background: #f8f9fa; border-radius: 6px; border: 1px solid #e0e0e0;';
                
                const icon = doc.type === 'pdf' ? '📄' : doc.type === 'docx' ? '📝' : doc.type === 'xlsx' ? '📊' : '📎';
                const size = formatFileSize(doc.size);
                const date = new Date(doc.modified).toLocaleDateString();
                
                docItem.innerHTML = `
                    <div style="display: flex; align-items: start; gap: 6px;">
                        <span style="font-size: 16px;">${icon}</span>
                        <div style="flex: 1; min-width: 0;">
                            <div style="font-weight: 600; font-size: 11px; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${doc.filename}">
                                ${doc.filename}
                            </div>
                            <div style="font-size: 10px; color: #999; margin-top: 2px;">
                                ${size} • ${date}
                            </div>
                            <a href="${doc.download_url}" download style="display: inline-block; margin-top: 4px; padding: 4px 8px; background: #667eea; color: white; text-decoration: none; border-radius: 4px; font-size: 10px; font-weight: 600;">
                                ⬇️ Download
                            </a>
                        </div>
                    </div>
                `;
                
                docsList.appendChild(docItem);
            });
        });
}

function refreshDocuments() {
    loadDocuments();
}

// =============================================================================
// 10. MARKETING FUNCTIONS
// =============================================================================

function loadMarketingStatus() {
    fetch('/api/marketing/status')
        .then(r => r.json())
        .then(data => {
            const statusDiv = document.getElementById('platformStatus');
            if (data.platforms) {
                const linkedin = data.platforms.linkedin ? '✅' : '❌';
                const twitter = data.platforms.twitter ? '✅' : '❌';
                const facebook = data.platforms.facebook ? '✅' : '❌';
                
                statusDiv.innerHTML = `
                    <div style="font-size: 11px;">
                        ${linkedin} LinkedIn<br>
                        ${twitter} Twitter/X<br>
                        ${facebook} Facebook
                    </div>
                `;
            }
        });
}

function generateMarketingIdea() {
    addMessage('user', '🚀 "Hey Jim, I have an idea!"');
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/idea')
        .then(r => r.json())
        .then(data => {
            loading.classList.remove('active');
            
            if (data.success && data.has_idea) {
                addMessage('assistant', data.message, null, 'marketing');
            } else if (data.success && !data.has_idea) {
                addMessage('assistant', data.message, null, 'marketing');
            } else {
                addMessage('assistant', `❌ Error: ${data.error || 'Unknown error'}`);
            }
        })
        .catch(err => {
            loading.classList.remove('active');
            addMessage('assistant', `❌ Error: ${err.message}`);
        });
}

function generateSocialPost() {
    const topic = prompt('What topic should the post be about?');
    if (!topic) return;
    
    addMessage('user', `Generate a LinkedIn post about: ${topic}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic, platform: 'linkedin'})
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            const content = data.content;
            const postAction = `
                <div style="margin-top: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #0077b5; border-radius: 4px;">
                    <div style="font-weight: 600; margin-bottom: 8px; color: #0077b5;">
                        📝 LinkedIn Post Generated
                    </div>
                    <button onclick="postToLinkedIn(\`${content.replace(/`/g, '\\`')}\`)" style="padding: 8px 16px; background: #0077b5; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">
                        📤 Post to LinkedIn
                    </button>
                    <div style="font-size: 11px; color: #666; margin-top: 8px;">
                        ${data.length} characters • Ready to post
                    </div>
                </div>
            `;
            
            addMessage('assistant', content + postAction, null, 'marketing');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function postToLinkedIn(content) {
    if (!confirm('Post this to LinkedIn now?')) return;
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/post', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content, platform: 'linkedin'})
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            addMessage('assistant', `✅ Posted to LinkedIn successfully! Post ID: ${data.post_id}`, null, 'marketing');
        } else {
            addMessage('assistant', `❌ Error posting: ${data.error}`, null, 'marketing');
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function conductResearch() {
    const topic = prompt('What market research topic?');
    if (!topic) return;
    
    addMessage('user', `Conduct market research on: ${topic}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/research', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic})
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            addMessage('assistant', data.findings, null, 'marketing');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function analyzeCompetitors() {
    addMessage('user', 'Analyze competitors in the shift scheduling consulting space');
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/marketing/research', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic: 'competitive analysis for shift scheduling consulting services'})
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            addMessage('assistant', data.findings, null, 'marketing');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

// =============================================================================
// 11. CALCULATOR FUNCTIONS
// =============================================================================

function calculateOvertimeCost() {
    const baseWage = prompt('Enter base hourly wage (e.g., 25):');
    if (!baseWage) return;
    
    const otHours = prompt('Enter average overtime hours per week (e.g., 10):');
    if (!otHours) return;
    
    addMessage('user', `Calculate overtime cost: $${baseWage}/hr with ${otHours} OT hours/week`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/calculator/overtime', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            base_wage: parseFloat(baseWage),
            ot_hours_weekly: parseFloat(otHours)
        })
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            const calc = data.calculation;
            const response = `
💰 OVERTIME COST ANALYSIS

Base Wage: $${calc.base_wage}/hour
Overtime Rate: $${calc.overtime_rate}/hour (1.5x)
Weekly OT Hours: ${calc.overtime_hours_weekly}

📊 ANNUAL COSTS:
• OT Wages: $${calc.overtime_wages_annual.toLocaleString()}
• Burden/Benefits: $${calc.burden_cost_annual.toLocaleString()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• TOTAL: $${calc.total_cost_annual.toLocaleString()}/year

Weekly Cost: $${calc.total_cost_weekly.toLocaleString()}
            `;
            addMessage('assistant', response, null, 'calculator');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function compareHireVsOT() {
    const currentOT = prompt('Enter current annual overtime cost (e.g., 50000):');
    if (!currentOT) return;
    
    const newWage = prompt('Enter annual wage for new employee (e.g., 45000):');
    if (!newWage) return;
    
    addMessage('user', `Compare: $${currentOT} OT vs hiring at $${newWage}/year`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/calculator/hire-vs-ot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            current_ot_cost: parseFloat(currentOT),
            new_employee_wage: parseFloat(newWage)
        })
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            const comp = data.comparison;
            const response = `
👥 HIRE vs OVERTIME COMPARISON

Current OT Cost: $${comp.current_overtime_cost.toLocaleString()}/year
New Employee Cost: $${comp.new_employee_annual_cost.toLocaleString()}/year
First Year (with training): $${comp.new_employee_first_year_cost.toLocaleString()}

💡 FINANCIAL IMPACT:
• Annual Savings: $${comp.annual_savings.toLocaleString()}
• First Year Savings: $${comp.first_year_savings.toLocaleString()}
• Payback Period: ${comp.payback_months} months

✅ RECOMMENDATION: ${comp.recommendation}
${comp.break_even_analysis}
            `;
            addMessage('assistant', response, null, 'calculator');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function scheduleImpact() {
    addMessage('user', 'Calculate schedule change financial impact');
    addMessage('assistant', '🔧 Schedule impact calculator coming soon! For now, use the AI to analyze schedule changes by describing your current and proposed schedules.', null, 'calculator');
}

// =============================================================================
// 12. SURVEY FUNCTIONS
// =============================================================================

function loadQuestionBank() {
    fetch('/api/survey/questions')
        .then(r => r.json())
        .then(data => {
            const statusDiv = document.getElementById('questionBankStatus');
            if (data.success) {
                statusDiv.innerHTML = `
                    <div style="font-size: 11px;">
                        ✅ ${data.total_count} validated questions<br>
                        Ready to build surveys
                    </div>
                `;
            }
        });
}

function createNewSurvey() {
    const projectName = prompt('Enter project/client name:');
    if (!projectName) return;
    
    addMessage('user', `Create new survey for: ${projectName}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/survey/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            project_name: projectName,
            selected_questions: ['dept', 'shift', 'time_off_importance', 'current_satisfaction', 'overtime_willing']
        })
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            const survey = data.survey;
            const response = `
✅ SURVEY CREATED

Project: ${survey.project_name}
Survey ID: ${survey.id}
Questions: ${survey.questions.length}
Survey Link: ${survey.link}

📋 Included Questions:
${survey.questions.map(q => `• ${q.text}`).join('\n')}

🔗 Share this link with employees to collect responses.
            `;
            addMessage('assistant', response, null, 'survey');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function viewSurveyResults() {
    const surveyId = prompt('Enter Survey ID:');
    if (!surveyId) return;
    
    addMessage('user', `View results for survey: ${surveyId}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch(`/api/survey/${surveyId}/analyze`)
        .then(r => r.json())
        .then(data => {
            loading.classList.remove('active');
            
            if (data.success || data.response_count !== undefined) {
                if (data.response_count === 0) {
                    addMessage('assistant', '📊 No responses yet. Share the survey link with employees.', null, 'survey');
                } else {
                    const insights = data.key_insights ? data.key_insights.join('\n') : 'Analysis complete';
                    const response = `
📊 SURVEY RESULTS ANALYSIS

Project: ${data.project_name}
Responses: ${data.response_count}

🔍 KEY INSIGHTS:
${insights}

Questions Analyzed: ${Object.keys(data.questions_analyzed || {}).length}

Use the Export function to download full data for detailed analysis.
                    `;
                    addMessage('assistant', response, null, 'survey');
                }
            } else {
                addMessage('assistant', `❌ Error: ${data.error || 'Unknown error'}`);
            }
        })
        .catch(err => {
            loading.classList.remove('active');
            addMessage('assistant', `❌ Error: ${err.message}`);
        });
}

function exportSurveyData() {
    const surveyId = prompt('Enter Survey ID to export:');
    if (!surveyId) return;
    
    addMessage('user', `Export survey data: ${surveyId}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch(`/api/survey/${surveyId}/export`)
        .then(r => r.json())
        .then(data => {
            loading.classList.remove('active');
            
            if (data.success) {
                // Create downloadable CSV file
                const blob = new Blob([data.csv_data], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `survey_${surveyId}_export.csv`;
                a.click();
                
                addMessage('assistant', `✅ Survey data exported successfully! Check your downloads for survey_${surveyId}_export.csv (Remark-compatible format)`, null, 'survey');
            } else {
                addMessage('assistant', `❌ Error: ${data.error}`);
            }
        })
        .catch(err => {
            loading.classList.remove('active');
            addMessage('assistant', `❌ Error: ${err.message}`);
        });
}

// =============================================================================
// 13. OPPORTUNITIES FUNCTIONS
// =============================================================================

function loadNormativeStatus() {
    fetch('/api/opportunities/status')
        .then(r => r.json())
        .then(data => {
            const statusDiv = document.getElementById('normativeStatus');
            if (data.success) {
                statusDiv.innerHTML = `
                    <div style="font-size: 11px;">
                        ✅ ${data.schedules_count || 0} companies<br>
                        ✅ ${data.metrics_count || 0} metrics<br>
                        Ready for analysis
                    </div>
                `;
            } else {
                statusDiv.innerHTML = '<div style="font-size: 11px; color: #d32f2f;">⚠️ Database loading...</div>';
            }
        })
        .catch(err => {
            document.getElementById('normativeStatus').innerHTML = 
                '<div style="font-size: 11px; color: #d32f2f;">⚠️ Database loading...</div>';
        });
}

function analyzeScheduleOpportunities() {
    const scheduleInfo = prompt('Describe your current schedule (e.g., "12-hour rotating DuPont, 4 crews, 24/7"):');
    if (!scheduleInfo) return;
    
    addMessage('user', `Analyze opportunities for: ${scheduleInfo}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/opportunities/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ schedule_description: scheduleInfo })
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            let response = `🎯 OPPORTUNITY ANALYSIS\n\n`;
            response += `Current Schedule: ${data.analysis.schedule_type}\n\n`;
            response += `📊 KEY FINDINGS:\n`;
            data.analysis.opportunities.forEach(opp => {
                response += `\n• ${opp.finding}\n`;
                response += `  Impact: ${opp.impact}\n`;
                response += `  Priority: ${opp.priority}\n`;
            });
            
            if (data.analysis.recommendations) {
                response += `\n💡 RECOMMENDATIONS:\n`;
                data.analysis.recommendations.forEach(rec => {
                    response += `\n• ${rec}\n`;
                });
            }
            
            addMessage('assistant', response, null, 'opportunities');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function compareToNorms() {
    const metrics = prompt('Enter your current metrics (e.g., "15% turnover, 12% overtime, 85% coverage"):');
    if (!metrics) return;
    
    addMessage('user', `Compare to industry norms: ${metrics}`);
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/opportunities/compare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ current_metrics: metrics })
    })
    .then(r => r.json())
    .then(data => {
        loading.classList.remove('active');
        
        if (data.success) {
            let response = `📈 INDUSTRY COMPARISON\n\n`;
            response += `Your Performance vs Industry Norms:\n\n`;
            
            data.comparison.forEach(item => {
                response += `${item.metric}:\n`;
                response += `  You: ${item.your_value}\n`;
                response += `  Industry: ${item.norm_value}\n`;
                response += `  Status: ${item.status} (${item.variance})\n\n`;
            });
            
            if (data.gap_analysis) {
                response += `🎯 GAP ANALYSIS:\n${data.gap_analysis}\n`;
            }
            
            addMessage('assistant', response, null, 'opportunities');
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    })
    .catch(err => {
        loading.classList.remove('active');
        addMessage('assistant', `❌ Error: ${err.message}`);
    });
}

function findImprovements() {
    addMessage('user', 'Find improvement opportunities');
    
    const loading = document.getElementById('loadingIndicator');
    loading.classList.add('active');
    
    fetch('/api/opportunities/suggest')
        .then(r => r.json())
        .then(data => {
            loading.classList.remove('active');
            
            if (data.success) {
                let response = `💡 IMPROVEMENT OPPORTUNITIES\n\n`;
                response += `Top Recommendations:\n\n`;
                
                data.suggestions.forEach((sugg, idx) => {
                    response += `${idx + 1}. ${sugg.title}\n`;
                    response += `   ${sugg.description}\n`;
                    response += `   Expected Impact: ${sugg.impact}\n`;
                    response += `   Difficulty: ${sugg.difficulty}\n\n`;
                });
                
                addMessage('assistant', response, null, 'opportunities');
            } else {
                addMessage('assistant', `❌ Error: ${data.error}`);
            }
        })
        .catch(err => {
            loading.classList.remove('active');
            addMessage('assistant', `❌ Error: ${err.message}`);
        });
}

// =============================================================================
// 14. INITIALIZATION
// =============================================================================

function initializeApp() {
    // Initialize quick actions
    updateQuickActions();
    
    // Load initial stats
    loadStats();
    
    // Load documents
    loadDocuments();
    
    // Set up Enter key handler for input
    document.getElementById('userInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Set up periodic refresh (every 30 seconds)
    setInterval(() => {
        loadStats();
        loadDocuments();
    }, 30000);
    
    console.log('AI Swarm Interface initialized successfully');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

/* I did no harm and this file is not truncated */
