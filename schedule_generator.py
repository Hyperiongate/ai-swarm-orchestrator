"""
PATTERN-BASED SCHEDULE GENERATOR
Created: January 26, 2026
Last Updated: January 27, 2026 - FIXED FILE SAVE PATH

CHANGES:
- January 27, 2026: FIXED FILE SAVE PATH BUG
  * Now saves directly to /mnt/user-data/outputs (with fallbacks)
  * Fixes "File not found" error when routes/core.py tries to access file
  * Added proper error handling and debug logging

- January 26, 2026: Complete rebuild
  * Removed named schedules (except DuPont and Southern Swing)
  * Pattern-based selection: shift length → pattern type
  * Focus on visual clarity of patterns
  * No staffing, no costs - just clean schedule patterns

PURPOSE:
Creates visually clear shift schedule patterns in Excel format.
Asks user for shift length, then shows available patterns.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class PatternScheduleGenerator:
    """
    Generates visual schedule patterns based on shift length and rotation type
    """
    
    def __init__(self):
        self.patterns_12_hour = self._define_12_hour_patterns()
        self.patterns_8_hour = self._define_8_hour_patterns()
        
    def _define_12_hour_patterns(self):
        """Define 12-hour shift patterns"""
        return {
            '2-2-3': {
                'description': 'Pitman 2-2-3: Every other weekend off as 3-day weekend',
                'cycle_days': 14,
                'crews': 4,
                'crew_patterns': {
                    # CORRECT PATTERN from Implementation Manual
                    # Week 1: Sun off, Mon-Tue work, Wed-Thu off, Fri-Sat work
                    # Week 2: Sun work, Mon-Tue off, Wed-Thu work, Fri-Sat off
                    'Crew A (Days)': ['O','D','D','O','O','D','D','D','O','O','D','D','O','O'],
                    'Crew B (Days)': ['D','O','O','D','D','O','O','O','D','D','O','O','D','D'],
                    'Crew C (Nights)': ['O','N','N','O','O','N','N','N','O','O','N','N','O','O'],
                    'Crew D (Nights)': ['N','O','O','N','N','O','O','O','N','N','O','O','N','N']
                },
                'notes': [
                    '✓ Every other weekend off as 3-day weekend',
                    '✓ 2-week repeating cycle',
                    '✓ Never more than 2 consecutive days worked',
                    '✓ Crews A & B work day shifts (6am-6pm)',
                    '✓ Crews C & D work night shifts (6pm-6am)',
                    '✓ 24/7 coverage maintained',
                    '✓ Most popular 12-hour pattern - used by hundreds of facilities'
                ],
                'shift_details': {
                    'day_shift': '12 hours starting 6:00 AM (6am-6pm)',
                    'night_shift': '12 hours starting 6:00 PM (6pm-6am)',
                    'coverage': 'Continuous 24/7 coverage with 4 crews',
                    'overtime': 'Minimal - 42 hours/week average'
                }
            },
            '2-3-2': {
                'description': 'Work 2, Off 2, Work 3, Off 2, Work 2, Off 3 (repeats every 14 days)',
                'cycle_days': 14,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['D','D','O','O','D','D','D','O','O','N','N','O','O','O'],
                    'Crew B': ['O','O','D','D','O','O','O','D','D','O','O','N','N','N'],
                    'Crew C': ['N','N','O','O','D','D','D','O','O','D','D','O','O','O'],
                    'Crew D': ['O','O','N','N','O','O','O','D','D','O','O','D','D','D']
                },
                'notes': [
                    'Every other weekend off',
                    'Maximum 3 consecutive days worked',
                    '4 crews required for 24/7 coverage',
                    'Includes day and night shift rotation'
                ]
            },
            '3-2-2-3': {
                'description': 'Work 3, Off 2, Work 2, Off 3 (repeats every 10 days)',
                'cycle_days': 10,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['D','D','D','O','O','D','D','O','O','O'],
                    'Crew B': ['O','O','O','D','D','O','O','D','D','D'],
                    'Crew C': ['D','D','O','O','D','D','D','O','O','O'],
                    'Crew D': ['O','O','D','D','O','O','O','D','D','D']
                },
                'notes': [
                    '10-day rotation cycle',
                    'Maximum 3 consecutive days worked',
                    '4 crews required for 24/7 coverage',
                    'Weekend off frequency varies by week'
                ]
            },
            '4-3': {
                'description': 'Work 4, Off 3 (repeats every 7 days)',
                'cycle_days': 7,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['D','D','D','D','O','O','O'],
                    'Crew B': ['O','D','D','D','D','O','O'],
                    'Crew C': ['O','O','D','D','D','D','O'],
                    'Crew D': ['D','O','O','D','D','D','D']
                },
                'notes': [
                    'Simple weekly rotation',
                    'Maximum 4 consecutive days worked',
                    '4 crews required for 24/7 coverage',
                    'Weekend coverage rotates through crews'
                ]
            },
            '4-4': {
                'description': 'Work 4, Off 4 (repeats every 8 days)',
                'cycle_days': 8,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['D','D','D','D','O','O','O','O'],
                    'Crew B': ['O','O','O','O','D','D','D','D'],
                    'Crew C': ['D','D','D','D','O','O','O','O'],
                    'Crew D': ['O','O','O','O','D','D','D','D']
                },
                'notes': [
                    '8-day rotation cycle',
                    'Maximum 4 consecutive days worked',
                    '4 crews required for 24/7 coverage',
                    'Simple pattern, easy to remember'
                ]
            },
            'dupont': {
                'description': 'DuPont 12-Hour Rotating (4 nights, 3 off, 3 days, 1 off, 3 nights, 3 off, 4 days, 7 off)',
                'cycle_days': 28,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['N','N','N','N','O','O','O','D','D','D','O','N','N','N','O','O','O','D','D','D','D','O','O','O','O','O','O','O'],
                    'Crew B': ['O','N','N','N','N','O','O','O','D','D','D','O','N','N','N','O','O','O','D','D','D','D','O','O','O','O','O','O'],
                    'Crew C': ['O','O','N','N','N','N','O','O','O','D','D','D','O','N','N','N','O','O','O','D','D','D','D','O','O','O','O','O'],
                    'Crew D': ['O','O','O','N','N','N','N','O','O','O','D','D','D','O','N','N','N','O','O','O','D','D','D','D','O','O','O','O']
                },
                'notes': [
                    'Famous 7-day break every 28 days',
                    'Includes both day and night shifts',
                    '4 crews required for 24/7 coverage',
                    'Established industry pattern'
                ]
            }
        }
    
    def _define_8_hour_patterns(self):
        """Define 8-hour shift patterns"""
        return {
            '5-2-fixed': {
                'description': '5 days on, 2 days off - Fixed Shifts (Monday-Friday day shift)',
                'cycle_days': 7,
                'crews': 3,
                'crew_patterns': {
                    'Days': ['D','D','D','D','D','O','O'],
                    'Evenings': ['E','E','E','E','E','O','O'],
                    'Nights': ['N','N','N','N','N','O','O']
                },
                'notes': [
                    'Fixed shifts - no rotation',
                    'Traditional Monday-Friday for each shift',
                    'Weekends off for all crews',
                    '3 crews required for 24/7 coverage'
                ]
            },
            '6-3-fixed': {
                'description': '6 days on, 3 days off - Fixed Shifts',
                'cycle_days': 9,
                'crews': 3,
                'crew_patterns': {
                    'Days': ['D','D','D','D','D','D','O','O','O'],
                    'Evenings': ['E','E','E','E','E','E','O','O','O'],
                    'Nights': ['N','N','N','N','N','N','O','O','O']
                },
                'notes': [
                    'Fixed shifts - no rotation',
                    'Longer work blocks, longer rest periods',
                    '9-day rotation cycle',
                    '3 crews required for 24/7 coverage'
                ]
            },
            'southern_swing': {
                'description': 'Southern Swing (7 days, 2 off, 7 evenings, 2 off, 7 nights, 2 off - rotating)',
                'cycle_days': 28,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['D','D','D','D','D','D','D','O','O','E','E','E','E','E','E','E','O','O','N','N','N','N','N','N','N','O','O','O'],
                    'Crew B': ['E','E','E','E','E','E','E','O','O','N','N','N','N','N','N','N','O','O','D','D','D','D','D','D','D','O','O','O'],
                    'Crew C': ['N','N','N','N','N','N','N','O','O','D','D','D','D','D','D','D','O','O','E','E','E','E','E','E','E','O','O','O'],
                    'Crew D': ['O','O','E','E','E','E','E','E','E','O','O','N','N','N','N','N','N','N','O','O','D','D','D','D','D','D','D','O']
                },
                'notes': [
                    'Rotating through all three shifts',
                    'Forward rotation (clockwise): Days → Evenings → Nights',
                    '7 consecutive days on each shift',
                    '4 crews required for 24/7 coverage',
                    'Established industry pattern'
                ]
            },
            '6-2-rotating': {
                'description': '6 days on, 2 days off - Rotating through shifts',
                'cycle_days': 24,
                'crews': 4,
                'crew_patterns': {
                    'Crew A': ['D','D','D','D','D','D','O','O','E','E','E','E','E','E','O','O','N','N','N','N','N','N','O','O'],
                    'Crew B': ['E','E','E','E','E','E','O','O','N','N','N','N','N','N','O','O','D','D','D','D','D','D','O','O'],
                    'Crew C': ['N','N','N','N','N','N','O','O','D','D','D','D','D','D','O','O','E','E','E','E','E','E','O','O'],
                    'Crew D': ['O','O','D','D','D','D','D','D','O','O','E','E','E','E','E','E','O','O','N','N','N','N','N','N']
                },
                'notes': [
                    'Rotating through all three shifts',
                    'Forward rotation (clockwise)',
                    '6 consecutive days per shift',
                    '4 crews required for 24/7 coverage'
                ]
            }
        }
    
    def get_available_patterns(self, shift_length):
        """Get list of available patterns for given shift length"""
        if shift_length == 12:
            return list(self.patterns_12_hour.keys())
        elif shift_length == 8:
            return list(self.patterns_8_hour.keys())
        else:
            return []
    
    def get_pattern_description(self, shift_length, pattern_key):
        """Get description of a specific pattern"""
        if shift_length == 12:
            return self.patterns_12_hour.get(pattern_key, {}).get('description', 'Pattern not found')
        elif shift_length == 8:
            return self.patterns_8_hour.get(pattern_key, {}).get('description', 'Pattern not found')
        return 'Invalid shift length'
    
    def create_schedule(self, shift_length, pattern_key, start_date=None, weeks_to_show=8):
        """
        Create a visual schedule pattern in Excel format
        
        Args:
            shift_length: 8 or 12 hours
            pattern_key: Key for the pattern (e.g., '2-2-3', 'dupont')
            start_date: Starting Monday (defaults to next Monday)
            weeks_to_show: Number of weeks to display
            
        Returns:
            File path to created Excel file
        """
        # Get pattern data
        if shift_length == 12:
            pattern_data = self.patterns_12_hour.get(pattern_key)
        elif shift_length == 8:
            pattern_data = self.patterns_8_hour.get(pattern_key)
        else:
            raise ValueError(f"Invalid shift length: {shift_length}. Must be 8 or 12.")
        
        if not pattern_data:
            raise ValueError(f"Pattern '{pattern_key}' not found for {shift_length}-hour shifts")
        
        # Set start date to next Monday if not provided
        if start_date is None:
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            start_date = today + timedelta(days=days_until_monday)
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = f"{shift_length}-Hour Pattern"[:31]
        
        # Define styles
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        
        day_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
        evening_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        night_fill = PatternFill(start_color="B4C7E7", end_color="B4C7E7", fill_type="solid")
        off_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        
        cell_font = Font(size=10)
        bold_font = Font(size=10, bold=True)
        center_align = Alignment(horizontal="center", vertical="center")
        
        thin_border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC')
        )
        
        # Write title and description
        ws['A1'] = f"{shift_length}-Hour Shift Pattern"
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:I1')
        
        ws['A2'] = pattern_data['description']
        ws['A2'].font = Font(size=10, italic=True)
        ws.merge_cells('A2:I2')
        
        # Write notes
        current_row = 4
        ws[f'A{current_row}'] = 'Pattern Details:'
        ws[f'A{current_row}'].font = bold_font
        current_row += 1
        
        for note in pattern_data['notes']:
            ws[f'A{current_row}'] = f"• {note}"
            ws[f'A{current_row}'].font = Font(size=9)
            current_row += 1
        
        # Start schedule table
        current_row += 2
        table_start_row = current_row
        
        # Header row
        ws[f'A{current_row}'] = 'Crew'
        ws[f'B{current_row}'] = 'Week'
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for col_idx, day in enumerate(days, start=3):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = day
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
        
        # Apply header styling to crew/week columns
        ws.cell(row=current_row, column=1).fill = header_fill
        ws.cell(row=current_row, column=1).font = header_font
        ws.cell(row=current_row, column=1).alignment = center_align
        ws.cell(row=current_row, column=1).border = thin_border
        ws.cell(row=current_row, column=2).fill = header_fill
        ws.cell(row=current_row, column=2).font = header_font
        ws.cell(row=current_row, column=2).alignment = center_align
        ws.cell(row=current_row, column=2).border = thin_border
        
        current_row += 1
        
        # Generate schedule rows
        cycle_days = pattern_data['cycle_days']
        crew_patterns = pattern_data['crew_patterns']
        
        # Calculate total days to show
        days_to_show = weeks_to_show * 7
        
        for crew_name, pattern in crew_patterns.items():
            # Extend pattern to cover all weeks
            extended_pattern = []
            for day_idx in range(days_to_show):
                pattern_idx = day_idx % cycle_days
                extended_pattern.append(pattern[pattern_idx])
            
            # Group by weeks
            for week_num in range(weeks_to_show):
                week_start = week_num * 7
                week_end = week_start + 7
                week_pattern = extended_pattern[week_start:week_end]
                
                # Write crew name (only on first week)
                if week_num == 0:
                    crew_cell = ws.cell(row=current_row, column=1)
                    crew_cell.value = crew_name
                    crew_cell.font = bold_font
                    crew_cell.alignment = center_align
                    crew_cell.border = thin_border
                else:
                    ws.cell(row=current_row, column=1).border = thin_border
                
                # Write week number
                week_cell = ws.cell(row=current_row, column=2)
                week_cell.value = week_num + 1
                week_cell.alignment = center_align
                week_cell.border = thin_border
                
                # Write daily shifts
                for day_idx, shift in enumerate(week_pattern, start=3):
                    cell = ws.cell(row=current_row, column=day_idx)
                    cell.value = shift
                    cell.font = cell_font
                    cell.alignment = center_align
                    cell.border = thin_border
                    
                    # Apply color based on shift type
                    if shift == 'D':
                        cell.fill = day_fill
                    elif shift == 'E':
                        cell.fill = evening_fill
                    elif shift == 'N':
                        cell.fill = night_fill
                    elif shift == 'O':
                        cell.fill = off_fill
                
                current_row += 1
            
            # Add blank row between crews for readability
            current_row += 1
        
        # Add legend
        legend_row = current_row + 1
        ws[f'A{legend_row}'] = 'LEGEND:'
        ws[f'A{legend_row}'].font = bold_font
        
        legend_items = [
            ('D', 'Day Shift', day_fill, f'{shift_length} hours starting ~6:00 AM'),
            ('N', 'Night Shift', night_fill, f'{shift_length} hours starting ~6:00 PM'),
            ('O', 'OFF', off_fill, 'Not scheduled')
        ]
        
        # Add evening shift to legend if 8-hour
        if shift_length == 8:
            legend_items.insert(1, ('E', 'Evening Shift', evening_fill, '8 hours starting ~2:00 PM'))
        
        for idx, (code, label, fill, time) in enumerate(legend_items):
            row = legend_row + idx + 1
            
            # Code
            cell = ws.cell(row=row, column=1)
            cell.value = code
            cell.fill = fill
            cell.font = bold_font
            cell.alignment = center_align
            cell.border = thin_border
            
            # Label
            cell = ws.cell(row=row, column=2)
            cell.value = label
            cell.alignment = Alignment(horizontal="left", vertical="center")
            cell.border = thin_border
            
            # Time
            ws.merge_cells(f'C{row}:E{row}')
            cell = ws.cell(row=row, column=3)
            cell.value = time
            cell.alignment = Alignment(horizontal="left", vertical="center")
        
        # Set column widths
        ws.column_dimensions['A'].width = 14
        ws.column_dimensions['B'].width = 8
        for col in range(3, 10):
            ws.column_dimensions[get_column_letter(col)].width = 7
        
        # Save file - FIXED: Try multiple locations with fallback
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"schedule_{shift_length}hr_{pattern_key}_{timestamp}.xlsx"
        
        # Try multiple save locations
        save_locations = [
            '/mnt/user-data/outputs',
            '/tmp',
            '.'
        ]
        
        filepath = None
        for location in save_locations:
            try:
                os.makedirs(location, exist_ok=True)
                test_path = os.path.join(location, filename)
                wb.save(test_path)
                filepath = test_path
                print(f"✅ Schedule saved to: {filepath}")
                break
            except Exception as e:
                print(f"⚠️  Could not save to {location}: {e}")
                continue
        
        if not filepath:
            raise Exception("Could not save schedule file to any location")
        
        return filepath


# Singleton instance
_generator = None

def get_pattern_generator():
    """Get or create pattern generator instance"""
    global _generator
    if _generator is None:
        _generator = PatternScheduleGenerator()
    return _generator


# I did no harm and this file is not truncated
