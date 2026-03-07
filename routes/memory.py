"""
AI SWARM ORCHESTRATOR - Memory API Routes
Phase 2A: Memory System — API Layer
Phase 2B: Memory Retrieval & Context Injection — preview endpoint added

Created: March 05, 2026
Last Updated: March 07, 2026 - Added /api/memory/delete-ids admin endpoint

CHANGELOG:
- March 07, 2026: Added DELETE /api/memory/delete-ids endpoint
  PROBLEM: Memory self-poisoning — AI denial responses ("not in the knowledge
    base") were being extracted as high-score procedural memories (0.7) that
    outranked correct semantic facts (0.6), causing the AI to repeatedly
    follow its own wrong behavior. Specific bad memory IDs: 76, 77, 78.
  FIX: New POST /api/memory/delete-ids endpoint accepts a JSON body with
    an "ids" array and hard-deletes those specific memory rows from
    memory_store. Returns a full report of deleted vs not-found IDs.
  ALSO FIXED: memory_extractor.py now detects denial responses and suppresses
    procedural/semantic extraction from them (see that file's changelog).
  Usage: POST /api/memory/delete-ids  body: {"ids": [76, 77, 78]}
  Auth note: Development-only endpoint — add auth before production use.

- March 07, 2026: Phase 2B — added /api/memory/preview endpoint
  * GET /api/memory/preview?q=your+search+text
  * Calls retrieve_relevant_memories() and format_memories_for_prompt()
  * Returns the exact memory context block that WOULD be injected into
    the AI system prompt for the given query
  * Includes timing information (retrieval_ms, format_ms, total_ms)
  * Includes memory count and character count of formatted context
  * Critical debugging tool: if the Swarm gives an unexpected answer,
    hit this endpoint with the same text to see what memory context
    the AI received
  * Follows the same error handling pattern as all existing endpoints
  * No changes to existing endpoints

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

ENDPOINTS:
  GET  /api/memory/health          — operational status check
  GET  /api/memory/stats           — aggregate statistics
  GET  /api/memory/recent          — most recent memories, ?limit=N&type=T&category=C
  GET  /api/memory/search          — keyword search, ?q=term&limit=N
  GET  /api/memory/preview         — debug: what memory context would AI receive? ?q=text
  POST /api/memory/delete-ids      — admin: hard-delete specific memory IDs

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import time as time_module
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
            "phase": "2B"
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
                'phase': '2B',
                'by_type': stats.get('by_type', {}),
                'avg_relevance': stats.get('avg_relevance', 0.0)
            })
        else:
            return jsonify({
                'status': 'degraded',
                'operational': False,
                'total_memories': 0,
                'message': f"Memory store unreachable: {stats.get('error', 'unknown error')}",
                'phase': '2B'
            }), 503

    except ImportError:
        return jsonify({
            'status': 'unavailable',
            'operational': False,
            'total_memories': 0,
            'message': 'Memory package not installed — Phase 2B not yet deployed',
            'phase': '2B'
        }), 503

    except Exception as e:
        return jsonify({
            'status': 'degraded',
            'operational': False,
            'total_memories': 0,
            'message': f'Memory health check failed: {str(e)}',
            'phase': '2B'
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
# PREVIEW — DEBUG ENDPOINT (Phase 2B)
# ============================================================================

@memory_bp.route('/preview', methods=['GET'])
def memory_preview():
    """
    Show exactly what memory context would be injected into the AI prompt
    for a given query. Critical debugging tool for Phase 2B.

    If the Swarm gives an unexpected answer, hit this endpoint with the
    same query text to see what memory context the AI received.

    Query params:
        q     (str, required): The query text to simulate (same as user request)
        limit (int, optional): Max memories to retrieve. Default 10, max 20.

    Returns JSON:
        {
            "success": true,
            "query": "the search text",
            "memory_count": int,
            "context_chars": int,
            "formatted_context": "the exact block that would be injected",
            "memories": [ {id, memory_type, category, content, relevance_score,
                           created_at}, ... ],
            "timing": {
                "retrieval_ms": float,
                "format_ms": float,
                "total_ms": float
            }
        }

    If no memories match: formatted_context will be "" and memory_count will be 0.
    This is normal on a fresh system before any /api/orchestrate calls have been made.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({
            'success': False,
            'error': 'Query parameter "q" is required. Example: /api/memory/preview?q=TestCorp+schedule',
            'formatted_context': '',
            'memory_count': 0,
            'context_chars': 0
        }), 400

    limit = request.args.get('limit', 10, type=int)
    limit = max(1, min(limit, 20))

    try:
        from memory.memory_retriever import retrieve_relevant_memories, format_memories_for_prompt

        # Time the retrieval
        t0 = time_module.time()
        memories = retrieve_relevant_memories(query, limit=limit)
        t1 = time_module.time()
        retrieval_ms = round((t1 - t0) * 1000, 1)

        # Time the formatting
        formatted_context = format_memories_for_prompt(memories)
        t2 = time_module.time()
        format_ms = round((t2 - t1) * 1000, 1)
        total_ms = round((t2 - t0) * 1000, 1)

        # Serialize memories for the response (strip any internal fields)
        serialized_memories = []
        for mem in memories:
            serialized_memories.append({
                'id': mem.get('id'),
                'memory_type': mem.get('memory_type'),
                'category': mem.get('category'),
                'content': mem.get('content'),
                'relevance_score': mem.get('relevance_score'),
                'created_at': mem.get('created_at'),
            })

        return jsonify({
            'success': True,
            'query': query,
            'memory_count': len(memories),
            'context_chars': len(formatted_context),
            'formatted_context': formatted_context,
            'memories': serialized_memories,
            'timing': {
                'retrieval_ms': retrieval_ms,
                'format_ms': format_ms,
                'total_ms': total_ms
            }
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Memory retriever not installed — Phase 2B not yet deployed',
            'formatted_context': '',
            'memory_count': 0,
            'context_chars': 0
        }), 503

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Memory preview failed: {str(e)}',
            'formatted_context': '',
            'memory_count': 0,
            'context_chars': 0
        }), 500


