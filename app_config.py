"""
Application Configuration Module

This module defines an immutable configuration dataclass for the Lokal-RAG application.
All settings are centralized here and passed to functions that need them.

Following functional programming principles, this configuration object is:
- Immutable (frozen=True)
- Created once at startup
- Passed explicitly to functions that need it
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """
    Immutable configuration for the Lokal-RAG application.

    Attributes:
        OLLAMA_BASE_URL: URL of the local Ollama instance
        LLM_MODEL: Name of the LLM model to use for translation, tagging, and RAG
        EMBEDDING_MODEL: Name of the HuggingFace embedding model
        VECTOR_DB_PATH: Path to the ChromaDB persistent storage
        MARKDOWN_OUTPUT_PATH: Path where processed Markdown files will be saved
        CHUNK_SIZE: Size of text chunks for vector database (in characters)
        CHUNK_OVERLAP: Overlap between consecutive chunks (in characters)
        MAX_TAGS: Maximum number of tags to generate per document
        OLLAMA_REQUEST_TIMEOUT: Timeout for Ollama API requests (in seconds)
    """

    # LLM Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b-instruct"
    OLLAMA_REQUEST_TIMEOUT: int = 300  # 5 minutes for large documents

    # Embedding Configuration
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Storage Configuration
    VECTOR_DB_PATH: Path = Path("./lokal_rag_db")
    MARKDOWN_OUTPUT_PATH: Path = Path("./output_markdown")

    # Text Processing Configuration
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200

    # Tagging Configuration
    MAX_TAGS: int = 3

    # RAG Configuration
    RAG_TOP_K: int = 4  # Number of documents to retrieve for context

    # Performance Configuration
    CLEANUP_MEMORY_AFTER_PDF: bool = True  # Free memory after batch completes (not between PDFs)

    # Web Scraping Configuration
    WEB_USE_BROWSER_COOKIES: bool = True  # Use browser cookies for authenticated requests (e.g., Medium)
    WEB_REQUEST_TIMEOUT: int = 30  # Timeout for web requests (in seconds)
    WEB_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


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
        >>> print(config.LLM_MODEL)
        'qwen2.5:7b-instruct'
    """
    return AppConfig()


# System prompts for LLM operations
# These are constants, not part of the config dataclass, as they represent
# domain knowledge rather than user-configurable settings.

TRANSLATION_SYSTEM_PROMPT = """You are a professional translator.
Translate the following text from English to Russian.
Preserve all formatting, including Markdown syntax.
Only output the translated text, no explanations or comments."""

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
