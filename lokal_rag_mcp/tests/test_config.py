"""
Tests for configuration module
"""

import pytest
from lokal_rag_mcp.config import (
    ReRankConfig,
    MCPConfig,
    create_default_mcp_config,
)


def test_rerank_config_defaults():
    """Test ReRankConfig default values."""
    config = ReRankConfig()

    assert config.enabled is True
    assert config.model == "jinaai/jina-reranker-v2-base-multilingual"
    assert config.device == "auto"
    assert config.default_top_k == 25
    assert config.default_top_n == 5
    assert config.batch_size == 16
    assert config.cache_model is True
    assert config.threshold == 0.0


def test_rerank_config_custom():
    """Test ReRankConfig with custom values."""
    config = ReRankConfig(
        enabled=False, device="cpu", default_top_k=50, default_top_n=10, batch_size=32
    )

    assert config.enabled is False
    assert config.device == "cpu"
    assert config.default_top_k == 50
    assert config.default_top_n == 10
    assert config.batch_size == 32


def test_mcp_config_defaults():
    """Test MCPConfig default values."""
    config = MCPConfig()

    assert config.log_level == "INFO"
    assert config.log_format == "json"
    assert config.enable_metrics is True
    assert config.cache_ttl == 0
    assert isinstance(config.rerank, ReRankConfig)


def test_create_default_mcp_config():
    """Test factory function for creating default config."""
    config = create_default_mcp_config()

    assert isinstance(config, MCPConfig)
    assert isinstance(config.rerank, ReRankConfig)
    assert config.rerank.enabled is True


def test_config_immutability():
    """Test that configs are immutable (frozen=True)."""
    config = create_default_mcp_config()

    with pytest.raises(AttributeError):
        config.log_level = "DEBUG"  # Should raise error

    with pytest.raises(AttributeError):
        config.rerank.enabled = False  # Should raise error
