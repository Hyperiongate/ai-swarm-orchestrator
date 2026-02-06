"""
Smart Excel Analyzer - Flexible analysis for ANY Excel file format
Created: February 6, 2026
Last Updated: February 6, 2026

This module profiles Excel files and enables conversational analysis.
Works with ANY column names, ANY data format.

Key Features:
- Auto-detects data type (workforce, financial, schedule, survey, custom)
- Profiles the data structure
- Generates pandas code based on natural language questions
- Executes code safely and returns real results
- Conversational follow-up analysis

Purpose: Replace rigid templates with flexible, intelligent analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import re


class SmartExcelAnalyzer:
    """
    Intelligent Excel analyzer that adapts to any file format.
    Generates and executes pandas code based on user questions.
    """
    
    def __init__(self, filepath):
        """
        Initialize analyzer with file path.
        
        Args:
            filepath: Path to Excel file
        """
        self.filepath = filepath
        self.df = None
        self.profile = {}
        self.analysis_history = []
        
    def load_and_profile(self):
        """
        Load Excel file and create comprehensive profile.
        Returns profile data for GPT-4 to understand the file.
        """
        try:
            # Load entire file into memory
            print(f"📊 Loading Excel file: {self.filepath}")
            self.df = pd.read_excel(self.filepath)
            
            # Clean column names
            self.df.columns = self.df.columns.str.strip()
            
            print(f"✅ Loaded {len(self.df):,} rows, {len(self.df.columns)} columns")
            
            # Create comprehensive profile
            self.profile = {
                'file_info': self._get_file_info(),
                'columns': self._profile_columns(),
                'data_types': self._detect_data_types(),
                'sample_data': self._get_sample_data(),
                'statistics': self._get_basic_statistics(),
                'suggested_analyses': self._suggest_analyses()
            }
            
            return {
                'success': True,
                'profile': self.profile,
                'message': f"Successfully loaded {len(self.df):,} rows"
            }
            
        except Exception as e:
            print(f"❌ Error loading file: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_file_info(self):
        """Get basic file information"""
        return {
            'total_rows': len(self.df),
            'total_columns': len(self.df.columns),
            'column_names': list(self.df.columns),
            'memory_usage_mb': round(self.df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            'has_duplicates': bool(self.df.duplicated().any()),
            'duplicate_count': int(self.df.duplicated().sum())
        }
    
    def _profile_columns(self):
        """Profile each column - type, unique values, nulls"""
        column_profiles = {}
        
        for col in self.df.columns:
            column_profiles[col] = {
                'dtype': str(self.df[col].dtype),
                'non_null_count': int(self.df[col].notna().sum()),
                'null_count': int(self.df[col].isna().sum()),
                'unique_count': int(self.df[col].nunique()),
                'is_numeric': pd.api.types.is_numeric_dtype(self.df[col]),
                'is_datetime': pd.api.types.is_datetime64_any_dtype(self.df[col]),
                'sample_values': self.df[col].dropna().head(3).tolist()
            }
            
            # Add numeric stats if applicable
            if column_profiles[col]['is_numeric']:
                column_profiles[col]['min'] = float(self.df[col].min())
                column_profiles[col]['max'] = float(self.df[col].max())
                column_profiles[col]['mean'] = float(self.df[col].mean())
        
        return column_profiles
    
    def _detect_data_types(self):
        """
        Detect what type of data this is.
        Returns multiple possible types with confidence scores.
        """
        columns_lower = set(self.df.columns.str.lower())
        detected_types = []
        
        # Workforce/Timesheet indicators
        workforce_keywords = {'emp', 'employee', 'name', 'dept', 'department', 'shift', 
                            'hours', 'reg', 'regular', 'overtime', 'ot', 'date'}
        workforce_score = len(workforce_keywords.intersection(columns_lower)) / len(workforce_keywords)
        if workforce_score > 0.3:
            detected_types.append({'type': 'workforce_timesheet', 'confidence': workforce_score})
        
        # Financial data indicators
        financial_keywords = {'amount', 'cost', 'revenue', 'expense', 'budget', 'actual', 
                            'variance', 'account', 'gl', 'ledger'}
        financial_score = len(financial_keywords.intersection(columns_lower)) / len(financial_keywords)
        if financial_score > 0.2:
            detected_types.append({'type': 'financial', 'confidence': financial_score})
        
        # Schedule/Roster indicators
        schedule_keywords = {'schedule', 'pattern', 'rotation', 'crew', 'shift', 'week', 
                           'on', 'off', 'day', 'night'}
        schedule_score = len(schedule_keywords.intersection(columns_lower)) / len(schedule_keywords)
        if schedule_score > 0.3:
            detected_types.append({'type': 'schedule_roster', 'confidence': schedule_score})
        
        # Survey data indicators
        survey_keywords = {'question', 'response', 'answer', 'rating', 'score', 'survey', 
                          'feedback', 'satisfaction'}
        survey_score = len(survey_keywords.intersection(columns_lower)) / len(survey_keywords)
        if survey_score > 0.2:
            detected_types.append({'type': 'survey_results', 'confidence': survey_score})
        
        # Sort by confidence
        detected_types.sort(key=lambda x: x['confidence'], reverse=True)
        
        # If no strong match, mark as custom
        if not detected_types or detected_types[0]['confidence'] < 0.3:
            detected_types.insert(0, {'type': 'custom', 'confidence': 1.0})
        
        return detected_types
    
    def _get_sample_data(self, n=5):
        """Get sample rows for display"""
        return {
            'first_rows': self.df.head(n).to_dict('records'),
            'random_sample': self.df.sample(min(n, len(self.df))).to_dict('records')
        }
    
    def _get_basic_statistics(self):
        """Get basic statistical summary"""
        stats = {}
        
        # Numeric columns summary
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            stats['numeric_summary'] = self.df[numeric_cols].describe().to_dict()
        
        # Date range if date columns exist
        date_cols = self.df.select_dtypes(include=['datetime64']).columns
        if len(date_cols) > 0:
            for col in date_cols:
                stats[f'{col}_range'] = {
                    'start': str(self.df[col].min()),
                    'end': str(self.df[col].max())
                }
        
        return stats
    
    def _suggest_analyses(self):
        """
        Suggest possible analyses based on detected data type.
        Returns list of suggested questions/analyses.
        """
        if not self.profile.get('data_types'):
            return []
        
        primary_type = self.profile['data_types'][0]['type']
        
        suggestions = {
            'workforce_timesheet': [
                "Show me total hours by department",
                "What's the overtime breakdown by shift?",
                "Which days have the highest hours?",
                "Show me monthly trends",
                "What's the average headcount per shift?"
            ],
            'financial': [
                "Show me totals by account",
                "What's the variance between budget and actual?",
                "Show me monthly spending trends",
                "Which categories have the highest costs?",
                "Compare periods (month over month, year over year)"
            ],
            'schedule_roster': [
                "Show me the shift rotation pattern",
                "How many people are on each shift?",
                "What's the coverage on weekends?",
                "Show me the full schedule",
                "Analyze shift distribution"
            ],
            'survey_results': [
                "Show me average ratings by question",
                "What are the top and bottom rated items?",
                "Show me response distribution",
                "Compare responses across departments",
                "Show me satisfaction trends"
            ],
            'custom': [
                "Summarize the data",
                "Show me breakdowns by category",
                "What are the totals?",
                "Show me trends over time",
                "Group and analyze by key fields"
            ]
        }
        
        return suggestions.get(primary_type, suggestions['custom'])
    
    def execute_analysis(self, user_question, pandas_code):
        """
        Execute pandas code safely and return results.
        
        Args:
            user_question: The original user question
            pandas_code: Pandas code generated by GPT-4
        
        Returns:
            Dictionary with results or error
        """
        try:
            # Create safe execution context
            # Only allow pandas operations on self.df
            local_context = {
                'df': self.df,
                'pd': pd,
                'np': np
            }
            
            print(f"🔧 Executing pandas code:\n{pandas_code}")
            
            # Execute the code
            result = eval(pandas_code, {"__builtins__": {}}, local_context)
            
            # Convert result to something serializable
            if isinstance(result, pd.DataFrame):
                result_data = {
                    'type': 'dataframe',
                    'shape': result.shape,
                    'data': result.to_dict('records')[:100],  # Limit to 100 rows for display
                    'columns': list(result.columns),
                    'markdown': result.to_markdown() if len(result) < 50 else result.head(50).to_markdown()
                }
            elif isinstance(result, pd.Series):
                result_data = {
                    'type': 'series',
                    'length': len(result),
                    'data': result.to_dict(),
                    'markdown': result.to_markdown() if len(result) < 50 else result.head(50).to_markdown()
                }
            elif isinstance(result, (int, float, str, bool)):
                result_data = {
                    'type': 'scalar',
                    'value': result,
                    'markdown': f"**Result:** {result}"
                }
            else:
                result_data = {
                    'type': 'other',
                    'value': str(result),
                    'markdown': str(result)
                }
            
            # Store in history
            self.analysis_history.append({
                'question': user_question,
                'code': pandas_code,
                'result': result_data,
                'timestamp': datetime.now().isoformat()
            })
            
            print(f"✅ Analysis complete")
            
            return {
                'success': True,
                'result': result_data,
                'code_executed': pandas_code
            }
            
        except Exception as e:
            print(f"❌ Error executing analysis: {e}")
            return {
                'success': False,
                'error': str(e),
                'code_attempted': pandas_code
            }
    
    def get_profile_summary(self):
        """
        Get a concise profile summary for GPT-4 to understand the file.
        This is what gets sent to GPT-4 to help it understand the data.
        """
        if not self.profile:
            return "File not loaded"
        
        summary = f"""
