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
from dataclasses import dataclass, replace, field
from pathlib import Path
from typing import Optional, List, Dict


@dataclass(frozen=True)
class AppConfig:
    """
    Immutable configuration for the Lokal-RAG application.

    Attributes:
        LLM_PROVIDER: Which LLM provider to use for document processing ("ollama", "lmstudio", "claude", "gemini", or "mistral")
        LLM_PROVIDER_CHAT: Which LLM provider to use for chat (independent from document processing)
        OLLAMA_BASE_URL: URL of the local Ollama instance
        OLLAMA_MODEL: Name of the Ollama model to use for translation, tagging, and document processing
        LMSTUDIO_BASE_URL: URL of the local LM Studio instance
        LMSTUDIO_MODEL: Name of the LM Studio model to use for translation, tagging, and RAG
        CLAUDE_API_KEY: Anthropic API key for Claude models
        CLAUDE_MODEL: Claude model to use (claude-3-5-sonnet-20241022, claude-3-7-sonnet-20250219, claude-3-opus-20240229)
        GEMINI_API_KEY: Google API key for Gemini models
        GEMINI_MODEL: Gemini model to use (gemini-2.5-flash, gemini-2.5-pro-preview-03-25, gemini-2.0-flash-exp)
        MISTRAL_API_KEY: Mistral AI API key for Mistral models
        MISTRAL_MODEL: Mistral model to use (mistral-large-2411, mistral-small-2506, mistral-small-latest)
        LLM_REQUEST_TIMEOUT: Timeout for LLM API requests (in seconds)
        EMBEDDING_MODEL: Name of the HuggingFace embedding model
        EMBEDDING_CACHE_DIR: Directory for caching HuggingFace models (to avoid re-downloading)
        VECTOR_DB_PATH_EN: Path to the English ChromaDB persistent storage
        VECTOR_DB_PATH_RU: Path to the Russian ChromaDB persistent storage
        MARKDOWN_OUTPUT_PATH_EN: Path where English processed Markdown files will be saved
        MARKDOWN_OUTPUT_PATH_RU: Path where Russian processed Markdown files will be saved
        CHANGELOG_PATH: Path where changelog files will be saved
        NOTES_DIR: Path where user notes will be saved
        CHUNK_SIZE: Size of text chunks for vector database (in characters)
        CHUNK_OVERLAP: Overlap between consecutive chunks (in characters)
        TRANSLATION_CHUNK_SIZE: Size of text chunks for translation (in characters)
        MAX_TAGS: Maximum number of tags to generate per document
        RAG_TOP_K: Number of documents to retrieve for RAG context
        CHAT_CONTEXT_MESSAGES: Number of messages to keep in chat history context
        CHAT_SEND_KEY: Send message key ("enter" or "shift_enter")
        CLEANUP_MEMORY_AFTER_PDF: Whether to free memory after batch processing
        WEB_USE_BROWSER_COOKIES: Whether to use browser cookies for authenticated requests
        WEB_BROWSER_CHOICE: Which browser to extract cookies from
        WEB_REQUEST_TIMEOUT: Timeout for web requests (in seconds)
        WEB_USER_AGENT: User agent string for web requests
        WEB_SAVE_RAW_HTML: Whether to save raw HTML for debugging
        VISION_MODE: Vision extraction mode ("disabled", "auto", "local")
        VISION_PROVIDER: Vision provider ("ollama" or "lmstudio") for local vision model
        VISION_BASE_URL: URL of the vision provider instance
        VISION_MODEL: Name of the vision model for local extraction
        VISION_MAX_IMAGES: Maximum number of images to process per document
        PDF_CONVERSION_METHOD: PDF extraction method ("marker-pdf" or "llm-studio-ocr")
        LLM_OCR_URL: LLM Studio URL for OCR (when using llm-studio-ocr)
        LLM_OCR_MODEL: OCR model name (e.g., ocrflux-3b, deepseek-ocr)
        LLM_OCR_API_KEY: Optional API key for LLM Studio OCR
        NOTE_TEMPLATES: List of note templates with name and content
        CHAT_PROMPTS: List of chat system prompts with name and content
        CHAT_ACTIVE_PROMPT: Name of the currently active chat prompt
    """

    # LLM Configuration
    LLM_PROVIDER: str = "ollama"  # "ollama", "lmstudio", "claude", "gemini", or "mistral" (for document processing)
    LLM_PROVIDER_CHAT: str = "ollama"  # LLM provider for chat (can be different from document processing)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct"
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LMSTUDIO_MODEL: str = "meta-llama-3.1-8b-instruct"
    CLAUDE_API_KEY: str = ""  # Anthropic API key (get from https://console.anthropic.com/)
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"  # claude-3-5-sonnet-20241022, claude-3-7-sonnet-20250219, claude-3-opus-20240229
    GEMINI_API_KEY: str = ""  # Google API key (get from https://makersuite.google.com/app/apikey)
    GEMINI_MODEL: str = "gemini-2.5-flash"  # gemini-2.5-flash, gemini-2.5-pro-preview-03-25, gemini-2.0-flash-exp
    MISTRAL_API_KEY: str = ""  # Mistral AI API key (get from https://console.mistral.ai/)
    MISTRAL_MODEL: str = "mistral-small-latest"  # mistral-large-2411, mistral-small-2506, mistral-small-latest
    LLM_REQUEST_TIMEOUT: int = 300  # 5 minutes for large documents

    # Embedding Configuration
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_CACHE_DIR: Path = Path.home() / ".cache" / "huggingface" / "hub"  # HuggingFace models cache

    # Storage Configuration
    VECTOR_DB_PATH_EN: Path = Path("./chroma_db_en")  # English vector database
    VECTOR_DB_PATH_RU: Path = Path("./chroma_db_ru")  # Russian vector database
    MARKDOWN_OUTPUT_PATH_EN: Path = Path("./output_markdown/en")  # English markdown output
    MARKDOWN_OUTPUT_PATH_RU: Path = Path("./output_markdown/ru")  # Russian markdown output
    CHANGELOG_PATH: Path = Path("./changelog")  # Path for changelog files
    NOTES_DIR: Path = Path("./notes")  # Path for user notes
    DATABASE_LANGUAGE: str = "en"  # Language for database to use: "en" or "ru"

    # Text Processing Configuration
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200
    TRANSLATION_CHUNK_SIZE: int = 2000  # Size of chunks for translation (larger to preserve context)

    # Tagging Configuration
    MAX_TAGS: int = 3

    # RAG Configuration
    RAG_TOP_K: int = 20  # Number of documents to retrieve for context (increased for full document retrieval)

    # Chat Configuration
    CHAT_CONTEXT_MESSAGES: int = 10  # Number of messages to keep in chat history context
    CHAT_SEND_KEY: str = "shift_enter"  # Send message key: "enter" or "shift_enter"

    # Performance Configuration
    CLEANUP_MEMORY_AFTER_PDF: bool = True  # Free memory after batch completes (not between PDFs)

    # Web Scraping Configuration
    WEB_USE_BROWSER_COOKIES: bool = True  # Use browser cookies for authenticated requests (e.g., Medium)
    WEB_BROWSER_CHOICE: str = "chrome"  # Browser to extract cookies from: "all", "chrome", "firefox", "safari", "edge"
    WEB_REQUEST_TIMEOUT: int = 30  # Timeout for web requests (in seconds)
    WEB_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    WEB_SAVE_RAW_HTML: bool = False  # Save raw HTML for debugging (in output_markdown/_debug/)

    # Vision Configuration (Image Processing)
    VISION_MODE: str = "auto"  # "disabled", "auto" (smart fallback), or "local" (use dedicated vision provider)
    VISION_PROVIDER: str = "ollama"  # Vision provider for local mode: "ollama" or "lmstudio"
    VISION_BASE_URL: str = "http://localhost:11434"  # URL of the vision provider instance
    VISION_MODEL: str = "granite-docling:258m"  # Vision model name for local extraction
    VISION_MAX_IMAGES: int = 20  # Maximum images to process per document (to avoid excessive API calls)

    # PDF Conversion Configuration
    PDF_CONVERSION_METHOD: str = "marker-pdf"  # "marker-pdf" or "llm-studio-ocr"
    LLM_OCR_URL: str = "http://localhost:1234/v1"  # LLM Studio URL for OCR (when using llm-studio-ocr)
    LLM_OCR_MODEL: str = "ocrflux-3b"  # OCR model name (ocrflux-3b, deepseek-ocr, or any vision model)
    LLM_OCR_API_KEY: str = ""  # Optional API key for LLM Studio OCR

    # Chat Prompts Configuration
    CHAT_PROMPTS: List[Dict[str, str]] = field(default_factory=lambda: [
        {
            "name": "Default RAG Assistant",
            "content": """You are a helpful AI assistant with access to a document database.

LANGUAGE DETECTION AND RESPONSE:
- If the user's question is in RUSSIAN (Cyrillic text), you MUST:
  * Respond ONLY in Russian
  * Think about the question in Russian
  * Provide answers in Russian

- If the user's question is in ENGLISH (Latin text), you MUST:
  * Respond ONLY in English
  * Think about the question in English
  * Provide answers in English

TASK:
Answer the user's question based on the provided context from the document database.
- Use ALL available context chunks when answering
- If the context contains the answer, provide it clearly
- If the context doesn't contain enough information, say so (in the same language as the question)
- Be accurate and helpful

RESPONSE LENGTH:
- For general questions: Provide concise, focused answers
- If the user explicitly requests full content (e.g., "выведи полностью", "покажи весь документ", "show full document", "give me all details", "дай полное содержание"):
  * OUTPUT EVERYTHING from ALL available document chunks
  * Combine all chunks sequentially to reconstruct the full document
  * Include ALL text from ALL chunks - DO NOT summarize or omit anything
  * Preserve structure, headings, lists, and formatting from the source
  * If you have 10, 20, or more chunks - use them ALL

IMPORTANT:
- The document chunks you receive are parts of the SAME document
- When asked for "full content", you MUST output ALL chunks combined
- Always match your response language to the user's question language!"""
        }
    ])
    CHAT_ACTIVE_PROMPT: str = "Default RAG Assistant"  # Name of the currently active chat prompt

    # Notes Templates Configuration
    NOTE_TEMPLATES: List[Dict[str, str]] = field(default_factory=lambda: [
        {
            "name": "Meeting Notes",
            "content": "📋 Meeting Notes\n\nAttendees:\n- \n\nAgenda:\n- \n\nAction Items:\n- "
        },
        {
            "name": "Daily Log",
            "content": "📅 Daily Log\n\nCompleted:\n- \n\nIn Progress:\n- \n\nBlocked:\n- "
        }
    ])


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


