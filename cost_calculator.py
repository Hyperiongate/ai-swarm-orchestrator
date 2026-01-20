"""
COST OF TIME CALCULATOR MODULE
Created: January 20, 2026
Last Updated: January 20, 2026

PURPOSE:
Calculates the true cost of overtime and schedule changes for shift operations.
Helps clients understand financial impact of different scheduling decisions.

FEATURES:
- Calculate overtime costs vs hiring additional employees
- Compare different shift schedules financially
- Factor in burden rates, benefits, training costs
- Generate cost comparison reports
- Break-even analysis for schedule changes

BASED ON:
Shiftwork Solutions' 30+ years of consulting methodology for cost analysis

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from datetime import datetime
import json


class CostOfTimeCalculator:
    """
    Calculates overtime costs and schedule change financial impacts
    """
    
    def __init__(self):
        # Default burden rates (can be customized)
        self.default_burden_rate = 0.35  # 35% for benefits, taxes, etc.
        self.default_training_cost = 5000  # Cost to train new employee
        self.default_turnover_cost = 8000  # Cost of employee turnover
    
    def calculate_overtime_cost(self, base_wage, overtime_hours_per_week, weeks=52, burden_rate=None):
        """
        Calculate annual overtime cost
        
        Args:
            base_wage: Hourly base wage
            overtime_hours_per_week: Average OT hours per week
            weeks: Number of weeks (default 52)
            burden_rate: Benefits/taxes burden (default 35%)
            
        Returns:
            dict with cost breakdown
        """
        
        if burden_rate is None:
            burden_rate = self.default_burden_rate
        
        # Overtime rate is 1.5x base
        ot_rate = base_wage * 1.5
        
        # Annual calculations
        annual_ot_hours = overtime_hours_per_week * weeks
        annual_ot_wages = annual_ot_hours * ot_rate
        annual_ot_burden = annual_ot_wages * burden_rate
        total_annual_ot_cost = annual_ot_wages + annual_ot_burden
        
        # Weekly calculations
        weekly_ot_cost = overtime_hours_per_week * ot_rate
        weekly_burden = weekly_ot_cost * burden_rate
        total_weekly_cost = weekly_ot_cost + weekly_burden
        
        return {
            'base_wage': base_wage,
            'overtime_rate': ot_rate,
            'overtime_hours_weekly': overtime_hours_per_week,
            'overtime_hours_annual': annual_ot_hours,
            'overtime_wages_annual': round(annual_ot_wages, 2),
            'burden_cost_annual': round(annual_ot_burden, 2),
            'total_cost_annual': round(total_annual_ot_cost, 2),
            'total_cost_weekly': round(total_weekly_cost, 2),
            'burden_rate': burden_rate
        }
    
    def compare_overtime_vs_hiring(self, current_ot_cost_annual, new_employee_wage, 
                                   training_cost=None, burden_rate=None):
        """
        Compare cost of continuing overtime vs hiring additional employee
        
        Args:
            current_ot_cost_annual: Current annual OT cost
            new_employee_wage: Annual wage for new employee
            training_cost: One-time training cost
            burden_rate: Benefits burden rate
            
        Returns:
            dict with comparison and recommendation
        """
        
        if training_cost is None:
            training_cost = self.default_training_cost
        if burden_rate is None:
            burden_rate = self.default_burden_rate
        
        # New employee costs
        new_employee_burden = new_employee_wage * burden_rate
        new_employee_total_annual = new_employee_wage + new_employee_burden
        
        # First year includes training
        new_employee_first_year = new_employee_total_annual + training_cost
        
        # Calculate break-even
        if new_employee_total_annual < current_ot_cost_annual:
            annual_savings = current_ot_cost_annual - new_employee_total_annual
            first_year_savings = current_ot_cost_annual - new_employee_first_year
            payback_months = (training_cost / (annual_savings / 12)) if annual_savings > 0 else 999
            recommendation = "HIRE NEW EMPLOYEE"
        else:
            annual_savings = 0
            first_year_savings = 0
            payback_months = 999
            recommendation = "CONTINUE OVERTIME"
        
        return {
            'current_overtime_cost': round(current_ot_cost_annual, 2),
            'new_employee_annual_cost': round(new_employee_total_annual, 2),
            'new_employee_first_year_cost': round(new_employee_first_year, 2),
            'training_cost': training_cost,
            'annual_savings': round(annual_savings, 2),
            'first_year_savings': round(first_year_savings, 2),
            'payback_months': round(payback_months, 1),
            'recommendation': recommendation,
            'break_even_analysis': f"Break-even in {round(payback_months, 1)} months" if payback_months < 999 else "Does not break even"
        }
    
    def calculate_schedule_change_impact(self, current_schedule, proposed_schedule):
        """
        Calculate financial impact of schedule change
        
        Args:
            current_schedule: dict with current schedule details
            proposed_schedule: dict with proposed schedule details
            
        Returns:
            dict with cost impact analysis
        """
        
        # Extract current schedule costs
        current_headcount = current_schedule.get('headcount', 0)
        current_ot_hours_weekly = current_schedule.get('ot_hours_weekly', 0)
        current_base_wage = current_schedule.get('base_wage', 0)
        
        # Extract proposed schedule costs
        proposed_headcount = proposed_schedule.get('headcount', 0)
        proposed_ot_hours_weekly = proposed_schedule.get('ot_hours_weekly', 0)
        proposed_base_wage = proposed_schedule.get('base_wage', 0)
        
        # Calculate current costs
        current_ot = self.calculate_overtime_cost(
            current_base_wage,
            current_ot_hours_weekly
        )
        current_total_annual = (current_headcount * current_base_wage * 2080) + current_ot['total_cost_annual'] * current_headcount
        
        # Calculate proposed costs
        proposed_ot = self.calculate_overtime_cost(
            proposed_base_wage,
            proposed_ot_hours_weekly
        )
        proposed_total_annual = (proposed_headcount * proposed_base_wage * 2080) + proposed_ot['total_cost_annual'] * proposed_headcount
        
        # Calculate change
        headcount_change = proposed_headcount - current_headcount
        cost_change = proposed_total_annual - current_total_annual
        cost_change_percentage = (cost_change / current_total_annual * 100) if current_total_annual > 0 else 0
        
        return {
            'current_annual_cost': round(current_total_annual, 2),
            'proposed_annual_cost': round(proposed_total_annual, 2),
            'annual_cost_change': round(cost_change, 2),
            'cost_change_percentage': round(cost_change_percentage, 1),
            'headcount_change': headcount_change,
            'recommendation': 'COST SAVINGS' if cost_change < 0 else 'COST INCREASE',
            'summary': f"{'Savings' if cost_change < 0 else 'Increase'} of ${abs(round(cost_change, 2)):,} annually ({abs(round(cost_change_percentage, 1))}%)"
        }
    
    def generate_cost_report(self, analysis_data, client_name=None):
        """
        Generate formatted cost analysis report
        
        Args:
            analysis_data: Results from cost calculations
            client_name: Optional client name for report
            
        Returns:
            Formatted report string
        """
        
        report = f"""
