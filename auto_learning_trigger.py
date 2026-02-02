"""
AUTOMATIC COLLECTIVE INTELLIGENCE LEARNING TRIGGER
Created: February 2, 2026
Last Updated: February 2, 2026

This module automatically triggers collective intelligence learning when:
1. New files are added to the knowledge base
2. Files are updated
3. On a schedule (daily/weekly)

No manual intervention needed - the system learns automatically.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class AutoLearningTrigger:
    """
    Automatically triggers collective intelligence learning when appropriate.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create auto-learning tracking table"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_learning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_reason TEXT NOT NULL,
                files_analyzed INTEGER DEFAULT 0,
                patterns_discovered INTEGER DEFAULT 0,
                learning_duration_seconds REAL,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'running',
                results TEXT,
                metadata TEXT
            )
        ''')
        
        # Track when last learning occurred
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_learning_run TIMESTAMP,
                last_file_count INTEGER DEFAULT 0,
                auto_learning_enabled BOOLEAN DEFAULT 1,
                learning_frequency_hours INTEGER DEFAULT 168,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Initialize state if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO learning_state (id, auto_learning_enabled, learning_frequency_hours)
            VALUES (1, 1, 168)
        ''')
        
        db.commit()
        db.close()
    
    def should_trigger_learning(self, knowledge_base=None) -> Dict[str, Any]:
        """
        Determine if learning should be triggered.
        
        Returns:
            Dict with should_trigger (bool) and reason (str)
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Get current state
        cursor.execute('SELECT * FROM learning_state WHERE id = 1')
        state = dict(cursor.fetchone())
        
        db.close()
        
        # Check if auto-learning is enabled
        if not state['auto_learning_enabled']:
            return {
                'should_trigger': False,
                'reason': 'Auto-learning disabled'
            }
        
        # Check if new files added
        if knowledge_base:
            current_file_count = len(knowledge_base.knowledge_index)
            last_file_count = state['last_file_count']
            
            if current_file_count > last_file_count:
                new_files = current_file_count - last_file_count
                return {
                    'should_trigger': True,
                    'reason': f'new_files_added',
                    'details': f'{new_files} new files detected'
                }
        
        # Check if enough time passed since last learning
        if state['last_learning_run']:
            last_run = datetime.fromisoformat(state['last_learning_run'])
            hours_since = (datetime.now() - last_run).total_seconds() / 3600
            frequency = state['learning_frequency_hours']
            
            if hours_since >= frequency:
                return {
                    'should_trigger': True,
                    'reason': 'scheduled_refresh',
                    'details': f'{hours_since:.1f} hours since last learning (threshold: {frequency})'
                }
        else:
            # Never run before
            return {
                'should_trigger': True,
                'reason': 'initial_learning',
                'details': 'First-time learning'
            }
        
        return {
            'should_trigger': False,
            'reason': 'no_trigger_conditions_met'
        }
    
    def trigger_learning(self, knowledge_base=None, reason: str = 'manual') -> Dict[str, Any]:
        """
        Trigger collective intelligence learning.
        
        Args:
            knowledge_base: Knowledge base to learn from
            reason: Why learning was triggered
            
        Returns:
            Learning results
        """
        from collective_intelligence_engine import get_collective_intelligence
        from time import time
        
        print(f"🚀 Auto-triggering collective intelligence learning: {reason}")
        
        start_time = time()
        
        # Get file count
        file_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
        
        # Run learning
        try:
            ci = get_collective_intelligence(knowledge_base=knowledge_base)
            results = ci.learn_from_existing_materials()
            
            duration = time() - start_time
            
            # Log the learning run
            db = sqlite3.connect(self.db_path)
            cursor = db.cursor()
            
            import json
            cursor.execute('''
                INSERT INTO auto_learning_log (
                    trigger_reason, files_analyzed, patterns_discovered,
                    learning_duration_seconds, status, results
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                reason,
                file_count,
                results.get('patterns_discovered', 0),
                duration,
                'completed',
                json.dumps(results)
            ))
            
            # Update state
            cursor.execute('''
                UPDATE learning_state
                SET last_learning_run = ?,
                    last_file_count = ?,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now(), file_count, datetime.now()))
            
            db.commit()
            db.close()
            
            print(f"✅ Auto-learning complete in {duration:.1f}s")
            print(f"   📊 {results.get('patterns_discovered', 0)} patterns discovered")
            print(f"   📁 {file_count} files analyzed")
            
            return {
                'success': True,
                'trigger_reason': reason,
                'files_analyzed': file_count,
                'duration_seconds': duration,
                'results': results
            }
            
        except Exception as e:
            duration = time() - start_time
            
            # Log failure
            db = sqlite3.connect(self.db_path)
            cursor = db.cursor()
            
            cursor.execute('''
                INSERT INTO auto_learning_log (
                    trigger_reason, files_analyzed,
                    learning_duration_seconds, status, results
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                reason,
                file_count,
                duration,
                'failed',
                str(e)
            ))
            
            db.commit()
            db.close()
            
            print(f"❌ Auto-learning failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'trigger_reason': reason
            }
    
    def check_and_trigger(self, knowledge_base=None) -> Optional[Dict[str, Any]]:
        """
        Check if learning should trigger and run if needed.
        
        This is the main function to call periodically or after file uploads.
        
        Returns:
            Learning results if triggered, None if not triggered
        """
        check = self.should_trigger_learning(knowledge_base)
        
        if check['should_trigger']:
            return self.trigger_learning(knowledge_base, check['reason'])
        
        return None
    
    def get_auto_learning_status(self) -> Dict[str, Any]:
        """Get status of auto-learning system"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Get state
        cursor.execute('SELECT * FROM learning_state WHERE id = 1')
        state = dict(cursor.fetchone())
        
        # Get recent runs
        cursor.execute('''
            SELECT * FROM auto_learning_log
            ORDER BY triggered_at DESC
            LIMIT 5
        ''')
        recent_runs = [dict(row) for row in cursor.fetchall()]
        
        # Count total runs
        cursor.execute('SELECT COUNT(*) as count FROM auto_learning_log WHERE status = "completed"')
        total_runs = cursor.fetchone()['count']
        
        db.close()
        
        return {
            'enabled': bool(state['auto_learning_enabled']),
            'last_run': state['last_learning_run'],
            'last_file_count': state['last_file_count'],
            'frequency_hours': state['learning_frequency_hours'],
            'total_learning_runs': total_runs,
            'recent_runs': recent_runs
        }
    
    def set_learning_frequency(self, hours: int):
        """
        Set how often auto-learning should run.
        
        Args:
            hours: Hours between automatic learning runs
        """
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            UPDATE learning_state
            SET learning_frequency_hours = ?,
                updated_at = ?
            WHERE id = 1
        ''', (hours, datetime.now()))
        
        db.commit()
        db.close()
        
        print(f"✅ Auto-learning frequency set to every {hours} hours")
    
    def enable_auto_learning(self):
        """Enable automatic learning"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            UPDATE learning_state
            SET auto_learning_enabled = 1,
                updated_at = ?
            WHERE id = 1
        ''', (datetime.now(),))
        
        db.commit()
        db.close()
        
        print("✅ Auto-learning enabled")
    
    def disable_auto_learning(self):
        """Disable automatic learning"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            UPDATE learning_state
            SET auto_learning_enabled = 0,
                updated_at = ?
            WHERE id = 1
        ''', (datetime.now(),))
        
        db.commit()
        db.close()
        
        print("⏸️  Auto-learning disabled")


# Singleton instance
_auto_trigger = None

def get_auto_learning_trigger() -> AutoLearningTrigger:
    """Get singleton auto-learning trigger"""
    global _auto_trigger
    if _auto_trigger is None:
        _auto_trigger = AutoLearningTrigger()
    return _auto_trigger


def check_and_auto_learn(knowledge_base=None):
    """
    Convenience function to check and trigger learning if needed.
    Call this after file uploads or periodically.
    """
    trigger = get_auto_learning_trigger()
    return trigger.check_and_trigger(knowledge_base)


# I did no harm and this file is not truncated
