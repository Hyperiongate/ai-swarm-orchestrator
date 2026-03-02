"""
AI SWARM ORCHESTRATOR - Database Additions for Survey Module
Created: January 28, 2026
Last Updated: March 02, 2026 - POSTGRESQL MIGRATION (Phase 1)

CHANGELOG:
- March 02, 2026: POSTGRESQL MIGRATION
  * Removed hardcoded db_path='swarm_intelligence.db' parameter
  * Now uses get_db_connection() from db_engine
  * All SQL parameters changed from ? to %s
  * add_surveys_table() is now a no-op wrapper — survey tables are created
    by migrations/001_initial_schema.py on every startup
  * Preserved for backward compatibility (app.py calls add_surveys_table())

PURPOSE:
    Survey tables are now created by the main migration script.
    This module retained for backward compatibility only.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from db_engine import get_db_connection


def add_surveys_table():
    """
    Ensure survey tables exist.

    Tables are now created by migrations/001_initial_schema.py on startup.
    This function is retained for backward compatibility since app.py calls it.
    It verifies the tables exist and creates them if somehow missing.
    """
    db = get_db_connection()
    try:
        from db_engine import get_db_type
        db_type = get_db_type()

        if db_type == 'postgresql':
            pk = 'SERIAL PRIMARY KEY'
        else:
            pk = 'INTEGER PRIMARY KEY AUTOINCREMENT'

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS surveys (
                id {pk},
                project_name TEXT NOT NULL,
                company_name TEXT NOT NULL,
                created_date TEXT NOT NULL,
                created_by TEXT DEFAULT 'Jim @ Shiftwork Solutions LLC',
                survey_data TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                response_count INTEGER DEFAULT 0,
                notes TEXT,
                last_updated TEXT
            )
        ''')

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS survey_responses (
                id {pk},
                survey_id INTEGER NOT NULL,
                employee_id TEXT,
                response_date TEXT NOT NULL,
                response_data TEXT NOT NULL
            )
        ''')

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS normative_data (
                id {pk},
                question_id TEXT NOT NULL,
                industry TEXT,
                facility_type TEXT,
                response_option TEXT NOT NULL,
                percentage REAL NOT NULL,
                sample_size INTEGER NOT NULL,
                last_updated TEXT NOT NULL
            )
        ''')

        db.commit()
        print("✅ Survey tables verified/initialized")
    finally:
        db.close()


if __name__ == '__main__':
    add_surveys_table()
    print("Survey tables created successfully!")

# I did no harm and this file is not truncated
