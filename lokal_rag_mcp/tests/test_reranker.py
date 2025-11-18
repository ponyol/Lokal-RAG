"""
Tests for re-ranker module
"""

import pytest
from lokal_rag_mcp.config import ReRankConfig
from lokal_rag_mcp.reranker import ReRanker


def test_reranker_initialization():
    """Test ReRanker initialization."""
    config = ReRankConfig(device="cpu")  # Force CPU for testing
    reranker = ReRanker(config)

    assert reranker.config == config
    assert reranker._model is None  # Model not loaded yet (lazy loading)
    assert reranker._model_loaded is False


def test_reranker_device_detection():
    """Test device auto-detection."""
    config = ReRankConfig(device="auto")
    reranker = ReRanker(config)

    device = reranker._detect_device()
    assert device in ["cpu", "mps", "cuda"]


def test_reranker_explicit_device():
    """Test explicit device configuration."""
    config = ReRankConfig(device="cpu")
    reranker = ReRanker(config)

    device = reranker._detect_device()
    assert device == "cpu"


@pytest.mark.slow
def test_reranker_basic_ranking():
    """Test basic re-ranking functionality.

    NOTE: This test loads the model (~600MB) and may take a few seconds.
    """
    config = ReRankConfig(device="cpu", cache_model=False)
    reranker = ReRanker(config)

    query = "machine learning optimization"
    docs = [
        {"id": "1", "content": "Machine learning uses gradient descent for optimization."},
        {"id": "2", "content": "The cat sat on the mat."},
        {"id": "3", "content": "Adam optimizer is a popular optimization algorithm."},
    ]

    results = reranker.rerank(query, docs, top_n=2, return_scores=True)

    # Should return 2 results
    assert len(results) == 2

    # Results should be ranked (first should have higher score)
    assert results[0]["rerank_score"] >= results[1]["rerank_score"]

    # ML-related docs should rank higher than cat doc
    assert results[0]["id"] in ["1", "3"]
    assert results[1]["id"] in ["1", "3"]

    # All results should have reranked flag
    for r in results:
        assert r["reranked"] is True
        assert "rerank_score" in r


def test_reranker_empty_documents():
    """Test re-ranking with empty document list."""
    config = ReRankConfig(device="cpu")
    reranker = ReRanker(config)

    results = reranker.rerank("test query", [], top_n=5)

    assert results == []


def test_reranker_threshold_filtering():
    """Test threshold filtering (requires model load)."""
    # Skip if model not available
    pytest.skip("Requires model loading, use @pytest.mark.slow")


def test_reranker_get_info():
    """Test getting re-ranker information."""
    config = ReRankConfig(device="cpu", batch_size=32)
    reranker = ReRanker(config)

    info = reranker.get_info()

    assert info["model"] == config.model
    assert info["device"] in ["cpu", "auto"]
    assert info["loaded"] is False
    assert info["batch_size"] == 32
    assert "metrics" in info


@pytest.mark.slow
def test_reranker_test_latency():
    """Test latency benchmarking (requires model load)."""
    config = ReRankConfig(device="cpu", cache_model=False)
    reranker = ReRanker(config)

    metrics = reranker.test_latency(num_docs=10)

    assert "num_docs" in metrics
    assert metrics["num_docs"] == 10
    assert "device" in metrics
    assert "rerank_time_ms" in metrics
    assert metrics["rerank_time_ms"] > 0
