"""
DATABASE ADDITIONS FOR SURVEY MODULE
Created: January 28, 2026
Last Updated: January 28, 2026

PURPOSE:
Add surveys table to existing database for storing created surveys.
This is ADDITIVE - it doesn't replace existing tables.

USAGE:
Import this and call add_surveys_table() in your database.py init_db() function

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import sqlite3

def add_surveys_table(db_path='swarm_intelligence.db'):
    """
    Add surveys table to existing database
    
    Table schema:
    - id: Primary key
    - project_name: Name of project/client
    - company_name: Client company name
    - created_date: When survey was created
    - created_by: Who created it (always "Jim @ Shiftwork Solutions LLC")
    - survey_data: JSON blob containing full survey structure
    - status: draft, finalized, deployed
    - response_count: Number of responses received
    """
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create surveys table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    # Create survey_responses table for future use
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            employee_id TEXT,
            response_date TEXT NOT NULL,
            response_data TEXT NOT NULL,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    ''')
    
    # Create normative_data table for benchmarking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS normative_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            industry TEXT,
            facility_type TEXT,
            response_option TEXT NOT NULL,
            percentage REAL NOT NULL,
            sample_size INTEGER NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ Survey tables added to database")


if __name__ == '__main__':
    # Test the function
    add_surveys_table()
    print("Survey tables created successfully!")

# I did no harm and this file is not truncated
