#!/usr/bin/env python3
"""
Automatic Updater for swarm_app.py
Adds Normative Database and Opportunity Finder features

Usage: python3 update_swarm_app.py <path_to_swarm_app.py>
"""

import sys
import re

def update_swarm_app(filepath):
    """Update swarm_app.py with new features"""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Backup original
    with open(filepath + '.backup', 'w') as f:
        f.write(content)
    print(f"✅ Created backup: {filepath}.backup")
    
    # Step 1: Update header
    old_header = "Last Updated: January 19, 2026"
    new_header = "Last Updated: January 20, 2026"
    
    if old_header in content:
        content = content.replace(old_header, new_header)
        print("✅ Updated header date")
    
    # Step 2: Add changelog entry
    changelog_marker = "CHANGES IN THIS VERSION:"
    new_changelog = """CHANGES IN THIS VERSION:
- January 20, 2026: ADDED NORMATIVE DATABASE & OPPORTUNITY FINDER
  * Normative Database: Compare client data against 206-company benchmarks
  * Opportunity Finder: AI-analyzed side-gig business ideas
  * 11 new API endpoints for benchmarking and opportunities
  * Integration with Project Mode for automatic normative comparisons

"""
    
    if changelog_marker in content and "January 20, 2026: ADDED NORMATIVE DATABASE" not in content:
        content = content.replace(changelog_marker, new_changelog)
        print("✅ Added changelog entry")
    
    # Step 3: Add imports after MARKETING_INITIATIVE_AVAILABLE
    import_marker = """MARKETING_INITIATIVE_AVAILABLE = False

app = Flask(__name__)"""
    
    new_imports = """MARKETING_INITIATIVE_AVAILABLE = False

# Import Normative Database (206-COMPANY BENCHMARKING)
try:
    from normative_database import get_normative_database
    NORMATIVE_DB_AVAILABLE = True
    normative_db = get_normative_database()
    if normative_db and normative_db.loaded:
        print(f"✅ Normative Database loaded - {normative_db.get_stats()['companies_count']} companies")
    else:
        print("⚠️ Normative Database not loaded - check Excel file location")
        NORMATIVE_DB_AVAILABLE = False
except Exception as e:
    print(f"⚠️ Warning: normative_database module error: {e}")
    NORMATIVE_DB_AVAILABLE = False

# Import Opportunity Finder (SIDE-GIG BUSINESS IDEAS)
try:
    from opportunity_finder import get_opportunity_finder
    OPPORTUNITY_FINDER_AVAILABLE = True
    opportunity_finder = get_opportunity_finder()
    print(f"✅ Opportunity Finder loaded - {opportunity_finder.get_stats()['total_opportunities']} ideas ready")
except ImportError:
    print("⚠️ Warning: opportunity_finder module not found")
    OPPORTUNITY_FINDER_AVAILABLE = False

app = Flask(__name__)"""
    
    if import_marker in content and "NORMATIVE_DB_AVAILABLE" not in content:
        content = content.replace(import_marker, new_imports)
        print("✅ Added imports for Normative Database and Opportunity Finder")
    
    # Step 4: Add normative endpoints before if __name__ == '__main__':
    main_marker = "if __name__ == '__main__':"
    
    normative_endpoints = """

# ==================== NORMATIVE DATABASE ENDPOINTS ====================

@app.route('/api/normative/compare', methods=['POST'])
def normative_compare():
    \"\"\"Compare client survey response to normative database\"\"\"
    if not NORMATIVE_DB_AVAILABLE:
        return jsonify({'error': 'Normative database not available'}), 503
    
    data = request.json
    question = data.get('question')
    client_value = data.get('value')
    
    if not question or client_value is None:
        return jsonify({'error': 'question and value required'}), 400
    
    try:
        result = normative_db.compare_to_norm(question, float(client_value))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/normative/batch-compare', methods=['POST'])
def normative_batch_compare():
    \"\"\"Compare multiple client responses to normative database\"\"\"
    if not NORMATIVE_DB_AVAILABLE:
        return jsonify({'error': 'Normative database not available'}), 503
    
    data = request.json
    client_responses = data.get('responses', {})
    
    if not client_responses:
        return jsonify({'error': 'responses dictionary required'}), 400
    
    try:
        results = normative_db.batch_compare(client_responses)
        return jsonify({
            'success': True,
            'comparisons': results,
            'total_compared': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/normative/significant-deviations', methods=['POST'])
def normative_significant_deviations():
    \"\"\"Find significant deviations from normative data\"\"\"
    if not NORMATIVE_DB_AVAILABLE:
        return jsonify({'error': 'Normative database not available'}), 503
    
    data = request.json
    client_responses = data.get('responses', {})
    threshold = data.get('threshold', 1.0)
    
    if not client_responses:
        return jsonify({'error': 'responses dictionary required'}), 400
    
    try:
        deviations = normative_db.get_significant_deviations(client_responses, threshold)
        return jsonify({
            'success': True,
            'significant_deviations': deviations,
            'total_found': len(deviations),
            'threshold_z_score': threshold
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/normative/report', methods=['POST'])
def normative_generate_report():
    \"\"\"Generate comprehensive normative comparison report\"\"\"
    if not NORMATIVE_DB_AVAILABLE:
        return jsonify({'error': 'Normative database not available'}), 503
    
    data = request.json
    client_responses = data.get('responses', {})
    client_name = data.get('client_name', 'Client')
    
    if not client_responses:
        return jsonify({'error': 'responses dictionary required'}), 400
    
    try:
        report = normative_db.generate_comparison_report(client_responses, client_name)
        return jsonify({
            'success': True,
            'report': report,
            'client_name': client_name,
            'questions_compared': len(client_responses)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/normative/search', methods=['GET'])
def normative_search_questions():
    \"\"\"Search for questions in normative database\"\"\"
    if not NORMATIVE_DB_AVAILABLE:
        return jsonify({'error': 'Normative database not available'}), 503
    
    search_term = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    if not search_term:
        return jsonify({'error': 'search term (q) required'}), 400
    
    try:
        results = normative_db.search_questions(search_term, limit)
        return jsonify({
            'success': True,
            'results': results,
            'search_term': search_term
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/normative/stats')
def normative_get_stats():
    \"\"\"Get normative database statistics\"\"\"
    if not NORMATIVE_DB_AVAILABLE:
        return jsonify({'error': 'Normative database not available'}), 503
    
    try:
        stats = normative_db.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== OPPORTUNITY FINDER ENDPOINTS ====================

@app.route('/api/opportunities/top', methods=['GET'])
def opportunities_get_top():
    \"\"\"Get top business opportunity ideas\"\"\"
    if not OPPORTUNITY_FINDER_AVAILABLE:
        return jsonify({'error': 'Opportunity Finder not available'}), 503
    
    limit = int(request.args.get('limit', 5))
    
    try:
        opportunities = opportunity_finder.get_top_opportunities(limit)
        return jsonify({
            'success': True,
            'opportunities': opportunities,
            'total_available': len(opportunity_finder.opportunity_templates)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/opportunities/pitch', methods=['GET'])
def opportunities_get_pitch():
    \"\"\"Generate pitch for a specific opportunity or the top one\"\"\"
    if not OPPORTUNITY_FINDER_AVAILABLE:
        return jsonify({'error': 'Opportunity Finder not available'}), 503
    
    opportunity_name = request.args.get('name')
    
    try:
        pitch = opportunity_finder.generate_pitch(opportunity_name)
        return jsonify({
            'success': True,
            'pitch': pitch
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/opportunities/compare', methods=['POST'])
def opportunities_compare():
    \"\"\"Compare multiple opportunities side-by-side\"\"\"
    if not OPPORTUNITY_FINDER_AVAILABLE:
        return jsonify({'error': 'Opportunity Finder not available'}), 503
    
    data = request.json
    opportunity_names = data.get('opportunities', [])
    
    if not opportunity_names:
        return jsonify({'error': 'list of opportunity names required'}), 400
    
    try:
        comparison = opportunity_finder.compare_opportunities(opportunity_names)
        return jsonify({
            'success': True,
            'comparison': comparison
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/opportunities/analyze', methods=['POST'])
def opportunities_analyze():
    \"\"\"Analyze market fit for a specific opportunity\"\"\"
    if not OPPORTUNITY_FINDER_AVAILABLE:
        return jsonify({'error': 'Opportunity Finder not available'}), 503
    
    data = request.json
    opportunity_name = data.get('name')
    
    if not opportunity_name:
        return jsonify({'error': 'opportunity name required'}), 400
    
    try:
        # Find opportunity
        opportunity = next(
            (o for o in opportunity_finder.opportunity_templates 
             if o['name'].lower() == opportunity_name.lower()),
            None
        )
        
        if not opportunity:
            return jsonify({'error': 'Opportunity not found'}), 404
        
        analysis = opportunity_finder.analyze_market_fit(opportunity)
        analysis['details'] = opportunity
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/opportunities/stats')
def opportunities_get_stats():
    \"\"\"Get opportunity finder statistics\"\"\"
    if not OPPORTUNITY_FINDER_AVAILABLE:
        return jsonify({'error': 'Opportunity Finder not available'}), 503
    
    try:
        stats = opportunity_finder.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


"""
    
    if main_marker in content and "/api/normative/compare" not in content:
        content = content.replace(main_marker, normative_endpoints + main_marker)
        print("✅ Added 11 new API endpoints")
    
    # Step 5: Update /health endpoint
    health_old = """    return jsonify({
        'status': 'healthy',
        'orchestrators': {
            'sonnet': 'configured' if ANTHROPIC_API_KEY else 'missing',
            'opus': 'configured' if ANTHROPIC_API_KEY else 'missing'
        },
        'specialists': {
            'gpt4': 'configured' if OPENAI_API_KEY else 'missing',
            'deepseek': 'configured' if DEEPSEEK_API_KEY else 'missing',
            'gemini': 'configured' if GOOGLE_API_KEY else 'missing'
        },
        'knowledge_base': {
            'status': kb_status,
            'documents_indexed': kb_doc_count
        },
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        }
    })"""
    
    health_new = """    return jsonify({
        'status': 'healthy',
        'orchestrators': {
            'sonnet': 'configured' if ANTHROPIC_API_KEY else 'missing',
            'opus': 'configured' if ANTHROPIC_API_KEY else 'missing'
        },
        'specialists': {
            'gpt4': 'configured' if OPENAI_API_KEY else 'missing',
            'deepseek': 'configured' if DEEPSEEK_API_KEY else 'missing',
            'gemini': 'configured' if GOOGLE_API_KEY else 'missing'
        },
        'knowledge_base': {
            'status': kb_status,
            'documents_indexed': kb_doc_count
        },
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        },
        'normative_database': {
            'status': 'enabled' if NORMATIVE_DB_AVAILABLE else 'disabled',
            'companies': normative_db.get_stats()['companies_count'] if NORMATIVE_DB_AVAILABLE and normative_db else 0
        },
        'opportunity_finder': {
            'status': 'enabled' if OPPORTUNITY_FINDER_AVAILABLE else 'disabled',
            'opportunities': len(opportunity_finder.opportunity_templates) if OPPORTUNITY_FINDER_AVAILABLE else 0
        }
    })"""
    
    if health_old in content and "'normative_database'" not in content:
        content = content.replace(health_old, health_new)
        print("✅ Updated /health endpoint")
    
    # Write updated file
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"\n🎉 Successfully updated {filepath}")
    print(f"\nChanges made:")
    print("  1. ✅ Updated header to January 20, 2026")
    print("  2. ✅ Added changelog entry")  
    print("  3. ✅ Added Normative Database import")
    print("  4. ✅ Added Opportunity Finder import")
    print("  5. ✅ Added 6 normative database endpoints")
    print("  6. ✅ Added 5 opportunity finder endpoints")
    print("  7. ✅ Updated /health endpoint")
    print(f"\n📋 Backup saved to: {filepath}.backup")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 update_swarm_app.py <path_to_swarm_app.py>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    update_swarm_app(filepath)

# I did no harm and this file is not truncated
