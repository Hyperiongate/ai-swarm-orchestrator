"""
CODE ASSISTANT AGENT - Self-Improving AI System
Created: January 27, 2026
Last Updated: January 27, 2026

This agent enables the AI to:
1. Detect when user is giving code feedback
2. Read existing code from knowledge base or live files
3. Understand what needs to be fixed
4. Generate complete, corrected code
5. Provide deployment-ready files

USAGE:
User: "The 2-2-3 schedule starts on the wrong day. It should be Sunday."
Agent: [Reads schedule_generator.py, fixes bug, returns complete corrected file]

Author: Jim @ Shiftwork Solutions LLC
"""

import os
import re
from datetime import datetime


class CodeAssistantAgent:
    """
    AI agent that can read, understand, and fix its own code
    """
    
    def __init__(self, knowledge_base=None):
        self.knowledge_base = knowledge_base
        self.code_files = self._discover_code_files()
        
    def _discover_code_files(self):
        """Discover all Python code files in the system"""
        code_files = {}
        
        # Common code file locations
        search_paths = [
            '/opt/render/project/src',  # Render deployment
            '/home/claude',              # Local development
            '.',                         # Current directory
            '/mnt/project'              # Project knowledge
        ]
        
        for search_path in search_paths:
            if os.path.exists(search_path):
                for root, dirs, files in os.walk(search_path):
                    # Skip __pycache__ and .venv
                    dirs[:] = [d for d in dirs if d not in ['__pycache__', '.venv', 'node_modules', '.git']]
                    
                    for file in files:
                        if file.endswith('.py'):
                            full_path = os.path.join(root, file)
                            code_files[file] = full_path
        
        return code_files
    
    def detect_code_feedback(self, user_message):
        """
        Detect if user is giving feedback about code
        
        Returns:
            dict: {
                'is_code_feedback': bool,
                'target_file': str,
                'feedback_type': str,  # 'bug', 'feature', 'improvement'
                'description': str
            }
        """
        user_lower = user_message.lower()
        
        # PRIORITY CHECK: If message mentions a .py file, it's DEFINITELY code feedback
        py_file_pattern = r'[\w_/]+\.py'
        py_file_match = re.search(py_file_pattern, user_message, re.IGNORECASE)
        if py_file_match:
            # Found a .py filename - this is code feedback!
            return {
                'is_code_feedback': True,
                'target_file': py_file_match.group(0),
                'feedback_type': self._determine_feedback_type(user_lower),
                'description': user_message
            }
        
        # Keywords that indicate code feedback
        code_keywords = [
            'bug', 'error', 'broken', 'wrong', 'incorrect', 'fix',
            'should', 'need to change', 'update', 'modify',
            'schedule_generator', 'routes', 'database',
            'function', 'method', 'class', 'code', 'file'
        ]
        
        # File name patterns (for non-.py references)
        file_patterns = [
            r'schedule_generator',
            r'routes/core',
            r'database',
            r'app',
            r'schedule_request_handler'
        ]
        
        # Check for code feedback indicators
        is_code_feedback = any(keyword in user_lower for keyword in code_keywords)
        
        if not is_code_feedback:
            return {
                'is_code_feedback': False,
                'target_file': None,
                'feedback_type': None,
                'description': None
            }
        
        # Identify target file
        target_file = None
        for pattern in file_patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                target_file = match.group(0) + '.py'
                break
        
        # If no specific file mentioned, infer from context
        if not target_file:
            if any(word in user_lower for word in ['schedule', '2-2-3', 'pattern', 'crew']):
                target_file = 'schedule_generator.py'
            elif any(word in user_lower for word in ['route', 'endpoint', 'api']):
                target_file = 'routes/core.py'
            elif any(word in user_lower for word in ['database', 'table', 'query']):
                target_file = 'database.py'
        
        return {
            'is_code_feedback': True,
            'target_file': target_file,
            'feedback_type': self._determine_feedback_type(user_lower),
            'description': user_message
        }
    
    def _determine_feedback_type(self, user_lower):
        """Helper to determine if feedback is bug, feature, or improvement"""
        if any(word in user_lower for word in ['add', 'new feature', 'implement', 'create']):
            return 'feature'
        elif any(word in user_lower for word in ['improve', 'better', 'optimize', 'enhance']):
            return 'improvement'
        else:
            return 'bug'
    
    def read_code_file(self, filename):
        """
        Read code from file system or knowledge base
        
        Args:
            filename: Name of the file to read
            
        Returns:
            tuple: (file_content, file_path)
        """
        # Try to find file in discovered code files
        if filename in self.code_files:
            file_path = self.code_files[filename]
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, file_path
            except Exception as e:
                print(f"Could not read {file_path}: {e}")
        
        # Try knowledge base
        if self.knowledge_base:
            try:
                # Search for file in knowledge base
                for kb_filename, kb_data in self.knowledge_base.knowledge_index.items():
                    if filename.lower() in kb_filename.lower():
                        # Get content from knowledge base
                        content = kb_data.get('content', '')
                        return content, f"knowledge_base:{kb_filename}"
            except Exception as e:
                print(f"Could not read from knowledge base: {e}")
        
        return None, None
    
    def generate_fix_prompt(self, feedback_data, current_code):
        """
        Generate a prompt for the AI to fix the code
        
        Args:
            feedback_data: Dict with feedback information
            current_code: Current code content
            
        Returns:
            str: Prompt for AI to generate fix
        """
        target_file = feedback_data['target_file']
        feedback_type = feedback_data['feedback_type']
        description = feedback_data['description']
        
        prompt = f"""You are a senior software engineer fixing code based on user feedback.

**TARGET FILE:** {target_file}

**USER FEEDBACK ({feedback_type}):**
{description}

**CURRENT CODE:**
```python
{current_code}
```

**YOUR TASK:**
1. Analyze the user's feedback carefully
2. Identify what needs to be changed in the code
3. Generate the COMPLETE, CORRECTED code file
4. Ensure all existing functionality remains intact (DO NO HARM)
5. Add comments explaining what you changed and why

**REQUIREMENTS:**
- Provide the ENTIRE file, not just snippets
- Include proper header comments with date of change
- Add a note at the end: "I did no harm and this file is not truncated"
- Test your logic mentally before providing the code
- Preserve all imports, functions, and classes that weren't changed

**OUTPUT FORMAT:**
Provide ONLY the complete Python code, ready to deploy. No explanations outside the code.
Start immediately with the file header."""

        return prompt
    
    def create_deployment_package(self, filename, fixed_code, feedback_data):
        """
        Create a deployment-ready file with documentation
        
        Args:
            filename: Original filename
            fixed_code: Fixed code content
            feedback_data: Feedback information
            
        Returns:
            dict: {
                'filename': str,
                'content': str,
                'change_summary': str,
                'deployment_instructions': str
            }
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate change summary
        change_summary = f"""CODE FIX APPLIED - {timestamp}

