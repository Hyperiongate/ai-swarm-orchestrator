"""
NORMATIVE DATABASE MODULE
Created: January 20, 2026
Last Updated: January 20, 2026

CHANGES IN THIS VERSION:
- January 20, 2026: Initial creation
  * Loads 206-company benchmark data from Excel
  * Provides normative comparison functions
  * Calculates percentiles and deviations from norm
  * Integrates with Project Mode for client comparisons

PURPOSE:
Loads and manages the normative database of 206 companies with survey responses.
Provides comparison functions to benchmark client data against industry norms.

FEATURES:
- Load benchmark data from Excel file
- Compare client responses to normative averages
- Calculate percentiles and standard deviations
- Identify significant deviations
- Generate comparative insights

DATA STRUCTURE:
- 206 companies across rows
- Survey questions and responses across columns
- Calculated averages for each question
- Industry benchmarks by sector

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import openpyxl
import numpy as np
from pathlib import Path
import json
from datetime import datetime


class NormativeDatabase:
    """
    Manages the 206-company normative database for benchmarking client survey results.
    """
    
    def __init__(self, excel_path=None):
        """
        Initialize the normative database.
        
        Args:
            excel_path: Path to the normative database Excel file
                       Defaults to /mnt/user-data/uploads/Copy_of_Norms_-_Overall.xlsx
        """
        if excel_path is None:
            # Try multiple possible locations
            possible_paths = [
                Path("/mnt/user-data/uploads/Copy_of_Norms_-_Overall.xlsx"),
                Path("/mnt/project/Copy_of_Norms_-_Overall.xlsx"),
                Path("./Copy_of_Norms_-_Overall.xlsx")
            ]
            
            for path in possible_paths:
                if path.exists():
                    excel_path = path
                    break
        
        self.excel_path = excel_path
        self.data = {}
        self.questions = []
        self.companies = []
        self.loaded = False
        
    def load_database(self):
        """
        Load the normative database from Excel file.
        Extracts questions, companies, and response data.
        """
        if not self.excel_path or not Path(self.excel_path).exists():
            raise FileNotFoundError(f"Normative database not found at {self.excel_path}")
        
        print(f"📊 Loading normative database from {self.excel_path}...")
        
        # Load workbook
        wb = openpyxl.load_workbook(self.excel_path, data_only=True)
        data_sheet = wb['data']
        
        # Extract company names from row 1 (columns B onwards)
        company_row = list(data_sheet.iter_rows(min_row=1, max_row=1, values_only=True))[0]
        self.companies = [str(c) for c in company_row[1:] if c]  # Skip column A
        
        print(f"  ✅ Found {len(self.companies)} companies")
        
        # Extract questions and data
        current_section = None
        
        for i, row in enumerate(data_sheet.iter_rows(min_row=2, values_only=True)):
            question_text = str(row[0]) if row[0] else ''
            
            if not question_text:
                continue
            
            # Section headers (all caps, no data in row[1])
            if question_text.isupper() and not row[1]:
                current_section = question_text
                continue
            
            # Skip AVERAGE rows - we'll calculate our own
            if question_text == 'AVERAGE':
                continue
            
            # Question or response option
            # Store the question and all company responses
            company_responses = []
            for j in range(1, len(self.companies) + 1):
                value = row[j] if j < len(row) else None
                
                # Convert to numeric if possible
                try:
                    company_responses.append(float(value) if value else None)
                except (ValueError, TypeError):
                    company_responses.append(None)
            
            # Calculate average across companies (ignoring None values)
            valid_responses = [r for r in company_responses if r is not None]
            avg_response = sum(valid_responses) / len(valid_responses) if valid_responses else None
            
            # Calculate standard deviation
            std_dev = np.std(valid_responses) if len(valid_responses) > 1 else 0
            
            # Store question data
            question_data = {
                'row_number': i + 2,
                'section': current_section,
                'question': question_text,
                'company_responses': company_responses,
                'valid_response_count': len(valid_responses),
                'average': avg_response,
                'std_dev': std_dev,
                'min': min(valid_responses) if valid_responses else None,
                'max': max(valid_responses) if valid_responses else None
            }
            
            self.questions.append(question_data)
            self.data[question_text] = question_data
        
        self.loaded = True
        print(f"  ✅ Loaded {len(self.questions)} questions with normative data")
        print(f"  📈 Database ready for benchmarking")
        
        wb.close()
        
    def compare_to_norm(self, question, client_value):
        """
        Compare a client's response to the normative average.
        
        Args:
            question: Question text (exact match or partial match)
            client_value: Client's response value (numeric)
            
        Returns:
            dict with comparison results
        """
        if not self.loaded:
            self.load_database()
        
        # Find matching question
        question_data = self._find_question(question)
        
        if not question_data:
            return {
                'success': False,
                'error': f'Question not found: {question[:100]}'
            }
        
        if question_data['average'] is None:
            return {
                'success': False,
                'error': 'No normative data available for this question'
            }
        
        # Calculate comparison metrics
        norm_avg = question_data['average']
        std_dev = question_data['std_dev']
        
        # Deviation from norm
        deviation = client_value - norm_avg
        deviation_percent = (deviation / norm_avg * 100) if norm_avg != 0 else 0
        
        # Standard deviations from mean
        z_score = (deviation / std_dev) if std_dev > 0 else 0
        
        # Percentile (approximate)
        percentile = self._calculate_percentile(client_value, question_data['company_responses'])
        
        # Interpretation
        interpretation = self._interpret_deviation(deviation_percent, z_score)
        
        return {
            'success': True,
            'question': question_data['question'],
            'section': question_data['section'],
            'client_value': client_value,
            'norm_average': round(norm_avg, 2),
            'deviation': round(deviation, 2),
            'deviation_percent': round(deviation_percent, 1),
            'z_score': round(z_score, 2),
            'percentile': round(percentile, 0),
            'std_dev': round(std_dev, 2),
            'interpretation': interpretation,
            'companies_count': question_data['valid_response_count'],
            'norm_range': {
                'min': round(question_data['min'], 2) if question_data['min'] else None,
                'max': round(question_data['max'], 2) if question_data['max'] else None
            }
        }
    
    def _find_question(self, search_text):
        """Find question by exact or partial match."""
        search_lower = search_text.lower()
        
        # Try exact match first
        if search_text in self.data:
            return self.data[search_text]
        
        # Try partial match
        for question_text, question_data in self.data.items():
            if search_lower in question_text.lower():
                return question_data
        
        return None
    
    def _calculate_percentile(self, value, responses):
        """Calculate approximate percentile of value among responses."""
        valid_responses = [r for r in responses if r is not None]
        
        if not valid_responses:
            return 50
        
        count_below = sum(1 for r in valid_responses if r < value)
        percentile = (count_below / len(valid_responses)) * 100
        
        return percentile
    
    def _interpret_deviation(self, deviation_percent, z_score):
        """Provide interpretation of deviation from norm."""
        abs_dev = abs(deviation_percent)
        abs_z = abs(z_score)
        
        if abs_z > 2:
            magnitude = "HIGHLY SIGNIFICANT"
        elif abs_z > 1:
            magnitude = "Significant"
        elif abs_dev > 10:
            magnitude = "Moderate"
        else:
            magnitude = "Within normal range"
        
        direction = "higher than" if deviation_percent > 0 else "lower than"
        
        return f"{magnitude} deviation - client value is {abs(deviation_percent):.1f}% {direction} industry norm"
    
    def batch_compare(self, client_responses):
        """
        Compare multiple client responses to norms at once.
        
        Args:
            client_responses: dict of {question: value, ...}
            
        Returns:
            list of comparison results
        """
        results = []
        
        for question, value in client_responses.items():
            comparison = self.compare_to_norm(question, value)
            if comparison['success']:
                results.append(comparison)
        
        return results
    
    def get_significant_deviations(self, client_responses, threshold_z=1.0):
        """
        Identify client responses that significantly deviate from norms.
        
        Args:
            client_responses: dict of {question: value, ...}
            threshold_z: Minimum z-score to consider significant (default 1.0)
            
        Returns:
            list of significant deviations sorted by magnitude
        """
        comparisons = self.batch_compare(client_responses)
        
        significant = [
            c for c in comparisons 
            if abs(c['z_score']) >= threshold_z
        ]
        
        # Sort by absolute z-score (most significant first)
        significant.sort(key=lambda x: abs(x['z_score']), reverse=True)
        
        return significant
    
    def generate_comparison_report(self, client_responses, client_name="Client"):
        """
        Generate a formatted comparison report.
        
        Args:
            client_responses: dict of {question: value, ...}
            client_name: Name of client for report
            
        Returns:
            Formatted text report
        """
        if not self.loaded:
            self.load_database()
        
        # Get all comparisons
        comparisons = self.batch_compare(client_responses)
        
        if not comparisons:
            return f"No valid comparisons found for {client_name}"
        
        # Generate report
        report = f"""
