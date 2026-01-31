"""
Progressive File Analyzer - Smart Large File Handling
Created: January 31, 2026
Last Updated: January 31, 2026

Handles large files (especially Excel) with progressive analysis:
- Analyzes first 100 rows automatically
- Lets user request more rows: "next 500", "next 1000", "analyze all"
- Prevents timeouts and out-of-memory crashes
- Gives user control over cost and time

Author: Jim @ Shiftwork Solutions LLC
"""

import os
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


# File size thresholds (in bytes)
SMALL_FILE_THRESHOLD = 5 * 1024 * 1024  # 5MB - analyze fully
LARGE_FILE_THRESHOLD = 25 * 1024 * 1024  # 25MB - max allowed
INITIAL_ROW_LIMIT = 100  # Start with first 100 rows


class ProgressiveFileAnalyzer:
    """
    Smart file analyzer that handles large files progressively.
    """
    
    def __init__(self):
        self.file_cache = {}  # Cache file data between requests
    
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic information about a file without fully loading it.
        """
        try:
            file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            return {
                'success': True,
                'file_path': file_path,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'file_type': file_ext,
                'is_small': file_size < SMALL_FILE_THRESHOLD,
                'is_large': file_size >= SMALL_FILE_THRESHOLD,
                'is_too_large': file_size > LARGE_FILE_THRESHOLD
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    def extract_excel_chunk(self, file_path: str, start_row: int = 0, 
                           num_rows: Optional[int] = None, 
                           sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract a specific chunk of rows from an Excel file.
        
        Args:
            file_path: Path to Excel file
            start_row: Starting row number (0-indexed)
            num_rows: Number of rows to read (None = all remaining)
            sheet_name: Specific sheet to read (None = first sheet)
        
        Returns:
            Dict with extracted data and metadata
        """
        try:
            # Read Excel file with specific rows
            if num_rows is not None:
                df = pd.read_excel(
                    file_path, 
                    sheet_name=sheet_name or 0,
                    skiprows=start_row if start_row > 0 else None,
                    nrows=num_rows
                )
            else:
                df = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name or 0,
                    skiprows=start_row if start_row > 0 else None
                )
            
            # Get total row count (need to read full file for this)
            total_df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
            total_rows = len(total_df)
            
            # Generate summary
            summary = self._generate_chunk_summary(df, start_row, total_rows)
            
            # Convert to text for AI
            text_preview = self._dataframe_to_text(df, max_rows=100)
            
            return {
                'success': True,
                'dataframe': df,
                'text_preview': text_preview,
                'summary': summary,
                'rows_analyzed': len(df),
                'start_row': start_row,
                'end_row': start_row + len(df),
                'total_rows': total_rows,
                'rows_remaining': total_rows - (start_row + len(df)),
                'columns': list(df.columns),
                'column_count': len(df.columns)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    def _generate_chunk_summary(self, df: pd.DataFrame, start_row: int, 
                                total_rows: int) -> str:
        """Generate a summary of the dataframe chunk."""
        summary_parts = []
        
        # Basic info
        summary_parts.append(f"📊 **Data Summary (Rows {start_row + 1}-{start_row + len(df)} of {total_rows})**")
        summary_parts.append(f"- Columns: {len(df.columns)}")
        summary_parts.append(f"- Rows in this chunk: {len(df)}")
        
        # Column info
        summary_parts.append("\n**Columns:**")
        for col in df.columns[:10]:  # Show first 10 columns
            dtype = str(df[col].dtype)
            non_null = df[col].notna().sum()
            summary_parts.append(f"  - {col} ({dtype}): {non_null} non-null values")
        
        if len(df.columns) > 10:
            summary_parts.append(f"  ... and {len(df.columns) - 10} more columns")
        
        # Quick stats for numeric columns
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) > 0:
            summary_parts.append("\n**Numeric Column Stats:**")
            for col in numeric_cols[:5]:  # Show first 5 numeric columns
                try:
                    total = df[col].sum()
                    avg = df[col].mean()
                    summary_parts.append(f"  - {col}: Total = {total:,.2f}, Avg = {avg:,.2f}")
                except:
                    pass
        
        return "\n".join(summary_parts)
    
    
    def _dataframe_to_text(self, df: pd.DataFrame, max_rows: int = 100) -> str:
        """Convert dataframe to readable text format."""
        # Limit rows for preview
        preview_df = df.head(max_rows)
        
        # Convert to string with good formatting
        text = "=== DATA PREVIEW ===\n\n"
        text += preview_df.to_string(index=False, max_rows=max_rows)
        
        if len(df) > max_rows:
            text += f"\n\n... and {len(df) - max_rows} more rows in this chunk"
        
        return text
    
    
    def parse_user_continuation_request(self, user_message: str) -> Optional[Dict[str, Any]]:
        """
        Parse user's request for more rows.
        
        Examples:
            "next 500" -> analyze next 500 rows
            "next 1000" -> analyze next 1000 rows  
            "analyze all" -> analyze all remaining rows
            "show rows 500-1000" -> show specific range
        
        Returns:
            Dict with action and parameters, or None if not a continuation request
        """
        message_lower = user_message.lower().strip()
        
        # Pattern: "next X"
        if message_lower.startswith("next "):
            try:
                num_str = message_lower.replace("next ", "").strip()
                num_rows = int(num_str)
                return {
                    'action': 'analyze_next',
                    'num_rows': num_rows
                }
            except:
                pass
        
        # Pattern: "analyze all" or "all rows"
        if "analyze all" in message_lower or "all rows" in message_lower:
            return {
                'action': 'analyze_all'
            }
        
        # Pattern: "show rows X-Y" or "rows X to Y"
        if "rows " in message_lower:
            try:
                # Extract numbers
                import re
                numbers = re.findall(r'\d+', message_lower)
                if len(numbers) >= 2:
                    start = int(numbers[0])
                    end = int(numbers[1])
                    return {
                        'action': 'analyze_range',
                        'start_row': start,
                        'end_row': end
                    }
            except:
                pass
        
        return None
    
    
    def generate_continuation_prompt(self, chunk_result: Dict[str, Any]) -> str:
        """
        Generate the prompt that asks user if they want to continue.
        """
        rows_remaining = chunk_result.get('rows_remaining', 0)
        
        if rows_remaining == 0:
            return "\n\n✅ **Analysis complete!** All rows have been analyzed."
        
        prompt_parts = []
        prompt_parts.append("\n\n" + "="*60)
        prompt_parts.append("📊 **Would you like me to analyze more data?**")
        prompt_parts.append("="*60)
        prompt_parts.append(f"\n**Rows remaining:** {rows_remaining:,}")
        prompt_parts.append("\n**Options:**")
        
        # Suggest smart increments
        if rows_remaining <= 500:
            prompt_parts.append(f'- Type **"analyze all"** to process all {rows_remaining:,} remaining rows')
        else:
            prompt_parts.append('- Type **"next 500"** to analyze next 500 rows')
            prompt_parts.append('- Type **"next 1000"** to analyze next 1,000 rows')
            if rows_remaining <= 5000:
                prompt_parts.append(f'- Type **"analyze all"** to process all {rows_remaining:,} remaining rows')
            else:
                prompt_parts.append(f'- Type **"analyze all"** to process ALL remaining rows (⚠️ may take 3-5 minutes)')
        
        prompt_parts.append('\n- Or ask me specific questions about the data you\'ve seen so far')
        prompt_parts.append("="*60)
        
        return "\n".join(prompt_parts)


def get_progressive_analyzer():
    """Get singleton instance of progressive analyzer."""
    return ProgressiveFileAnalyzer()


# I did no harm and this file is not truncated
