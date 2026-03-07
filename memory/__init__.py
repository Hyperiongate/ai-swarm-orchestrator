"""
AI SWARM ORCHESTRATOR - Memory Package
Phase 2A: Memory System
Phase 2B: Memory Retrieval & Context Injection

Created: March 05, 2026
Last Updated: March 07, 2026 - Phase 2B: added retriever exports

CHANGELOG:
- March 07, 2026: Phase 2B — added memory retriever exports
  * Added retrieve_relevant_memories, format_memories_for_prompt
    from memory.memory_retriever
  * Both added to __all__
  * No other changes — all Phase 2A exports preserved

- March 05, 2026: Phase 2A initial build
  * New package — exports the public API for the memory system
  * store_memory, search_memories, get_memory_stats from memory_store
  * extract_memories from memory_extractor

USAGE:
    from memory import store_memory, search_memories, get_memory_stats, extract_memories
    from memory import retrieve_relevant_memories, format_memories_for_prompt

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from memory.memory_store import (
    store_memory,
    get_memories_by_type,
    get_memories_by_category,
    search_memories,
    get_memory_stats,
    update_relevance,
    delete_old_memories
)
from memory.memory_extractor import extract_memories
from memory.memory_retriever import (
    retrieve_relevant_memories,
    format_memories_for_prompt
)

__all__ = [
    # Phase 2A — store layer
    'store_memory',
    'get_memories_by_type',
    'get_memories_by_category',
    'search_memories',
    'get_memory_stats',
    'update_relevance',
    'delete_old_memories',
    # Phase 2A — extraction layer
    'extract_memories',
    # Phase 2B — retrieval layer
    'retrieve_relevant_memories',
    'format_memories_for_prompt',
]

# I did no harm and this file is not truncated