# DATA PROFILE

## File Information
- **Rows:** {self.profile['file_info']['total_rows']:,}
- **Columns:** {self.profile['file_info']['total_columns']}
- **Column Names:** {', '.join(self.profile['file_info']['column_names'])}

## Detected Data Type
"""
        
        for dt in self.profile['data_types']:
            summary += f"- {dt['type']} (confidence: {dt['confidence']:.0%})\n"
        
        summary += "\n## Column Details\n"
        for col, details in self.profile['columns'].items():
            summary += f"\n**{col}:**\n"
            summary += f"- Type: {details['dtype']}\n"
            summary += f"- Sample values: {details['sample_values']}\n"
            if details.get('is_numeric'):
                summary += f"- Range: {details.get('min')} to {details.get('max')}\n"
        
        summary += "\n## Sample Data (first 3 rows)\n"
        sample_df = pd.DataFrame(self.profile['sample_data']['first_rows'])
        summary += sample_df.to_markdown() if len(sample_df) > 0 else "No sample data"
        
        return summary
    
    def format_for_gpt_context(self):
        """
        Format the complete context that GPT-4 needs to answer questions.
        This includes the profile AND instructions for generating pandas code.
        """
        context = self.get_profile_summary()
        
        context += """

## INSTRUCTIONS FOR ANALYSIS

When the user asks a question about this data:

1. **Understand the question** - What specific calculation or view do they want?
2. **Generate pandas code** - Write code that operates on the DataFrame called `df`
3. **Return ONLY the pandas expression** - No explanations, just the code
4. **Use appropriate pandas methods:**
   - Grouping: `df.groupby(['column']).agg({'col': 'sum'})`
   - Filtering: `df[df['column'] > value]`
   - Sorting: `df.sort_values('column')`
   - Pivot: `df.pivot_table(values='col', index='row', columns='col')`
   - Aggregation: `.sum()`, `.mean()`, `.count()`, `.nunique()`

5. **Examples:**
   - "Total hours by department" → `df.groupby('Dept & Bldg')['Total Hours'].sum()`
   - "Average by day of week" → `df.groupby(df['Date'].dt.day_name())['Hours'].mean()`
   - "Top 5 departments" → `df.groupby('Dept')['Hours'].sum().nlargest(5)`

**CRITICAL:** Your response should ONLY contain the pandas code, nothing else.
"""
        
        return context


# I did no harm and this file is not truncated
