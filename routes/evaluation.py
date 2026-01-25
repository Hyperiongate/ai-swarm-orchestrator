"""
Evaluation Routes
Created: January 25, 2026
Last Updated: January 25, 2026

API endpoints for the Swarm Self-Evaluation System.

ENDPOINTS:
- GET  /api/evaluation/status     - Get evaluation system status
- GET  /api/evaluation/latest     - Get most recent evaluation report
- POST /api/evaluation/run        - Trigger a new evaluation
- GET  /api/evaluation/history    - Get evaluation history
- GET  /api/evaluation/<id>       - Get specific evaluation by ID
- GET  /api/evaluation/performance - Get raw performance metrics
- GET  /api/evaluation/market     - Get latest market scan

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import json

evaluation_bp = Blueprint('evaluation', __name__)


# ============================================================================
# IMPORT EVALUATION ENGINE
# ============================================================================

EVALUATION_AVAILABLE = False
evaluator = None

try:
    from swarm_self_evaluation import get_swarm_evaluator
    evaluator = get_swarm_evaluator()
    EVALUATION_AVAILABLE = True
    print("✅ Swarm Self-Evaluation Engine loaded")
except ImportError as e:
    print(f"ℹ️  Swarm Self-Evaluation not available: {e}")
except Exception as e:
    print(f"⚠️  Swarm Self-Evaluation error: {e}")


# ============================================================================
# STATUS ENDPOINT
# ============================================================================

@evaluation_bp.route('/api/evaluation/status', methods=['GET'])
def get_evaluation_status():
    """
    Get the status of the evaluation system.
    
    Returns:
    - available: Whether the evaluation system is operational
    - last_evaluation: Date of most recent evaluation
    - next_scheduled: When next evaluation should run (suggested)
    - evaluation_count: Total evaluations in database
    """
    try:
        if not EVALUATION_AVAILABLE or not evaluator:
            return jsonify({
                'success': True,
                'available': False,
                'message': 'Swarm Self-Evaluation system not installed'
            })
        
        # Get latest evaluation
        latest = evaluator.get_latest_evaluation()
        
        # Get evaluation count
        from database import get_db
        db = get_db()
        try:
            count = db.execute('SELECT COUNT(*) FROM swarm_evaluations').fetchone()[0]
        except:
            count = 0
        finally:
            db.close()
        
        # Calculate suggested next evaluation
        next_suggested = None
        if latest and latest.get('evaluation_date'):
            from datetime import timedelta
            last_date = datetime.strptime(latest['evaluation_date'], '%Y-%m-%d %H:%M:%S')
            next_date = last_date + timedelta(days=7)
            next_suggested = next_date.strftime('%Y-%m-%d')
        else:
            next_suggested = datetime.now().strftime('%Y-%m-%d')
        
        return jsonify({
            'success': True,
            'available': True,
            'last_evaluation': {
                'date': latest.get('evaluation_date') if latest else None,
                'health_score': latest.get('health_score') if latest else None,
                'trend': latest.get('trend') if latest else None
            } if latest else None,
            'next_suggested': next_suggested,
            'total_evaluations': count,
            'evaluation_engine': 'SwarmSelfEvaluator v1.0'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# RUN EVALUATION ENDPOINT
# ============================================================================

@evaluation_bp.route('/api/evaluation/run', methods=['POST'])
def run_evaluation():
    """
    Trigger a new swarm self-evaluation.
    
    Request Body (optional):
    {
        "days": 7,           // Number of days to analyze (default: 7)
        "save": true         // Whether to save to database (default: true)
    }
    
    Returns:
    - Complete evaluation report with health score, gaps, and recommendations
    """
    try:
        if not EVALUATION_AVAILABLE or not evaluator:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        # Parse request parameters
        data = request.json or {}
        days = data.get('days', 7)
        save_to_db = data.get('save', True)
        
        # Validate days parameter
        if not isinstance(days, int) or days < 1 or days > 90:
            return jsonify({
                'success': False,
                'error': 'Days must be an integer between 1 and 90'
            }), 400
        
        # Run the evaluation
        report = evaluator.run_evaluation(days=days, save_to_db=save_to_db)
        
        return jsonify({
            'success': True,
            'evaluation': {
                'generated_at': report.get('generated_at'),
                'week_of': report.get('week_of'),
                'executive_summary': report.get('executive_summary'),
                'health_score': report.get('health_score'),
                'performance_summary': report.get('performance_summary'),
                'market_developments': report.get('market_developments'),
                'gaps_identified': report.get('gaps_identified'),
                'high_priority_gaps': report.get('high_priority_gaps'),
                'recommendations': report.get('recommendations'),
                'next_week_focus': report.get('next_week_focus')
            },
            'saved': save_to_db
        })
    except Exception as e:
        import traceback
        print(f"Evaluation run error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET LATEST EVALUATION
# ============================================================================

@evaluation_bp.route('/api/evaluation/latest', methods=['GET'])
def get_latest_evaluation():
    """
    Get the most recent evaluation report.
    
    Query Parameters:
    - full: If 'true', include complete raw data (default: false)
    
    Returns:
    - Latest evaluation summary or full report
    """
    try:
        if not EVALUATION_AVAILABLE or not evaluator:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        include_full = request.args.get('full', 'false').lower() == 'true'
        
        latest = evaluator.get_latest_evaluation()
        
        if not latest:
            return jsonify({
                'success': True,
                'evaluation': None,
                'message': 'No evaluations found. Run an evaluation first.'
            })
        
        response = {
            'success': True,
            'evaluation': {
                'id': latest.get('id'),
                'evaluation_date': latest.get('evaluation_date'),
                'health_score': latest.get('health_score'),
                'trend': latest.get('trend'),
                'tasks_processed': latest.get('tasks_processed'),
                'success_rate': latest.get('success_rate'),
                'executive_summary': latest.get('executive_summary'),
                'gaps_count': latest.get('gaps_count'),
                'high_priority_gaps_count': latest.get('high_priority_gaps_count'),
                'recommendations_count': latest.get('recommendations_count')
            }
        }
        
        if include_full and latest.get('full_report'):
            response['full_report'] = latest.get('full_report')
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET EVALUATION HISTORY
# ============================================================================

@evaluation_bp.route('/api/evaluation/history', methods=['GET'])
def get_evaluation_history():
    """
    Get history of past evaluations.
    
    Query Parameters:
    - limit: Maximum number of evaluations to return (default: 10, max: 50)
    
    Returns:
    - List of evaluation summaries (newest first)
    """
    try:
        if not EVALUATION_AVAILABLE or not evaluator:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(limit, 1), 50)  # Clamp between 1 and 50
        
        history = evaluator.get_evaluation_history(limit=limit)
        
        return jsonify({
            'success': True,
            'evaluations': history,
            'count': len(history)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET SPECIFIC EVALUATION BY ID
# ============================================================================

@evaluation_bp.route('/api/evaluation/<int:evaluation_id>', methods=['GET'])
def get_evaluation_by_id(evaluation_id):
    """
    Get a specific evaluation by its ID.
    
    Returns:
    - Full evaluation report for the specified ID
    """
    try:
        if not EVALUATION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        from database import get_db
        db = get_db()
        
        try:
            row = db.execute('''
                SELECT * FROM swarm_evaluations WHERE id = ?
            ''', (evaluation_id,)).fetchone()
            
            if not row:
                return jsonify({
                    'success': False,
                    'error': f'Evaluation {evaluation_id} not found'
                }), 404
            
            evaluation = {
                'id': row['id'],
                'evaluation_date': row['evaluation_date'],
                'period_days': row['period_days'],
                'health_score': row['health_score'],
                'trend': row['trend'],
                'tasks_processed': row['tasks_processed'],
                'success_rate': row['success_rate'],
                'executive_summary': row['executive_summary'],
                'gaps_count': row['gaps_count'],
                'high_priority_gaps_count': row['high_priority_gaps_count'],
                'recommendations_count': row['recommendations_count'],
                'full_report': json.loads(row['full_report_json']) if row['full_report_json'] else None
            }
            
            return jsonify({
                'success': True,
                'evaluation': evaluation
            })
        finally:
            db.close()
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET RAW PERFORMANCE METRICS
# ============================================================================

@evaluation_bp.route('/api/evaluation/performance', methods=['GET'])
def get_performance_metrics():
    """
    Get raw performance metrics without running a full evaluation.
    
    Query Parameters:
    - days: Number of days to analyze (default: 7)
    
    Returns:
    - Raw performance metrics from the database
    """
    try:
        if not EVALUATION_AVAILABLE or not evaluator:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        days = request.args.get('days', 7, type=int)
        days = min(max(days, 1), 90)  # Clamp between 1 and 90
        
        # Use the performance collector
        from swarm_self_evaluation import PerformanceCollector
        collector = PerformanceCollector()
        metrics = collector.collect_weekly_metrics(days=days)
        
        return jsonify({
            'success': True,
            'period_days': days,
            'metrics': metrics
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET MARKET SCAN
# ============================================================================

@evaluation_bp.route('/api/evaluation/market', methods=['GET'])
def get_market_scan():
    """
    Run a market scan for new AI developments.
    
    Note: This uses web search if available, otherwise uses AI knowledge.
    
    Returns:
    - Market findings including new models, updates, and tools
    """
    try:
        if not EVALUATION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        from swarm_self_evaluation import MarketScanner
        scanner = MarketScanner()
        findings = scanner.scan_ai_landscape()
        
        return jsonify({
            'success': True,
            'scan_date': findings.get('scan_date'),
            'web_search_used': findings.get('web_search_used', False),
            'new_models': findings.get('new_models', []),
            'capability_updates': findings.get('capability_updates', []),
            'emerging_tools': findings.get('emerging_tools', []),
            'industry_specific': findings.get('industry_specific', []),
            'overall_assessment': findings.get('overall_assessment', '')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET GAPS ANALYSIS
# ============================================================================

@evaluation_bp.route('/api/evaluation/gaps', methods=['GET'])
def get_gaps_analysis():
    """
    Get current capability gaps analysis.
    
    Query Parameters:
    - days: Number of days to analyze (default: 7)
    - severity: Filter by severity (high/medium/low, optional)
    
    Returns:
    - List of identified gaps with recommendations
    """
    try:
        if not EVALUATION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        days = request.args.get('days', 7, type=int)
        severity_filter = request.args.get('severity')
        
        from swarm_self_evaluation import PerformanceCollector, MarketScanner, GapAnalyzer
        
        # Collect metrics
        collector = PerformanceCollector()
        performance = collector.collect_weekly_metrics(days=days)
        
        # Scan market
        scanner = MarketScanner()
        market = scanner.scan_ai_landscape()
        
        # Analyze gaps
        analyzer = GapAnalyzer(performance, market)
        gaps = analyzer.analyze_gaps()
        prioritized = analyzer.prioritize_gaps()
        
        # Filter by severity if requested
        if severity_filter:
            prioritized = [g for g in prioritized if g.get('severity') == severity_filter.lower()]
        
        return jsonify({
            'success': True,
            'period_days': days,
            'total_gaps': len(gaps),
            'gaps': prioritized,
            'by_severity': {
                'high': len([g for g in gaps if g.get('severity') == 'high']),
                'medium': len([g for g in gaps if g.get('severity') == 'medium']),
                'low': len([g for g in gaps if g.get('severity') == 'low'])
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET RECOMMENDATIONS
# ============================================================================

@evaluation_bp.route('/api/evaluation/recommendations', methods=['GET'])
def get_recommendations():
    """
    Get current recommendations based on performance and market analysis.
    
    Query Parameters:
    - days: Number of days to analyze (default: 7)
    - priority: Filter by priority (1/2/3, optional)
    
    Returns:
    - Prioritized list of recommendations
    """
    try:
        if not EVALUATION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        days = request.args.get('days', 7, type=int)
        priority_filter = request.args.get('priority', type=int)
        
        from swarm_self_evaluation import (
            PerformanceCollector, MarketScanner, GapAnalyzer, RecommendationEngine
        )
        
        # Collect and analyze
        collector = PerformanceCollector()
        performance = collector.collect_weekly_metrics(days=days)
        
        scanner = MarketScanner()
        market = scanner.scan_ai_landscape()
        
        analyzer = GapAnalyzer(performance, market)
        gaps = analyzer.prioritize_gaps()
        
        # Generate recommendations
        engine = RecommendationEngine(performance, market, gaps)
        recommendations = engine.generate_recommendations()
        
        # Filter by priority if requested
        if priority_filter:
            recommendations = [r for r in recommendations if r.get('priority') == priority_filter]
        
        return jsonify({
            'success': True,
            'period_days': days,
            'total_recommendations': len(recommendations),
            'recommendations': recommendations,
            'by_priority': {
                'priority_1': len([r for r in recommendations if r.get('priority') == 1]),
                'priority_2': len([r for r in recommendations if r.get('priority') == 2]),
                'priority_3': len([r for r in recommendations if r.get('priority') == 3])
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# DELETE EVALUATION
# ============================================================================

@evaluation_bp.route('/api/evaluation/<int:evaluation_id>', methods=['DELETE'])
def delete_evaluation(evaluation_id):
    """
    Delete a specific evaluation from the database.
    
    Returns:
    - Success/failure status
    """
    try:
        if not EVALUATION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Swarm Self-Evaluation system not available'
            }), 503
        
        from database import get_db
        db = get_db()
        
        try:
            # Check if evaluation exists
            row = db.execute('SELECT id FROM swarm_evaluations WHERE id = ?', (evaluation_id,)).fetchone()
            if not row:
                return jsonify({
                    'success': False,
                    'error': f'Evaluation {evaluation_id} not found'
                }), 404
            
            # Delete it
            db.execute('DELETE FROM swarm_evaluations WHERE id = ?', (evaluation_id,))
            db.commit()
            
            return jsonify({
                'success': True,
                'message': f'Evaluation {evaluation_id} deleted successfully'
            })
        finally:
            db.close()
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
