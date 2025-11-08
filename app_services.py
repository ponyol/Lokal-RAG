"""
Application Services - Functional Core

This module contains ONLY pure functions for the business logic.
No classes, no global state, no direct I/O mutations.

All functions follow functional programming principles:
- Pure functions (same input = same output)
- Immutability (create new data structures instead of modifying)
- Composition (build complex logic from simple functions)
- Explicit dependencies (config and data are passed as parameters)

Side effects (I/O) are isolated and clearly marked.
"""

import json
import re
from pathlib import Path
from typing import Optional

import httpx
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.document import Document

from app_config import (
    AppConfig,
    RAG_SYSTEM_PROMPT,
    TAGGING_SYSTEM_PROMPT,
    TRANSLATION_SYSTEM_PROMPT,
)


# ============================================================================
# LLM Interaction
# ============================================================================


def fn_call_ollama(
    prompt: str,
    system_prompt: str,
    config: AppConfig,
) -> str:
    """
    Call the Ollama API with a user prompt and system prompt.

    This function performs an I/O side effect (HTTP request) but is otherwise pure:
    given the same inputs, it will produce the same output (assuming Ollama is deterministic).

    Args:
        prompt: The user's input text to send to the LLM
        system_prompt: The system instructions for the LLM
        config: Application configuration containing Ollama URL and model name

    Returns:
        str: The LLM's response text

    Raises:
        httpx.HTTPError: If the request to Ollama fails
        ValueError: If the response format is invalid

    Example:
        >>> config = AppConfig()
        >>> response = fn_call_ollama("Hello", "You are helpful", config)
    """
    url = f"{config.OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    with httpx.Client(timeout=config.OLLAMA_REQUEST_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()

    # Extract the message content from the response
    if "message" not in data or "content" not in data["message"]:
        raise ValueError(f"Invalid Ollama response format: {data}")

    return data["message"]["content"].strip()


def fn_check_ollama_availability(config: AppConfig) -> tuple[bool, Optional[str]]:
    """
    Check if Ollama is running and accessible.

    Args:
        config: Application configuration containing Ollama URL

    Returns:
        tuple[bool, Optional[str]]: (is_available, error_message)
            - (True, None) if Ollama is available
            - (False, error_message) if Ollama is not accessible

    Example:
        >>> config = AppConfig()
        >>> is_available, error = fn_check_ollama_availability(config)
        >>> if not is_available:
        ...     print(f"Ollama error: {error}")
    """
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/tags"
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()

        # Check if the required model is available
        data = response.json()
        models = data.get("models", [])
        model_names = [model.get("name", "") for model in models]

        if config.LLM_MODEL not in model_names:
            return (
                False,
                f"Model '{config.LLM_MODEL}' not found. Available models: {', '.join(model_names)}",
            )

        return (True, None)

    except httpx.ConnectError:
        return (False, "Cannot connect to Ollama. Is it running?")
    except httpx.TimeoutException:
        return (False, "Ollama connection timeout")
    except Exception as e:
        return (False, f"Ollama error: {str(e)}")


# ============================================================================
# PDF Processing
# ============================================================================


def fn_extract_markdown(pdf_path: Path) -> str:
    """
    Convert a PDF file to Markdown using marker-pdf.

    This function performs I/O (reading the PDF file) but is otherwise pure.

    Args:
        pdf_path: Path to the PDF file to convert

    Returns:
        str: The Markdown content extracted from the PDF

    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        Exception: If marker-pdf fails to process the file

    Example:
        >>> pdf_path = Path("document.pdf")
        >>> markdown = fn_extract_markdown(pdf_path)
    """
    try:
        # NOTE: marker-pdf is imported here to avoid loading heavy ML models
        # at module import time. This keeps startup fast.
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models

        # Load models (cached after first call)
        model_list = load_all_models()

        # Convert PDF to Markdown
        full_text, images, out_meta = convert_single_pdf(
            fname=str(pdf_path),
            model_lst=model_list,
        )

        return full_text

    except ImportError as e:
        raise ImportError(
            "marker-pdf is not installed. Run: python setup_marker.py"
        ) from e
    except FileNotFoundError as e:
        raise FileNotFoundError(f"PDF file not found: {pdf_path}") from e
    except Exception as e:
        raise Exception(f"Failed to extract Markdown from {pdf_path}: {e}") from e


# ============================================================================
# Text Transformation
# ============================================================================