def get_settings_path(location: str = "home") -> Path:
    """
    Get the path to the settings file based on location choice.

    Args:
        location: Either "home" for ~/.lokal-rag/settings.json
                  or "project" for .lokal-rag/settings.json

    Returns:
        Path: Path to the settings file

    Example:
        >>> home_path = get_settings_path("home")
        >>> print(home_path)
        /home/user/.lokal-rag/settings.json

        >>> project_path = get_settings_path("project")
        >>> print(project_path)
        /path/to/project/.lokal-rag/settings.json
    """
    if location == "project":
        # Project-local settings (relative to current working directory)
        settings_dir = Path.cwd() / ".lokal-rag"
    else:  # "home" is default
        # User home settings
        settings_dir = Path.home() / ".lokal-rag"

    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "settings.json"


def load_settings_from_json(location: str = "home") -> dict:
    """
    Load LLM settings from JSON file.

    Args:
        location: Either "home" for ~/.lokal-rag/settings.json
                  or "project" for .lokal-rag/settings.json

    Returns:
        dict: Settings dictionary, or empty dict if file doesn't exist

    Example:
        >>> settings = load_settings_from_json("home")
        >>> print(settings.get("llm_provider", "ollama"))

        >>> settings = load_settings_from_json("project")
        >>> print(settings.get("llm_provider", "ollama"))
    """
    settings_path = get_settings_path(location)

    if not settings_path.exists():
        return {}

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load settings from {settings_path}: {e}")
        return {}


