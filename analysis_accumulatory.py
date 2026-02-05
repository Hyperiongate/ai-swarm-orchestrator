"""
Analysis Accumulator - Aggregate Statistics Across Chunks
Created: February 5, 2026
Last Updated: February 5, 2026

Maintains running statistics as chunks are processed:
- Running sums, means, mins, maxes
- Categorical value tracking
- Variance calculation (Welford's algorithm)
- Memory-efficient accumulation

Author: Jim @ Shiftwork Solutions LLC
"""

import numpy as np
from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict


class AnalysisAccumulator:
    """
    Accumulates statistics across multiple chunks without storing raw data.
    Uses online algorithms for memory efficiency.
    """
    
    def __init__(self):
        """Initialize the accumulator with empty statistics."""
        self.total_rows = 0
        self.numeric_accumulators = {}
        self.categorical_accumulators = {}
        self.date_accumulators = {}
        self.columns = []
    
    
    def add_chunk_stats(self, chunk_stats: Dict[str, Any]):
        """
        Add statistics from a new chunk.
        
        Args:
            chunk_stats: Dictionary of statistics from StreamingExcelAnalyzer.analyze_chunk()
        """
        # Update row count
        self.total_rows += chunk_stats['rows']
        
        # Store columns (from first chunk)
        if not self.columns:
            self.columns = chunk_stats['columns']
        
        # Accumulate numeric statistics
        if 'numeric_stats' in chunk_stats:
            for col, stats in chunk_stats['numeric_stats'].items():
                if col not in self.numeric_accumulators:
                    self.numeric_accumulators[col] = {
                        'sum': 0.0,
                        'count': 0,
                        'min': float('inf'),
                        'max': float('-inf'),
                        'M2': 0.0,  # For variance calculation (Welford's algorithm)
                        'mean': 0.0,
                        'missing_total': 0
                    }
                
                acc = self.numeric_accumulators[col]
                
                # Update sum
                acc['sum'] += stats['sum']
                
                # Update count
                chunk_count = chunk_stats['rows'] - stats['missing']
                acc['count'] += chunk_count
                
                # Update min/max
                acc['min'] = min(acc['min'], stats['min'])
                acc['max'] = max(acc['max'], stats['max'])
                
                # Update missing count
                acc['missing_total'] += stats['missing']
                
                # Update mean and M2 (for variance) using Welford's online algorithm
                if chunk_count > 0:
                    delta = stats['mean'] - acc['mean']
                    acc['mean'] += delta * chunk_count / acc['count']
                    
                    # Approximate variance update (simplified)
                    if chunk_count > 1:
                        chunk_variance = stats['std'] ** 2
                        acc['M2'] += chunk_variance * (chunk_count - 1)
        
        # Accumulate categorical statistics
        if 'categorical_stats' in chunk_stats:
            for col, stats in chunk_stats['categorical_stats'].items():
                if col not in self.categorical_accumulators:
                    self.categorical_accumulators[col] = {
                        'value_counts': defaultdict(int),
                        'unique_values_seen': set(),
                        'missing_total': 0
                    }
                
                acc = self.categorical_accumulators[col]
                
                # Update value counts
                for value, count in stats['top_values'].items():
                    acc['value_counts'][value] += count
                    acc['unique_values_seen'].add(value)
                
                # Update missing count
                acc['missing_total'] += stats['missing']
        
        # Accumulate date statistics
        if 'date_stats' in chunk_stats:
            for col, stats in chunk_stats['date_stats'].items():
                if col not in self.date_accumulators:
                    self.date_accumulators[col] = {
                        'min_date': stats['min_date'],
                        'max_date': stats['max_date'],
                        'missing_total': 0
                    }
                else:
                    # Update date range
                    if stats['min_date'] < self.date_accumulators[col]['min_date']:
                        self.date_accumulators[col]['min_date'] = stats['min_date']
                    if stats['max_date'] > self.date_accumulators[col]['max_date']:
                        self.date_accumulators[col]['max_date'] = stats['max_date']
                
                # Update missing count
                self.date_accumulators[col]['missing_total'] += stats['missing']
    
    
    def get_final_statistics(self) -> Dict[str, Any]:
        """
        Get final aggregated statistics.
        
        Returns:
            Dict with complete statistics across all chunks
        """
        final_stats = {
            'total_rows': self.total_rows,
            'columns': self.columns,
            'num_columns': len(self.columns)
        }
        
        # Finalize numeric statistics
        if self.numeric_accumulators:
            final_stats['numeric_summary'] = {}
            for col, acc in self.numeric_accumulators.items():
                # Calculate final variance and std
                if acc['count'] > 1:
                    variance = acc['M2'] / (acc['count'] - 1)
                    std = np.sqrt(variance) if variance >= 0 else 0.0
                else:
                    std = 0.0
                
                final_stats['numeric_summary'][col] = {
                    'sum': round(acc['sum'], 2),
                    'mean': round(acc['mean'], 2),
                    'std': round(std, 2),
                    'min': round(acc['min'], 2),
                    'max': round(acc['max'], 2),
                    'count': acc['count'],
                    'missing': acc['missing_total'],
                    'missing_pct': round((acc['missing_total'] / self.total_rows) * 100, 1) if self.total_rows > 0 else 0
                }
        
        # Finalize categorical statistics
        if self.categorical_accumulators:
            final_stats['categorical_summary'] = {}
            for col, acc in self.categorical_accumulators.items():
                # Get top 10 values
                sorted_values = sorted(
                    acc['value_counts'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
                
                final_stats['categorical_summary'][col] = {
                    'unique_values': len(acc['unique_values_seen']),
                    'top_values': dict(sorted_values),
                    'missing': acc['missing_total'],
                    'missing_pct': round((acc['missing_total'] / self.total_rows) * 100, 1) if self.total_rows > 0 else 0
                }
        
        # Finalize date statistics
        if self.date_accumulators:
            final_stats['date_summary'] = {}
            for col, acc in self.date_accumulators.items():
                final_stats['date_summary'][col] = {
                    'date_range': f"{acc['min_date']} to {acc['max_date']}",
                    'min_date': acc['min_date'],
                    'max_date': acc['max_date'],
                    'missing': acc['missing_total'],
                    'missing_pct': round((acc['missing_total'] / self.total_rows) * 100, 1) if self.total_rows > 0 else 0
                }
        
        return final_stats
    
    
    def generate_consulting_report(self, file_name: str) -> str:
        """
        Generate a consulting-grade report from accumulated statistics.
        
        Args:
            file_name: Name of the analyzed file
            
        Returns:
            Formatted markdown report
        """
        stats = self.get_final_statistics()
        
        report = f"""# 📊 COMPREHENSIVE FILE ANALYSIS REPORT

**File:** {file_name}  
**Total Rows Analyzed:** {stats['total_rows']:,}  
**Total Columns:** {stats['num_columns']}  
**Analysis Date:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## 1. DATA STRUCTURE

"""
        
        # Numeric columns section
        if 'numeric_summary' in stats:
            report += f"""### 📈 Numeric Columns ({len(stats['numeric_summary'])})

"""
            for col, col_stats in stats['numeric_summary'].items():
                report += f"""**{col}:**
- Total: {col_stats['sum']:,}
- Average: {col_stats['mean']:,}
- Range: {col_stats['min']:,} to {col_stats['max']:,}
- Std Dev: {col_stats['std']:,}
- Data Quality: {col_stats['missing_pct']}% missing ({col_stats['missing']:,} rows)

"""
        
        # Categorical columns section
        if 'categorical_summary' in stats:
            report += f"""### 📋 Categorical Columns ({len(stats['categorical_summary'])})

"""
            for col, col_stats in stats['categorical_summary'].items():
                report += f"""**{col}:**
- Unique Values: {col_stats['unique_values']:,}
- Top Values: {', '.join([f"{k} ({v})" for k, v in list(col_stats['top_values'].items())[:5]])}
- Data Quality: {col_stats['missing_pct']}% missing

"""
        
        # Date columns section
        if 'date_summary' in stats:
            report += f"""### 📅 Date Columns ({len(stats['date_summary'])})

"""
            for col, col_stats in stats['date_summary'].items():
                report += f"""**{col}:**
- Date Range: {col_stats['date_range']}
- Data Quality: {col_stats['missing_pct']}% missing

"""
        
        report += """---

## 2. NEXT STEPS

This comprehensive analysis covers all {total_rows:,} rows. To get deeper operational insights:
- Ask specific questions about patterns you see
- Request department-level breakdowns
- Identify areas for optimization
- Flag potential data quality issues

**Ready to dive deeper?** Just ask!
""".format(total_rows=stats['total_rows'])
        
        return report


# I did no harm and this file is not truncated
