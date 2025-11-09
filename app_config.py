"""
Application Configuration Module

This module defines an immutable configuration dataclass for the Lokal-RAG application.
All settings are centralized here and passed to functions that need them.

Following functional programming principles, this configuration object is:
- Immutable (frozen=True)
- Created once at startup
- Passed explicitly to functions that need it

Settings can be persisted to and loaded from ~/.lokal-rag/settings.json
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    """
    Immutable configuration for the Lokal-RAG application.

    Attributes:
        LLM_PROVIDER: Which LLM provider to use ("ollama" or "lmstudio")
        OLLAMA_BASE_URL: URL of the local Ollama instance
        OLLAMA_MODEL: Name of the Ollama model to use for translation, tagging, and RAG
        LMSTUDIO_BASE_URL: URL of the local LM Studio instance
        LMSTUDIO_MODEL: Name of the LM Studio model to use for translation, tagging, and RAG
        LLM_REQUEST_TIMEOUT: Timeout for LLM API requests (in seconds)
        EMBEDDING_MODEL: Name of the HuggingFace embedding model
        VECTOR_DB_PATH: Path to the ChromaDB persistent storage
        MARKDOWN_OUTPUT_PATH: Path where processed Markdown files will be saved
        CHUNK_SIZE: Size of text chunks for vector database (in characters)
        CHUNK_OVERLAP: Overlap between consecutive chunks (in characters)
        TRANSLATION_CHUNK_SIZE: Size of text chunks for translation (in characters)
        MAX_TAGS: Maximum number of tags to generate per document
        RAG_TOP_K: Number of documents to retrieve for RAG context
        CLEANUP_MEMORY_AFTER_PDF: Whether to free memory after batch processing
        WEB_USE_BROWSER_COOKIES: Whether to use browser cookies for authenticated requests
        WEB_BROWSER_CHOICE: Which browser to extract cookies from
        WEB_REQUEST_TIMEOUT: Timeout for web requests (in seconds)
        WEB_USER_AGENT: User agent string for web requests
        WEB_SAVE_RAW_HTML: Whether to save raw HTML for debugging
    """

    # LLM Configuration
    LLM_PROVIDER: str = "ollama"  # "ollama" or "lmstudio"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct"
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LMSTUDIO_MODEL: str = "meta-llama-3.1-8b-instruct"
    LLM_REQUEST_TIMEOUT: int = 300  # 5 minutes for large documents

    # Embedding Configuration
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Storage Configuration
    VECTOR_DB_PATH: Path = Path("./lokal_rag_db")
    MARKDOWN_OUTPUT_PATH: Path = Path("./output_markdown")

    # Text Processing Configuration
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200
    TRANSLATION_CHUNK_SIZE: int = 2000  # Size of chunks for translation (larger to preserve context)

    # Tagging Configuration
    MAX_TAGS: int = 3

    # RAG Configuration
    RAG_TOP_K: int = 4  # Number of documents to retrieve for context

    # Performance Configuration
    CLEANUP_MEMORY_AFTER_PDF: bool = True  # Free memory after batch completes (not between PDFs)

    # Web Scraping Configuration
    WEB_USE_BROWSER_COOKIES: bool = True  # Use browser cookies for authenticated requests (e.g., Medium)
    WEB_BROWSER_CHOICE: str = "chrome"  # Browser to extract cookies from: "all", "chrome", "firefox", "safari", "edge"
    WEB_REQUEST_TIMEOUT: int = 30  # Timeout for web requests (in seconds)
    WEB_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    WEB_SAVE_RAW_HTML: bool = False  # Save raw HTML for debugging (in output_markdown/_debug/)


def create_default_config() -> AppConfig:
    """
    Factory function to create a default configuration instance.

    This function provides a clear entry point for configuration creation
    and can be extended to support loading from environment variables or
    configuration files in the future.

    Returns:
        AppConfig: An immutable configuration object with default values

    Example:
        >>> config = create_default_config()
        >>> print(config.OLLAMA_MODEL)
        'qwen2.5:7b-instruct'
    """
    return AppConfig()


def get_settings_path() -> Path:
    """
    Get the path to the settings file.

    Returns:
        Path: Path to ~/.lokal-rag/settings.json
    """
    settings_dir = Path.home() / ".lokal-rag"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "settings.json"


def load_settings_from_json() -> dict:
    """
    Load LLM settings from JSON file.

    Returns:
        dict: Settings dictionary, or empty dict if file doesn't exist

    Example:
        >>> settings = load_settings_from_json()
        >>> print(settings.get("llm_provider", "ollama"))
    """
    settings_path = get_settings_path()

    if not settings_path.exists():
        return {}

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load settings from {settings_path}: {e}")
        return {}


def save_settings_to_json(settings: dict) -> None:
    """
    Save LLM settings to JSON file.

    Args:
        settings: Settings dictionary to save

    Example:
        >>> settings = {
        ...     "llm_provider": "ollama",
        ...     "ollama_model": "qwen2.5:7b-instruct"
        ... }
        >>> save_settings_to_json(settings)
    """
    settings_path = get_settings_path()

    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to save settings to {settings_path}: {e}")


def create_config_from_settings(settings: Optional[dict] = None) -> AppConfig:
    """
    Create AppConfig instance from saved settings.

    Loads settings from JSON if not provided, merges with defaults.

    Args:
        settings: Optional settings dict (if None, loads from file)

    Returns:
        AppConfig: Configuration with user settings applied

    Example:
        >>> config = create_config_from_settings()
        >>> print(config.LLM_PROVIDER)
        'ollama'
    """
    if settings is None:
        settings = load_settings_from_json()

    # Start with defaults
    base_config = create_default_config()

    # Override with saved settings
    overrides = {}

    if "llm_provider" in settings:
        overrides["LLM_PROVIDER"] = settings["llm_provider"]

    if "ollama_base_url" in settings:
        overrides["OLLAMA_BASE_URL"] = settings["ollama_base_url"]

    if "ollama_model" in settings:
        overrides["OLLAMA_MODEL"] = settings["ollama_model"]

    if "lmstudio_base_url" in settings:
        overrides["LMSTUDIO_BASE_URL"] = settings["lmstudio_base_url"]

    if "lmstudio_model" in settings:
        overrides["LMSTUDIO_MODEL"] = settings["lmstudio_model"]

    if "timeout" in settings:
        overrides["LLM_REQUEST_TIMEOUT"] = settings["timeout"]

    if "translation_chunk_size" in settings:
        overrides["TRANSLATION_CHUNK_SIZE"] = settings["translation_chunk_size"]

    # Create new config with overrides
    if overrides:
        return replace(base_config, **overrides)

    return base_config


# System prompts for LLM operations
# These are constants, not part of the config dataclass, as they represent
# domain knowledge rather than user-configurable settings.

TRANSLATION_SYSTEM_PROMPT = """You are a professional translator. Your ONLY task is to translate text word-for-word.

CRITICAL RULES:
1. Translate EVERY word from English to Russian
2. DO NOT summarize, shorten, or skip any content
3. DO NOT add explanations or commentary
4. Preserve ALL formatting (Markdown, links, code blocks, etc.)
5. Keep the same length and structure as the original

If you receive a long text, translate it completely. Never create a summary.

Output ONLY the translated Russian text, nothing else."""

TAGGING_SYSTEM_PROMPT = """You are a content categorization expert.
Analyze the following text and extract 1-3 key topic tags.
Tags should be:
- Single words or short phrases (2-3 words max)
- In English
- Lowercase
- Separated by commas

Only output the tags, nothing else.

Example output: machine learning, python, neural networks"""

RAG_SYSTEM_PROMPT = """You are a helpful AI assistant.
Answer the user's question based on the provided context.
If the context doesn't contain enough information to answer the question, say so.
Be concise and accurate."""
