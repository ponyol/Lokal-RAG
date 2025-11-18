"""
Chat Wrapper for MCP Server

Provides RAG-powered chat functionality with re-ranked context.
Wraps the existing fn_get_rag_response function from app_services.py
and integrates with the SearchPipeline for high-quality context retrieval.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path to import from main app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_config import AppConfig
from app_services import fn_get_rag_response

logger = logging.getLogger(__name__)


def chat_with_context(
    query: str,
    search_pipeline: Any,
    config: AppConfig,
    context_initial_limit: int = 25,
    context_top_k: int = 5,
    enable_rerank: bool = True,
    filter_tags: Optional[List[str]] = None,
    include_sources: bool = True,
    chat_history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Chat with AI using re-ranked context from knowledge base.

    This function:
    1. Retrieves relevant documents using SearchPipeline (with re-ranking)
    2. Calls fn_get_rag_response with retrieved context
    3. Returns response with source citations and metadata

    Args:
        query: User's question
        search_pipeline: SearchPipeline instance
        config: AppConfig instance
        context_initial_limit: Stage 1 candidates (default: 25)
        context_top_k: Final context items after re-ranking (default: 5)
        enable_rerank: Enable re-ranking for context (default: True)
        filter_tags: Optional tag filter
        include_sources: Return source citations (default: True)
        chat_history: Previous conversation (list of {"role": "user/assistant", "content": "..."})
        temperature: LLM temperature (0-1)

    Returns:
        Dict with:
            - response: AI's answer
            - sources: List of source documents used
            - metadata: Timing and context info

    Example:
        >>> result = chat_with_context(
        ...     query="What are neural networks?",
        ...     search_pipeline=pipeline,
        ...     config=config,
        ...     context_top_k=5,
        ...     enable_rerank=True
        ... )
        >>> print(result['response'])
        'Neural networks are...'
        >>> print(len(result['sources']))
        5
    """
    start_time = time.time()

    logger.debug(
        f"Chat query: '{query}', context_top_k={context_top_k}, "
        f"rerank={'enabled' if enable_rerank else 'disabled'}"
    )

    # ============================================================================
    # Step 1: Retrieve context using SearchPipeline
    # ============================================================================

    context_start = time.time()

    try:
        search_results = search_pipeline.search(
            query=query,
            mode="hybrid",  # Always use hybrid for chat
            initial_limit=context_initial_limit,
            rerank_top_n=context_top_k,
            enable_rerank=enable_rerank,
            filter_tags=filter_tags,
            include_scores=True,
        )

        retrieved_docs_data = search_results["results"]
        search_info = search_results["search_info"]

    except Exception as e:
        logger.error(f"Context retrieval failed: {e}")
        return {
            "response": f"Sorry, I encountered an error retrieving context: {str(e)}",
            "sources": [],
            "metadata": {
                "context_items_used": 0,
                "context_reranked": False,
                "error": str(e),
            },
        }

    context_time = (time.time() - context_start) * 1000

    logger.debug(
        f"Retrieved {len(retrieved_docs_data)} context documents in {context_time:.1f}ms"
    )

    # ============================================================================
    # Step 2: Convert to Document format for fn_get_rag_response
    # ============================================================================

    from langchain_core.documents import Document

    retrieved_docs = []
    for doc_data in retrieved_docs_data:
        doc = Document(
            page_content=doc_data["content"],
            metadata={
                "id": doc_data["id"],
                "title": doc_data["title"],
                "source": doc_data.get("source", "unknown"),
                "tags": doc_data.get("tags", []),
                "type": doc_data.get("type", "document"),
            },
        )
        retrieved_docs.append(doc)

    # ============================================================================
    # Step 3: Get RAG response from LLM
    # ============================================================================

    llm_start = time.time()

    try:
        response_text = fn_get_rag_response(
            query=query, retrieved_docs=retrieved_docs, config=config, chat_history=chat_history
        )

    except Exception as e:
        logger.error(f"LLM response generation failed: {e}")
        return {
            "response": f"Sorry, I encountered an error generating a response: {str(e)}",
            "sources": [],
            "metadata": {
                "context_items_used": len(retrieved_docs),
                "context_reranked": enable_rerank,
                "error": str(e),
            },
        }

    llm_time = (time.time() - llm_start) * 1000

    logger.debug(f"LLM response generated in {llm_time:.1f}ms")

    # ============================================================================
    # Step 4: Prepare response
    # ============================================================================

    sources = []
    if include_sources:
        for doc_data in retrieved_docs_data:
            sources.append(
                {
                    "id": doc_data["id"],
                    "title": doc_data["title"],
                    "type": doc_data["type"],
                    "relevance_score": doc_data["score"],
                    "reranked": doc_data["metadata"].get("reranked", False),
                    "excerpt": doc_data["content"][:200],  # First 200 chars
                }
            )

    total_time = (time.time() - start_time) * 1000

    metadata = {
        "context_items_used": len(retrieved_docs),
        "context_reranked": enable_rerank,
        "total_context_chars": sum(len(doc.page_content) for doc in retrieved_docs),
        "llm_provider": config.LLM_PROVIDER,
        "response_time_ms": round(total_time, 1),
        "context_retrieval_time_ms": round(context_time, 1),
        "llm_time_ms": round(llm_time, 1),
    }

    logger.info(
        f"Chat completed: {len(retrieved_docs)} context items, "
        f"{total_time:.1f}ms total (context: {context_time:.1f}ms, llm: {llm_time:.1f}ms)"
    )

    return {"response": response_text, "sources": sources, "metadata": metadata}