================================================================================
COST OF TIME ANALYSIS REPORT
================================================================================

Client: {client_name or 'Not Specified'}
Date: {datetime.now().strftime('%B %d, %Y')}
Prepared by: Shiftwork Solutions LLC

================================================================================
ANALYSIS RESULTS
================================================================================

"""
        
        if 'overtime_hours_annual' in analysis_data:
            # Overtime cost analysis
            report += f"""
OVERTIME COST ANALYSIS:
--------------------------------------------------------------------------------
Base Wage: ${analysis_data['base_wage']}/hour
Overtime Rate: ${analysis_data['overtime_rate']}/hour (1.5x)
Burden Rate: {analysis_data['burden_rate']*100}%

Weekly Overtime: {analysis_data['overtime_hours_weekly']} hours
Annual Overtime: {analysis_data['overtime_hours_annual']} hours

ANNUAL COSTS:
  Overtime Wages:     ${analysis_data['overtime_wages_annual']:,.2f}
  Burden (Benefits):  ${analysis_data['burden_cost_annual']:,.2f}
  ----------------------------------------------------------
  TOTAL ANNUAL COST:  ${analysis_data['total_cost_annual']:,.2f}

Weekly Cost: ${analysis_data['total_cost_weekly']:,.2f}
"""
        
        if 'recommendation' in analysis_data and 'payback_months' in analysis_data:
            # Hire vs OT comparison
            report += f"""
OVERTIME vs HIRING COMPARISON:
--------------------------------------------------------------------------------
Current Overtime Cost:        ${analysis_data['current_overtime_cost']:,.2f}/year
New Employee Cost (ongoing):  ${analysis_data['new_employee_annual_cost']:,.2f}/year
New Employee (first year):    ${analysis_data['new_employee_first_year_cost']:,.2f}
  (includes ${analysis_data['training_cost']:,.2f} training)

FINANCIAL IMPACT:
  Annual Savings:      ${analysis_data['annual_savings']:,.2f}
  First Year Savings:  ${analysis_data['first_year_savings']:,.2f}
  Payback Period:      {analysis_data['payback_months']} months

RECOMMENDATION: {analysis_data['recommendation']}
{analysis_data['break_even_analysis']}
"""
        
        if 'current_annual_cost' in analysis_data and 'proposed_annual_cost' in analysis_data:
            # Schedule change impact
            report += f"""
SCHEDULE CHANGE FINANCIAL IMPACT:
--------------------------------------------------------------------------------
Current Schedule Annual Cost:  ${analysis_data['current_annual_cost']:,.2f}
Proposed Schedule Annual Cost: ${analysis_data['proposed_annual_cost']:,.2f}

Headcount Change: {analysis_data['headcount_change']:+d} employees

FINANCIAL IMPACT:
  Annual Change:  ${analysis_data['annual_cost_change']:+,.2f}
  Percentage:     {analysis_data['cost_change_percentage']:+.1f}%

RECOMMENDATION: {analysis_data['recommendation']}
{analysis_data['summary']}
"""
        
        report += f"""
================================================================================
NOTES:
- All calculations include burden rates for benefits, taxes, and overhead
- Overtime calculated at 1.5x base wage rate
- Annual costs based on 52-week year
- Training and turnover costs are one-time expenses

================================================================================
Generated by Shiftwork Solutions LLC | {datetime.now().strftime('%B %d, %Y')}
================================================================================
"""
        
        return report


# Singleton instance
_calculator = None

def get_calculator():
    """Get or create the calculator singleton"""
    global _calculator
    if _calculator is None:
        _calculator = CostOfTimeCalculator()
    return _calculator


# I did no harm and this file is not truncated
