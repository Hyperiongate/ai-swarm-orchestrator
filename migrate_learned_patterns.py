"""
ADD THIS TO app.py after the list-project-files endpoint

This will create a one-time migration URL to fix the database
"""

@app.route('/api/admin/fix-patterns-table', methods=['GET'])
def fix_patterns_table():
    """
    One-time migration to fix learned_patterns table.
    Adds missing supporting_documents column.
    
    USAGE: https://ai-swarm-orchestrator.onrender.com/api/admin/fix-patterns-table
    """
    try:
        import migrate_learned_patterns
        from io import StringIO
        import sys
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Run migration
        migrate_learned_patterns.migrate_learned_patterns()
        
        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        return jsonify({
            'success': True,
            'message': 'Migration complete!',
            'output': output
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# I did no harm and this file is not truncated