# ============================================================================
# DELETE BY IDs — ADMIN ENDPOINT (added March 07, 2026)
# ============================================================================

@memory_bp.route('/delete-ids', methods=['POST'])
def delete_memory_ids():
    """
    Hard-delete specific memory records by ID.

    Use this to purge bad memories that were created when the AI gave
    incorrect denial responses and the extractor incorrectly learned
    those denial behaviors as procedural lessons.

    Request body (JSON):
        {
            "ids": [76, 77, 78]
        }

    Returns JSON:
        {
            "success": true,
            "deleted": [76, 77],        <- IDs actually deleted
            "not_found": [78],          <- IDs that did not exist
            "deleted_count": 2,
            "requested_count": 3
        }

    Errors:
        400 — missing or invalid "ids" field
        500 — database error
    """
    try:
        body = request.get_json(silent=True) or {}
        ids_raw = body.get('ids', [])

        if not ids_raw:
            return jsonify({
                'success': False,
                'error': 'Request body must include "ids" as a non-empty array of integers',
                'example': '{"ids": [76, 77, 78]}'
            }), 400

        # Validate and convert all IDs to integers
        try:
            ids_to_delete = [int(i) for i in ids_raw]
        except (TypeError, ValueError) as e:
            return jsonify({
                'success': False,
                'error': f'All IDs must be integers: {e}'
            }), 400

        if len(ids_to_delete) > 100:
            return jsonify({
                'success': False,
                'error': 'Maximum 100 IDs per request'
            }), 400

        from db_engine import get_db_connection

        deleted = []
        not_found = []

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for memory_id in ids_to_delete:
                # Check if it exists first
                cursor.execute(
                    'SELECT id FROM memory_store WHERE id = %s',
                    (memory_id,)
                )
                row = cursor.fetchone()

                if row:
                    cursor.execute(
                        'DELETE FROM memory_store WHERE id = %s',
                        (memory_id,)
                    )
                    deleted.append(memory_id)
                    print(f"🧠 Admin: deleted memory id={memory_id}")
                else:
                    not_found.append(memory_id)
                    print(f"🧠 Admin: memory id={memory_id} not found (already deleted?)")

            conn.commit()

        return jsonify({
            'success': True,
            'deleted': deleted,
            'not_found': not_found,
            'deleted_count': len(deleted),
            'requested_count': len(ids_to_delete)
        })

    except Exception as e:
        import traceback
        print(f"🧠 Admin delete-ids error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Delete failed: {str(e)}'
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
