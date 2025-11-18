"""
Lokal-RAG MCP Server

FastMCP-based server providing AI assistants with access to local knowledge base.
Implements MCP tools for search, notes management, chat, and analytics.

Key Features:
- Two-stage search (Hybrid + Re-Ranking)
- Notes management with vector search
- Contextual chat with RAG
- Multilingual support (Russian/English)
- Apple Silicon optimized

Usage:
    python -m lokal_rag_mcp.server

    # With custom config
    python -m lokal_rag_mcp.server --settings /path/to/settings.json

    # Disable re-ranking
    python -m lokal_rag_mcp.server --no-rerank

    # Test mode
    python -m lokal_rag_mcp.server --test
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# FastMCP imports
try:
    from fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Install with: pip install fastmcp>=2.12.0")
    sys.exit(1)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Local imports
from lokal_rag_mcp.config import (
    MCPConfig,
    ReRankConfig,
    create_default_mcp_config,
    load_mcp_config_from_json,
    setup_logging,
)
from lokal_rag_mcp.reranker import ReRanker
from lokal_rag_mcp.search_pipeline import SearchPipeline
from lokal_rag_mcp.storage import (
    create_note,
    create_storage_service,
    delete_note,
    get_document_by_id,
    get_storage_stats,
    list_all_documents,
    update_note,
)
from lokal_rag_mcp.chat import chat_with_context, chat_with_history, clear_session, list_sessions

from app_config import create_config_from_settings

logger = logging.getLogger(__name__)

# ============================================================================
# Global State
# ============================================================================

# These are initialized in main() and used by MCP tools
_storage_service: Optional[Any] = None
_search_pipeline: Optional[SearchPipeline] = None
_reranker: Optional[ReRanker] = None
_app_config: Optional[Any] = None
_mcp_config: Optional[MCPConfig] = None

# ============================================================================
# FastMCP Server
# ============================================================================

mcp = FastMCP("Lokal-RAG")


# ============================================================================
# Search Tools
# ============================================================================


@mcp.tool()
def lokal_rag_search(
    query: str,
    mode: str = "hybrid",
    initial_limit: int = 25,
    rerank_top_n: int = 5,
    enable_rerank: bool = True,
    filter_tags: Optional[List[str]] = None,
    filter_type: Optional[str] = None,
    include_scores: bool = False,
) -> Dict[str, Any]:
    """
    Universal search with optional two-stage re-ranking for maximum precision.

    Args:
        query: Search query (required)
        mode: Stage 1 search mode - "hybrid" (BM25+Vector), "vector", or "fulltext" (default: "hybrid")
        initial_limit: Number of candidates for Stage 1 (default: 25, max: 100)
        rerank_top_n: Final results after Stage 2 re-ranking (default: 5, max: 20)
        enable_rerank: Enable Stage 2 re-ranking (default: True)
        filter_tags: Filter by tags (optional, list of strings)
        filter_type: Content type filter - "document", "note", or "all" (default: "all")
        include_scores: Include Stage 1 & 2 scores in metadata (default: False)

    Returns:
        Dict with:
            - results: List of documents with scores and metadata
            - search_info: Search metadata (timings, counts, etc.)

    Example:
        Basic search with re-ranking:
        >>> lokal_rag_search(
        ...     query="machine learning optimization",
        ...     mode="hybrid",
        ...     initial_limit=25,
        ...     rerank_top_n=5
        ... )

        High-precision search:
        >>> lokal_rag_search(
        ...     query="transformer architecture",
        ...     mode="vector",
        ...     initial_limit=50,
        ...     rerank_top_n=3,
        ...     include_scores=True
        ... )

        Fast search without re-ranking:
        >>> lokal_rag_search(
        ...     query="project ideas",
        ...     filter_type="note",
        ...     enable_rerank=False
        ... )
    """
    if _search_pipeline is None:
        return {
            "results": [],
            "search_info": {"error": "Search pipeline not initialized"},
        }

    logger.info(f"Search query: '{query}', mode: {mode}, rerank: {enable_rerank}")

    try:
        result = _search_pipeline.search(
            query=query,
            mode=mode,
            initial_limit=min(initial_limit, 100),  # Cap at 100
            rerank_top_n=min(rerank_top_n, 20),  # Cap at 20
            enable_rerank=enable_rerank,
            filter_tags=filter_tags,
            filter_type=filter_type,
            include_scores=include_scores,
        )

        logger.info(
            f"Search completed: {result['search_info']['total_returned']} results, "
            f"{result['search_info']['search_time_ms']:.1f}ms"
        )

        return result

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return {
            "results": [],
            "search_info": {
                "error": str(e),
                "query": query,
                "mode": mode,
            },
        }


@mcp.tool()
def lokal_rag_get_document(
    doc_id: str, include_related: bool = False, related_limit: int = 5
) -> Dict[str, Any]:
    """
    Retrieve a complete document or note by ID with full content.

    Args:
        doc_id: Document/note ID (required)
        include_related: Include related documents via similarity search (default: False)
        related_limit: Max related items (default: 5)

    Returns:
        Dict with document data and optional related documents

    Example:
        >>> lokal_rag_get_document(doc_id="doc_abc123")
        >>> lokal_rag_get_document(doc_id="note_xyz789", include_related=True, related_limit=3)
    """
    if _storage_service is None:
        return {"error": "Storage service not initialized"}

    logger.info(f"Get document: {doc_id}")

    try:
        doc = get_document_by_id(_storage_service, doc_id)

        if doc is None:
            return {"error": f"Document not found: {doc_id}"}

        # Get related documents if requested
        if include_related:
            # Use vector search to find similar documents
            related_results = _search_pipeline.search(
                query=doc.get("content", doc.get("title", ""))[:500],  # First 500 chars as query
                mode="vector",
                initial_limit=related_limit + 1,  # +1 because source doc will be in results
                rerank_top_n=related_limit + 1,
                enable_rerank=True,
            )

            # Filter out the source document itself
            related_docs = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "score": r["score"],
                    "tags": r["tags"],
                    "reranked": r["metadata"].get("reranked", False),
                }
                for r in related_results["results"]
                if r["id"] != doc_id
            ][:related_limit]

            doc["related_documents"] = related_docs

        logger.info(f"Document retrieved: {doc_id}")
        return doc

    except Exception as e:
        logger.error(f"Failed to get document {doc_id}: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
def lokal_rag_list_documents(
    doc_type: Optional[str] = "all",
    tags: Optional[List[str]] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List all documents and notes with pagination and filtering.

    Args:
        doc_type: Filter by type - "document", "note", or "all" (default: "all")
        tags: Filter by tags (optional, AND logic)
        sort_by: Sort field - "created_at", "updated_at", "title" (default: "created_at")
        sort_order: Sort direction - "asc" or "desc" (default: "desc")
        limit: Results per page (default: 20, max: 100)
        offset: Pagination offset (default: 0)

    Returns:
        Dict with:
            - items: List of documents/notes
            - pagination: Pagination metadata

    Example:
        >>> lokal_rag_list_documents(doc_type="document", limit=20)
        >>> lokal_rag_list_documents(tags=["ai", "machine-learning"], sort_by="title")
    """
    if _storage_service is None:
        return {
            "items": [],
            "pagination": {"total": 0, "limit": limit, "offset": offset, "has_more": False},
            "error": "Storage service not initialized",
        }

    logger.info(f"List documents: type={doc_type}, tags={tags}, limit={limit}, offset={offset}")

    try:
        # Convert "all" to None for storage layer
        type_filter = None if doc_type == "all" else doc_type

        result = list_all_documents(
            _storage_service,
            doc_type=type_filter,
            tags=tags,
            limit=min(limit, 100),  # Cap at 100
            offset=offset,
        )

        logger.info(f"Listed {len(result['items'])} documents")
        return result

    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        return {
            "items": [],
            "pagination": {"total": 0, "limit": limit, "offset": offset, "has_more": False},
            "error": str(e),
        }


