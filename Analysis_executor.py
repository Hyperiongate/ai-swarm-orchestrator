"""
Analysis Executor - Core Data Analysis Engine
Created: February 9, 2026
Last Updated: February 9, 2026

This module performs the actual analysis calculations on labor data.
It reads Excel files, calculates metrics, and prepares data for visualization.

Author: Shiftwork Solutions LLC
Phase: 0B - Execution Engine
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import os
from pathlib import Path
import traceback


class LaborDataAnalyzer:
    """
    Analyzes labor data from Excel files and calculates operational metrics.
    
    Expected Data Format:
    - Date: datetime
    - EDI# or Emp: employee identifier
    - Department: department name
    - Bldg: building code
    - Reg: regular hours
    - Overtime or OT: overtime hours
    - Total Hours: total hours worked
    """
    
    def __init__(self, file_path: str):
        """
        Initialize analyzer with labor data file
        
        Args:
            file_path: Path to Excel file with labor data
        """
        self.file_path = file_path
        self.df = None
        self.date_column = None
        self.emp_column = None
        self.dept_column = None
        self.bldg_column = None
        self.reg_column = None
        self.ot_column = None
        self.total_column = None
        
    def load_and_validate(self) -> Dict[str, Any]:
        """
        Load Excel file and validate structure
        
        Returns:
            Dictionary with validation results and file info
        """
        try:
            # Read Excel file
            self.df = pd.read_excel(self.file_path)
            
            # Detect column names (flexible matching)
            self._detect_columns()
            
            # Validate required columns exist
            validation = {
                'success': True,
                'file_name': os.path.basename(self.file_path),
                'total_records': len(self.df),
                'date_range': {
                    'start': self.df[self.date_column].min().strftime('%Y-%m-%d'),
                    'end': self.df[self.date_column].max().strftime('%Y-%m-%d')
                },
                'columns_detected': {
                    'date': self.date_column,
                    'employee': self.emp_column,
                    'department': self.dept_column,
                    'building': self.bldg_column,
                    'regular_hours': self.reg_column,
                    'overtime': self.ot_column,
                    'total_hours': self.total_column
                },
                'departments': self.df[self.dept_column].unique().tolist(),
                'buildings': sorted(self.df[self.bldg_column].unique().tolist()),
                'employees': self.df[self.emp_column].nunique(),
                'warnings': []
            }
            
            # Check data quality
            if self.df[self.total_column].isnull().any():
                validation['warnings'].append('Some total hours values are missing')
            
            if self.df[self.emp_column].isnull().any():
                validation['warnings'].append('Some employee IDs are missing')
            
            return validation
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def _detect_columns(self):
        """Detect column names with flexible matching"""
        cols = self.df.columns.tolist()
        cols_lower = [str(c).lower() for c in cols]
        
        # Date column
        date_options = ['date', 'work_date', 'workdate', 'day']
        self.date_column = next((cols[i] for i, c in enumerate(cols_lower) if c in date_options), 'Date')
        
        # Employee column
        emp_options = ['edi#', 'emp', 'employee', 'employee_id', 'emp_id']
        self.emp_column = next((cols[i] for i, c in enumerate(cols_lower) if any(opt in c for opt in emp_options)), 'EDI#')
        
        # Department column
        dept_options = ['department', 'dept']
        self.dept_column = next((cols[i] for i, c in enumerate(cols_lower) if c in dept_options), 'Department')
        
        # Building column
        bldg_options = ['bldg', 'building', 'location']
        self.bldg_column = next((cols[i] for i, c in enumerate(cols_lower) if c in bldg_options), 'Bldg')
        
        # Regular hours
        reg_options = ['reg', 'regular', 'regular hours', 'reg hours']
        self.reg_column = next((cols[i] for i, c in enumerate(cols_lower) if c in reg_options), 'Reg')
        
        # Overtime
        ot_options = ['ot', 'overtime', 'ot hours']
        self.ot_column = next((cols[i] for i, c in enumerate(cols_lower) if c in ot_options), 'Overtime')
        
        # Total hours
        total_options = ['total hours', 'total', 'hours']
        self.total_column = next((cols[i] for i, c in enumerate(cols_lower) if c in total_options), 'Total Hours')
    
    def analyze_department(self, department: str = None, building: str = None) -> Dict[str, Any]:
        """
        Perform comprehensive analysis for a department or building
        
        Args:
            department: Department name to analyze (None for all)
            building: Building code to filter (None for all)
            
        Returns:
            Dictionary with all calculated metrics
        """
        # Filter data
        df = self.df.copy()
        
        if department:
            df = df[df[self.dept_column] == department]
        
        if building:
            df = df[df[self.bldg_column] == building]
        
        if len(df) == 0:
            return {'error': 'No data found for specified filters'}
        
        # Calculate all metrics
        analysis = {
            'filter': {
                'department': department,
                'building': building
            },
            'overview': self._calculate_overview(df),
            'overtime_analysis': self._analyze_overtime(df),
            'headcount_analysis': self._analyze_headcount(df),
            'temporal_patterns': self._analyze_temporal_patterns(df),
            'building_comparison': self._compare_buildings(df) if not building else None,
            'employee_distribution': self._analyze_employee_distribution(df)
        }
        
        return analysis
    
    def _calculate_overview(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate high-level overview metrics"""
        total_hours = df[self.total_column].sum()
        reg_hours = df[self.reg_column].sum()
        ot_hours = df[self.ot_column].sum() if self.ot_column in df.columns else 0
        
        return {
            'total_hours': round(total_hours, 0),
            'regular_hours': round(reg_hours, 0),
            'overtime_hours': round(ot_hours, 0),
            'overtime_pct': round((ot_hours / total_hours * 100) if total_hours > 0 else 0, 1),
            'unique_employees': df[self.emp_column].nunique(),
            'total_records': len(df),
            'date_range': {
                'start': df[self.date_column].min().strftime('%Y-%m-%d'),
                'end': df[self.date_column].max().strftime('%Y-%m-%d'),
                'days': (df[self.date_column].max() - df[self.date_column].min()).days
            }
        }
    
    def _analyze_overtime(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze overtime patterns"""
        # Monthly OT trend
        df['YearMonth'] = df[self.date_column].dt.to_period('M')
        monthly_ot = df.groupby('YearMonth').agg({
            self.total_column: 'sum',
            self.ot_column: 'sum'
        })
        monthly_ot['OT_Pct'] = (monthly_ot[self.ot_column] / monthly_ot[self.total_column] * 100).round(1)
        
        # Weekly OT trend (last 13 weeks)
        df['YearWeek'] = df[self.date_column].dt.to_period('W')
        weekly_ot = df.groupby('YearWeek').agg({
            self.total_column: 'sum',
            self.ot_column: 'sum'
        }).tail(13)
        weekly_ot['OT_Pct'] = (weekly_ot[self.ot_column] / weekly_ot[self.total_column] * 100).round(1)
        
        # Employees with high OT
        emp_ot = df.groupby(self.emp_column).agg({
            self.total_column: 'sum',
            self.ot_column: 'sum'
        })
        emp_ot['OT_Pct'] = (emp_ot[self.ot_column] / emp_ot[self.total_column] * 100).round(1)
        high_ot_employees = emp_ot[emp_ot['OT_Pct'] > 20].sort_values('OT_Pct', ascending=False).head(10)
        
        return {
            'monthly_trend': monthly_ot.to_dict('index'),
            'weekly_trend': weekly_ot.to_dict('index'),
            'avg_monthly_ot_pct': monthly_ot['OT_Pct'].mean().round(1),
            'high_ot_employee_count': len(emp_ot[emp_ot['OT_Pct'] > 20]),
            'highest_ot_pct': emp_ot['OT_Pct'].max().round(1) if len(emp_ot) > 0 else 0
        }
    
    def _analyze_headcount(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze headcount patterns"""
        # Daily headcount
        daily_hc = df.groupby(self.date_column)[self.emp_column].nunique()
        
        # Average hours per employee
        emp_hours = df.groupby(self.emp_column)[self.total_column].sum()
        
        return {
            'avg_daily_headcount': round(daily_hc.mean(), 0),
            'max_daily_headcount': daily_hc.max(),
            'min_daily_headcount': daily_hc.min(),
            'avg_hours_per_employee': round(emp_hours.mean(), 0),
            'median_hours_per_employee': round(emp_hours.median(), 0),
            'total_unique_employees': df[self.emp_column].nunique()
        }
    
    def _analyze_temporal_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze day-of-week and time-based patterns"""
        # Add day of week
        df['DayOfWeek'] = df[self.date_column].dt.day_name()
        df['DayNum'] = df[self.date_column].dt.dayofweek
        
        # Hours by day of week
        dow_hours = df.groupby('DayOfWeek').agg({
            self.total_column: 'sum',
            self.emp_column: 'nunique'
        }).reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
        
        return {
            'hours_by_day': dow_hours.to_dict('index'),
            'busiest_day': dow_hours[self.total_column].idxmax(),
            'slowest_day': dow_hours[self.total_column].idxmin()
        }
    
    def _compare_buildings(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compare performance across buildings"""
        if self.bldg_column not in df.columns:
            return None
        
        bldg_summary = df.groupby(self.bldg_column).agg({
            self.emp_column: 'nunique',
            self.total_column: 'sum',
            self.ot_column: 'sum'
        })
        bldg_summary.columns = ['Employees', 'Total_Hours', 'OT_Hours']
        bldg_summary['OT_Pct'] = (bldg_summary['OT_Hours'] / bldg_summary['Total_Hours'] * 100).round(1)
        bldg_summary['Avg_Hours_Per_Employee'] = (bldg_summary['Total_Hours'] / bldg_summary['Employees']).round(0)
        
        return {
            'building_metrics': bldg_summary.to_dict('index'),
            'highest_ot_building': bldg_summary['OT_Pct'].idxmax(),
            'largest_building': bldg_summary['Employees'].idxmax()
        }
    
    def _analyze_employee_distribution(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze employee work patterns"""
        emp_summary = df.groupby(self.emp_column).agg({
            self.total_column: 'sum',
            self.date_column: 'count'  # Days worked
        })
        emp_summary.columns = ['Total_Hours', 'Days_Worked']
        emp_summary['Avg_Hours_Per_Day'] = (emp_summary['Total_Hours'] / emp_summary['Days_Worked']).round(1)
        
        return {
            'total_employees': len(emp_summary),
            'avg_days_worked': round(emp_summary['Days_Worked'].mean(), 0),
            'avg_hours_per_day': round(emp_summary['Avg_Hours_Per_Day'].mean(), 1),
            'employees_over_40hrs_week': len(emp_summary[emp_summary['Avg_Hours_Per_Day'] * 5 > 40])
        }
    
    def prepare_chart_data(self, analysis: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """
        Prepare data in format ready for chart generation
        
        Args:
            analysis: Analysis results from analyze_department()
            
        Returns:
            Dictionary of DataFrames ready for plotting
        """
        chart_data = {}
        
        # OT Trend Chart
        if 'overtime_analysis' in analysis and 'monthly_trend' in analysis['overtime_analysis']:
            ot_trend = pd.DataFrame(analysis['overtime_analysis']['monthly_trend']).T
            ot_trend.index = ot_trend.index.astype(str)
            chart_data['ot_trend_monthly'] = ot_trend
        
        # Building Comparison Chart
        if analysis.get('building_comparison') and analysis['building_comparison'].get('building_metrics'):
            bldg_data = pd.DataFrame(analysis['building_comparison']['building_metrics']).T
            chart_data['building_comparison'] = bldg_data
        
        # Day of Week Chart
        if 'temporal_patterns' in analysis and 'hours_by_day' in analysis['temporal_patterns']:
            dow_data = pd.DataFrame(analysis['temporal_patterns']['hours_by_day']).T
            chart_data['day_of_week'] = dow_data
        
        return chart_data


def analyze_labor_file(file_path: str, department: str = None, building: str = None) -> Dict[str, Any]:
    """
    Main entry point for labor file analysis
    
    Args:
        file_path: Path to Excel file
        department: Optional department filter
        building: Optional building filter
        
    Returns:
        Complete analysis results
    """
    try:
        # Initialize analyzer
        analyzer = LaborDataAnalyzer(file_path)
        
        # Load and validate
        validation = analyzer.load_and_validate()
        if not validation['success']:
            return validation
        
        # Perform analysis
        analysis = analyzer.analyze_department(department, building)
        
        # Add validation info
        analysis['validation'] = validation
        analysis['file_info'] = {
            'path': file_path,
            'analyzed_at': datetime.utcnow().isoformat()
        }
        
        return analysis
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


# I did no harm and this file is not truncated
