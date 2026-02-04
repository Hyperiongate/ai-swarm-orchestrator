/**
 * CONVERSATION LEARNING SYSTEM - FRONTEND
 * Created: February 4, 2026
 * 
 * Adds "Extract Lessons Learned" functionality to conversation interface.
 * Every conversation becomes a learning opportunity.
 * 
 * Author: Jim @ Shiftwork Solutions LLC
 */

class ConversationLearningUI {
    constructor() {
        this.currentConversationId = null;
        this.conversationHistory = [];
        this.isExtracting = false;
    }

    /**
     * Initialize the learning system
     * Call this after the chat interface loads
     */
    init(conversationId) {
        this.currentConversationId = conversationId;
        this.addExtractButton();
        this.trackConversation();
    }

    /**
     * Add "Extract Lessons" button to conversation interface
     */
    addExtractButton() {
        // Find the conversation controls area (adjust selector as needed)
        const controlsArea = document.querySelector('.conversation-controls') || 
                            document.querySelector('.chat-header') ||
                            document.querySelector('.header-nav');
        
        if (!controlsArea) {
            console.warn('Could not find conversation controls area');
            return;
        }

        // Create extract button
        const extractBtn = document.createElement('button');
        extractBtn.id = 'extractLessonsBtn';
        extractBtn.className = 'nav-btn extract-lessons-btn';
        extractBtn.innerHTML = '🎓 Extract Lessons';
        extractBtn.onclick = () => this.extractLessons();
        
        // Add to controls
        controlsArea.appendChild(extractBtn);
        
        console.log('✅ Extract Lessons button added');
    }

    /**
     * Track conversation messages
     * Call this after each message exchange
     */
    trackConversation() {
        // Hook into existing chat system to track messages
        // This is a placeholder - adjust based on actual chat implementation
        
        const originalSendMessage = window.sendMessage;
        if (originalSendMessage) {
            window.sendMessage = async (...args) => {
                const result = await originalSendMessage(...args);
                this.addToHistory('user', args[0]);
                return result;
            };
        }
    }