def save_config_location_preference(location: str) -> None:
    """
    Save user's config location preference for persistence across sessions.

    This saves the user's choice of config location (home vs project) to a
    special file so the application can remember it on next startup.

    Args:
        location: Either "home" or "project"

    Example:
        >>> save_config_location_preference("project")
        # Next app startup will load from project location
    """
    from pathlib import Path

    # Save preference to home directory (always)
    preference_file = Path.home() / ".lokal-rag-location"

    try:
        with open(preference_file, "w", encoding="utf-8") as f:
            f.write(location)
    except Exception as e:
        print(f"Warning: Failed to save config location preference: {e}")


def load_config_location_preference() -> str:
    """
    Load user's saved config location preference.

    Returns:
        str: Either "home" or "project" (defaults to "home" if not set)

    Example:
        >>> location = load_config_location_preference()
        >>> settings = load_settings_from_json(location)
    """
    from pathlib import Path

    preference_file = Path.home() / ".lokal-rag-location"

    if not preference_file.exists():
        return "home"  # Default

    try:
        with open(preference_file, "r", encoding="utf-8") as f:
            location = f.read().strip()
            # Validate
            if location in ["home", "project"]:
                return location
            else:
                return "home"
    except Exception as e:
        print(f"Warning: Failed to load config location preference: {e}")
        return "home"