NORMATIVE BENCHMARK COMPARISON REPORT
Client: {client_name}
Benchmark Database: {len(self.companies)} Companies
Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

{'='*80}

EXECUTIVE SUMMARY
{'='*80}

Total Questions Compared: {len(comparisons)}
Benchmark Companies: {len(self.companies)} facilities across multiple industries

SIGNIFICANT FINDINGS
{'-'*80}

"""
        # Add significant deviations
        significant = [c for c in comparisons if abs(c['z_score']) >= 1.0]
        
        if significant:
            for i, comp in enumerate(significant[:10], 1):  # Top 10
                report += f"{i}. {comp['question'][:70]}...\n"
                report += f"   Client: {comp['client_value']}% | Norm: {comp['norm_average']}%\n"
                report += f"   {comp['interpretation']}\n"
                report += f"   Percentile: {comp['percentile']}th among {comp['companies_count']} companies\n\n"
        else:
            report += "No significant deviations found. Client responses are within normal ranges.\n\n"
        
        report += f"\n{'='*80}\n"
        report += "DETAILED COMPARISON DATA\n"
        report += f"{'='*80}\n\n"
        
        # Group by section
        sections = {}
        for comp in comparisons:
            section = comp['section'] or 'General'
            if section not in sections:
                sections[section] = []
            sections[section].append(comp)
        
        for section, items in sections.items():
            report += f"\n{section}\n"
            report += f"{'-'*80}\n"
            
            for item in items:
                report += f"\n{item['question']}\n"
                report += f"  Client Response: {item['client_value']}%\n"
                report += f"  Industry Norm:   {item['norm_average']}% (±{item['std_dev']}%)\n"
                report += f"  Deviation:       {item['deviation']:+.1f}% ({item['deviation_percent']:+.1f}%)\n"
                report += f"  Percentile:      {item['percentile']}th\n"
                report += f"  Interpretation:  {item['interpretation']}\n"
        
        report += f"\n\n{'='*80}\n"
        report += "End of Report\n"
        
        return report
    
    def search_questions(self, search_term, limit=10):
        """
        Search for questions containing a term.
        
        Args:
            search_term: Text to search for
            limit: Maximum results to return
            
        Returns:
            list of matching questions
        """
        if not self.loaded:
            self.load_database()
        
        search_lower = search_term.lower()
        
        matches = []
        for q in self.questions:
            if search_lower in q['question'].lower():
                matches.append({
                    'question': q['question'],
                    'section': q['section'],
                    'average': q['average'],
                    'companies_count': q['valid_response_count']
                })
            
            if len(matches) >= limit:
                break
        
        return matches
    
    def get_stats(self):
        """Get database statistics."""
        if not self.loaded:
            self.load_database()
        
        return {
            'companies_count': len(self.companies),
            'questions_count': len(self.questions),
            'sections': list(set(q['section'] for q in self.questions if q['section'])),
            'data_coverage': {
                'avg_responses_per_question': np.mean([q['valid_response_count'] for q in self.questions]),
                'min_responses': min(q['valid_response_count'] for q in self.questions),
                'max_responses': max(q['valid_response_count'] for q in self.questions)
            }
        }


# Singleton instance
_normative_db = None

def get_normative_database():
    """Get or create singleton normative database instance."""
    global _normative_db
    if _normative_db is None:
        _normative_db = NormativeDatabase()
        try:
            _normative_db.load_database()
        except Exception as e:
            print(f"⚠️ Failed to load normative database: {e}")
            _normative_db = None
    return _normative_db


# I did no harm and this file is not truncated
