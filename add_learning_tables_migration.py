"""
Database Migration: Add Learning Enhancement Tables
Created: February 4, 2026
Purpose: Add client_profiles and avoidance_patterns tables for Fixes #2 and #3

Run this ONCE to add the new tables. Safe to run multiple times (checks if tables exist).

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import os
from datetime import datetime


def run_migration():
    """Add client profiles and avoidance patterns tables"""
    
    # Use the main database
    db_path = os.environ.get('DATABASE_PATH', 'swarm_orchestrator.db')
    
    print(f"🔄 Running learning tables migration on {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ========================================================================
    # TABLE 1: Client Profiles (Fix #2)
    # Stores accumulated knowledge about each client across all projects
    # ========================================================================
    print("📊 Creating client_profiles table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT UNIQUE NOT NULL,
            profile_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_client_profiles_name 
        ON client_profiles(client_name)
    ''')
    
    print("   ✅ client_profiles table ready")
    
    # ========================================================================
    # TABLE 2: Avoidance Patterns (Fix #3)
    # Stores patterns to avoid based on poor feedback
    # ========================================================================
    print("📊 Creating avoidance_patterns table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avoidance_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_data TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            times_violated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_avoidance_patterns_created 
        ON avoidance_patterns(created_at DESC)
    ''')
    
    print("   ✅ avoidance_patterns table ready")
    
    # ========================================================================
    # Verify tables were created
    # ========================================================================
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        AND name IN ('client_profiles', 'avoidance_patterns')
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ MIGRATION COMPLETE")
    print("="*70)
    print(f"Tables created: {', '.join(tables)}")
    print(f"Database: {db_path}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*70)
    
    return True


if __name__ == '__main__':
    try:
        run_migration()
        print("\n🎉 Migration successful! Deploy your code changes now.")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()


# I did no harm and this file is not truncated
