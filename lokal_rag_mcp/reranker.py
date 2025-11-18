"""
Re-Ranking Service

Implements Cross-Encoder based re-ranking for improved search precision.
Uses jina-reranker-v2-base-multilingual by default, with automatic device detection
and Apple Silicon (M1/M2/M3/M4) optimization.

Re-ranking is a second-stage refinement process that takes initially retrieved
documents and re-scores them using a more sophisticated model that reads both
the query and document together.

Why not use it for initial search?
- Vector/BM25: Fast (ms), can search millions, good recall
- Cross-Encoder: Slower (100-500ms), limited to small candidate set, excellent precision

Example:
    >>> from lokal_rag_mcp.config import ReRankConfig
    >>> from lokal_rag_mcp.reranker import ReRanker
    >>>
    >>> config = ReRankConfig(device="auto")
    >>> reranker = ReRanker(config)
    >>>
    >>> docs = [
    ...     {"id": "1", "content": "Neural networks use gradient descent..."},
    ...     {"id": "2", "content": "The cat sat on the mat."},
    ...     {"id": "3", "content": "Adam optimizer is adaptive..."}
    ... ]
    >>>
    >>> ranked = reranker.rerank("optimization techniques", docs, top_n=2)
    >>> print(ranked[0]['id'])  # Should be doc 3 or 1
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .config import ReRankConfig

logger = logging.getLogger(__name__)


class ReRanker:
    """
    Re-ranking service with lazy loading and device auto-detection.

    The model is loaded on first use, not at startup, to save memory.
    Supports CPU, Apple Silicon (MPS), and NVIDIA GPU (CUDA).

    Attributes:
        config: Re-ranking configuration
        _model: Lazy-loaded CrossEncoder model (None until first use)
        _device: Detected device ("cpu", "mps", "cuda")
        _model_loaded: Whether model has been loaded
        _total_reranks: Total number of rerank operations (for metrics)
        _total_time_ms: Total time spent re-ranking (for metrics)
    """

    def __init__(self, config: ReRankConfig):
        """
        Initialize re-ranker with configuration.

        NOTE: Model is NOT loaded here. It's loaded on first rerank() call.

        Args:
            config: Re-ranking configuration

        Example:
            >>> config = ReRankConfig(device="auto", cache_model=True)
            >>> reranker = ReRanker(config)
            >>> # Model is not loaded yet, no memory used
        """
        self.config = config
        self._model: Optional[Any] = None
        self._device: Optional[str] = None
        self._model_loaded = False

        # Metrics
        self._total_reranks = 0
        self._total_time_ms = 0.0

        logger.info(f"ReRanker initialized: model={config.model}, device={config.device}")

    def _detect_device(self) -> str:
        """
        Auto-detect the best available device.

        Priority:
        1. Apple Silicon (MPS) if available
        2. NVIDIA GPU (CUDA) if available
        3. CPU as fallback

        Returns:
            str: Device name ("mps", "cuda", or "cpu")

        NOTE: This requires torch to be installed. If torch is not available,
        falls back to CPU and logs a warning.

        Example:
            >>> reranker = ReRanker(ReRankConfig(device="auto"))
            >>> device = reranker._detect_device()
            >>> print(device)  # "mps" on M1 Mac, "cuda" on NVIDIA, "cpu" otherwise
        """
        # If device is explicitly set (not "auto"), use it
        if self.config.device != "auto":
            logger.info(f"Using explicitly configured device: {self.config.device}")
            return self.config.device

        try:
            import torch

            if torch.backends.mps.is_available():
                logger.info("Apple Silicon (MPS) detected and available")
                return "mps"
            elif torch.cuda.is_available():
                logger.info("NVIDIA GPU (CUDA) detected and available")
                return "cuda"
            else:
                logger.info("No GPU detected, falling back to CPU")
                return "cpu"
        except ImportError:
            logger.warning(
                "torch not installed, cannot detect device. "
                "Install with: pip install torch"
            )
            return "cpu"

    def _load_model(self) -> None:
        """
        Lazy-load the CrossEncoder model.

        This is called automatically on first rerank() call.
        Loading can take 1-3 seconds and uses ~600MB of memory.

        Raises:
            ImportError: If sentence-transformers is not installed
            Exception: If model loading fails

        NOTE: After loading, the model is kept in memory if config.cache_model=True
        """
        if self._model_loaded:
            return

        logger.info(f"Loading re-ranker model: {self.config.model}")
        start_time = time.time()

        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise

        # Detect device
        self._device = self._detect_device()
        logger.info(f"Using device: {self._device}")

        # Load model
        try:
            self._model = CrossEncoder(
                self.config.model,
                device=self._device,
                max_length=1024,  # jina-reranker-v2 context length
            )
            self._model_loaded = True

            load_time = (time.time() - start_time) * 1000
            logger.info(f"Model loaded successfully in {load_time:.0f}ms")

        except Exception as e:
            logger.error(f"Failed to load model {self.config.model}: {e}")
            raise

    @property
    def model(self) -> Any:
        """
        Get the CrossEncoder model, loading it if necessary.

        This property provides lazy access to the model.

        Returns:
            CrossEncoder: The loaded model

        Example:
            >>> reranker = ReRanker(ReRankConfig())
            >>> model = reranker.model  # Loads model on first access
            >>> model = reranker.model  # Returns cached model
        """
        if not self._model_loaded:
            self._load_model()
        return self._model

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: Optional[int] = None,
        return_scores: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Re-rank documents by relevance to query.

        Takes a list of documents and re-scores them using the Cross-Encoder model.
        Documents are sorted by relevance score (descending) and top_n are returned.

        Args:
            query: Search query
            documents: List of dicts with at least 'content' or 'title' field
            top_n: Number of results to return (default: config.default_top_n)
            return_scores: Add 'rerank_score' field to each document

        Returns:
            List of re-ranked documents (top_n items)

        NOTE: Each document must have either 'content' or 'title' field.
        The re-ranker will use 'content' if available, otherwise 'title'.

        Example:
            >>> docs = [
            ...     {"id": "1", "content": "Machine learning optimization"},
            ...     {"id": "2", "content": "Cat on a mat"},
            ...     {"id": "3", "content": "Adam optimizer"}
            ... ]
            >>> ranked = reranker.rerank("optimization", docs, top_n=2)
            >>> len(ranked)
            2
            >>> ranked[0]['rerank_score'] > ranked[1]['rerank_score']
            True
        """
        start_time = time.time()

        if not documents:
            logger.debug("No documents to rerank")
            return []

        if top_n is None:
            top_n = self.config.default_top_n

        # Prepare query-document pairs
        pairs = []
        for doc in documents:
            # Use 'content' if available, otherwise 'title', otherwise empty string
            text = doc.get("content", doc.get("title", ""))
            pairs.append((query, text))

        logger.debug(f"Re-ranking {len(documents)} documents (top_n={top_n})")

        # Get scores from Cross-Encoder
        try:
            scores = self.model.predict(pairs, batch_size=self.config.batch_size)
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            # Fallback: return documents as-is
            return documents[:top_n]

        # Attach scores to documents
        for doc, score in zip(documents, scores):
            if return_scores:
                doc["rerank_score"] = float(score)
            doc["reranked"] = True

        # Filter by threshold if configured
        if self.config.threshold > 0:
            documents = [
                doc for doc in documents if doc.get("rerank_score", 0) >= self.config.threshold
            ]
            logger.debug(
                f"Filtered to {len(documents)} documents above threshold {self.config.threshold}"
            )

        # Sort by score (descending) and return top N
        ranked_docs = sorted(
            documents, key=lambda d: d.get("rerank_score", 0), reverse=True
        )

        # Update metrics
        elapsed_ms = (time.time() - start_time) * 1000
        self._total_reranks += 1
        self._total_time_ms += elapsed_ms

        logger.debug(f"Re-ranking completed in {elapsed_ms:.1f}ms")

        return ranked_docs[:top_n]

    def get_info(self) -> Dict[str, Any]:
        """
        Get re-ranker status and metrics.

        Returns:
            Dict with model info, device, metrics, etc.

        Example:
            >>> reranker = ReRanker(ReRankConfig())
            >>> info = reranker.get_info()
            >>> print(info['loaded'])
            False
            >>> reranker.rerank("test", [{"content": "doc"}])
            >>> info = reranker.get_info()
            >>> print(info['loaded'])
            True
        """
        info = {
            "model": self.config.model,
            "device": self._device if self._device else self.config.device,
            "loaded": self._model_loaded,
            "cache_enabled": self.config.cache_model,
            "batch_size": self.config.batch_size,
            "threshold": self.config.threshold,
            "metrics": {
                "total_reranks": self._total_reranks,
                "total_time_ms": round(self._total_time_ms, 1),
                "avg_time_ms": (
                    round(self._total_time_ms / self._total_reranks, 1)
                    if self._total_reranks > 0
                    else 0
                ),
            },
        }

        # Add memory usage if model is loaded
        if self._model_loaded:
            try:
                import torch

                if self._device == "mps":
                    # MPS doesn't expose memory stats directly
                    info["memory_mb"] = "~600"  # Approximate for jina-reranker-v2
                elif self._device == "cuda":
                    allocated = torch.cuda.memory_allocated(0) / (1024**2)
                    info["memory_mb"] = round(allocated, 1)
                else:
                    info["memory_mb"] = "~600"
            except Exception as e:
                logger.debug(f"Could not get memory info: {e}")
                info["memory_mb"] = "unknown"

        return info

    def unload_model(self) -> None:
        """
        Unload the model from memory.

        Useful for freeing memory when re-ranking is not needed for a while.

        Example:
            >>> reranker = ReRanker(ReRankConfig())
            >>> reranker.rerank("test", [{"content": "doc"}])
            >>> reranker.unload_model()  # Free ~600MB of memory
        """
        if self._model_loaded:
            del self._model
            self._model = None
            self._model_loaded = False
            logger.info("Re-ranker model unloaded from memory")

    def test_latency(self, num_docs: int = 25) -> Dict[str, float]:
        """
        Test re-ranking latency with dummy documents.

        Useful for benchmarking and checking device performance.

        Args:
            num_docs: Number of dummy documents to re-rank

        Returns:
            Dict with timing metrics

        Example:
            >>> reranker = ReRanker(ReRankConfig(device="mps"))
            >>> metrics = reranker.test_latency(25)
            >>> print(f"Re-rank 25 docs: {metrics['rerank_time_ms']:.0f}ms")
            Re-rank 25 docs: 156ms
        """
        logger.info(f"Testing re-ranking latency with {num_docs} documents")

        # Create dummy documents
        dummy_docs = [
            {"id": f"doc_{i}", "content": f"This is document number {i} about various topics."}
            for i in range(num_docs)
        ]

        # Warm-up (load model)
        start_load = time.time()
        _ = self.model
        load_time = (time.time() - start_load) * 1000

        # Test re-ranking
        start_rerank = time.time()
        _ = self.rerank("test query about topics", dummy_docs, top_n=5)
        rerank_time = (time.time() - start_rerank) * 1000

        metrics = {
            "num_docs": num_docs,
            "device": self._device,
            "model_load_time_ms": round(load_time, 1) if load_time > 10 else 0,
            "rerank_time_ms": round(rerank_time, 1),
            "ms_per_doc": round(rerank_time / num_docs, 2),
        }

        logger.info(f"Latency test results: {metrics}")
        return metrics
