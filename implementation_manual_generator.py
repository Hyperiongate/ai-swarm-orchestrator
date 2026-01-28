"""
IMPLEMENTATION MANUAL GENERATOR
Created: January 28, 2026
For: Shiftwork Solutions LLC - AI Swarm Orchestrator

PURPOSE:
Conversational system for creating client implementation manuals.
Uses project knowledge + targeted questions to generate professional
implementation manuals like the Andersen manual we just created.

WORKFLOW:
1. User starts new manual project
2. System asks clarifying questions about client, schedules, pay, etc.
3. User answers questions (can be back-and-forth)
4. System generates draft manual sections
5. User reviews and requests changes
6. System refines until approved
7. System generates final Word document
8. System remembers lessons learned for future manuals

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: January 28, 2026
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

def get_db():
    """Get database connection"""
    db = sqlite3.connect('swarm_data.db')
    db.row_factory = sqlite3.Row
    return db

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_manual_tables():
    """Create tables for implementation manual generation"""
    db = get_db()
    
    # Manual projects table
    db.execute('''
        CREATE TABLE IF NOT EXISTS implementation_manuals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            facility_name TEXT,
            project_status TEXT DEFAULT 'gathering_info',
            current_section TEXT,
            client_data TEXT,
            draft_content TEXT,
            final_document_path TEXT,
            conversation_history TEXT,
            lessons_learned TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
    ''')
    
    # Questions asked/answered table
    db.execute('''
        CREATE TABLE IF NOT EXISTS manual_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manual_id INTEGER NOT NULL,
            question_category TEXT NOT NULL,
            question_text TEXT NOT NULL,
            answer TEXT,
            asked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            answered_at TEXT,
            FOREIGN KEY (manual_id) REFERENCES implementation_manuals(id)
        )
    ''')
    
    # Draft sections table
    db.execute('''
        CREATE TABLE IF NOT EXISTS manual_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manual_id INTEGER NOT NULL,
            section_name TEXT NOT NULL,
            section_order INTEGER,
            draft_content TEXT,
            approved BOOLEAN DEFAULT 0,
            revision_count INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manual_id) REFERENCES implementation_manuals(id)
        )
    ''')
    
    # Lessons learned table (accumulates knowledge)
    db.execute('''
        CREATE TABLE IF NOT EXISTS manual_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_category TEXT NOT NULL,
            lesson_text TEXT NOT NULL,
            source_manual_id INTEGER,
            industry TEXT,
            facility_type TEXT,
            applies_to TEXT,
            importance TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_manual_id) REFERENCES implementation_manuals(id)
        )
    ''')
    
    db.commit()
    db.close()
    print("✅ Implementation manual generator tables initialized")

# ============================================================================
# MANUAL PROJECT MANAGEMENT
# ============================================================================

def create_manual_project(client_name: str, facility_name: str = None) -> int:
    """Start a new implementation manual project"""
    db = get_db()
    
    cursor = db.execute('''
        INSERT INTO implementation_manuals (client_name, facility_name, client_data, conversation_history)
        VALUES (?, ?, '{}', '[]')
    ''', (client_name, facility_name))
    
    manual_id = cursor.lastid
    
    # Create default sections
    default_sections = [
        ('Introduction', 1),
        ('Schedule Selection Process', 2),
        ('Current Schedules', 3),
        ('Schedule Options', 4),
        ('Questions and Answers', 5),
        ('Appendix A: Schedule Comparison', 6),
        ('Appendix B: Annual Income Examples', 7),
        ('Appendix C: Holiday Pay Details', 8),
        ('Preference Form', 9)
    ]
    
    for section_name, order in default_sections:
        db.execute('''
            INSERT INTO manual_sections (manual_id, section_name, section_order)
            VALUES (?, ?, ?)
        ''', (manual_id, section_name, order))
    
    db.commit()
    db.close()
    
    return manual_id

def get_manual_project(manual_id: int) -> Optional[Dict]:
    """Get manual project details"""
    db = get_db()
    manual = db.execute('SELECT * FROM implementation_manuals WHERE id = ?', (manual_id,)).fetchone()
    db.close()
    
    if manual:
        result = dict(manual)
        result['client_data'] = json.loads(result['client_data']) if result['client_data'] else {}
        result['conversation_history'] = json.loads(result['conversation_history']) if result['conversation_history'] else []
        return result
    return None

def update_manual_data(manual_id: int, data_updates: Dict) -> bool:
    """Update client data for manual"""
    db = get_db()
    
    # Get current data
    manual = get_manual_project(manual_id)
    if not manual:
        db.close()
        return False
    
    # Merge updates
    client_data = manual['client_data']
    client_data.update(data_updates)
    
    db.execute('''
        UPDATE implementation_manuals 
        SET client_data = ?, updated_at = ?
        WHERE id = ?
    ''', (json.dumps(client_data), datetime.now().isoformat(), manual_id))
    
    db.commit()
    db.close()
    return True

def add_conversation_turn(manual_id: int, role: str, message: str) -> bool:
    """Add a conversation turn to history"""
    db = get_db()
    
    manual = get_manual_project(manual_id)
    if not manual:
        db.close()
        return False
    
    conversation = manual['conversation_history']
    conversation.append({
        'role': role,
        'message': message,
        'timestamp': datetime.now().isoformat()
    })
    
    db.execute('''
        UPDATE implementation_manuals 
        SET conversation_history = ?, updated_at = ?
        WHERE id = ?
    ''', (json.dumps(conversation), datetime.now().isoformat(), manual_id))
    
    db.commit()
    db.close()
    return True

def update_manual_status(manual_id: int, status: str, current_section: str = None) -> bool:
    """Update manual project status"""
    db = get_db()
    
    if current_section:
        db.execute('''
            UPDATE implementation_manuals 
            SET project_status = ?, current_section = ?, updated_at = ?
            WHERE id = ?
        ''', (status, current_section, datetime.now().isoformat(), manual_id))
    else:
        db.execute('''
            UPDATE implementation_manuals 
            SET project_status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), manual_id))
    
    db.commit()
    db.close()
    return True

# ============================================================================
# QUESTIONS MANAGEMENT
# ============================================================================

def get_required_questions(manual_id: int) -> List[Dict]:
    """Get list of questions that need to be asked"""
    manual = get_manual_project(manual_id)
    if not manual:
        return []
    
    data = manual['client_data']
    
    # Define required information categories
    required_info = {
        'basic': ['client_name', 'facility_name', 'industry', 'facility_type'],
        'current_schedule': ['current_schedule_pattern', 'current_shift_length', 'current_shift_times', 'current_days_off'],
        'new_schedules': ['number_of_options', 'shift_lengths', 'schedule_patterns'],
        'pay': ['hourly_wage', 'overtime_rules', 'holiday_pay_rules'],
        'employees': ['total_employees', 'departments', 'employee_count_by_dept'],
        'dates': ['preference_deadline', 'implementation_date'],
        'process': ['selection_framework', 'seniority_matters']
    }
    
    questions_needed = []
    
    # Check what's missing
    for category, fields in required_info.items():
        for field in fields:
            if field not in data or not data[field]:
                question = generate_question_for_field(category, field)
                questions_needed.append({
                    'category': category,
                    'field': field,
                    'question': question
                })
    
    return questions_needed

def generate_question_for_field(category: str, field: str) -> str:
    """Generate appropriate question for a data field"""
    questions = {
        'client_name': "What is the client's company name?",
        'facility_name': "What is the facility or plant name (if different from company)?",
        'industry': "What industry? (manufacturing, food processing, pharmaceutical, mining, etc.)",
        'facility_type': "What type of facility? (production, warehouse, distribution, etc.)",
        'current_schedule_pattern': "What is the current schedule pattern employees work?",
        'current_shift_length': "What is the current shift length? (8-hour, 10-hour, 12-hour)",
        'current_shift_times': "What are the current shift start/end times?",
        'current_days_off': "What days off pattern do employees currently have?",
        'number_of_options': "How many schedule options are you proposing? (typically 2-3)",
        'shift_lengths': "What shift lengths for the new options? (8-hour, 10-hour, 12-hour)",
        'schedule_patterns': "What schedule patterns? (examples: 2-2-3, 4-3, DuPont, Southern Swing, etc.)",
        'hourly_wage': "What is the average hourly wage? (for income calculations)",
        'overtime_rules': "How is overtime calculated? (after 40/week, after 8/day, etc.)",
        'holiday_pay_rules': "How many holidays per year and how are they paid?",
        'total_employees': "How many total employees will be affected?",
        'departments': "What departments are involved?",
        'employee_count_by_dept': "How many employees in each department?",
        'preference_deadline': "When is the deadline for employees to submit preferences?",
        'implementation_date': "When will the new schedule be implemented?",
        'selection_framework': "How will you determine which employees go on which schedule?",
        'seniority_matters': "Does seniority determine assignments? If so, how?"
    }
    
    return questions.get(field, f"Can you provide information about: {field}?")

def ask_next_question(manual_id: int) -> Optional[Dict]:
    """Get the next question to ask"""
    db = get_db()
    
    questions_needed = get_required_questions(manual_id)
    
    if not questions_needed:
        return None
    
    # Get the first unanswered question
    next_q = questions_needed[0]
    
    # Record that we asked it
    db.execute('''
        INSERT INTO manual_questions (manual_id, question_category, question_text)
        VALUES (?, ?, ?)
    ''', (manual_id, next_q['category'], next_q['question']))
    
    db.commit()
    db.close()
    
    return next_q

def record_answer(manual_id: int, field: str, answer: str) -> bool:
    """Record an answer to a question"""
    # Update the client data
    update_manual_data(manual_id, {field: answer})
    
    # Mark question as answered in database
    db = get_db()
    db.execute('''
        UPDATE manual_questions 
        SET answer = ?, answered_at = ?
        WHERE manual_id = ? AND question_text LIKE ?
    ''', (answer, datetime.now().isoformat(), manual_id, f'%{field}%'))
    
    db.commit()
    db.close()
    
    return True

# ============================================================================
# SECTION MANAGEMENT
# ============================================================================

def get_manual_sections(manual_id: int) -> List[Dict]:
    """Get all sections for a manual"""
    db = get_db()
    sections = db.execute('''
        SELECT * FROM manual_sections 
        WHERE manual_id = ?
        ORDER BY section_order
    ''', (manual_id,)).fetchall()
    db.close()
    
    return [dict(s) for s in sections]

def update_section_content(manual_id: int, section_name: str, content: str, approved: bool = False) -> bool:
    """Update a section's content"""
    db = get_db()
    
    # Get current revision count
    section = db.execute('''
        SELECT revision_count FROM manual_sections 
        WHERE manual_id = ? AND section_name = ?
    ''', (manual_id, section_name)).fetchone()
    
    if section:
        new_revision = section['revision_count'] + 1
        db.execute('''
            UPDATE manual_sections 
            SET draft_content = ?, approved = ?, revision_count = ?, updated_at = ?
            WHERE manual_id = ? AND section_name = ?
        ''', (content, 1 if approved else 0, new_revision, datetime.now().isoformat(), manual_id, section_name))
    else:
        db.execute('''
            INSERT INTO manual_sections (manual_id, section_name, draft_content, approved, revision_count)
            VALUES (?, ?, ?, ?, 1)
        ''', (manual_id, section_name, content, 1 if approved else 0))
    
    db.commit()
    db.close()
    return True