def save_settings_to_json(settings: dict, location: str = "home") -> None:
    """
    Save LLM settings to JSON file.

    Args:
        settings: Settings dictionary to save
        location: Either "home" for ~/.lokal-rag/settings.json
                  or "project" for .lokal-rag/settings.json

    Example:
        >>> settings = {
        ...     "llm_provider": "ollama",
        ...     "ollama_model": "qwen2.5:7b-instruct"
        ... }
        >>> save_settings_to_json(settings, "home")
    """
    settings_path = get_settings_path(location)

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

    if "llm_provider_chat" in settings:
        overrides["LLM_PROVIDER_CHAT"] = settings["llm_provider_chat"]

    if "ollama_base_url" in settings:
        overrides["OLLAMA_BASE_URL"] = settings["ollama_base_url"]

    if "ollama_model" in settings:
        overrides["OLLAMA_MODEL"] = settings["ollama_model"]

    if "lmstudio_base_url" in settings:
        overrides["LMSTUDIO_BASE_URL"] = settings["lmstudio_base_url"]

    if "lmstudio_model" in settings:
        overrides["LMSTUDIO_MODEL"] = settings["lmstudio_model"]

    if "claude_api_key" in settings:
        overrides["CLAUDE_API_KEY"] = settings["claude_api_key"]

    if "claude_model" in settings:
        overrides["CLAUDE_MODEL"] = settings["claude_model"]

    if "gemini_api_key" in settings:
        overrides["GEMINI_API_KEY"] = settings["gemini_api_key"]

    if "gemini_model" in settings:
        overrides["GEMINI_MODEL"] = settings["gemini_model"]

    if "mistral_api_key" in settings:
        overrides["MISTRAL_API_KEY"] = settings["mistral_api_key"]

    if "mistral_model" in settings:
        overrides["MISTRAL_MODEL"] = settings["mistral_model"]

    if "timeout" in settings:
        overrides["LLM_REQUEST_TIMEOUT"] = settings["timeout"]

    if "translation_chunk_size" in settings:
        overrides["TRANSLATION_CHUNK_SIZE"] = settings["translation_chunk_size"]

    if "embedding_cache_dir" in settings:
        overrides["EMBEDDING_CACHE_DIR"] = Path(settings["embedding_cache_dir"])

    if "vector_db_path_en" in settings:
        overrides["VECTOR_DB_PATH_EN"] = Path(settings["vector_db_path_en"])

    if "vector_db_path_ru" in settings:
        overrides["VECTOR_DB_PATH_RU"] = Path(settings["vector_db_path_ru"])

    # Markdown output paths (separate for EN and RU)
    if "markdown_output_path_en" in settings:
        overrides["MARKDOWN_OUTPUT_PATH_EN"] = Path(settings["markdown_output_path_en"])

    if "markdown_output_path_ru" in settings:
        overrides["MARKDOWN_OUTPUT_PATH_RU"] = Path(settings["markdown_output_path_ru"])

    # Backward compatibility: if old single path exists, use it for both
    if "markdown_output_path" in settings and "markdown_output_path_en" not in settings:
        base_path = Path(settings["markdown_output_path"])
        overrides["MARKDOWN_OUTPUT_PATH_EN"] = base_path / "en"
        overrides["MARKDOWN_OUTPUT_PATH_RU"] = base_path / "ru"

    if "changelog_path" in settings:
        overrides["CHANGELOG_PATH"] = Path(settings["changelog_path"])

    if "notes_path" in settings:
        overrides["NOTES_DIR"] = Path(settings["notes_path"])

    if "database_language" in settings:
        overrides["DATABASE_LANGUAGE"] = settings["database_language"]

    # Vision settings
    if "vision_mode" in settings:
        overrides["VISION_MODE"] = settings["vision_mode"]

    if "vision_provider" in settings:
        overrides["VISION_PROVIDER"] = settings["vision_provider"]

    if "vision_base_url" in settings:
        overrides["VISION_BASE_URL"] = settings["vision_base_url"]

    if "vision_model" in settings:
        overrides["VISION_MODEL"] = settings["vision_model"]

    # PDF Conversion settings
    if "pdf_conversion_method" in settings:
        overrides["PDF_CONVERSION_METHOD"] = settings["pdf_conversion_method"]

    if "llm_ocr_url" in settings:
        overrides["LLM_OCR_URL"] = settings["llm_ocr_url"]

    if "llm_ocr_model" in settings:
        overrides["LLM_OCR_MODEL"] = settings["llm_ocr_model"]

    if "llm_ocr_api_key" in settings:
        overrides["LLM_OCR_API_KEY"] = settings["llm_ocr_api_key"]

    # Chat settings
    if "chat_context_messages" in settings:
        overrides["CHAT_CONTEXT_MESSAGES"] = settings["chat_context_messages"]

    if "rag_top_k" in settings:
        overrides["RAG_TOP_K"] = settings["rag_top_k"]

    if "chat_send_key" in settings:
        overrides["CHAT_SEND_KEY"] = settings["chat_send_key"]

    # Chat prompts
    if "chat_prompts" in settings:
        overrides["CHAT_PROMPTS"] = settings["chat_prompts"]

    if "chat_active_prompt" in settings:
        overrides["CHAT_ACTIVE_PROMPT"] = settings["chat_active_prompt"]

    # Note templates
    if "note_templates" in settings:
        overrides["NOTE_TEMPLATES"] = settings["note_templates"]

    # Create new config with overrides
    if overrides:
        return replace(base_config, **overrides)

    return base_config