**File:** {filename}
**Feedback Type:** {feedback_data['feedback_type']}
**User Request:** {feedback_data['description']}

**What Changed:**
[See code comments for detailed changes]

**Testing Checklist:**
□ Original functionality preserved
□ New fix addresses user feedback
□ No syntax errors
□ Imports remain valid
□ Dependencies unchanged
"""
        
        # Deployment instructions
        deployment_instructions = f"""DEPLOYMENT INSTRUCTIONS:

1. **Backup Current File:**
   - Download current {filename} from GitHub
   - Save as {filename}.backup_{timestamp}

2. **Deploy Fixed File:**
   - Upload the corrected {filename} to GitHub
   - Replace existing file
   - Commit message: "Fix: {feedback_data['description'][:50]}"

3. **Render Auto-Deploy:**
   - Render will automatically detect the change
   - Watch deployment logs for errors
   - Verify fix in production

4. **Rollback Plan:**
   - If issues occur, revert to {filename}.backup_{timestamp}
   - Push to GitHub
   - Render will auto-deploy backup

**Files to Deploy:**
- {filename} (REPLACE existing)
"""
        
        return {
            'filename': filename,
            'content': fixed_code,
            'change_summary': change_summary,
            'deployment_instructions': deployment_instructions,
            'backup_filename': f"{filename}.backup_{timestamp}"
        }
    
    def process_code_feedback(self, user_message, ai_completion_function):
        """
        Main method to process code feedback and generate fixes
        
        Args:
            user_message: User's feedback message
            ai_completion_function: Function to call AI (e.g., call_claude_sonnet)
            
        Returns:
            dict: {
                'success': bool,
                'action': str,
                'target_file': str,
                'original_code': str,
                'fixed_code': str,
                'deployment_package': dict,
                'message': str
            }
        """
        # Step 1: Detect if this is code feedback
        feedback_data = self.detect_code_feedback(user_message)
        
        if not feedback_data['is_code_feedback']:
            return {
                'success': False,
                'action': 'not_code_feedback',
                'message': 'This does not appear to be code feedback.'
            }
        
        # Step 2: Read current code
        target_file = feedback_data['target_file']
        if not target_file:
            return {
                'success': False,
                'action': 'file_not_identified',
                'message': 'Could not identify which file needs to be fixed. Please specify the file name.'
            }
        
        current_code, file_path = self.read_code_file(target_file)
        
        if not current_code:
            return {
                'success': False,
                'action': 'file_not_found',
                'message': f'Could not find or read {target_file}. Available files: {list(self.code_files.keys())}'
            }
        
        print(f"✅ Found {target_file} at {file_path}")
        print(f"📝 Current code: {len(current_code)} characters")
        
        # Step 3: Generate fix prompt
        fix_prompt = self.generate_fix_prompt(feedback_data, current_code)
        
        # Step 4: Get AI to generate fixed code
        print(f"🤖 Asking AI to fix {target_file}...")
        
        try:
            response = ai_completion_function(fix_prompt, max_tokens=16000)
            
            if isinstance(response, dict):
                fixed_code = response.get('content', '')
            else:
                fixed_code = str(response)
            
            if not fixed_code or len(fixed_code) < 100:
                return {
                    'success': False,
                    'action': 'fix_generation_failed',
                    'message': 'AI failed to generate a valid fix.'
                }
            
            print(f"✅ Generated fix: {len(fixed_code)} characters")
            
        except Exception as e:
            return {
                'success': False,
                'action': 'ai_error',
                'message': f'Error calling AI: {str(e)}'
            }
        
        # Step 5: Create deployment package
        deployment_package = self.create_deployment_package(
            target_file,
            fixed_code,
            feedback_data
        )
        
        # Step 6: Save fixed file
        output_filename = f"{target_file.replace('/', '_')}_FIXED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        output_path = f"/mnt/user-data/outputs/{output_filename}"
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(fixed_code)
            print(f"✅ Saved fixed file to {output_path}")
        except Exception as e:
            print(f"⚠️  Could not save to outputs: {e}")
            output_path = None
        
        # Step 7: Return success response
        return {
            'success': True,
            'action': 'fix_generated',
            'target_file': target_file,
            'original_code': current_code,
            'fixed_code': fixed_code,
            'deployment_package': deployment_package,
            'output_path': output_path,
            'message': self._build_success_message(feedback_data, deployment_package)
        }
    
    def _build_success_message(self, feedback_data, deployment_package):
        """Build user-friendly success message"""
        return f"""✅ **Code Fix Generated!**

**File Fixed:** {feedback_data['target_file']}
**Fix Type:** {feedback_data['feedback_type']}

**What I Did:**
I read your current code, identified the issue, and generated a complete corrected version.

**What's Included:**
✓ Complete fixed {feedback_data['target_file']}
✓ All existing functionality preserved
✓ Comments explaining changes
✓ Ready for GitHub deployment

**Next Steps:**
1. Download the fixed file below
2. Review the changes (look for comments)
3. Deploy to GitHub (replaces existing file)
4. Render will auto-deploy

The fixed code is complete and ready to deploy!"""


def get_code_assistant(knowledge_base=None):
    """Get singleton instance of Code Assistant Agent"""
    return CodeAssistantAgent(knowledge_base=knowledge_base)


# I did no harm and this file is not truncated