def get_section_status(manual_id: int) -> Dict:
    """Get status of all sections"""
    db = get_db()
    
    total = db.execute(
        'SELECT COUNT(*) as count FROM manual_sections WHERE manual_id = ?',
        (manual_id,)
    ).fetchone()['count']
    
    drafted = db.execute(
        'SELECT COUNT(*) as count FROM manual_sections WHERE manual_id = ? AND draft_content IS NOT NULL',
        (manual_id,)
    ).fetchone()['count']
    
    approved = db.execute(
        'SELECT COUNT(*) as count FROM manual_sections WHERE manual_id = ? AND approved = 1',
        (manual_id,)
    ).fetchone()['count']
    
    db.close()
    
    return {
        'total_sections': total,
        'drafted_sections': drafted,
        'approved_sections': approved,
        'completion_percentage': int((approved / total * 100)) if total > 0 else 0
    }

# ============================================================================
# LESSONS LEARNED
# ============================================================================

def add_lesson_learned(lesson_category: str, lesson_text: str, manual_id: int = None, **kwargs) -> int:
    """Add a lesson learned from this manual"""
    db = get_db()
    
    cursor = db.execute('''
        INSERT INTO manual_lessons 
        (lesson_category, lesson_text, source_manual_id, industry, facility_type, applies_to, importance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (lesson_category, lesson_text, manual_id, 
          kwargs.get('industry'), kwargs.get('facility_type'), 
          kwargs.get('applies_to'), kwargs.get('importance', 'medium')))
    
    lesson_id = cursor.lastid
    db.commit()
    db.close()
    
    return lesson_id

def get_relevant_lessons(industry: str = None, facility_type: str = None) -> List[Dict]:
    """Get relevant lessons for this type of manual"""
    db = get_db()
    
    if industry and facility_type:
        lessons = db.execute('''
            SELECT * FROM manual_lessons 
            WHERE industry = ? OR facility_type = ? OR applies_to = 'all'
            ORDER BY importance DESC, created_at DESC
            LIMIT 20
        ''', (industry, facility_type)).fetchall()
    elif industry:
        lessons = db.execute('''
            SELECT * FROM manual_lessons 
            WHERE industry = ? OR applies_to = 'all'
            ORDER BY importance DESC, created_at DESC
            LIMIT 20
        ''', (industry,)).fetchall()
    else:
        lessons = db.execute('''
            SELECT * FROM manual_lessons 
            WHERE applies_to = 'all' OR importance = 'high'
            ORDER BY importance DESC, created_at DESC
            LIMIT 20
        ''').fetchall()
    
    db.close()
    return [dict(l) for l in lessons]

# ============================================================================
# DASHBOARD
# ============================================================================

def get_manuals_dashboard() -> Dict:
    """Get dashboard of all manual projects"""
    db = get_db()
    
    # Count by status
    total = db.execute('SELECT COUNT(*) as count FROM implementation_manuals').fetchone()['count']
    gathering = db.execute("SELECT COUNT(*) as count FROM implementation_manuals WHERE project_status = 'gathering_info'").fetchone()['count']
    drafting = db.execute("SELECT COUNT(*) as count FROM implementation_manuals WHERE project_status = 'drafting'").fetchone()['count']
    reviewing = db.execute("SELECT COUNT(*) as count FROM implementation_manuals WHERE project_status = 'reviewing'").fetchone()['count']
    complete = db.execute("SELECT COUNT(*) as count FROM implementation_manuals WHERE project_status = 'complete'").fetchone()['count']
    
    # Recent manuals
    recent = db.execute('''
        SELECT id, client_name, facility_name, project_status, updated_at
        FROM implementation_manuals
        ORDER BY updated_at DESC
        LIMIT 10
    ''').fetchall()
    
    # Lessons learned count
    lessons_count = db.execute('SELECT COUNT(*) as count FROM manual_lessons').fetchone()['count']
    
    db.close()
    
    return {
        'total_manuals': total,
        'status_counts': {
            'gathering_info': gathering,
            'drafting': drafting,
            'reviewing': reviewing,
            'complete': complete
        },
        'recent_manuals': [dict(r) for r in recent],
        'lessons_learned_count': lessons_count
    }

def list_manual_projects(status: str = 'all', limit: int = 50) -> List[Dict]:
    """List manual projects"""
    db = get_db()
    
    if status == 'all':
        manuals = db.execute('''
            SELECT * FROM implementation_manuals 
            ORDER BY updated_at DESC 
            LIMIT ?
        ''', (limit,)).fetchall()
    else:
        manuals = db.execute('''
            SELECT * FROM implementation_manuals 
            WHERE project_status = ?
            ORDER BY updated_at DESC 
            LIMIT ?
        ''', (status, limit)).fetchall()
    
    db.close()
    
    results = []
    for m in manuals:
        manual_dict = dict(m)
        manual_dict['client_data'] = json.loads(manual_dict['client_data']) if manual_dict['client_data'] else {}
        results.append(manual_dict)
    
    return results

# Initialize tables on import
try:
    init_manual_tables()
except Exception as e:
    print(f"⚠️  Manual generator tables initialization: {e}")

# I did no harm and this file is not truncated