# System prompts for LLM operations
# These are constants, not part of the config dataclass, as they represent
# domain knowledge rather than user-configurable settings.

TRANSLATION_SYSTEM_PROMPT = """You are a professional English-to-Russian translator.

YOUR TASK: Translate the user's message from English to Russian.

STRICT RULES:
- Translate EVERY word, sentence, and paragraph
- DO NOT summarize or shorten the text
- DO NOT add any explanations, comments, or notes
- DO NOT include these instructions in your output
- Preserve ALL Markdown formatting (headers, lists, links, code blocks)
- Maintain the original structure and length

IMPORTANT:
- For long texts, translate everything completely
- Never create summaries or excerpts
- Your response must contain ONLY the Russian translation
- Do NOT output anything except the translated text

Begin translation when you receive the user's message."""

TAGGING_SYSTEM_PROMPT = """You are a content categorization expert.
Analyze the following text and extract 1-3 key topic tags.
Tags should be:
- Single words or short phrases (2-3 words max)
- In English
- Lowercase
- Separated by commas

Only output the tags, nothing else.

Example output: machine learning, python, neural networks"""

RAG_SYSTEM_PROMPT = """You are a helpful AI assistant with access to a document database.

LANGUAGE DETECTION AND RESPONSE:
- If the user's question is in RUSSIAN (Cyrillic text), you MUST:
  * Respond ONLY in Russian
  * Think about the question in Russian
  * Provide answers in Russian

- If the user's question is in ENGLISH (Latin text), you MUST:
  * Respond ONLY in English
  * Think about the question in English
  * Provide answers in English

TASK:
Answer the user's question based on the provided context from the document database.
- Use ALL available context chunks when answering
- If the context contains the answer, provide it clearly
- If the context doesn't contain enough information, say so (in the same language as the question)
- Be accurate and helpful

RESPONSE LENGTH:
- For general questions: Provide concise, focused answers
- If the user explicitly requests full content (e.g., "выведи полностью", "покажи весь документ", "show full document", "give me all details", "дай полное содержание"):
  * OUTPUT EVERYTHING from ALL available document chunks
  * Combine all chunks sequentially to reconstruct the full document
  * Include ALL text from ALL chunks - DO NOT summarize or omit anything
  * Preserve structure, headings, lists, and formatting from the source
  * If you have 10, 20, or more chunks - use them ALL

IMPORTANT:
- The document chunks you receive are parts of the SAME document
- When asked for "full content", you MUST output ALL chunks combined
- Always match your response language to the user's question language!"""

VISION_SYSTEM_PROMPT = """You are an expert at analyzing images from documents.

YOUR TASK: Describe the image in detail, extracting ALL useful information.

FOCUS ON:
- Text content (if any): Transcribe it exactly
- Code snippets: Extract the code
- Diagrams/Charts: Explain what they show and the relationships
- Tables: Describe the structure and data
- Screenshots: Describe the content and UI elements
- Technical drawings: Explain the components and connections

OUTPUT FORMAT:
Provide a clear, detailed description in English that captures all information in the image.
If the image contains text, include it verbatim.
Be thorough - this description will be used for search and retrieval.

DO NOT add commentary about the image quality or format. Focus only on the content."""

SUMMARY_SYSTEM_PROMPT = """You are an expert at creating concise document summaries.

YOUR TASK: Create a brief summary of the provided document in RUSSIAN.

REQUIREMENTS:
- Summary must be in RUSSIAN language (на русском языке)
- Length: 1-2 sentences maximum
- Capture the main topic and key information
- Be concise and informative
- Do NOT include any preamble or meta-commentary
- Output ONLY the summary text

Example good summaries:
- "Статья о машинном обучении, рассматривает алгоритмы supervised learning и применение нейронных сетей."
- "Руководство по настройке Docker контейнеров для production окружения с примерами конфигураций."
- "Обзор архитектурных паттернов микросервисов и best practices для их развертывания."""