class ConversationSession:
    """
    Manages multi-turn conversation with persistent history.

    Attributes:
        session_id: Unique session identifier
        history: List of conversation turns
        max_history_turns: Maximum turns to keep in history
        created_at: Session creation timestamp
    """

    def __init__(self, session_id: str, max_history_turns: int = 10):
        """
        Initialize a conversation session.

        Args:
            session_id: Unique session identifier
            max_history_turns: Max conversation history to keep

        Example:
            >>> session = ConversationSession("session_123", max_history_turns=10)
        """
        self.session_id = session_id
        self.history: List[Dict[str, str]] = []
        self.max_history_turns = max_history_turns

        import datetime

        self.created_at = datetime.datetime.now().isoformat()

        logger.info(f"Conversation session created: {session_id}")

    def add_turn(self, user_message: str, assistant_response: str) -> None:
        """
        Add a conversation turn to history.

        Args:
            user_message: User's message
            assistant_response: Assistant's response

        Example:
            >>> session.add_turn("Hello", "Hi there!")
            >>> print(len(session.history))
            2
        """
        import datetime

        timestamp = datetime.datetime.now().isoformat()

        self.history.append({"role": "user", "content": user_message, "timestamp": timestamp})

        self.history.append(
            {"role": "assistant", "content": assistant_response, "timestamp": timestamp}
        )

        # Trim history if too long
        if len(self.history) > self.max_history_turns * 2:  # *2 because user+assistant
            self.history = self.history[-(self.max_history_turns * 2) :]
            logger.debug(f"Trimmed conversation history to {self.max_history_turns} turns")

    def get_history_for_llm(self) -> List[Dict[str, str]]:
        """
        Get conversation history in format suitable for LLM.

        Returns:
            List of {"role": "user"/"assistant", "content": "..."} dicts

        Example:
            >>> history = session.get_history_for_llm()
            >>> print(history[0]['role'])
            'user'
        """
        return [{"role": msg["role"], "content": msg["content"]} for msg in self.history]

    def get_info(self) -> Dict[str, Any]:
        """
        Get session metadata.

        Returns:
            Dict with session info

        Example:
            >>> info = session.get_info()
            >>> print(info['turn_count'])
            5
        """
        return {
            "session_id": self.session_id,
            "turn_count": len(self.history) // 2,  # Divide by 2 (user+assistant)
            "created_at": self.created_at,
            "max_history_turns": self.max_history_turns,
        }


# Global session storage (in-memory)
# NOTE: For production, consider using Redis or SQLite
_sessions: Dict[str, ConversationSession] = {}


def chat_with_history(
    query: str,
    search_pipeline: Any,
    config: AppConfig,
    session_id: Optional[str] = None,
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
        query: User's message
        search_pipeline: SearchPipeline instance
        config: AppConfig instance
        session_id: Session ID (auto-generated if None)
        context_initial_limit: Stage 1 candidates
        context_top_k: Final context items
        enable_rerank: Enable re-ranking
        filter_tags: Optional tag filter
        include_sources: Return source citations
        max_history_turns: Max conversation history to keep
        temperature: LLM temperature

    Returns:
        Dict with response, session_id, sources, conversation_history, metadata

    Example:
        >>> # First message
        >>> result1 = chat_with_history("What is Python?", pipeline, config)
        >>> session_id = result1['session_id']
        >>>
        >>> # Follow-up
        >>> result2 = chat_with_history(
        ...     "Tell me more about it",
        ...     pipeline,
        ...     config,
        ...     session_id=session_id
        ... )
        >>> print(len(result2['conversation_history']))
        4  # 2 turns (user+assistant, user+assistant)
    """
    # Get or create session
    if session_id is None:
        import uuid

        session_id = f"session_{uuid.uuid4().hex[:12]}"

    if session_id not in _sessions:
        _sessions[session_id] = ConversationSession(session_id, max_history_turns)
        logger.info(f"Created new conversation session: {session_id}")

    session = _sessions[session_id]

    # Get conversation history
    chat_history = session.get_history_for_llm()

    # Call chat_with_context with history
    result = chat_with_context(
        query=query,
        search_pipeline=search_pipeline,
        config=config,
        context_initial_limit=context_initial_limit,
        context_top_k=context_top_k,
        enable_rerank=enable_rerank,
        filter_tags=filter_tags,
        include_sources=include_sources,
        chat_history=chat_history,
        temperature=temperature,
    )

    # Add turn to history
    session.add_turn(query, result["response"])

    # Add session info to response
    result["session_id"] = session_id
    result["conversation_history"] = session.history.copy()
    result["metadata"]["turn_number"] = len(session.history) // 2

    return result


def clear_session(session_id: str) -> bool:
    """
    Clear a conversation session.

    Args:
        session_id: Session ID to clear

    Returns:
        True if session existed and was cleared, False otherwise

    Example:
        >>> cleared = clear_session("session_123")
        >>> print(cleared)
        True
    """
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info(f"Conversation session cleared: {session_id}")
        return True
    else:
        logger.debug(f"Session not found: {session_id}")
        return False


def get_session_info(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a conversation session.

    Args:
        session_id: Session ID

    Returns:
        Dict with session info, or None if session doesn't exist

    Example:
        >>> info = get_session_info("session_123")
        >>> print(info['turn_count'])
        5
    """
    if session_id in _sessions:
        return _sessions[session_id].get_info()
    else:
        return None


def list_sessions() -> List[Dict[str, Any]]:
    """
    List all active conversation sessions.

    Returns:
        List of session info dicts

    Example:
        >>> sessions = list_sessions()
        >>> print(len(sessions))
        3
    """
    return [session.get_info() for session in _sessions.values()]
