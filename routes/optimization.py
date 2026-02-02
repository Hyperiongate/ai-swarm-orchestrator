"""
SELF-OPTIMIZATION API ROUTES - Phase 3
Created: February 2, 2026
Last Updated: February 2, 2026

API endpoints for self-optimization features.
Provides A/B testing, threshold tuning, and cost optimization.

Endpoints:
- GET  /api/optimization/status - Get optimization system status
- POST /api/optimization/run-cycle - Run optimization cycle
- GET  /api/optimization/experiments - List all experiments
- POST /api/optimization/experiments/create - Create new experiment
- GET  /api/optimization/experiments/:id - Get experiment details
- POST /api/optimization/experiments/:id/finalize - Finalize experiment
- GET  /api/optimization/adjustments - Get pending adjustments
- POST /api/optimization/adjustments/:id/approve - Approve adjustment
- POST /api/optimization/adjustments/:id/reject - Reject adjustment
- GET  /api/optimization/cost-analysis - Analyze cost optimizations
- GET  /api/optimization/report - Comprehensive optimization report

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

from flask import Blueprint, jsonify, request
from self_optimization_engine import get_optimization_engine
import sqlite3
from datetime import datetime


# Create blueprint
optimization_bp = Blueprint('optimization', __name__)


@optimization_bp.route('/api/optimization/status', methods=['GET'])
def get_status():
    """
    Get current status of self-optimization system.
    
    Returns metrics about experiments and optimizations.
    """
    try:
        engine = get_optimization_engine()
        status = engine.get_optimization_status()
        
        return jsonify({
            'success': True,
            'enabled': True,
            'status': status['status'],
            'metrics': {
                'active_experiments': status['active_experiments'],
                'completed_experiments': status['completed_experiments'],
                'pending_adjustments': status['pending_adjustments'],
                'applied_adjustments': status['applied_adjustments']
            },
            'recent_optimizations': status['recent_optimizations'],
            'needs_action': status['pending_adjustments'] > 0
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/run-cycle', methods=['POST'])
def run_optimization_cycle():
    """
    Run complete optimization cycle.
    
    Query params:
    - days_back: Number of days to analyze (default 30)
    
    Analyzes performance, suggests optimizations, and checks experiments.
    """
    try:
        days_back = request.args.get('days_back', 30, type=int)
        
        engine = get_optimization_engine()
        results = engine.run_optimization_cycle(days_back=days_back)
        
        summary = {
            'threshold_adjustments': len(results['threshold_adjustments']),
            'cost_optimizations': len(results['cost_optimizations']),
            'experiments_analyzed': len(results['experiments_analyzed'])
        }
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': summary,
            'message': f'Optimization cycle complete - found {sum(summary.values())} opportunities'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/experiments', methods=['GET'])
def list_experiments():
    """
    List all optimization experiments.
    
    Query params:
    - status: Filter by status (running, completed, all) - default: all
    - limit: Max results (default 20)
    """
    try:
        status_filter = request.args.get('status', 'all')
        limit = request.args.get('limit', 20, type=int)
        
        engine = get_optimization_engine()
        db = sqlite3.connect(engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        if status_filter == 'all':
            cursor.execute('''
                SELECT * FROM optimization_experiments
                ORDER BY started_at DESC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT * FROM optimization_experiments
                WHERE status = ?
                ORDER BY started_at DESC
                LIMIT ?
            ''', (status_filter, limit))
        
        experiments = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(experiments),
            'experiments': experiments
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/experiments/create', methods=['POST'])
def create_experiment():
    """
    Create a new A/B experiment.
    
    Body:
    {
        "experiment_name": "Test Consensus Threshold",
        "variable": "consensus_threshold",
        "control_value": "0.85",
        "test_value": "0.80"
    }
    
    Returns experiment_id for tracking.
    """
    try:
        data = request.get_json() or {}
        
        experiment_name = data.get('experiment_name')
        variable = data.get('variable')
        control_value = data.get('control_value')
        test_value = data.get('test_value')
        
        if not all([experiment_name, variable, control_value, test_value]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: experiment_name, variable, control_value, test_value'
            }), 400
        
        engine = get_optimization_engine()
        experiment_id = engine.experiment_manager.create_experiment(
            experiment_name, variable, control_value, test_value
        )
        
        return jsonify({
            'success': True,
            'experiment_id': experiment_id,
            'message': f'Experiment created: {experiment_name}',
            'details': {
                'variable': variable,
                'control': control_value,
                'test': test_value,
                'traffic_split': '20% test / 80% control'
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/experiments/<int:experiment_id>', methods=['GET'])
def get_experiment_details(experiment_id):
    """
    Get detailed information about an experiment.
    
    Includes current metrics and analysis if ready.
    """
    try:
        engine = get_optimization_engine()
        db = sqlite3.connect(engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT * FROM optimization_experiments
            WHERE id = ?
        ''', (experiment_id,))
        
        experiment = cursor.fetchone()
        db.close()
        
        if not experiment:
            return jsonify({
                'success': False,
                'error': 'Experiment not found'
            }), 404
        
        exp_dict = dict(experiment)
        
        # Try to analyze if enough data
        if exp_dict['control_sample_size'] >= 20 and exp_dict['test_sample_size'] >= 20:
            analysis = engine.experiment_manager.analyze_experiment(experiment_id)
            exp_dict['analysis'] = analysis
        else:
            exp_dict['analysis'] = {
                'status': 'collecting_data',
                'control_samples': exp_dict['control_sample_size'],
                'test_samples': exp_dict['test_sample_size'],
                'needed': 20
            }
        
        return jsonify({
            'success': True,
            'experiment': exp_dict
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/experiments/<int:experiment_id>/finalize', methods=['POST'])
def finalize_experiment(experiment_id):
    """
    Finalize an experiment and determine winner.
    
    Requires at least 20 samples in each group.
    """
    try:
        engine = get_optimization_engine()
        
        # Analyze experiment
        analysis = engine.experiment_manager.analyze_experiment(experiment_id)
        
        if analysis['status'] != 'complete':
            return jsonify({
                'success': False,
                'error': f"Experiment not ready: {analysis['status']}",
                'details': analysis
            }), 400
        
        # Finalize
        engine.experiment_manager.finalize_experiment(experiment_id, analysis)
        
        return jsonify({
            'success': True,
            'experiment_id': experiment_id,
            'winner': analysis['winner'],
            'recommendation': analysis['recommendation'],
            'analysis': analysis
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/adjustments', methods=['GET'])
def get_adjustments():
    """
    Get all pending adjustments awaiting approval.
    
    Query params:
    - include_applied: Include already-applied adjustments (default false)
    """
    try:
        include_applied = request.args.get('include_applied', 'false').lower() == 'true'
        
        engine = get_optimization_engine()
        db = sqlite3.connect(engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        if include_applied:
            cursor.execute('''
                SELECT * FROM auto_adjustments_log
                WHERE reverted = 0
                ORDER BY created_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT * FROM auto_adjustments_log
                WHERE approved = 0 AND reverted = 0
                ORDER BY created_at DESC
            ''')
        
        adjustments = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(adjustments),
            'adjustments': adjustments
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/adjustments/<int:adjustment_id>/approve', methods=['POST'])
def approve_adjustment(adjustment_id):
    """
    Approve and apply a suggested optimization.
    
    Body (optional):
    {
        "approved_by": "jim",
        "apply_immediately": true
    }
    """
    try:
        data = request.get_json() or {}
        approved_by = data.get('approved_by', 'jim')
        apply_immediately = data.get('apply_immediately', True)
        
        engine = get_optimization_engine()
        db = sqlite3.connect(engine.db_path)
        cursor = db.cursor()
        
        # Check if adjustment exists
        cursor.execute('''
            SELECT * FROM auto_adjustments_log
            WHERE id = ? AND approved = 0
        ''', (adjustment_id,))
        
        adjustment = cursor.fetchone()
        if not adjustment:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Adjustment not found or already approved'
            }), 404
        
        # Approve the adjustment
        cursor.execute('''
            UPDATE auto_adjustments_log
            SET approved = 1,
                approved_by = ?,
                approved_at = ?,
                applied = ?,
                applied_at = ?
            WHERE id = ?
        ''', (
            approved_by,
            datetime.now(),
            1 if apply_immediately else 0,
            datetime.now() if apply_immediately else None,
            adjustment_id
        ))
        
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Optimization approved' + (' and applied' if apply_immediately else ''),
            'adjustment_id': adjustment_id,
            'applied': apply_immediately,
            'note': 'Configuration changes require orchestrator restart to take effect' if apply_immediately else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/adjustments/<int:adjustment_id>/reject', methods=['POST'])
def reject_adjustment(adjustment_id):
    """
    Reject a suggested optimization.
    
    Body (optional):
    {
        "reason": "Not appropriate for current workload"
    }
    """
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'User rejected')
        
        engine = get_optimization_engine()
        db = sqlite3.connect(engine.db_path)
        cursor = db.cursor()
        
        # Mark as reverted (used for rejection)
        cursor.execute('''
            UPDATE auto_adjustments_log
            SET reverted = 1,
                reverted_at = ?
            WHERE id = ? AND approved = 0
        ''', (datetime.now(), adjustment_id))
        
        if cursor.rowcount == 0:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Adjustment not found or already processed'
            }), 404
        
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Optimization rejected',
            'adjustment_id': adjustment_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/cost-analysis', methods=['GET'])
def get_cost_analysis():
    """
    Get cost optimization analysis.
    
    Query params:
    - days_back: Number of days to analyze (default 30)
    
    Returns AI models ranked by cost/performance efficiency.
    """
    try:
        days_back = request.args.get('days_back', 30, type=int)
        
        engine = get_optimization_engine()
        configs = engine.cost_optimizer.analyze_cost_performance(days_back)
        
        # Get optimization suggestion
        optimization = engine.cost_optimizer.suggest_cost_optimization(configs)
        
        return jsonify({
            'success': True,
            'configurations': configs,
            'suggested_optimization': optimization,
            'message': f'Analyzed {len(configs)} AI configurations over last {days_back} days'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/api/optimization/report', methods=['GET'])
def get_comprehensive_report():
    """
    Get comprehensive self-optimization report.
    
    Includes all experiments, adjustments, and optimizations.
    """
    try:
        engine = get_optimization_engine()
        status = engine.get_optimization_status()
        
        # Get cost analysis
        try:
            configs = engine.cost_optimizer.analyze_cost_performance(30)
            cost_optimization = engine.cost_optimizer.suggest_cost_optimization(configs)
        except:
            configs = []
            cost_optimization = None
        
        insights = []
        
        if status['active_experiments'] > 0:
            insights.append({
                'type': 'experiments_running',
                'message': f"{status['active_experiments']} optimization experiments in progress",
                'action': 'Check experiment progress',
                'endpoint': 'GET /api/optimization/experiments'
            })
        
        if status['pending_adjustments'] > 0:
            insights.append({
                'type': 'pending_adjustments',
                'message': f"{status['pending_adjustments']} optimization suggestions awaiting approval",
                'action': 'Review and approve',
                'endpoint': 'GET /api/optimization/adjustments'
            })
        
        if cost_optimization:
            insights.append({
                'type': 'cost_savings',
                'message': f"Potential {cost_optimization['cost_savings_pct']:.0f}% cost savings identified",
                'action': 'Review cost optimization',
                'endpoint': 'GET /api/optimization/cost-analysis'
            })
        
        if status['applied_adjustments'] > 0:
            insights.append({
                'type': 'optimizations_active',
                'message': f"{status['applied_adjustments']} optimizations active and improving performance",
                'action': None,
                'endpoint': None
            })
        
        return jsonify({
            'success': True,
            'status': status,
            'cost_analysis': {
                'configurations': configs,
                'optimization': cost_optimization
            },
            'insights': insights,
            'recommendations': _generate_recommendations(status, cost_optimization)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_recommendations(status: dict, cost_opt: dict) -> list:
    """Generate actionable recommendations"""
    recommendations = []
    
    if status['status'] == 'needs_more_data':
        recommendations.append({
            'priority': 'info',
            'category': 'data_collection',
            'title': 'Building Optimization Foundation',
            'description': 'Self-optimization needs 30+ tasks before it can suggest improvements. Keep using the system!',
            'action': None,
            'endpoint': None
        })
    
    if status['pending_adjustments'] > 0:
        recommendations.append({
            'priority': 'high',
            'category': 'action_needed',
            'title': 'Review Optimization Suggestions',
            'description': f"{status['pending_adjustments']} optimization opportunities identified. Review and approve to improve performance.",
            'action': 'Review adjustments',
            'endpoint': 'GET /api/optimization/adjustments'
        })
    
    if cost_opt:
        recommendations.append({
            'priority': 'medium',
            'category': 'cost_savings',
            'title': 'Cost Optimization Available',
            'description': cost_opt['recommendation'],
            'action': 'View cost analysis',
            'endpoint': 'GET /api/optimization/cost-analysis'
        })
    
    if status['completed_experiments'] > 3:
        recommendations.append({
            'priority': 'low',
            'category': 'success',
            'title': 'Self-Optimization Active',
            'description': f"{status['completed_experiments']} experiments completed. System is learning and optimizing!",
            'action': None,
            'endpoint': None
        })
    
    return recommendations


# I did no harm and this file is not truncated
