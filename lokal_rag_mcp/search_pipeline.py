"""
Two-Stage Search Pipeline

Orchestrates the two-stage search process:
1. Stage 1: Broad retrieval using hybrid search (BM25 + Vector)
2. Stage 2: Precision re-ranking using Cross-Encoder

This architecture provides the best of both worlds:
- Stage 1: Fast, high recall (finds all potentially relevant documents)
- Stage 2: Slow, high precision (selects the truly best documents)

Example:
    >>> from lokal_rag_mcp.search_pipeline import SearchPipeline
    >>> from lokal_rag_mcp.reranker import ReRanker
    >>> from lokal_rag_mcp.config import ReRankConfig
    >>>
    >>> # Assuming storage_service is initialized
    >>> reranker = ReRanker(ReRankConfig())
    >>> pipeline = SearchPipeline(storage_service, reranker)
    >>>
    >>> results = pipeline.search(
    ...     query="optimization techniques",
    ...     initial_limit=25,
    ...     rerank_top_n=5,
    ...     enable_rerank=True
    ... )
    >>> print(len(results['results']))  # 5
    >>> print(results['search_info']['rerank_enabled'])  # True
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .query_utils import fn_expand_query_with_dates

logger = logging.getLogger(__name__)


class SearchPipeline:
    """
    Two-stage search pipeline with optional re-ranking.

    Attributes:
        storage_service: StorageService instance for vector/BM25 search
        reranker: Optional ReRanker instance for Stage 2
    """

    def __init__(self, storage_service: Any, reranker: Optional[Any] = None):
        """
        Initialize search pipeline.

        Args:
            storage_service: StorageService instance from app_storage.py
            reranker: Optional ReRanker instance (if None, re-ranking is disabled)

        Example:
            >>> pipeline = SearchPipeline(storage_service)  # No re-ranking
            >>> pipeline = SearchPipeline(storage_service, reranker)  # With re-ranking
        """
        self.storage_service = storage_service
        self.reranker = reranker

        logger.info(
            f"SearchPipeline initialized: reranker={'enabled' if reranker else 'disabled'}"
        )

    def search(
        self,
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
        Execute two-stage search with optional re-ranking.

        Args:
            query: Search query
            mode: Stage 1 search mode ("hybrid", "vector", "fulltext")
            initial_limit: Number of candidates to retrieve in Stage 1
            rerank_top_n: Number of results to return after Stage 2
            enable_rerank: Enable Stage 2 re-ranking
            filter_tags: Optional list of tags to filter by
            filter_type: Optional type filter ("document", "note")
            include_scores: Include Stage 1 and Stage 2 scores in results

        Returns:
            Dict with:
                - results: List of documents with scores and metadata
                - search_info: Metadata about the search (timings, counts, etc.)

        NOTE: If enable_rerank=False or reranker is None, only Stage 1 runs.

        Example:
            >>> results = pipeline.search(
            ...     query="machine learning",
            ...     mode="hybrid",
            ...     initial_limit=25,
            ...     rerank_top_n=5,
            ...     enable_rerank=True
            ... )
            >>> print(results['search_info']['stage1_candidates'])
            25
            >>> print(results['search_info']['stage2_reranked'])
            25
            >>> print(len(results['results']))
            5
        """
        total_start = time.time()

        # Determine if we should re-rank
        should_rerank = enable_rerank and self.reranker is not None

        # ============================================================================
        # Query Expansion for Date-Based Searches
        # ============================================================================

        # Expand query with date variations for better BM25 matching
        # This is CRITICAL for queries like "документы за октябрь"
        # because documents contain dates in genitive case: "8 октября 2025"
        expanded_query = fn_expand_query_with_dates(query)

        # DEBUG: Log query expansion
        if expanded_query != query:
            logger.debug(
                f"QUERY_EXPANDED: '{query[:100]}...' → '{expanded_query[:150]}...'"
            )

        # DEBUG: Log full search parameters
        logger.debug(
            f"SEARCH_START: query='{query[:100]}...', expanded='{expanded_query[:100]}...', "
            f"mode={mode}, initial_limit={initial_limit}, rerank_top_n={rerank_top_n}, "
            f"enable_rerank={enable_rerank}, should_rerank={should_rerank}, "
            f"filter_tags={filter_tags}, filter_type={filter_type}, "
            f"include_scores={include_scores}, reranker_available={self.reranker is not None}"
        )

        # ============================================================================
        # Stage 1: Broad Retrieval
        # ============================================================================

        stage1_start = time.time()

        # Call storage service search with EXPANDED query
        # NOTE: We request more documents if re-ranking is enabled
        stage1_limit = initial_limit if should_rerank else rerank_top_n

        try:
            stage1_results = self._execute_stage1(
                query=expanded_query,  # ← USE EXPANDED QUERY!
                mode=mode,
                limit=stage1_limit,
                filter_tags=filter_tags
            )
        except Exception as e:
            logger.error(f"Stage 1 search failed: {e}")
            return self._create_error_response(str(e))

        stage1_time = (time.time() - stage1_start) * 1000

        logger.debug(f"Stage 1 retrieved {len(stage1_results)} candidates in {stage1_time:.1f}ms")

        # ============================================================================
        # Stage 2: Re-Ranking (Optional)
        # ============================================================================

        stage2_time = 0.0
        final_results = stage1_results

        if should_rerank and len(stage1_results) > 0:
            stage2_start = time.time()

            try:
                # Convert to format expected by reranker
                docs_for_rerank = [
                    {
                        "id": doc.get("id", ""),
                        "content": doc.get("content", doc.get("title", "")),
                        "title": doc.get("title", ""),
                        "stage1_score": doc.get("score", 0.0),
                        # Preserve all original fields
                        **doc,
                    }
                    for doc in stage1_results
                ]

                # Re-rank
                reranked_docs = self.reranker.rerank(
                    query=query, documents=docs_for_rerank, top_n=rerank_top_n, return_scores=True
                )

                final_results = reranked_docs

                stage2_time = (time.time() - stage2_start) * 1000

                logger.debug(f"Stage 2 re-ranked to {len(final_results)} results in {stage2_time:.1f}ms")

            except Exception as e:
                logger.error(f"Stage 2 re-ranking failed: {e}, falling back to Stage 1 results")
                final_results = stage1_results[:rerank_top_n]
                should_rerank = False  # Mark as disabled due to error

        else:
            # No re-ranking, just take top N from Stage 1
            final_results = stage1_results[:rerank_top_n]

        # ============================================================================
        # Prepare Response
        # ============================================================================

        total_time = (time.time() - total_start) * 1000

        # Format results
        formatted_results = []
        for doc in final_results:
            result = {
                "id": doc.get("id", ""),
                "title": doc.get("title", ""),
                "content": doc.get("content", ""),
                "score": doc.get("rerank_score", doc.get("score", 0.0)),
                "type": doc.get("type", "document"),
                "tags": doc.get("tags", []),
                "language": doc.get("language", "en"),
                "created_at": doc.get("created_at", ""),
                "source": doc.get("source"),
                "metadata": {
                    "reranked": doc.get("reranked", False),
                    "snippet_context": doc.get("snippet_context"),
                },
            }

            # Add scores if requested
            if include_scores:
                result["metadata"]["stage1_score"] = doc.get("stage1_score", doc.get("score", 0.0))
                if should_rerank:
                    result["metadata"]["stage2_score"] = doc.get("rerank_score", 0.0)

            formatted_results.append(result)

        # Build search info
        search_info = {
            "query": query,
            "mode": mode,
            "stage1_candidates": len(stage1_results),
            "stage2_reranked": len(stage1_results) if should_rerank else 0,
            "total_returned": len(formatted_results),
            "rerank_enabled": should_rerank,
            "search_time_ms": round(total_time, 1),
        }

        if include_scores:
            search_info["stage1_time_ms"] = round(stage1_time, 1)
            search_info["stage2_time_ms"] = round(stage2_time, 1)

        response = {"results": formatted_results, "search_info": search_info}

        logger.info(
            f"Search completed: {len(formatted_results)} results in {total_time:.1f}ms "
            f"(Stage1: {stage1_time:.1f}ms, Stage2: {stage2_time:.1f}ms)"
        )

        return response

    def _execute_stage1(
        self,
        query: str,
        mode: str,
        limit: int,
        filter_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute Stage 1 search (hybrid, vector, or fulltext).

        Args:
            query: Search query
            mode: Search mode
            limit: Number of candidates to retrieve
            filter_tags: Optional tag filter

        Returns:
            List of documents with Stage 1 scores

        NOTE: This method wraps the storage_service.search_similar_documents() method.
        """
        # Call storage service
        # NOTE: The search_similar_documents method returns a list of tuples:
        # (Document, score, metadata)

        # DEBUG: Log storage service call parameters
        logger.debug(
            f"STAGE1_CALL: Calling storage_service.search_similar_documents with "
            f"query='{query[:100]}...', k={limit}, search_type={mode}"
        )

        results = self.storage_service.search_similar_documents(
            query=query, k=limit, search_type=mode
        )

        # DEBUG: Log raw results from storage service
        logger.debug(
            f"STAGE1_RESULT: Got {len(results)} results from storage_service, "
            f"result_type={type(results)}"
        )

        # Convert to dict format
        docs = []
        for doc, score, metadata in results:
            doc_dict = {
                "id": doc.metadata.get("id", ""),
                "title": doc.metadata.get("title", ""),
                "content": doc.page_content,
                "score": score,
                "type": doc.metadata.get("type", "document"),
                "tags": doc.metadata.get("tags", []),
                "language": doc.metadata.get("language", "en"),
                "created_at": doc.metadata.get("created_at", ""),
                "source": doc.metadata.get("source"),
                "snippet_context": metadata.get("snippet_context"),
            }

            # Filter by tags if specified
            if filter_tags:
                doc_tags = doc_dict.get("tags", [])
                if not any(tag in doc_tags for tag in filter_tags):
                    continue

            docs.append(doc_dict)

        return docs

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create an error response.

        Args:
            error_message: Error message

        Returns:
            Dict with empty results and error info
        """
        return {
            "results": [],
            "search_info": {
                "query": "",
                "mode": "",
                "stage1_candidates": 0,
                "stage2_reranked": 0,
                "total_returned": 0,
                "rerank_enabled": False,
                "search_time_ms": 0,
                "error": error_message,
            },
        }

    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        Get pipeline status and configuration.

        Returns:
            Dict with pipeline info

        Example:
            >>> info = pipeline.get_pipeline_info()
            >>> print(info['reranker_enabled'])
            True
        """
        info = {
            "reranker_enabled": self.reranker is not None,
            "storage_service": type(self.storage_service).__name__,
        }

        if self.reranker:
            info["reranker_info"] = self.reranker.get_info()

        return info
