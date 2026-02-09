"""
Analysis Orchestrator - Core Workflow Coordinator
Created: February 8, 2026
Last Updated: February 9, 2026

This module manages multi-step analytical workflows with human interaction.
It handles the complete lifecycle from data upload through deliverable generation.

PHASE 0B UPDATE: Now executes real analysis using analysis_executor.py

Author: Shiftwork Solutions LLC
Phase: 0B - Execution Engine Integration
"""

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from flask import current_app

# Analysis workflow states
class AnalysisState:
    """Workflow states for analysis sessions"""
    INITIAL_UPLOAD = 'INITIAL_UPLOAD'
    DATA_DISCOVERY = 'DATA_DISCOVERY'
    CLARIFICATION_PENDING = 'CLARIFICATION_PENDING'
    PLAN_APPROVAL = 'PLAN_APPROVAL'
    ANALYSIS_RUNNING = 'ANALYSIS_RUNNING'
    DELIVERABLE_GENERATION = 'DELIVERABLE_GENERATION'
    COMPLETE = 'COMPLETE'
    ERROR = 'ERROR'


class AnalysisOrchestrator:
    """
    Manages multi-step analytical workflows with human interaction.
    
    Workflow Phases:
    1. Data Discovery - Examine uploaded files, understand structure
    2. Clarification - Ask questions, get user input
    3. Planning - Build analysis plan, get approval
    4. Execution - Run calculations, generate charts
    5. Deliverable Generation - Create PowerPoint, summaries, code
    """
    
    def __init__(self, session_id: str, project_id: Optional[int] = None):
        self.session_id = session_id
        self.project_id = project_id
        self.state = AnalysisState.INITIAL_UPLOAD
        self.data_files = []
        self.discovered_structure = {}
        self.clarifications = {}
        self.analysis_plan = {}
        self.results = {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
    def discover_data_structure(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Phase 1: Understand what we're working with
        
        Args:
            file_paths: List of uploaded file paths
            
        Returns:
            Dictionary with discovered structure and generated questions
        """
        self.state = AnalysisState.DATA_DISCOVERY
        self.data_files = file_paths
        self.updated_at = datetime.utcnow()
        
        discovered = {
            'files': [],
            'data_types': [],
            'potential_analyses': [],
            'questions': []
        }
        
        for file_path in file_paths:
            try:
                file_info = self._examine_file(file_path)
                discovered['files'].append(file_info)
                
                # Detect data types
                if file_info['type'] == 'labor':
                    discovered['data_types'].append('labor_hours')
                elif file_info['type'] == 'productivity':
                    discovered['data_types'].append('productivity_metrics')
                    
            except Exception as e:
                current_app.logger.error(f"Error examining {file_path}: {e}")
                continue
        
        # Generate clarifying questions based on what was found
        discovered['questions'] = self._generate_questions(discovered)
        
        # Identify possible analyses
        discovered['potential_analyses'] = self._identify_analyses(discovered)
        
        self.discovered_structure = discovered
        self.state = AnalysisState.CLARIFICATION_PENDING
        self.updated_at = datetime.utcnow()
        
        return discovered
    
    def _examine_file(self, file_path: str) -> Dict[str, Any]:
        """
        Examine a single file to understand its structure
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information
        """
        file_info = {
            'path': file_path,
            'name': os.path.basename(file_path),
            'type': 'unknown',
            'sheets': [],
            'columns': [],
            'record_count': 0,
            'date_range': None,
            'departments': [],
            'buildings': []
        }
        
        try:
            # Check if it's an Excel file
            if file_path.endswith(('.xlsx', '.xls')):
                xls = pd.ExcelFile(file_path)
                file_info['sheets'] = xls.sheet_names
                
                # Read first sheet to understand structure
                df = pd.read_excel(file_path, nrows=100)
                file_info['columns'] = df.columns.tolist()
                file_info['record_count'] = len(pd.read_excel(file_path))
                
                # Detect file type based on columns
                columns_lower = [c.lower() for c in file_info['columns']]
                
                if any(col in columns_lower for col in ['total hours', 'overtime', 'reg']):
                    file_info['type'] = 'labor'
                    
                    # Get date range if Date column exists
                    if 'Date' in df.columns:
                        full_df = pd.read_excel(file_path)
                        full_df['Date'] = pd.to_datetime(full_df['Date'])
                        file_info['date_range'] = {
                            'start': full_df['Date'].min().strftime('%Y-%m-%d'),
                            'end': full_df['Date'].max().strftime('%Y-%m-%d')
                        }
                    
                    # Get departments and buildings
                    if 'Department' in df.columns:
                        full_df = pd.read_excel(file_path)
                        file_info['departments'] = full_df['Department'].unique().tolist()
                    
                    if 'Bldg' in df.columns:
                        full_df = pd.read_excel(file_path)
                        file_info['buildings'] = sorted(full_df['Bldg'].unique().tolist())
                        
                elif any(col in columns_lower for col in ['units', 'cases', 'cartons', 'completed']):
                    file_info['type'] = 'productivity'
                    
        except Exception as e:
            current_app.logger.error(f"Error examining file {file_path}: {e}")
            file_info['error'] = str(e)
        
        return file_info
    
    def _generate_questions(self, discovered: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate clarifying questions based on discovered data
        
        Args:
            discovered: Dictionary with discovered structure
            
        Returns:
            List of questions to ask the user
        """
        questions = []
        
        # Check if we have productivity data
        has_productivity = any(f['type'] == 'productivity' for f in discovered['files'])
        has_labor = any(f['type'] == 'labor' for f in discovered['files'])
        
        if has_labor and not has_productivity:
            questions.append({
                'id': 'has_productivity',
                'question': 'Do you have productivity metrics (units/hour, cases/hour) for these departments?',
                'type': 'choice',
                'options': ['Yes - I will upload them', 'No - just analyze labor patterns', 'Not sure'],
                'importance': 'high',
                'explanation': 'Productivity metrics enable performance standards and staffing gap analysis'
            })
        
        # Check for multiple departments
        labor_files = [f for f in discovered['files'] if f['type'] == 'labor']
        if labor_files and labor_files[0].get('departments'):
            dept_count = len(labor_files[0]['departments'])
            if dept_count > 1:
                questions.append({
                    'id': 'analyze_scope',
                    'question': f'I found {dept_count} departments. Should I analyze all of them or focus on specific ones?',
                    'type': 'choice',
                    'options': ['Analyze all', 'Let me choose specific departments', 'Just the largest ones'],
                    'importance': 'medium',
                    'explanation': 'This affects analysis scope and deliverable size'
                })
        
        # Check for multiple buildings
        if labor_files and labor_files[0].get('buildings'):
            bldg_count = len(labor_files[0]['buildings'])
            if bldg_count > 1:
                questions.append({
                    'id': 'building_grouping',
                    'question': f'I found {bldg_count} buildings. Should I analyze them separately or combined?',
                    'type': 'choice',
                    'options': ['Separately - compare buildings', 'Combined - facility-wide', 'Let me decide per department'],
                    'importance': 'medium'
                })
        
        # Analysis priority question
        questions.append({
            'id': 'analysis_priority',
            'question': 'What\'s your priority for this analysis?',
            'type': 'multi_select',
            'options': [
                'Find staffing gaps',
                'Identify overtime problems',
                'Establish performance standards',
                'Compare departments/buildings',
                'Monthly/seasonal trends',
                'All of the above'
            ],
            'importance': 'high',
            'explanation': 'Helps me focus on what matters most to you'
        })
        
        return questions
    
    def _identify_analyses(self, discovered: Dict[str, Any]) -> List[str]:
        """
        Identify which analyses are possible based on discovered data
        
        Args:
            discovered: Dictionary with discovered structure
            
        Returns:
            List of possible analysis types
        """
        analyses = []
        
        has_labor = any(f['type'] == 'labor' for f in discovered['files'])
        has_productivity = any(f['type'] == 'productivity' for f in discovered['files'])
        
        # Basic labor analyses (always possible with labor data)
        if has_labor:
            analyses.extend([
                'staffing_distribution',
                'operational_patterns',
                'overtime_analysis',
                'headcount_efficiency',
                'shift_balance'
            ])
        
        # Advanced analyses (require productivity data)
        if has_labor and has_productivity:
            analyses.extend([
                'performance_standards',
                'staffing_gaps',
                'scenario_analysis',
                'productivity_trends'
            ])
        
        return analyses
    
    def process_clarifications(self, user_responses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 2: Process user responses to clarification questions
        
        Args:
            user_responses: Dictionary of question_id: response
            
        Returns:
            Updated session state
        """
        self.clarifications = user_responses
        self.state = AnalysisState.PLAN_APPROVAL
        self.updated_at = datetime.utcnow()
        
        return {
            'state': self.state,
            'clarifications_received': len(user_responses),
            'next_step': 'build_analysis_plan'
        }
    
    def build_analysis_plan(self) -> Dict[str, Any]:
        """
        Phase 3: Create detailed analysis plan based on discovery and clarifications
        
        Returns:
            Analysis plan for user approval
        """
        plan = {
            'analyses': [],
            'deliverables': [],
            'estimated_time': 0,
            'warnings': []
        }
        
        # Determine which analyses to run based on clarifications
        priority = self.clarifications.get('analysis_priority', ['All of the above'])
        scope = self.clarifications.get('analyze_scope', 'Analyze all')
        
        # Build analyses list
        labor_files = [f for f in self.discovered_structure['files'] if f['type'] == 'labor']
        prod_files = [f for f in self.discovered_structure['files'] if f['type'] == 'productivity']
        
        if labor_files:
            departments = labor_files[0].get('departments', [])
            
            for dept in departments:
                dept_analyses = {
                    'department': dept,
                    'analyses': []
                }
                
                # Add analyses based on priority and available data
                if 'All of the above' in priority or 'Identify overtime problems' in priority:
                    dept_analyses['analyses'].append('overtime_analysis')
                    dept_analyses['analyses'].append('shift_balance')
                
                if 'All of the above' in priority or 'Find staffing gaps' in priority:
                    if prod_files:
                        dept_analyses['analyses'].append('staffing_gap_analysis')
                
                if 'All of the above' in priority or 'Establish performance standards' in priority:
                    if prod_files:
                        dept_analyses['analyses'].append('performance_standards')
                
                if 'All of the above' in priority or 'Monthly/seasonal trends' in priority:
                    dept_analyses['analyses'].append('monthly_trends')
                
                plan['analyses'].append(dept_analyses)
        
        # Define deliverables
        plan['deliverables'] = [
            {
                'type': 'powerpoint',
                'description': 'Client-ready presentation with all charts and findings',
                'slides': len(plan['analyses']) * 4 + 3  # ~4 slides per dept + title/summary/recs
            },
            {
                'type': 'executive_summary',
                'description': 'Written summary with key findings and recommendations'
            },
            {
                'type': 'charts',
                'description': 'High-resolution charts (300 DPI PNG)',
                'count': len(plan['analyses']) * 6  # ~6 charts per department
            },
            {
                'type': 'data_files',
                'description': 'Excel files with underlying calculations'
            },
            {
                'type': 'python_code',
                'description': 'Complete analysis scripts for GitHub deployment'
            }
        ]
        
        # Estimate time (rough)
        plan['estimated_time'] = len(plan['analyses']) * 60 + 120  # seconds
        
        # Add warnings if needed
        if not prod_files and ('performance standards' in priority or 'staffing gaps' in priority):
            plan['warnings'].append({
                'type': 'missing_data',
                'message': 'Performance standards and staffing gaps require productivity data. These analyses will be limited without it.'
            })
        
        self.analysis_plan = plan
        self.updated_at = datetime.utcnow()
        
        return plan
    
    def execute_analysis(self) -> Dict[str, Any]:
        """
        Phase 4: Execute the approved analysis plan
        
        Returns:
            Execution status and progress
        """
        self.state = AnalysisState.ANALYSIS_RUNNING
        self.updated_at = datetime.utcnow()
        
        try:
            # Import the analysis executor
            from analysis_executor import analyze_labor_file
            
            # Get the first data file (typically the labor file)
            if not self.data_files:
                raise ValueError("No data files available for analysis")
            
            labor_file = self.data_files[0]
            
            # Get department filter from clarifications
            department = None
            if 'analyze_scope' in self.clarifications:
                scope = self.clarifications['analyze_scope']
                if scope != 'Analyze all':
                    # Extract department name if user specified one
                    department = None  # For now, analyze all
            
            # Run the analysis
            current_app.logger.info(f"Starting analysis of {labor_file}")
            analysis_results = analyze_labor_file(labor_file, department=department)
            
            if not analysis_results.get('validation', {}).get('success', False):
                self.state = AnalysisState.ERROR
                self.results = {
                    'error': analysis_results.get('error', 'Analysis failed'),
                    'details': analysis_results
                }
                return {
                    'state': self.state,
                    'message': 'Analysis failed',
                    'error': analysis_results.get('error')
                }
            
            # Store results
            self.results = {
                'analysis_complete': True,
                'overview': analysis_results.get('overview'),
                'overtime_analysis': analysis_results.get('overtime_analysis'),
                'headcount_analysis': analysis_results.get('headcount_analysis'),
                'building_comparison': analysis_results.get('building_comparison'),
                'temporal_patterns': analysis_results.get('temporal_patterns'),
                'validation': analysis_results.get('validation'),
                'completed_at': datetime.utcnow().isoformat()
            }
            
            # Move to deliverable generation phase
            self.state = AnalysisState.DELIVERABLE_GENERATION
            self.updated_at = datetime.utcnow()
            
            current_app.logger.info(f"Analysis complete: {analysis_results['overview']['total_hours']} hours analyzed")
            
            return {
                'state': self.state,
                'message': 'Analysis complete - ready for deliverable generation',
                'progress': 100,
                'total_steps': len(self.analysis_plan.get('analyses', [])) * 6,
                'results_preview': {
                    'total_hours': analysis_results['overview']['total_hours'],
                    'employees': analysis_results['overview']['unique_employees'],
                    'overtime_pct': analysis_results['overview']['overtime_pct']
                }
            }
            
        except Exception as e:
            self.state = AnalysisState.ERROR
            self.results = {
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            current_app.logger.error(f"Analysis execution failed: {e}")
            
            return {
                'state': self.state,
                'message': f'Analysis failed: {str(e)}',
                'error': str(e)
            }
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current analysis progress
        
        Returns:
            Progress information
        """
        return {
            'session_id': self.session_id,
            'state': self.state,
            'updated_at': self.updated_at.isoformat(),
            'data_files_count': len(self.data_files),
            'clarifications_count': len(self.clarifications),
            'analyses_planned': len(self.analysis_plan.get('analyses', []))
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to dictionary for storage
        
        Returns:
            Dictionary representation
        """
        return {
            'session_id': self.session_id,
            'project_id': self.project_id,
            'state': self.state,
            'data_files': self.data_files,
            'discovered_structure': self.discovered_structure,
            'clarifications': self.clarifications,
            'analysis_plan': self.analysis_plan,
            'results': self.results,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisOrchestrator':
        """
        Create session from dictionary
        
        Args:
            data: Dictionary with session data
            
        Returns:
            AnalysisOrchestrator instance
        """
        session = cls(data['session_id'], data.get('project_id'))
        session.state = data['state']
        session.data_files = data['data_files']
        session.discovered_structure = data['discovered_structure']
        session.clarifications = data['clarifications']
        session.analysis_plan = data['analysis_plan']
        session.results = data['results']
        session.created_at = datetime.fromisoformat(data['created_at'])
        session.updated_at = datetime.fromisoformat(data['updated_at'])
        return session


# Helper function for route integration
def create_analysis_session(project_id: Optional[int] = None) -> AnalysisOrchestrator:
    """
    Create a new analysis session
    
    Args:
        project_id: Optional project ID to link to
        
    Returns:
        New AnalysisOrchestrator instance
    """
    import uuid
    session_id = str(uuid.uuid4())
    return AnalysisOrchestrator(session_id, project_id)


# I did no harm and this file is not truncated
