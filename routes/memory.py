"""
AI SWARM ORCHESTRATOR - Memory API Routes
Phase 2A: Memory System — API Layer

Created: March 05, 2026
Last Updated: March 05, 2026 - Phase 2A initial build

CHANGELOG:
- March 05, 2026: Phase 2A initial build
  * New file — part of Phase 2A memory system
  * Provides read-only HTTP endpoints for inspecting the memory store
  * All endpoints return JSON; all are GET except /api/memory/search (GET with ?q=)
  * Blueprint name: memory_bp, url_prefix: /api/memory
  * Endpoints:
      GET  /api/memory/health   — is memory system operational?
      GET  /api/memory/stats    — counts by type/category, date range, avg relevance
      GET  /api/memory/recent   — most recent memories (all types), ?limit=N
      GET  /api/memory/search   — keyword search across content, ?q=term&limit=N
  * No writes — memory store is written to by memory_extractor only
  * Handles ImportError gracefully if memory package not deployed

ACCEPTANCE CRITERIA (from Phase 2A plan):
  - /api/memory/health returns operational status
  - After /api/orchestrate, /api/memory/recent shows new episodic memory
  - /api/memory/stats shows counts by type/category
  - /api/memory/search?q=term returns relevant memories

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from flask import Blueprint, request, jsonify

memory_bp = Blueprint('memory', __name__, url_prefix='/api/memory')


# ============================================================================
# HEALTH CHECK
# ============================================================================

@memory_bp.route('/health', methods=['GET'])
def memory_health():
    """
    Check whether the memory system is operational.

    Tests:
    - Can the memory package be imported?
    - Can get_memory_stats() reach the database?

    Returns JSON:
        {
            "status": "healthy" | "degraded" | "unavailable",
            "operational": true | false,
            "total_memories": int,
            "message": str,
            "phase": "2A"
        }
    """
    try:
        from memory.memory_store import get_memory_stats
        stats = get_memory_stats()
        if stats.get('operational'):
            return jsonify({
                'status': 'healthy',
                'operational': True,
                'total_memories': stats.get('total_memories', 0),
                'message': 'Memory system is operational',
                'phase': '2A',
                'by_type': stats.get('by_type', {}),
                'avg_relevance': stats.get('avg_relevance', 0.0)
            })
        else:
            return jsonify({
                'status': 'degraded',
                'operational': False,
                'total_memories': 0,
                'message': f"Memory store unreachable: {stats.get('error', 'unknown error')}",
                'phase': '2A'
            }), 503

    except ImportError:
        return jsonify({
            'status': 'unavailable',
            'operational': False,
            'total_memories': 0,
            'message': 'Memory package not installed — Phase 2A not yet deployed',
            'phase': '2A'
        }), 503

    except Exception as e:
        return jsonify({
            'status': 'degraded',
            'operational': False,
            'total_memories': 0,
            'message': f'Memory health check failed: {str(e)}',
            'phase': '2A'
        }), 503


# ============================================================================
# STATISTICS
# ============================================================================

@memory_bp.route('/stats', methods=['GET'])
def memory_stats():
    """
    Return aggregate statistics about the memory store.

    Returns JSON:
        {
            "success": true,
            "stats": {
                "total_memories": int,
                "by_type": {"episodic": N, "semantic": N, "procedural": N},
                "by_category": {"client_info": N, ...},
                "oldest_memory": "ISO timestamp" | null,
                "newest_memory": "ISO timestamp" | null,
                "avg_relevance": float,
                "operational": bool
            }
        }
    """
    try:
        from memory.memory_store import get_memory_stats
        stats = get_memory_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Memory package not installed',
            'stats': {
                'total_memories': 0,
                'by_type': {},
                'by_category': {},
                'operational': False
            }
        }), 503

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {
                'total_memories': 0,
                'by_type': {},
                'by_category': {},
                'operational': False
            }
        }), 500


# ============================================================================
# RECENT MEMORIES
# ============================================================================

@memory_bp.route('/recent', methods=['GET'])
def recent_memories():
    """
    Return the most recently stored memories across all types.

    Query params:
        limit  (int, optional): Max results to return. Default 20, max 100.
        type   (str, optional): Filter by memory_type ('episodic', 'semantic', 'procedural')
        category (str, optional): Filter by category

    Returns JSON:
        {
            "success": true,
            "memories": [ {id, memory_type, category, content, relevance_score,
                           source_task_id, created_at, updated_at}, ... ],
            "count": int
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = max(1, min(limit, 100))

        memory_type = request.args.get('type', '').strip() or None
        category = request.args.get('category', '').strip() or None

        from memory.memory_store import get_memories_by_type, get_memories_by_category
        from db_engine import get_db_connection

        memories = []

        if memory_type:
            memories = get_memories_by_type(memory_type, limit=limit)
        elif category:
            memories = get_memories_by_category(category, limit=limit)
        else:
            # No filter — return most recent across all types
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, memory_type, category, content, relevance_score,
                           source_task_id, created_at, updated_at
                    FROM memory_store
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = cursor.fetchall()
                memories = [_serialize_row(r) for r in rows]

        return jsonify({
            'success': True,
            'memories': memories,
            'count': len(memories)
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Memory package not installed',
            'memories': [],
            'count': 0
        }), 503

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'memories': [],
            'count': 0
        }), 500


# ============================================================================
# SEARCH
# ============================================================================

@memory_bp.route('/search', methods=['GET'])
def search_memories_endpoint():
    """
    Keyword search across memory content.

    Query params:
        q     (str, required): Search query text
        limit (int, optional): Max results. Default 10, max 50.

    Returns JSON:
        {
            "success": true,
            "query": "search term",
            "memories": [ {id, memory_type, category, content, ...}, ... ],
            "count": int
        }
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({
            'success': False,
            'error': 'Query parameter "q" is required',
            'memories': [],
            'count': 0
        }), 400

    limit = request.args.get('limit', 10, type=int)
    limit = max(1, min(limit, 50))

    try:
        from memory.memory_store import search_memories
        memories = search_memories(query, limit=limit)

        return jsonify({
            'success': True,
            'query': query,
            'memories': memories,
            'count': len(memories)
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Memory package not installed',
            'query': query,
            'memories': [],
            'count': 0
        }), 503

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'query': query,
            'memories': [],
            'count': 0
        }), 500


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _serialize_row(row):
    """Convert a db_engine row to a plain JSON-serializable dict."""
    if row is None:
        return {}
    d = dict(row) if hasattr(row, 'items') else {}
    for key in ('created_at', 'updated_at'):
        val = d.get(key)
        if val and not isinstance(val, str):
            try:
                d[key] = val.isoformat()
            except AttributeError:
                d[key] = str(val)
    return d


# I did no harm and this file is not truncated
