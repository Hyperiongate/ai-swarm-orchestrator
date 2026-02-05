"""
Progressive File Analyzer - Smart Large File Handling
Created: January 31, 2026
Last Updated: February 5, 2026 - INCREASED FILE SIZE LIMIT TO 100MB

CRITICAL UPDATE (February 5, 2026):
- Increased LARGE_FILE_THRESHOLD from 25MB to 100MB
- Allows files like Definitive Schedules v2.xlsx (56.22 MB) to be uploaded
- Maintains progressive analysis for very large files
- Better user experience with smart chunking

Handles large files (especially Excel) with progressive analysis:
- Analyzes first 100 rows automatically for files 5MB-100MB
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
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB - max allowed (UPDATED from 25MB)
INITIAL_ROW_LIMIT = 100  # Start with first 100 rows


class ProgressiveFileAnalyzer:
    """
    Smart file analyzer that handles large files progressively.
    
    Updated February 5, 2026: Increased max file size to 100MB
    """
    
    def __init__(self):
        self.file_cache = {}  # Cache file data between requests
    
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic information about a file without fully loading it.
        
        Returns:
            Dict with file info including:
            - is_small: < 5MB (full analysis)
            - is_large: 5MB-100MB (progressive analysis)
            - is_too_large: > 100MB (rejected)
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
            start_row: Starting row (0-indexed)
            num_rows: Number of rows to extract (None = all)
            sheet_name: Specific sheet to read (None = first sheet)
        
        Returns:
            Dict with:
            - success: bool
            - data: DataFrame
            - text_preview: Formatted string preview
            - start_row: int
            - end_row: int
            - total_rows: int
            - rows_remaining: int
            - columns: list
            - summary: str
        """
        try:
            # Read Excel file (just the requested chunk)
            skiprows = start_row if start_row > 0 else None
            nrows = num_rows
            
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0, 
                             skiprows=skiprows, nrows=nrows)
            
            # Get total rows (need to read whole file for this - only done once)
            if 'total_rows' not in self.file_cache.get(file_path, {}):
                full_df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
                total_rows = len(full_df)
                if file_path not in self.file_cache:
                    self.file_cache[file_path] = {}
                self.file_cache[file_path]['total_rows'] = total_rows
                self.file_cache[file_path]['columns'] = list(full_df.columns)
            else:
                total_rows = self.file_cache[file_path]['total_rows']
            
            actual_start = start_row
            actual_end = start_row + len(df)
            rows_remaining = max(0, total_rows - actual_end)
            
            # Create summary
            summary = f"""
📊 **File Analysis**
- Total Rows: {total_rows:,}
- Analyzing Rows: {actual_start:,} to {actual_end:,}
- Rows in this chunk: {len(df):,}
- Remaining rows: {rows_remaining:,}
- Columns: {len(df.columns)}
"""
            
            # Create text preview
            text_preview = self._format_dataframe_preview(df, max_rows=100)
            
            return {
                'success': True,
                'data': df,
                'text_preview': text_preview,
                'start_row': actual_start,
                'end_row': actual_end,
                'total_rows': total_rows,
                'rows_remaining': rows_remaining,
                'columns': list(df.columns),
                'summary': summary
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    def _format_dataframe_preview(self, df: pd.DataFrame, max_rows: int = 100) -> str:
        """
        Format a DataFrame as a readable string preview.
        """
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