def fn_translate_text(text: str, config: AppConfig) -> str:
    """
    Translate text from English to Russian using the LLM.

    This is a pure function that composes fn_call_ollama with a specific prompt.

    Args:
        text: The English text to translate
        config: Application configuration

    Returns:
        str: The translated Russian text

    Example:
        >>> config = AppConfig()
        >>> russian = fn_translate_text("Hello world", config)
    """
    return fn_call_ollama(
        prompt=text,
        system_prompt=TRANSLATION_SYSTEM_PROMPT,
        config=config,
    )


def fn_generate_tags(text: str, config: AppConfig) -> list[str]:
    """
    Generate topic tags for the given text using the LLM.

    This function composes fn_call_ollama and parses the response into a list.
    It ensures we return at most MAX_TAGS tags, with a fallback default.

    Args:
        text: The text to analyze
        config: Application configuration

    Returns:
        list[str]: A list of topic tags (1-3 items)
            Returns ["general"] if no tags could be extracted

    Example:
        >>> config = AppConfig()
        >>> tags = fn_generate_tags("Python machine learning tutorial", config)
        >>> print(tags)
        ['python', 'machine learning']
    """
    # Limit input text to first 3000 chars to avoid token limits
    sample_text = text[:3000]

    response = fn_call_ollama(
        prompt=sample_text,
        system_prompt=TAGGING_SYSTEM_PROMPT,
        config=config,
    )

    # Parse the response: extract tags separated by commas
    tags = [tag.strip().lower() for tag in response.split(",")]

    # Clean tags: remove empty strings and normalize
    tags = [re.sub(r"[^\w\s-]", "", tag) for tag in tags if tag]
    tags = [tag.replace(" ", "-") for tag in tags if tag]

    # Limit to MAX_TAGS
    tags = tags[: config.MAX_TAGS]

    # Fallback if no tags were extracted
    if not tags:
        tags = ["general"]

    return tags


# ============================================================================
# Text Chunking
# ============================================================================


def fn_create_text_chunks(text: str, source_file: str, config: AppConfig) -> list[Document]:
    """
    Split text into chunks suitable for embedding and vector storage.

    This is a pure function that uses LangChain's text splitter.

    Args:
        text: The text to split into chunks
        source_file: The name of the source file (for metadata)
        config: Application configuration containing chunk size parameters

    Returns:
        list[Document]: A list of LangChain Document objects with:
            - page_content: The chunk text
            - metadata: {"source": source_file}

    Example:
        >>> config = AppConfig()
        >>> chunks = fn_create_text_chunks("Long text...", "doc.pdf", config)
        >>> print(len(chunks))
        5
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = text_splitter.split_text(text)

    # Create Document objects with metadata
    documents = [
        Document(
            page_content=chunk,
            metadata={"source": source_file},
        )
        for chunk in chunks
    ]

    return documents


# ============================================================================
# RAG (Retrieval-Augmented Generation)
# ============================================================================


def fn_get_rag_response(
    query: str,
    retrieved_docs: list[Document],
    config: AppConfig,
) -> str:
    """
    Generate a response to a query using retrieved documents as context.

    This is a pure function that composes:
    1. Context formatting (joining retrieved documents)
    2. Prompt construction
    3. LLM call

    Args:
        query: The user's question
        retrieved_docs: Documents retrieved from the vector store
        config: Application configuration

    Returns:
        str: The LLM's answer based on the retrieved context

    Example:
        >>> config = AppConfig()
        >>> docs = [Document(page_content="Python is a programming language")]
        >>> answer = fn_get_rag_response("What is Python?", docs, config)
    """
    # Format the context from retrieved documents
    context = "\n\n".join(
        [
            f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
            for doc in retrieved_docs
        ]
    )

    # Construct the prompt
    prompt = f"""Context:
{context}

Question: {query}

Answer:"""

    # Get response from LLM
    response = fn_call_ollama(
        prompt=prompt,
        system_prompt=RAG_SYSTEM_PROMPT,
        config=config,
    )

    return response


# ============================================================================
# Utility Functions
# ============================================================================


def fn_find_pdf_files(directory: Path) -> list[Path]:
    """
    Recursively find all PDF files in a directory.

    This is a pure function (aside from the I/O of reading directory contents).

    Args:
        directory: The directory to search

    Returns:
        list[Path]: A sorted list of PDF file paths

    Example:
        >>> pdf_files = fn_find_pdf_files(Path("./documents"))
        >>> print(len(pdf_files))
        15
    """
    if not directory.exists():
        return []

    pdf_files = sorted(directory.rglob("*.pdf"))
    return list(pdf_files)
