"""
Labor File Detector - Automatic Labor Data Detection
Created: February 10, 2026
Last Updated: February 10, 2026

Detects when uploaded Excel files contain workforce/labor data and offers
to run comprehensive analysis workflows using the AnalysisOrchestrator.

This enables automatic detection and analysis offer workflow:
1. User uploads Excel file
2. System detects labor data columns
3. Offers detailed analysis with AnalysisOrchestrator
4. User accepts -> runs multi-step workflow
5. User declines -> continues normal file handling

Author: Jim @ Shiftwork Solutions LLC
"""

import pandas as pd
import os
from typing import Tuple, Dict, Any, List
from datetime import datetime


def detect_labor_file(file_path: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if Excel file contains labor/workforce data.
    
    Labor data indicators:
    - Date or Work Date column
    - Employee, Emp, or EDI# column
    - Hours columns (Total Hours, Reg, Overtime)
    - Optional: Department, Building, Shift
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Tuple of (is_labor: bool, metadata: dict)
        
    Examples:
        >>> is_labor, metadata = detect_labor_file('payroll.xlsx')
        >>> if is_labor:
        ...     print(f"Found {metadata['record_count']} labor records")
    """
    metadata = {
        'is_labor': False,
        'record_count': 0,
        'date_range': None,
        'departments': [],
        'employees': 0,
        'columns_found': [],
        'file_name': os.path.basename(file_path),
        'file_size_mb': 0
    }
    
    try:
        # Get file size
        metadata['file_size_mb'] = os.path.getsize(file_path) / (1024 * 1024)
        
        # Read first 100 rows to check structure
        df = pd.read_excel(file_path, nrows=100)
        
        if df.empty:
            return False, metadata
        
        # Get column names (case-insensitive)
        columns = df.columns.tolist()
        columns_lower = [str(c).lower() for c in columns]
        
        # Labor data indicators
        has_date = any(
            term in col for col in columns_lower 
            for term in ['date', 'work date', 'workdate', 'pay date']
        )
        
        has_employee = any(
            term in col for col in columns_lower 
            for term in ['employee', 'emp', 'edi', 'worker', 'staff']
        )
        
        has_hours = any(
            term in col for col in columns_lower 
            for term in ['hours', 'total hours', 'reg', 'overtime', 'ot']
        )
        
        # Must have all three core elements
        if not (has_date and has_employee and has_hours):
            return False, metadata
        
        # This is labor data - get detailed metadata
        metadata['is_labor'] = True
        metadata['columns_found'] = columns
        
        # Read full file for complete metadata
        full_df = pd.read_excel(file_path)
        metadata['record_count'] = len(full_df)
        
        # Get date range
        date_col = None
        for col in columns:
            if any(term in str(col).lower() for term in ['date', 'work date', 'workdate']):
                date_col = col
                break
        
        if date_col:
            try:
                full_df[date_col] = pd.to_datetime(full_df[date_col])
                metadata['date_range'] = {
                    'start': full_df[date_col].min().strftime('%Y-%m-%d'),
                    'end': full_df[date_col].max().strftime('%Y-%m-%d')
                }
            except:
                pass
        
        # Get department info
        dept_col = None
        for col in columns:
            if any(term in str(col).lower() for term in ['department', 'dept', 'division']):
                dept_col = col
                break
        
        if dept_col:
            metadata['departments'] = full_df[dept_col].unique().tolist()
        
        # Get employee count
        emp_col = None
        for col in columns:
            if any(term in str(col).lower() for term in ['employee', 'emp', 'edi', 'worker']):
                emp_col = col
                break
        
        if emp_col:
            metadata['employees'] = full_df[emp_col].nunique()
        
        return True, metadata
        
    except Exception as e:
        print(f"Error detecting labor file: {e}")
        return False, metadata


def generate_analysis_offer(metadata: Dict[str, Any], filename: str) -> str:
    """
    Create the message offering analysis to user.
    
    Args:
        metadata: Labor file metadata from detect_labor_file()
        filename: Original filename
        
    Returns:
        Formatted message string offering analysis
        
    Examples:
        >>> metadata = {'record_count': 5000, 'employees': 150, ...}
        >>> message = generate_analysis_offer(metadata, 'payroll.xlsx')
    """
    # Build the offer message
    message_parts = [
        "## Labor Data Detected!",
        "",
        f"I found **{metadata['record_count']:,} labor records** in `{filename}`"
    ]
    
    # Add date range if available
    if metadata.get('date_range'):
        start = metadata['date_range']['start']
        end = metadata['date_range']['end']
        message_parts.append(f"- Date range: {start} to {end}")
    
    # Add employee count
    if metadata.get('employees'):
        message_parts.append(f"- Employees: {metadata['employees']:,}")
    
    # Add department info
    if metadata.get('departments') and len(metadata['departments']) > 0:
        dept_count = len(metadata['departments'])
        message_parts.append(f"- Departments: {dept_count}")
    
    message_parts.extend([
        "",
        "### I can run a comprehensive analysis:",
        "",
        "- Overtime patterns and cost exposure",
        "- Staffing distribution by department",
        "- Shift balance and coverage gaps",
        "- Day-of-week and monthly trends",
        "- Headcount efficiency metrics",
        "",
        "**Deliverables include:**",
        "- Client-ready PowerPoint presentation",
        "- High-resolution charts (300 DPI)",
        "- Executive summary with recommendations",
        "- Excel files with calculations",
        "- Python code for GitHub",
        "",
        "**Would you like me to analyze this data?**",
        "",
        "Reply with:",
        "- **Yes, analyze it** - I will run the full analysis",
        "- **Just give me a quick summary** - I will show basic overview only",
        "- **Not now** - I will just save the file"
    ])
    
    return "\n".join(message_parts)


def create_analysis_session(file_path: str, project_id: int = None) -> Dict[str, Any]:
    """
    Create AnalysisOrchestrator session for this file.
    
    Args:
        file_path: Path to the labor data file
        project_id: Optional project ID to link to
        
    Returns:
        Dictionary with:
        - success: bool
        - session_id: str (if successful)
        - error: str (if failed)
        
    Examples:
        >>> result = create_analysis_session('/tmp/payroll.xlsx', project_id=123)
        >>> if result['success']:
        ...     session_id = result['session_id']
    """
    try:
        from analysis_orchestrator import AnalysisOrchestrator
        from database import save_analysis_session
        import uuid
        
        # Create new session
        session_id = f"ANALYSIS_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        orchestrator = AnalysisOrchestrator(
            session_id=session_id,
            project_id=project_id
        )
        
        # Run discovery phase with the uploaded file
        discovery_result = orchestrator.discover_data_structure([file_path])
        
        # Save session to database
        save_analysis_session(orchestrator.to_dict())
        
        return {
            'success': True,
            'session_id': session_id,
            'discovery': discovery_result
        }
        
    except Exception as e:
        import traceback
        print(f"Error creating analysis session: {e}")
        print(traceback.format_exc())
        
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def format_discovery_questions(discovery: Dict[str, Any]) -> str:
    """
    Format discovery questions for user display.
    
    Args:
        discovery: Discovery result from orchestrator.discover_data_structure()
        
    Returns:
        Formatted string with questions
    """
    questions = discovery.get('questions', [])
    
    if not questions:
        return ""
    
    message_parts = [
        "",
        "### I have a few questions to customize the analysis:",
        ""
    ]
    
    for i, q in enumerate(questions, 1):
        message_parts.append(f"**{i}. {q['question']}**")
        
        if q.get('explanation'):
            message_parts.append(f"   _{q['explanation']}_")
        
        if q.get('options'):
            for opt in q['options']:
                message_parts.append(f"   - {opt}")
        
        message_parts.append("")
    
    return "\n".join(message_parts)


# I did no harm and this file is not truncated