# ============================================================================
# Notes Tools
# ============================================================================


@mcp.tool()
def lokal_rag_create_note(
    title: str, content: str, tags: Optional[List[str]] = None, language: str = "en"
) -> Dict[str, Any]:
    """
    Create a new note in the knowledge base with automatic embedding generation.

    Args:
        title: Note title (required)
        content: Note content in markdown (required)
        tags: Tags for organization (optional)
        language: Content language - "ru" or "en" (default: "en")

    Returns:
        Dict with note ID and creation metadata

    Example:
        >>> lokal_rag_create_note(
        ...     title="Meeting Notes - AI Strategy",
        ...     content="# Key Points\\n- Focus on RAG systems\\n- Budget approved",
        ...     tags=["meeting", "ai", "strategy"]
        ... )
    """
    if _storage_service is None:
        return {"error": "Storage service not initialized"}

    logger.info(f"Create note: '{title}'")

    try:
        result = create_note(
            _storage_service, title=title, content=content, tags=tags, language=language
        )

        logger.info(f"Note created: {result['id']}")
        return result

    except Exception as e:
        logger.error(f"Failed to create note: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
def lokal_rag_get_note(note_id: str) -> Dict[str, Any]:
    """
    Retrieve a note by ID with full content.

    Args:
        note_id: Note ID (required)

    Returns:
        Dict with note data

    Example:
        >>> lokal_rag_get_note(note_id="note_abc123")
    """
    # Notes are documents with type="note", use get_document
    return lokal_rag_get_document(doc_id=note_id, include_related=False)


@mcp.tool()
def lokal_rag_list_notes(
    search: Optional[str] = None,
    tags: Optional[List[str]] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List all notes with filtering and search.

    Args:
        search: Search in title/content (optional)
        tags: Filter by tags (optional)
        sort_by: Sort field (default: "created_at")
        sort_order: Sort direction (default: "desc")
        limit: Results per page (default: 20)
        offset: Pagination offset (default: 0)

    Returns:
        Dict with notes and pagination info

    Example:
        >>> lokal_rag_list_notes(tags=["meeting"], limit=10)
        >>> lokal_rag_list_notes(search="project ideas")
    """
    # List documents with type="note"
    return lokal_rag_list_documents(
        doc_type="note", tags=tags, sort_by=sort_by, sort_order=sort_order, limit=limit, offset=offset
    )


@mcp.tool()
def lokal_rag_update_note(
    note_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Update an existing note.

    Args:
        note_id: Note ID (required)
        title: New title (optional)
        content: New content (optional)
        tags: New tags (optional, replaces existing)

    Returns:
        Dict with update status

    Example:
        >>> lokal_rag_update_note(note_id="note_123", content="Updated content")
    """
    if _storage_service is None:
        return {"error": "Storage service not initialized"}

    logger.info(f"Update note: {note_id}")

    try:
        result = update_note(_storage_service, note_id, title, content, tags)
        logger.info(f"Note updated: {note_id}")
        return result

    except NotImplementedError:
        return {"error": "Note update feature coming soon"}
    except Exception as e:
        logger.error(f"Failed to update note: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
def lokal_rag_delete_note(note_id: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Delete a note from the knowledge base.

    Args:
        note_id: Note ID (required)
        confirm: Confirmation flag (must be True to delete)

    Returns:
        Dict with deletion status

    Example:
        >>> lokal_rag_delete_note(note_id="note_123", confirm=True)
    """
    if _storage_service is None:
        return {"error": "Storage service not initialized"}

    if not confirm:
        return {"deleted": False, "message": "Confirmation required (set confirm=True)"}

    logger.info(f"Delete note: {note_id}")

    try:
        result = delete_note(_storage_service, note_id, confirm)
        logger.info(f"Note deleted: {note_id}")
        return result

    except NotImplementedError:
        return {"error": "Note deletion feature coming soon"}
    except Exception as e:
        logger.error(f"Failed to delete note: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# Chat Tools
# ============================================================================


@mcp.tool()
def lokal_rag_chat(
    message: str,
    context_mode: str = "auto",
    context_initial_limit: int = 25,
    context_top_k: int = 5,
    enable_rerank: bool = True,
    filter_tags: Optional[List[str]] = None,
    include_sources: bool = True,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Chat with AI assistant using your knowledge base as context.

    Automatically retrieves relevant documents/notes using re-ranking and
    includes them in the conversation.

    Args:
        message: User message (required)
        context_mode: What to search - "auto", "documents", "notes", "all" (default: "auto")
        context_initial_limit: Stage 1 candidates (default: 25)
        context_top_k: Final context items after re-ranking (default: 5, max: 10)
        enable_rerank: Enable re-ranking for context (default: True)
        filter_tags: Limit context to specific tags (optional)
        include_sources: Return source citations (default: True)
        temperature: LLM temperature (default: 0.7, range: 0-1)

    Returns:
        Dict with:
            - response: AI assistant's response
            - sources: Context sources used (if include_sources=True)
            - metadata: Timing and context info

    Example:
        >>> lokal_rag_chat(
        ...     message="What are the main optimization techniques?",
        ...     context_top_k=5,
        ...     enable_rerank=True
        ... )

        >>> lokal_rag_chat(
        ...     message="Summarize my notes about RAG",
        ...     context_mode="notes",
        ...     filter_tags=["rag", "ai"]
        ... )
    """
    if _search_pipeline is None or _app_config is None:
        return {"error": "Server not fully initialized"}

    logger.info(f"Chat message: '{message[:50]}...', context_top_k={context_top_k}")

    try:
        result = chat_with_context(
            query=message,
            search_pipeline=_search_pipeline,
            config=_app_config,
            context_initial_limit=context_initial_limit,
            context_top_k=min(context_top_k, 10),  # Cap at 10
            enable_rerank=enable_rerank,
            filter_tags=filter_tags,
            include_sources=include_sources,
            temperature=temperature,
        )

        logger.info(f"Chat response generated: {result['metadata']['response_time_ms']:.1f}ms")
        return result

    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        return {
            "response": f"Sorry, I encountered an error: {str(e)}",
            "sources": [],
            "metadata": {"error": str(e)},
        }


@mcp.tool()
def lokal_rag_chat_with_history(
    message: str,
    session_id: Optional[str] = None,
    context_mode: str = "auto",
    context_initial_limit: int = 25,
    context_top_k: int = 5,
    enable_rerank: bool = True,
    filter_tags: Optional[List[str]] = None,
    include_sources: bool = True,
    max_history_turns: int = 10,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Multi-turn conversation with persistent context and history.

    Args:
        message: User message (required)
        session_id: Session ID (auto-generated if not provided)
        context_mode: What to search (default: "auto")
        context_initial_limit: Stage 1 candidates (default: 25)
        context_top_k: Final context items (default: 5)
        enable_rerank: Enable re-ranking (default: True)
        filter_tags: Tag filter (optional)
        include_sources: Return sources (default: True)
        max_history_turns: Max conversation history (default: 10)
        temperature: LLM temperature (default: 0.7)

    Returns:
        Dict with response, session_id, sources, conversation_history, metadata

    Example:
        First message:
        >>> chat1 = lokal_rag_chat_with_history(
        ...     message="What are the main topics in my documents?"
        ... )
        >>> session_id = chat1['session_id']

        Follow-up:
        >>> chat2 = lokal_rag_chat_with_history(
        ...     message="Which ones discuss transformers?",
        ...     session_id=session_id
        ... )
    """
    if _search_pipeline is None or _app_config is None:
        return {"error": "Server not fully initialized"}

    logger.info(f"Chat with history: '{message[:50]}...', session_id={session_id}")

    try:
        result = chat_with_history(
            query=message,
            search_pipeline=_search_pipeline,
            config=_app_config,
            session_id=session_id,
            context_initial_limit=context_initial_limit,
            context_top_k=min(context_top_k, 10),
            enable_rerank=enable_rerank,
            filter_tags=filter_tags,
            include_sources=include_sources,
            max_history_turns=max_history_turns,
            temperature=temperature,
        )

        logger.info(f"Chat response: session={result['session_id']}, turn={result['metadata']['turn_number']}")
        return result

    except Exception as e:
        logger.error(f"Chat with history failed: {e}", exc_info=True)
        return {
            "response": f"Sorry, I encountered an error: {str(e)}",
            "session_id": session_id or "error",
            "sources": [],
            "conversation_history": [],
            "metadata": {"error": str(e)},
        }


# ============================================================================
# Info & Analytics Tools
# ============================================================================


@mcp.tool()
def lokal_rag_get_stats(include_tag_stats: bool = True) -> Dict[str, Any]:
    """
    Get comprehensive statistics about your knowledge base.

    Args:
        include_tag_stats: Include tag distribution (default: True)

    Returns:
        Dict with statistics

    Example:
        >>> stats = lokal_rag_get_stats()
        >>> print(stats['overview']['total_documents'])
        42
    """
    if _storage_service is None:
        return {"error": "Storage service not initialized"}

    logger.info("Get storage stats")

    try:
        stats = get_storage_stats(_storage_service)
        logger.info(f"Stats retrieved: {stats['overview']['total_items']} total items")
        return stats

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
def lokal_rag_health_check(
    include_diagnostics: bool = False, check_reranker: bool = True
) -> Dict[str, Any]:
    """
    Check the health and status of the Lokal-RAG system, including re-ranker.

    Args:
        include_diagnostics: Include detailed diagnostics (default: False)
        check_reranker: Test re-ranker model loading (default: True)

    Returns:
        Dict with system health status

    Example:
        >>> health = lokal_rag_health_check(check_reranker=True)
        >>> print(health['status'])
        'healthy'
        >>> print(health['components']['reranker']['device'])
        'mps'
    """
    logger.info("Health check")

    import platform

    health = {
        "status": "healthy",
        "components": {},
        "platform": {
            "system": platform.system(),
            "processor": platform.machine(),
            "apple_silicon": platform.machine() == "arm64" and platform.system() == "Darwin",
            "mps_available": False,
        },
    }

    # Check torch/MPS availability
    try:
        import torch

        health["platform"]["mps_available"] = torch.backends.mps.is_available()
    except ImportError:
        pass

    # Check storage
    if _storage_service is not None:
        try:
            doc_count = _storage_service.get_document_count()
            health["components"]["storage"] = {"status": "ok", "document_count": doc_count}
        except Exception as e:
            health["components"]["storage"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"
    else:
        health["components"]["storage"] = {"status": "not_initialized"}
        health["status"] = "degraded"

    # Check LLM provider
    if _app_config is not None:
        health["components"]["llm_provider"] = {
            "status": "ok",
            "provider": _app_config.LLM_PROVIDER,
        }
    else:
        health["components"]["llm_provider"] = {"status": "not_initialized"}
        health["status"] = "degraded"

    # Check re-ranker
    if _reranker is not None:
        reranker_info = _reranker.get_info()
        health["components"]["reranker"] = {
            "status": "ok" if reranker_info["loaded"] else "not_loaded",
            "model": reranker_info["model"],
            "device": reranker_info["device"],
            "memory_mb": reranker_info.get("memory_mb", "unknown"),
        }

        # Test re-ranker if requested
        if check_reranker and not reranker_info["loaded"]:
            try:
                test_metrics = _reranker.test_latency(num_docs=10)
                health["components"]["reranker"]["test_latency_ms"] = test_metrics[
                    "rerank_time_ms"
                ]
                health["components"]["reranker"]["status"] = "ok"
            except Exception as e:
                health["components"]["reranker"]["status"] = "error"
                health["components"]["reranker"]["error"] = str(e)
                health["status"] = "degraded"

    else:
        health["components"]["reranker"] = {"status": "disabled"}

    import datetime

    health["timestamp"] = datetime.datetime.now().isoformat()

    logger.info(f"Health check: {health['status']}")
    return health


# ============================================================================
# Server Initialization
# ============================================================================


def initialize_server(
    settings_path: Optional[Path] = None,
    disable_rerank: bool = False,
    rerank_device: Optional[str] = None,
) -> None:
    """
    Initialize the MCP server with all services.

    Args:
        settings_path: Path to settings file
        disable_rerank: Disable re-ranking globally
        rerank_device: Force re-ranker device ("auto", "cpu", "mps", "cuda")
    """
    global _storage_service, _search_pipeline, _reranker, _app_config, _mcp_config

    logger.info("Initializing Lokal-RAG MCP Server...")

    # Load MCP configuration
    _mcp_config = load_mcp_config_from_json(settings_path)

    # Override re-ranking if disabled via CLI
    if disable_rerank:
        from dataclasses import replace

        _mcp_config = replace(_mcp_config, rerank=replace(_mcp_config.rerank, enabled=False))

    # Override device if specified
    if rerank_device:
        _mcp_config = replace(
            _mcp_config, rerank=replace(_mcp_config.rerank, device=rerank_device)
        )

    # Setup logging
    setup_logging(_mcp_config)

    logger.info(f"MCP Config: rerank_enabled={_mcp_config.rerank.enabled}")

    # Load app configuration
    _app_config = create_config_from_settings()
    logger.info(f"App Config: llm_provider={_app_config.LLM_PROVIDER}")

    # Initialize storage service
    _storage_service = create_storage_service(_app_config)
    logger.info("Storage service initialized")

    # Initialize re-ranker (if enabled)
    if _mcp_config.rerank.enabled:
        try:
            _reranker = ReRanker(_mcp_config.rerank)
            logger.info(f"Re-ranker initialized: model={_mcp_config.rerank.model}")
        except Exception as e:
            logger.warning(f"Failed to initialize re-ranker: {e}")
            _reranker = None
    else:
        logger.info("Re-ranking disabled")
        _reranker = None

    # Initialize search pipeline
    _search_pipeline = SearchPipeline(_storage_service, _reranker)
    logger.info("Search pipeline initialized")

    logger.info("✅ Lokal-RAG MCP Server initialized successfully")


def main():
    """
    Main entry point for the MCP server.
    """
    parser = argparse.ArgumentParser(description="Lokal-RAG MCP Server")
    parser.add_argument(
        "--settings", type=Path, help="Path to settings.json file"
    )
    parser.add_argument(
        "--no-rerank", action="store_true", help="Disable re-ranking globally"
    )
    parser.add_argument(
        "--rerank-device",
        choices=["auto", "cpu", "mps", "cuda"],
        help="Force re-ranker device",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--test", action="store_true", help="Run in test mode (health check and exit)"
    )

    args = parser.parse_args()

    # Initialize server
    try:
        initialize_server(
            settings_path=args.settings,
            disable_rerank=args.no_rerank,
            rerank_device=args.rerank_device,
        )
    except Exception as e:
        print(f"ERROR: Failed to initialize server: {e}")
        sys.exit(1)

    # Test mode: run health check and exit
    if args.test:
        print("\n=== Test Mode ===")
        health = lokal_rag_health_check(include_diagnostics=True, check_reranker=True)

        import json
        print(json.dumps(health, indent=2))

        if health["status"] == "healthy":
            print("\n✅ Server is healthy")
            sys.exit(0)
        else:
            print(f"\n⚠️  Server status: {health['status']}")
            sys.exit(1)

    # Run server
    logger.info("Starting FastMCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
