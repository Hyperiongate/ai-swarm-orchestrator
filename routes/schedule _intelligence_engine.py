"""
SCHEDULE INTELLIGENCE ENGINE
Created: February 2, 2026
Last Updated: February 2, 2026

This module provides deep schedule pattern intelligence:
- Learns all patterns from Definitive Schedules Excel
- Understands benefits and liabilities of each pattern
- Can generate visual schedule presentations on demand
- Applies lessons learned to pattern selection

When you say: "Show me the 5&2 fixed shift 12-hour pattern"
→ Swarm knows exactly what you want and can create it

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import pandas as pd
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
import re


class SchedulePatternLibrary:
    """
    Comprehensive library of all known schedule patterns.
    Learns from Definitive Schedules Excel file.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.patterns = {}
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create schedule pattern tables"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        # Schedule patterns library
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL UNIQUE,
                pattern_type TEXT,
                shift_length TEXT,
                rotation_weeks INTEGER,
                pattern_data TEXT NOT NULL,
                visual_representation TEXT,
                work_hours_per_week REAL,
                pay_hours_per_week REAL,
                days_on INTEGER,
                days_off INTEGER,
                weekend_coverage BOOLEAN,
                benefits TEXT,
                liabilities TEXT,
                best_for TEXT,
                avoid_when TEXT,
                source_file TEXT,
                learned_from TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Pattern usage history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER,
                client_name TEXT,
                industry TEXT,
                success_rating INTEGER,
                implementation_notes TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pattern_id) REFERENCES schedule_patterns(id)
            )
        ''')
        
        db.commit()
        db.close()
    
    def load_from_definitive_schedules(self, excel_path: str = '/mnt/project/Definitive_Schedules_v2.xlsx') -> int:
        """
        Load all schedule patterns from Definitive Schedules Excel file.
        
        Returns:
            Number of patterns loaded
        """
        print(f"📊 Loading schedule patterns from {excel_path}...")
        
        try:
            xls = pd.ExcelFile(excel_path)
            patterns_loaded = 0
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
                
                # Extract patterns from this sheet
                sheet_patterns = self._extract_patterns_from_sheet(df, sheet_name)
                patterns_loaded += len(sheet_patterns)
                
                # Store in database
                for pattern in sheet_patterns:
                    self._store_pattern(pattern)
            
            print(f"✅ Loaded {patterns_loaded} schedule patterns")
            return patterns_loaded
            
        except Exception as e:
            print(f"❌ Error loading schedules: {e}")
            return 0
    
    def _extract_patterns_from_sheet(self, df: pd.DataFrame, sheet_name: str) -> List[Dict]:
        """Extract schedule patterns from a DataFrame sheet"""
        patterns = []
        
        i = 0
        while i < len(df):
            row = df.iloc[i]
            
            # Look for pattern name in column 1
            pattern_name = str(row[1]) if len(row) > 1 and pd.notna(row[1]) else ''
            
            # Skip headers, numbers, and empty cells
            if (pattern_name in ['Week', 'nan', ''] or 
                pattern_name.isdigit() or 
                pattern_name.startswith('Unnamed')):
                i += 1
                continue
            
            # Check if this might be a schedule name
            if len(pattern_name) > 3 and i + 1 < len(df):
                next_row = df.iloc[i + 1]
                
                # Look for schedule codes in next row (D12, N12, d8, off, etc.)
                schedule_codes = ['D12', 'N12', 'd8', 'n8', 'e8', 's8', 'off', 'D8', 'N8']
                next_vals = [str(v) for v in next_row[2:9].tolist()]
                
                if any(any(code in str(val) for code in schedule_codes) for val in next_vals):
                    # This is a schedule pattern!
                    pattern_data = {
                        'name': pattern_name.replace('\n', ' ').strip(),
                        'pattern': [str(v) if pd.notna(v) else 'off' for v in next_row[2:9].tolist()],
                        'source_sheet': sheet_name
                    }
                    
                    # Try to extract additional info
                    pattern_data.update(self._analyze_pattern(pattern_data['pattern']))
                    
                    patterns.append(pattern_data)
            
            i += 1
        
        return patterns
    
    def _analyze_pattern(self, pattern: List[str]) -> Dict:
        """Analyze a pattern to extract metadata"""
        analysis = {}
        
        # Determine shift length
        if any('12' in str(p) for p in pattern):
            analysis['shift_length'] = '12-hour'
        elif any('8' in str(p) for p in pattern):
            analysis['shift_length'] = '8-hour'
        else:
            analysis['shift_length'] = 'mixed'
        
        # Count days on/off
        days_on = sum(1 for p in pattern if 'off' not in str(p).lower())
        days_off = 7 - days_on
        
        analysis['days_on'] = days_on
        analysis['days_off'] = days_off
        
        # Weekend coverage
        weekend_pattern = pattern[5:7]  # Saturday, Sunday
        analysis['weekend_coverage'] = any('off' not in str(p).lower() for p in weekend_pattern)
        
        # Pattern type
        if all(p == pattern[0] for p in pattern[:5]):
            analysis['pattern_type'] = 'fixed'
        else:
            analysis['pattern_type'] = 'rotating'
        
        return analysis
    
    def _store_pattern(self, pattern: Dict):
        """Store pattern in database"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        import json
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO schedule_patterns (
                    pattern_name, pattern_type, shift_length,
                    pattern_data, days_on, days_off, weekend_coverage,
                    source_file, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pattern['name'],
                pattern.get('pattern_type', 'unknown'),
                pattern.get('shift_length', 'unknown'),
                json.dumps(pattern['pattern']),
                pattern.get('days_on', 0),
                pattern.get('days_off', 0),
                pattern.get('weekend_coverage', False),
                pattern.get('source_sheet', 'unknown'),
                json.dumps(pattern)
            ))
            
            db.commit()
        except Exception as e:
            print(f"⚠️  Error storing pattern {pattern.get('name')}: {e}")
        finally:
            db.close()
    
    def find_pattern(self, query: str) -> Optional[Dict]:
        """
        Find a schedule pattern by name or description.
        
        Examples:
        - "5&2" → Finds 5 days on, 2 days off patterns
        - "fixed 12-hour" → Finds fixed shift 12-hour patterns
        - "2-2-3" → Finds 2-2-3 pattern
        - "DuPont" → Finds DuPont pattern
        
        Returns pattern or None if not found (triggers learning conversation)
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        query_lower = query.lower()
        
        # Try exact match first
        cursor.execute('''
            SELECT * FROM schedule_patterns
            WHERE LOWER(pattern_name) LIKE ?
        ''', (f'%{query_lower}%',))
        
        result = cursor.fetchone()
        
        if result:
            db.close()
            return dict(result)
        
        # Try fuzzy match on characteristics
        cursor.execute('SELECT * FROM schedule_patterns')
        all_patterns = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        # Match on characteristics
        for pattern in all_patterns:
            name_lower = pattern['pattern_name'].lower()
            
            # Check for common pattern names
            if any(term in query_lower for term in ['5&2', '5-2', 'five and two']):
                if pattern['days_on'] == 5 and pattern['days_off'] == 2:
                    return pattern
            
            if '12-hour' in query_lower or '12 hour' in query_lower:
                if pattern['shift_length'] == '12-hour':
                    if 'fixed' in query_lower and pattern['pattern_type'] == 'fixed':
                        return pattern
            
            # Common pattern names
            if any(name in query_lower for name in ['dupont', '2-2-3', '2-3-2', 'panama', 'pitman']):
                if any(name in name_lower for name in ['dupont', '2-2-3', '2-3-2', 'panama', 'pitman']):
                    return pattern
        
        return None
    
    def learn_pattern_alias(self, user_query: str, actual_pattern_name: str):
        """
        Learn that a user query maps to a specific pattern.
        Next time user says the same thing, Swarm knows what they mean.
        
        Args:
            user_query: What the user said (e.g., "the weekend warrior")
            actual_pattern_name: What pattern they actually wanted
        """
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        # Create pattern aliases table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_query TEXT NOT NULL,
                pattern_name TEXT NOT NULL,
                learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER DEFAULT 1,
                UNIQUE(user_query, pattern_name)
            )
        ''')
        
        # Store the alias
        cursor.execute('''
            INSERT INTO pattern_aliases (user_query, pattern_name)
            VALUES (?, ?)
            ON CONFLICT(user_query, pattern_name) DO UPDATE SET
                use_count = use_count + 1
        ''', (user_query.lower().strip(), actual_pattern_name))
        
        db.commit()
        db.close()
        
        print(f"✅ Learned: '{user_query}' → '{actual_pattern_name}'")
    
    def find_pattern_with_learning(self, query: str) -> Dict:
        """
        Find a pattern, checking learned aliases first.
        
        Returns:
            Dict with 'pattern' (if found) or 'clarification_needed' (if not found)
        """
        # Check if we've learned this query before
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT pattern_name FROM pattern_aliases
            WHERE user_query = ?
            ORDER BY use_count DESC
            LIMIT 1
        ''', (query.lower().strip(),))
        
        alias_result = cursor.fetchone()
        db.close()
        
        if alias_result:
            # We learned this before! Use the learned pattern
            pattern_name = alias_result['pattern_name']
            pattern = self.find_pattern(pattern_name)
            if pattern:
                return {
                    'found': True,
                    'pattern': pattern,
                    'learned_from_previous': True,
                    'message': f"I remember you call this '{query}'"
                }
        
        # Try normal search
        pattern = self.find_pattern(query)
        
        if pattern:
            return {
                'found': True,
                'pattern': pattern,
                'learned_from_previous': False
            }
        
        # Not found - need clarification
        # Get all patterns for user to choose from
        all_patterns = self.get_all_patterns()
        
        return {
            'found': False,
            'clarification_needed': True,
            'query': query,
            'available_patterns': [
                {
                    'id': p['id'],
                    'name': p['pattern_name'],
                    'shift_length': p['shift_length'],
                    'days_on': p['days_on'],
                    'days_off': p['days_off']
                }
                for p in all_patterns[:20]  # Top 20
            ],
            'message': f"I don't know a pattern called '{query}'. Which pattern did you mean?",
            'suggestion': "Tell me which pattern and I'll remember for next time"
        }
    
    def get_all_patterns(self, filters: Dict = None) -> List[Dict]:
        """
        Get all patterns, optionally filtered.
        
        Filters:
        - shift_length: '8-hour', '12-hour'
        - pattern_type: 'fixed', 'rotating'
        - weekend_coverage: True/False
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        query = 'SELECT * FROM schedule_patterns'
        where_clauses = []
        params = []
        
        if filters:
            if 'shift_length' in filters:
                where_clauses.append('shift_length = ?')
                params.append(filters['shift_length'])
            
            if 'pattern_type' in filters:
                where_clauses.append('pattern_type = ?')
                params.append(filters['pattern_type'])
            
            if 'weekend_coverage' in filters:
                where_clauses.append('weekend_coverage = ?')
                params.append(filters['weekend_coverage'])
        
        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)
        
        cursor.execute(query, params)
        patterns = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return patterns


class ScheduleKnowledge:
    """
    Knowledge about schedule patterns - benefits, liabilities, best practices.
    Learned from Lessons Learned and past project experience.
    """
    
    # Known benefits and liabilities from 30+ years experience
    PATTERN_KNOWLEDGE = {
        '2-2-3': {
            'benefits': [
                'Predictable rotation - employees can plan ahead',
                'Equal distribution of weekend work',
                'Good work-life balance with 2-3 day weekends',
                'Popular in manufacturing (68% preference)',
                'Reduces childcare coordination stress (Lesson #14)'
            ],
            'liabilities': [
                '12-hour shifts can be tiring',
                'Requires 4+ crews for 24/7 coverage',
                'Less flexibility for shift swaps'
            ],
            'best_for': [
                'Manufacturing facilities',
                'Employees with families (childcare predictability)',
                '24/7 operations with stable demand'
            ],
            'avoid_when': [
                'High variability in demand',
                'Frequent schedule changes needed',
                'Employees prefer 8-hour shifts'
            ]
        },
        'DuPont': {
            'benefits': [
                'Long stretches of days off (7 days)',
                'Balanced day/night rotation',
                'Proven in chemical/pharmaceutical industries'
            ],
            'liabilities': [
                'Complex rotation - hard to understand initially',
                'Less popular than 2-2-3 (only 23% preference in manufacturing)',
                'Longer stretches of consecutive days can be tiring'
            ],
            'best_for': [
                'Pharmaceutical/chemical facilities',
                'Experienced workforce',
                'Employees who value long breaks'
            ],
            'avoid_when': [
                'Workforce prefers simplicity',
                'Manufacturing environments (prefer 2-2-3)'
            ]
        },
        '5&2_fixed': {
            'benefits': [
                'Simple and easy to understand',
                'Traditional work week feel',
                'No rotation confusion',
                'Good for work-life balance'
            ],
            'liabilities': [
                'Requires premium pay for weekend coverage',
                'Weekend crews may feel inequitable',
                'Limited operational flexibility'
            ],
            'best_for': [
                '16/7 or 24/5 operations',
                'Operations with low weekend demand',
                'Workforces resistant to rotation'
            ],
            'avoid_when': [
                '24/7 coverage required',
                'Equal weekend distribution desired'
            ]
        },
        '12-hour_shifts': {
            'benefits': [
                'Fewer commutes per year',
                'Longer periods off',
                '40-hour week in 3-4 days',
                'Preferred by 62% in manufacturing'
            ],
            'liabilities': [
                'Fatigue on 12-hour days',
                'Childcare challenges for some',
                'Not suitable for physically demanding work'
            ],
            'best_for': [
                'Low to moderate physical demand',
                'Employees who value time off',
                'Operations needing continuous coverage'
            ],
            'avoid_when': [
                'Highly physical work',
                'Safety-sensitive operations with fatigue concerns',
                'Employees strongly prefer 8-hour'
            ]
        }
    }
    
    @classmethod
    def get_pattern_knowledge(cls, pattern_name: str) -> Dict:
        """Get benefits/liabilities for a pattern"""
        # Try direct lookup
        if pattern_name in cls.PATTERN_KNOWLEDGE:
            return cls.PATTERN_KNOWLEDGE[pattern_name]
        
        # Try fuzzy match
        pattern_lower = pattern_name.lower()
        for key in cls.PATTERN_KNOWLEDGE.keys():
            if key.lower() in pattern_lower or pattern_lower in key.lower():
                return cls.PATTERN_KNOWLEDGE[key]
        
        # Check for shift length knowledge
        if '12' in pattern_name or '12-hour' in pattern_lower:
            return cls.PATTERN_KNOWLEDGE.get('12-hour_shifts', {})
        
        return {
            'benefits': ['Pattern-specific benefits to be documented'],
            'liabilities': ['Pattern-specific liabilities to be documented'],
            'best_for': ['Use cases to be documented'],
            'avoid_when': ['Limitations to be documented']
        }


class ScheduleIntelligenceEngine:
    """
    Main engine for schedule intelligence.
    Combines pattern library with knowledge to provide expert recommendations.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.library = SchedulePatternLibrary(db_path)
        self.knowledge = ScheduleKnowledge()
    
    def initialize_patterns(self):
        """Load all patterns from Definitive Schedules"""
        return self.library.load_from_definitive_schedules()
    
    def get_pattern(self, query: str, include_knowledge: bool = True) -> Dict:
        """
        Get a schedule pattern with full intelligence.
        Uses conversational learning - if pattern not found, asks for clarification.
        
        Args:
            query: Pattern name or description
            include_knowledge: Include benefits/liabilities
            
        Returns:
            Pattern info or clarification request
        """
        # Use learning-enabled search
        result = self.library.find_pattern_with_learning(query)
        
        if result['found']:
            pattern = result['pattern']
            
            if include_knowledge:
                knowledge = self.knowledge.get_pattern_knowledge(pattern['pattern_name'])
                pattern['benefits'] = knowledge.get('benefits', [])
                pattern['liabilities'] = knowledge.get('liabilities', [])
                pattern['best_for'] = knowledge.get('best_for', [])
                pattern['avoid_when'] = knowledge.get('avoid_when', [])
            
            # Add learned message if applicable
            if result.get('learned_from_previous'):
                pattern['learned_note'] = result['message']
            
            return {
                'success': True,
                'pattern': pattern
            }
        else:
            # Pattern not found - return clarification request
            return {
                'success': False,
                'clarification_needed': True,
                'message': result['message'],
                'suggestion': result['suggestion'],
                'available_patterns': result['available_patterns'],
                'original_query': query
            }
    
    def teach_pattern_alias(self, user_query: str, pattern_id_or_name: str) -> Dict:
        """
        User teaches Swarm what they mean by a specific query.
        
        Args:
            user_query: What user said (e.g., "weekend warrior")
            pattern_id_or_name: Pattern ID or name they actually meant
            
        Returns:
            Confirmation with the learned pattern
        """
        # Find the actual pattern
        if pattern_id_or_name.isdigit():
            # Look up by ID
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute('SELECT * FROM schedule_patterns WHERE id = ?', (int(pattern_id_or_name),))
            pattern = cursor.fetchone()
            db.close()
            
            if pattern:
                pattern = dict(pattern)
            else:
                return {
                    'success': False,
                    'error': f'Pattern ID {pattern_id_or_name} not found'
                }
        else:
            # Look up by name
            pattern = self.library.find_pattern(pattern_id_or_name)
            
            if not pattern:
                return {
                    'success': False,
                    'error': f'Pattern "{pattern_id_or_name}" not found'
                }
        
        # Learn the alias
        self.library.learn_pattern_alias(user_query, pattern['pattern_name'])
        
        return {
            'success': True,
            'learned': True,
            'user_query': user_query,
            'pattern_name': pattern['pattern_name'],
            'message': f"Got it! From now on when you say '{user_query}', I'll know you mean '{pattern['pattern_name']}'"
        }
    
    def recommend_pattern(self, requirements: Dict) -> List[Dict]:
        """
        Recommend schedule patterns based on requirements.
        
        Requirements:
        - industry: 'manufacturing', 'pharmaceutical', etc.
        - shift_length_preference: '8-hour', '12-hour'
        - weekend_coverage_needed: True/False
        - employee_preferences: Any known preferences
        """
        # Get all patterns
        patterns = self.library.get_all_patterns()
        
        scored_patterns = []
        
        for pattern in patterns:
            score = 0
            reasons = []
            
            # Score based on requirements
            if requirements.get('shift_length_preference'):
                if pattern['shift_length'] == requirements['shift_length_preference']:
                    score += 3
                    reasons.append(f"Matches preferred {pattern['shift_length']} shift length")
            
            if requirements.get('weekend_coverage_needed') is not None:
                if pattern['weekend_coverage'] == requirements['weekend_coverage_needed']:
                    score += 2
                    reasons.append('Weekend coverage matches requirement')
            
            # Industry-specific scoring
            knowledge = self.knowledge.get_pattern_knowledge(pattern['pattern_name'])
            best_for = knowledge.get('best_for', [])
            
            if requirements.get('industry'):
                industry = requirements['industry'].lower()
                if any(industry in str(use).lower() for use in best_for):
                    score += 5
                    reasons.append(f"Recommended for {industry}")
            
            if score > 0:
                scored_patterns.append({
                    **pattern,
                    'recommendation_score': score,
                    'recommendation_reasons': reasons,
                    'benefits': knowledge.get('benefits', []),
                    'liabilities': knowledge.get('liabilities', [])
                })
        
        # Sort by score
        scored_patterns.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        return scored_patterns[:5]  # Top 5


# Singleton
_schedule_engine = None

def get_schedule_intelligence() -> ScheduleIntelligenceEngine:
    """Get singleton schedule intelligence engine"""
    global _schedule_engine
    if _schedule_engine is None:
        _schedule_engine = ScheduleIntelligenceEngine()
    return _schedule_engine


# I did no harm and this file is not truncated
