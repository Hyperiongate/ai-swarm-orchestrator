"""
AI SWARM ORCHESTRATOR - Memory Package
Phase 2A: Memory System

Created: March 05, 2026
Last Updated: March 05, 2026 - Phase 2A initial build

CHANGELOG:
- March 05, 2026: Phase 2A initial build
  * New package — exports the public API for the memory system
  * store_memory, search_memories, get_memory_stats from memory_store
  * extract_memories from memory_extractor

USAGE:
    from memory import store_memory, search_memories, get_memory_stats, extract_memories

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

__all__ = [
    'store_memory',
    'get_memories_by_type',
    'get_memories_by_category',
    'search_memories',
    'get_memory_stats',
    'update_relevance',
    'delete_old_memories',
    'extract_memories',
]

# I did no harm and this file is not truncated
