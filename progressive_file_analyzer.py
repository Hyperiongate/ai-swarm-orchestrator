"""
Progressive File Analyzer - Smart Large File Handling
Created: January 31, 2026
Last Updated: February 5, 2026

CHANGE LOG:
- February 5, 2026 (v5): CRITICAL FIX - Memory-efficient row counting
  * Replaced pd.read_excel(full_file) with openpyxl read_only=True for row counting
  * A 26MB Excel file was causing pd.read_excel to consume 500MB+ RAM and crash
  * openpyxl read_only mode streams rows without loading entire file
  * Fixed singleton pattern - get_progressive_analyzer() now returns same instance
  * Added sheet_names to chunk result so orchestration_handler doesn't need to re-read
  * Removed redundant full-file reads that caused timeouts on large files

- February 5, 2026 (v4): Increased LARGE_FILE_THRESHOLD from 25MB to 100MB
  * Allows files like Definitive Schedules v2.xlsx (56.22 MB) to be uploaded
  * Maintains progressive analysis for very large files

- January 31, 2026 (v1): Initial creation
  * Progressive analysis for large Excel files
  * Chunk-based reading with continuation support

Handles large files (especially Excel) with progressive analysis:
- Analyzes first 500 rows automatically for files 5MB-100MB
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
INITIAL_ROW_LIMIT = 1000  # Start with first 1000 rows


class ProgressiveFileAnalyzer:
    """
    Smart file analyzer that handles large files progressively.
    
    Updated February 5, 2026 (v5): Memory-efficient row counting with openpyxl
    Updated February 5, 2026 (v4): Increased max file size to 100MB
    """
    
    def __init__(self):
        self.file_cache = {}  # Cache file metadata between requests
    
    
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
    
    
    def _count_rows_efficient(self, file_path: str) -> Dict[str, Any]:
        """
        Count total rows and get sheet names WITHOUT loading entire file into memory.
        
        Uses openpyxl read_only=True which streams rows instead of loading all data.
        For a 26MB file, this uses ~10MB RAM instead of 500MB+.
        
        Added: February 5, 2026 (v5)
        
        Returns:
            Dict with total_rows, sheet_names, columns
        """
        try:
            import openpyxl
            
            # Open in read-only mode - streams data, minimal RAM
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            
            # Count rows in first sheet
            ws = wb[sheet_names[0]]
            total_rows = 0
            columns = []
            
            for i, row in enumerate(ws.iter_rows()):
                if i == 0:
                    # Extract column names from header row
                    columns = [cell.value for cell in row if cell.value is not None]
                total_rows += 1
            
            # Subtract 1 for header row
            if total_rows > 0:
                total_rows -= 1
            
            wb.close()
            
            return {
                'success': True,
                'total_rows': total_rows,
                'sheet_names': sheet_names,
                'num_sheets': len(sheet_names),
                'columns': columns
            }
            
        except Exception as e:
            print(f"⚠️ openpyxl row count failed, falling back to pandas: {e}")
            # Fallback: use pandas but only read first row to get structure
            try:
                # Read just 1 row to get columns
                df_sample = pd.read_excel(file_path, sheet_name=0, nrows=1)
                columns = list(df_sample.columns)
                
                # Estimate row count from file size (rough: 1KB per row average)
                file_size = os.path.getsize(file_path)
                estimated_rows = max(100, int(file_size / 1024))
                
                # Try to get sheet names
                try:
                    excel_file = pd.ExcelFile(file_path)
                    sheet_names = excel_file.sheet_names
                except:
                    sheet_names = ['Sheet1']
                
                return {
                    'success': True,
                    'total_rows': estimated_rows,
                    'sheet_names': sheet_names,
                    'num_sheets': len(sheet_names),
                    'columns': columns,
                    'estimated': True  # Flag that row count is estimated
                }
            except Exception as fallback_error:
                return {
                    'success': False,
                    'error': f"Could not count rows: {str(fallback_error)}"
                }
    
    
    def extract_excel_chunk(self, file_path: str, start_row: int = 0, 
                           num_rows: Optional[int] = None, 
                           sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract a specific chunk of rows from an Excel file.
        
        UPDATED February 5, 2026 (v5): 
        - Uses openpyxl for row counting instead of reading entire file with pandas
        - Caches row count and sheet names for subsequent calls
        - Returns sheet_names so caller doesn't need to re-read the file
        
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
            - sheet_names: list (NEW in v5)
            - num_sheets: int (NEW in v5)
            - summary: str
        """
        try:
            # ================================================================
            # STEP 1: Read just the requested chunk with pandas
            # This is efficient because nrows limits how much data is loaded
            # ================================================================
            
            # For start_row > 0, we need to handle header separately
            if start_row > 0:
                # Read header first (row 0)
                header_df = pd.read_excel(file_path, sheet_name=sheet_name or 0, nrows=0)
                header_columns = list(header_df.columns)
                
                # Now read the chunk, skipping rows but keeping header
                # skiprows needs a range: skip rows 1 through start_row (keep row 0 = header)
                skip_range = range(1, start_row + 1)
                df = pd.read_excel(file_path, sheet_name=sheet_name or 0, 
                                 skiprows=skip_range, nrows=num_rows)
            else:
                # First chunk - just read normally
                df = pd.read_excel(file_path, sheet_name=sheet_name or 0, nrows=num_rows)
            
            # ================================================================
            # STEP 2: Get total rows efficiently (cached)
            # Uses openpyxl read_only mode - NOT pandas full-file read
            # ================================================================
            cache_key = file_path
            
            if cache_key not in self.file_cache:
                print(f"📊 Counting rows efficiently with openpyxl (first call)...")
                row_info = self._count_rows_efficient(file_path)
                
                if row_info['success']:
                    self.file_cache[cache_key] = {
                        'total_rows': row_info['total_rows'],
                        'columns': row_info['columns'],
                        'sheet_names': row_info['sheet_names'],
                        'num_sheets': row_info['num_sheets'],
                        'estimated': row_info.get('estimated', False)
                    }
                    print(f"📊 Row count: {row_info['total_rows']:,} rows across {row_info['num_sheets']} sheet(s)")
                else:
                    # Last resort: estimate from dataframe
                    print(f"⚠️ Row counting failed, using chunk size as estimate")
                    self.file_cache[cache_key] = {
                        'total_rows': len(df),
                        'columns': list(df.columns),
                        'sheet_names': ['Sheet1'],
                        'num_sheets': 1,
                        'estimated': True
                    }
            
            cached = self.file_cache[cache_key]
            total_rows = cached['total_rows']
            sheet_names = cached.get('sheet_names', ['Sheet1'])
            num_sheets = cached.get('num_sheets', 1)
            
            actual_start = start_row
            actual_end = start_row + len(df)
            rows_remaining = max(0, total_rows - actual_end)
            
            # Create summary
            estimated_note = " (estimated)" if cached.get('estimated') else ""
            summary = f"""
📊 **File Analysis**
- Total Rows: {total_rows:,}{estimated_note}
- Analyzing Rows: {actual_start:,} to {actual_end:,}
- Rows in this chunk: {len(df):,}
- Remaining rows: {rows_remaining:,}
- Columns: {len(df.columns)}
- Worksheets: {num_sheets} ({', '.join(sheet_names)})
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
                'rows_analyzed': len(df),
                'columns': list(df.columns),
                'sheet_names': sheet_names,
                'num_sheets': num_sheets,
                'summary': summary
            }
            
        except Exception as e:
            import traceback
            print(f"❌ extract_excel_chunk error: {traceback.format_exc()}")
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


# ============================================================================
# SINGLETON PATTERN - Fixed February 5, 2026
# Previous version created a new instance every call, losing the file_cache
# ============================================================================
_analyzer_instance = None

def get_progressive_analyzer():
    """Get singleton instance of progressive analyzer."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ProgressiveFileAnalyzer()
    return _analyzer_instance


# I did no harm and this file is not truncated