    /**
     * Add message to conversation history
     */
    addToHistory(role, message) {
        this.conversationHistory.push({
            role: role,
            message: message,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Main function - Extract lessons from conversation
     */
    async extractLessons() {
        if (this.isExtracting) {
            return;
        }

        if (this.conversationHistory.length < 4) {
            this.showNotification('Need at least 2 message exchanges to extract lessons', 'info');
            return;
        }

        const button = document.getElementById('extractLessonsBtn');
        const originalText = button.innerHTML;
        
        this.isExtracting = true;
        button.disabled = true;
        button.innerHTML = '⏳ Analyzing conversation...';

        try {
            // Get conversation metadata
            const metadata = this.getConversationMetadata();

            // Call API to extract lessons
            const response = await fetch(`/api/conversations/${this.currentConversationId}/extract-lessons`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversation: this.conversationHistory,
                    metadata: metadata
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccessModal(data);
            } else {
                this.showNotification(data.error || 'Failed to extract lessons', 'error');
            }

        } catch (error) {
            console.error('Extract lessons error:', error);
            this.showNotification('Failed to extract lessons: ' + error.message, 'error');
        } finally {
            this.isExtracting = false;
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }

    /**
     * Get metadata about current conversation
     */
    getConversationMetadata() {
        // Try to detect topic from conversation
        const firstUserMessage = this.conversationHistory.find(m => m.role === 'user');
        
        return {
            topic: this.detectTopic(firstUserMessage?.message || ''),
            started_at: this.conversationHistory[0]?.timestamp,
            message_count: this.conversationHistory.length
        };
    }

    /**
     * Simple topic detection
     */
    detectTopic(message) {
        const topics = {
            'schedule': /schedule|shift|rotation|pattern/i,
            'overtime': /overtime|ot|hours/i,
            'cost': /cost|wage|salary|budget/i,
            'implementation': /implement|deploy|rollout|change/i,
            'survey': /survey|questionnaire|feedback/i,
            'client': /client|customer|company/i
        };

        for (const [topic, regex] of Object.entries(topics)) {
            if (regex.test(message)) {
                return topic;
            }
        }

        return 'general';
    }

    /**
     * Show success modal with extracted lessons
     */
    showSuccessModal(data) {
        const modal = document.createElement('div');
        modal.className = 'lesson-extraction-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h2>🎉 Lessons Captured!</h2>
                    <button class="close-btn" onclick="this.closest('.lesson-extraction-modal').remove()">×</button>
                </div>
                <div class="modal-body">
                    <div class="success-stats">
                        <div class="stat">
                            <div class="stat-value">${data.lessons_extracted}</div>
                            <div class="stat-label">Lessons Extracted</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${data.patterns_extracted || 0}</div>
                            <div class="stat-label">Patterns Found</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${data.insights_extracted || 0}</div>
                            <div class="stat-label">Insights Captured</div>
                        </div>
                    </div>
                    
                    ${data.categories && data.categories.length > 0 ? `
                    <div class="lesson-categories">
                        <h3>Categories:</h3>
                        <div class="category-tags">
                            ${data.categories.map(cat => `<span class="category-tag">${cat.replace(/_/g, ' ')}</span>`).join('')}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${data.preview && data.preview.length > 0 ? `
                    <div class="lesson-preview">
                        <h3>Preview:</h3>
                        ${data.preview.map(lesson => `
                            <div class="lesson-item">
                                <div class="lesson-title">${lesson.title}</div>
                                <div class="lesson-insight">${lesson.insight.substring(0, 150)}${lesson.insight.length > 150 ? '...' : ''}</div>
                            </div>
                        `).join('')}
                    </div>
                    ` : ''}
                    
                    <div class="success-message">
                        <p><strong>${data.message}</strong></p>
                        <p>These lessons are now part of your knowledge base and will inform future conversations.</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" onclick="window.location.href='/knowledge'">
                        View Knowledge Base
                    </button>
                    <button class="btn btn-secondary" onclick="this.closest('.lesson-extraction-modal').remove()">
                        Continue Conversation
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()">×</button>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Styles for the learning UI
const styles = `
<style>
.extract-lessons-btn {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    border: none;
}

.extract-lessons-btn:hover {
    background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
}

.lesson-extraction-modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
}

.modal-content {
    position: relative;
    background: white;
    border-radius: 16px;
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modal-header {
    padding: 24px;
    border-bottom: 2px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h2 {
    margin: 0;
    color: #667eea;
}

.close-btn {
    background: none;
    border: none;
    font-size: 32px;
    cursor: pointer;
    color: #999;
    line-height: 1;
}

.close-btn:hover {
    color: #333;
}

.modal-body {
    padding: 24px;
}

.success-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.stat {
    text-align: center;
    padding: 16px;
    background: #f8f9ff;
    border-radius: 8px;
}

.stat-value {
    font-size: 32px;
    font-weight: 700;
    color: #667eea;
}

.stat-label {
    font-size: 14px;
    color: #666;
    margin-top: 4px;
}

.lesson-categories {
    margin-bottom: 24px;
}

.category-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
}

.category-tag {
    background: #667eea;
    color: white;
    padding: 6px 12px;
    border-radius: 16px;
    font-size: 13px;
    text-transform: capitalize;
}

.lesson-preview {
    margin-bottom: 24px;
}

.lesson-item {
    background: #f8f9ff;
    padding: 12px;
    border-radius: 8px;
    margin-top: 12px;
}

.lesson-title {
    font-weight: 600;
    color: #333;
    margin-bottom: 6px;
}

.lesson-insight {
    font-size: 14px;
    color: #666;
}

.success-message {
    background: #d4edda;
    padding: 16px;
    border-radius: 8px;
    border: 1px solid #c3e6cb;
}

.success-message p {
    margin: 8px 0;
    color: #155724;
}

.modal-footer {
    padding: 16px 24px;
    border-top: 2px solid #f0f0f0;
    display: flex;
    gap: 12px;
    justify-content: flex-end;
}

.btn {
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
    background: white;
    color: #667eea;
    border: 2px solid #667eea;
}

.btn-secondary:hover {
    background: #f8f9ff;
}

.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 16px 24px;
    border-radius: 8px;
    background: white;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 10000;
    animation: slideIn 0.3s ease;
}

.notification-info {
    border-left: 4px solid #667eea;
}

.notification-success {
    border-left: 4px solid #28a745;
}

.notification-error {
    border-left: 4px solid #dc3545;
}

.notification button {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: #999;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', styles);

// Export for use
window.ConversationLearningUI = ConversationLearningUI;

// Auto-initialize if conversation exists
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a conversation page
    const conversationId = window.location.search.match(/conversation=([^&]+)/)?.[1];
    
    if (conversationId) {
        window.conversationLearning = new ConversationLearningUI();
        window.conversationLearning.init(conversationId);
        console.log('✅ Conversation Learning System initialized');
    }
});
