"""
MCP Server Configuration

Extends the base AppConfig with MCP-specific settings, particularly for re-ranking.
Follows functional programming principles with immutable configuration.
"""

import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReRankConfig:
    """
    Configuration for the re-ranking feature.

    Attributes:
        enabled: Enable/disable re-ranking globally
        model: Re-ranker model name (HuggingFace model ID)
        device: Device to use ("auto", "cpu", "mps", "cuda")
        default_top_k: Default number of candidates to retrieve in Stage 1
        default_top_n: Default number of results to return after re-ranking
        batch_size: Batch size for re-ranking
        cache_model: Keep model in memory after loading
        threshold: Minimum re-rank score to include in results (0-1)
    """

    enabled: bool = True
    model: str = "jinaai/jina-reranker-v2-base-multilingual"
    device: str = "auto"
    default_top_k: int = 25
    default_top_n: int = 5
    batch_size: int = 16
    cache_model: bool = True
    threshold: float = 0.0


@dataclass(frozen=True)
class MCPConfig:
    """
    MCP Server-specific configuration.

    Extends base configuration with MCP-specific settings.

    Attributes:
        rerank: Re-ranking configuration
        log_level: Logging level ("DEBUG", "INFO", "WARNING", "ERROR")
        log_format: Log format ("json" for structured logging, "text" for human-readable)
        enable_metrics: Enable performance metrics collection
        cache_ttl: Cache TTL in seconds (0 = no cache)
    """

    rerank: ReRankConfig = ReRankConfig()
    log_level: str = "INFO"
    log_format: str = "json"
    enable_metrics: bool = True
    cache_ttl: int = 0  # Disabled by default


def create_default_mcp_config() -> MCPConfig:
    """
    Factory function to create a default MCP configuration.

    Returns:
        MCPConfig: An immutable MCP configuration object with default values

    Example:
        >>> config = create_default_mcp_config()
        >>> print(config.rerank.enabled)
        True
    """
    return MCPConfig()


def load_mcp_config_from_json(settings_path: Optional[Path] = None) -> MCPConfig:
    """
    Load MCP configuration from JSON settings file.

    Args:
        settings_path: Path to settings file (if None, uses ~/.lokal-rag/settings.json)

    Returns:
        MCPConfig: Configuration loaded from file, with defaults for missing values

    Example:
        >>> config = load_mcp_config_from_json()
        >>> print(config.rerank.model)
        'jinaai/jina-reranker-v2-base-multilingual'
    """
    if settings_path is None:
        settings_path = Path.home() / ".lokal-rag" / "settings.json"

    if not settings_path.exists():
        logger.info(f"Settings file not found at {settings_path}, using defaults")
        return create_default_mcp_config()

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load settings from {settings_path}: {e}")
        return create_default_mcp_config()

    # Extract re-ranking settings
    rerank_settings = settings.get("rerank", {})
    rerank_config = ReRankConfig(
        enabled=rerank_settings.get("enabled", True),
        model=rerank_settings.get(
            "model", "jinaai/jina-reranker-v2-base-multilingual"
        ),
        device=rerank_settings.get("device", "auto"),
        default_top_k=rerank_settings.get("default_top_k", 25),
        default_top_n=rerank_settings.get("default_top_n", 5),
        batch_size=rerank_settings.get("batch_size", 16),
        cache_model=rerank_settings.get("cache_model", True),
        threshold=rerank_settings.get("threshold", 0.0),
    )

    # Extract MCP settings
    mcp_settings = settings.get("mcp", {})
    mcp_config = MCPConfig(
        rerank=rerank_config,
        log_level=mcp_settings.get("log_level", "INFO"),
        log_format=mcp_settings.get("log_format", "json"),
        enable_metrics=mcp_settings.get("enable_metrics", True),
        cache_ttl=mcp_settings.get("cache_ttl", 0),
    )

    logger.info(f"Loaded MCP configuration from {settings_path}")
    logger.debug(f"Re-ranking enabled: {mcp_config.rerank.enabled}")
    logger.debug(f"Re-ranker model: {mcp_config.rerank.model}")
    logger.debug(f"Re-ranker device: {mcp_config.rerank.device}")

    return mcp_config


def save_mcp_config_to_json(
    mcp_config: MCPConfig, settings_path: Optional[Path] = None
) -> None:
    """
    Save MCP configuration to JSON settings file.

    WARNING: This merges with existing settings, does not overwrite entire file.

    Args:
        mcp_config: MCP configuration to save
        settings_path: Path to settings file (if None, uses ~/.lokal-rag/settings.json)

    Example:
        >>> config = create_default_mcp_config()
        >>> config = replace(config, rerank=replace(config.rerank, enabled=False))
        >>> save_mcp_config_to_json(config)
    """
    if settings_path is None:
        settings_path = Path.home() / ".lokal-rag" / "settings.json"

    # Ensure directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing settings
    existing_settings = {}
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                existing_settings = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load existing settings: {e}")

    # Update with MCP settings
    existing_settings["rerank"] = {
        "enabled": mcp_config.rerank.enabled,
        "model": mcp_config.rerank.model,
        "device": mcp_config.rerank.device,
        "default_top_k": mcp_config.rerank.default_top_k,
        "default_top_n": mcp_config.rerank.default_top_n,
        "batch_size": mcp_config.rerank.batch_size,
        "cache_model": mcp_config.rerank.cache_model,
        "threshold": mcp_config.rerank.threshold,
    }

    existing_settings["mcp"] = {
        "log_level": mcp_config.log_level,
        "log_format": mcp_config.log_format,
        "enable_metrics": mcp_config.enable_metrics,
        "cache_ttl": mcp_config.cache_ttl,
    }

    # Save to file
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(existing_settings, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved MCP configuration to {settings_path}")
    except Exception as e:
        logger.error(f"Failed to save settings to {settings_path}: {e}")
        raise


def setup_logging(mcp_config: MCPConfig) -> None:
    """
    Setup structured logging based on MCP configuration.

    Configures:
    - Log level
    - JSON structured logging (if log_format="json")
    - Human-readable text logging (if log_format="text")

    Args:
        mcp_config: MCP configuration with logging settings

    Example:
        >>> config = create_default_mcp_config()
        >>> setup_logging(config)
    """
    log_level = getattr(logging, mcp_config.log_level.upper(), logging.INFO)

    if mcp_config.log_format == "json":
        # JSON structured logging with additional context fields
        logging.basicConfig(
            level=log_level,
            format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "function": "%(funcName)s", '
            '"line": %(lineno)d, "message": "%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        # Human-readable text logging
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    logger.info(f"Logging configured: level={mcp_config.log_level}, format={mcp_config.log_format}")
