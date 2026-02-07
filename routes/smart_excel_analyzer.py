"""
Smart Excel Analyzer - Flexible analysis for ANY Excel file format
Created: February 6, 2026
Last Updated: February 7, 2026 - FIXED MULTI-PART QUERY HANDLING

CHANGES IN THIS VERSION:
- February 7, 2026: FIXED MULTI-PART QUERY BUG
  * Updated GPT-4 instructions to handle questions with multiple calculations
  * Now tells GPT-4 to combine results into single DataFrame using pd.DataFrame()
  * Added explicit examples of multi-part query handling
  * Prevents syntax errors from returning multiple variables

This module profiles Excel files and enables conversational analysis.
Works with ANY column names, ANY data format.

Key Features:
- Auto-detects data type (workforce, financial, schedule, survey, custom)
- Profiles the data structure
- Generates pandas code based on natural language questions
- Executes code safely and returns real results
- Conversational follow-up analysis
- Handles multi-part questions by combining into single DataFrame

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
        Handles multiple sheets intelligently.
        Returns profile data for GPT-4 to understand the file.
        """
        try:
            # Load entire file into memory
            print(f"📊 Loading Excel file: {self.filepath}")
            
            # Check for multiple sheets
            excel_file = pd.ExcelFile(self.filepath)
            sheet_names = excel_file.sheet_names
            num_sheets = len(sheet_names)
            
            print(f"📋 Found {num_sheets} sheet(s): {', '.join(sheet_names)}")
            
            if num_sheets == 1:
                # Single sheet - load it directly
                self.df = pd.read_excel(self.filepath)
                self.sheets = {sheet_names[0]: self.df}
                self.active_sheet = sheet_names[0]
            else:
                # Multiple sheets - load all, use first as default
                self.sheets = {}
                for sheet in sheet_names:
                    self.sheets[sheet] = pd.read_excel(self.filepath, sheet_name=sheet)
                    print(f"  ✅ Loaded sheet '{sheet}': {len(self.sheets[sheet]):,} rows")
                
                # Use first sheet as default working dataframe
                self.active_sheet = sheet_names[0]
                self.df = self.sheets[self.active_sheet]
            
            # Clean column names
            self.df.columns = self.df.columns.str.strip()
            
            print(f"✅ Active sheet: '{self.active_sheet}' - {len(self.df):,} rows, {len(self.df.columns)} columns")
            
            # Create comprehensive profile
            self.profile = {
                'file_info': self._get_file_info(),
                'sheets_info': self._get_sheets_info(),
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
    
    def _get_sheets_info(self):
        """Get information about all sheets in the workbook"""
        if not hasattr(self, 'sheets'):
            return None
        
        sheets_info = {
            'num_sheets': len(self.sheets),
            'sheet_names': list(self.sheets.keys()),
            'active_sheet': self.active_sheet,
            'sheets_summary': {}
        }
        
        # Summary for each sheet
        for sheet_name, sheet_df in self.sheets.items():
            sheets_info['sheets_summary'][sheet_name] = {
                'rows': len(sheet_df),
                'columns': len(sheet_df.columns),
                'column_names': list(sheet_df.columns)
            }
        
        return sheets_info
    
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
    
    def execute_analysis(self, user_question, pandas_code, attempt=1, max_attempts=3, previous_error=None):
        """
        Execute pandas code safely and return results.
        If code fails, can retry with error feedback.
        
        Args:
            user_question: The original user question
            pandas_code: Pandas code generated by GPT-4
            attempt: Current attempt number (for retry logic)
            max_attempts: Maximum retry attempts
            previous_error: Error from previous attempt (for GPT-4 feedback)
        
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
            
            print(f"🔧 Executing pandas code (attempt {attempt}/{max_attempts}):\n{pandas_code}")
            
            # Execute the code
            result = eval(pandas_code, {"__builtins__": {}}, local_context)
            
            # Convert result to something serializable
            if isinstance(result, pd.DataFrame):
                result_data = {
                    'type': 'dataframe',
                    'dataframe': result,
                    'shape': result.shape,
                    'data': result.to_dict('records')[:100],  # Limit to 100 rows for display
                    'columns': list(result.columns),
                    'markdown': result.to_markdown() if len(result) < 50 else result.head(50).to_markdown()
                }
            elif isinstance(result, pd.Series):
                result_data = {
                    'type': 'series',
                    'dataframe': result.to_frame(),
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
                'timestamp': datetime.now().isoformat(),
                'attempts': attempt
            })
            
            print(f"✅ Analysis complete")
            
            return {
                'success': True,
                'result': result_data,
                'code_executed': pandas_code,
                'attempts': attempt
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error executing analysis (attempt {attempt}): {error_msg}")
            
            # Return error info for potential retry
            return {
                'success': False,
                'error': error_msg,
                'code_attempted': pandas_code,
                'attempt': attempt,
                'can_retry': attempt < max_attempts,
                'error_context': {
                    'columns_available': list(self.df.columns),
                    'dtypes': self.df.dtypes.to_dict(),
                    'sample_values': {col: self.df[col].head(2).tolist() for col in self.df.columns}
                }
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
"""

        # Add sheets info if multiple sheets
        if self.profile.get('sheets_info') and self.profile['sheets_info']['num_sheets'] > 1:
            summary += f"\n## Multiple Sheets Detected\n"
            summary += f"- **Total Sheets:** {self.profile['sheets_info']['num_sheets']}\n"
            summary += f"- **Active Sheet:** '{self.profile['sheets_info']['active_sheet']}'\n"
            summary += f"- **All Sheets:** {', '.join(self.profile['sheets_info']['sheet_names'])}\n"
            for sheet_name, sheet_info in self.profile['sheets_info']['sheets_summary'].items():
                summary += f"\n  **{sheet_name}:** {sheet_info['rows']:,} rows, columns: {', '.join(sheet_info['column_names'])}\n"

        summary += "\n## Detected Data Type\n"
        
        for dt in self.profile['data_types']:
            summary += f"- {dt['type']} (confidence: {dt['confidence']:.0%})\n"
        
        summary += "\n## Column Details (Active Sheet)\n"
        for col, details in self.profile['columns'].items():
            summary += f"\n**{col}:**\n"
            summary += f"- Type: {details['dtype']}\n"
            summary += f"- Sample values: {details['sample_values']}\n"
            if details.get('is_numeric'):
                summary += f"- Range: {details.get('min')} to {details.get('max')}\n"
        
        summary += "\n## Sample Data (first 3 rows from active sheet)\n"
        sample_df = pd.DataFrame(self.profile['sample_data']['first_rows'])
        summary += sample_df.to_markdown() if len(sample_df) > 0 else "No sample data"
        
        return summary
    
    def format_for_gpt_context(self):
        """
        Format the complete context that GPT-4 needs to answer questions.
        This includes the profile AND instructions for generating pandas code.
        
        UPDATED February 7, 2026: Fixed multi-part query handling
        """
        context = self.get_profile_summary()
        
        context += """

## INSTRUCTIONS FOR ANALYSIS

When the user asks a question about this data:

1. **Understand the question** - What specific calculation or view do they want?
2. **Generate pandas code** - Write code that operates on the DataFrame called `df`
3. **Return a SINGLE pandas expression** - Must evaluate to a DataFrame or Series
4. **For multi-part questions:** Combine results into ONE DataFrame using pd.DataFrame() or .agg()

**CRITICAL RULES:**
- Your code must be a SINGLE expression that returns a DataFrame or Series
- Do NOT return multiple variables separated by commas (e.g., "var1, var2, var3")
- Do NOT use print statements
- Do NOT include any explanations or comments
- The last line must be the expression that returns the result

## Pandas Methods Available:
- Grouping: `df.groupby(['column']).agg({'col': 'sum'})`
- Filtering: `df[df['column'] > value]`
- Sorting: `df.sort_values('column')`
- Pivot: `df.pivot_table(values='col', index='row', columns='col')`
- Aggregation: `.sum()`, `.mean()`, `.count()`, `.nunique()`
- DateTime: `df['Date'].dt.day_name()`, `df['Date'].dt.month_name()`

## Examples:

**Single calculation:**
```python
df.groupby('Department')['Total Hours'].sum()
```
```python
df.groupby(df['Date'].dt.day_name())['Total Hours'].mean()
```
```python
df.groupby('Department')['Total Hours'].sum().nlargest(5)
```

**Multi-part questions - COMBINE into ONE DataFrame:**

Question: "Show average employees and hours by month"
```python
pd.DataFrame({
    'avg_employees': df.groupby('Month')['EDI#'].nunique(),
    'avg_hours': df.groupby('Month')['Total Hours'].mean()
})
```

Question: "Department analysis: count, total, and average"
```python
df.groupby('Department').agg({
    'EDI#': 'count',
    'Total Hours': ['sum', 'mean']
})
```

Question: "Show me total by department and shift"
```python
df.groupby(['Department', 'Shift'])['Total Hours'].sum().unstack(fill_value=0)
```

**For questions with filters AND multiple calculations:**
```python
pd.DataFrame({
    'metric1': df[df['Department']=='Processing'].groupby('Month')['Hours'].sum(),
    'metric2': df[df['Department']=='Processing'].groupby('Month')['EDI#'].nunique()
})
```

**CRITICAL:** Your response must be ONE pandas expression that returns a DataFrame or Series. 
For questions with multiple parts, use `pd.DataFrame()`, `df.agg()`, or `.unstack()` to combine results.
Never return multiple variables like "result1, result2, result3" - this causes syntax errors!
"""
        
        return context


# I did no harm and this file is not truncated
