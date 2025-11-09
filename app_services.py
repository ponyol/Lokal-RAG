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

import gc
import json
import logging
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


# Configure logging for this module
logger = logging.getLogger(__name__)


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

    IMPORTANT: This function uses aggressive OCR settings to handle PDFs with
    corrupted or missing text layers (common with Medium articles saved as PDF).

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
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Configure marker-pdf for aggressive OCR
        # This strips existing (potentially corrupted) OCR and re-OCRs everything
        config_dict = {
            "output_format": "markdown",
            "force_ocr": True,  # Force OCR on all pages
            "strip_existing_ocr": True,  # Remove existing OCR text and re-OCR
        }

        # Create config parser
        try:
            config_parser = ConfigParser(config_dict)

            # Create converter with enhanced OCR settings
            converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=create_model_dict(),
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
            )
        except Exception as e:
            # Fallback to basic config if ConfigParser fails
            # (for older versions of marker-pdf)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"ConfigParser failed, using basic config: {e}")

            converter = PdfConverter(
                artifact_dict=create_model_dict(),
            )

        # Convert PDF to rendered format
        rendered = converter(str(pdf_path))

        # Extract text from rendered output
        text, metadata, images = text_from_rendered(rendered)

        # Validate extracted text
        if not text or len(text.strip()) < 100:
            raise ValueError(
                f"Extracted text is too short ({len(text)} chars). "
                "PDF may be corrupted or contain only images."
            )

        return text

    except ImportError as e:
        raise ImportError(
            "marker-pdf is not installed. Run: python setup_marker.py"
        ) from e
    except FileNotFoundError as e:
        raise
    except Exception as e:
        raise Exception(f"Failed to extract Markdown from {pdf_path}: {e}") from e


def fn_cleanup_pdf_memory() -> None:
    """
    Force garbage collection to free memory after PDF batch processing.

    marker-pdf loads large ML models (~5-6GB) that stay in memory.
    This function should be called AFTER processing ALL PDFs, not between them.

    IMPORTANT: Do NOT call this between PDFs in a batch!
    - Causes crashes (trace trap) on Apple Silicon with marker-pdf
    - Models need to stay loaded during batch for stability
    - Only safe to call after entire batch completes

    On a MacBook with 16GB RAM, this can reduce memory from 14GB to ~4GB.

    Example:
        >>> for pdf in pdf_files:
        ...     markdown = fn_extract_markdown(pdf)
        ...     # Process markdown...
        >>> fn_cleanup_pdf_memory()  # Free ~10GB of RAM AFTER all PDFs
    """
    gc.collect()  # Force Python garbage collection

    # Try to clear PyTorch CUDA/MPS cache if available
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        # Note: MPS (Apple Silicon GPU) cache clearing is not supported yet
        # See: https://github.com/pytorch/pytorch/issues/82218
    except ImportError:
        pass  # PyTorch not installed or not needed


# ============================================================================
# Web Article Extraction
# ============================================================================


def fn_fetch_web_article(url: str, config: AppConfig) -> str:
    """
    Fetch, authenticate, clean, and convert a web article to Markdown.

    This function:
    1. Optionally loads browser cookies for authentication (Medium, paywalled sites)
    2. Fetches the HTML content
    3. Extracts the main article content using readability
    4. Converts to Markdown

    Works with authenticated sites (Medium) and public sites (blogs, news).

    Args:
        url: The URL of the article to fetch
        config: Application configuration

    Returns:
        str: The article content in Markdown format

    Raises:
        Exception: If fetching or parsing fails

    Example:
        >>> config = AppConfig()
        >>> md = fn_fetch_web_article("https://medium.com/...", config)
    """
    try:
        # Import web scraping libraries here (lazy loading)
        import browser_cookie3
        from markdownify import markdownify as md
        from readability import Document

        # Extract domain for cookie filtering
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        # Step 1: Prepare cookies (if enabled)
        cookies = None
        if config.WEB_USE_BROWSER_COOKIES:
            try:
                logger.info(f"Attempting to load browser cookies for domain: {domain}")
                logger.info(f"Browser choice: {config.WEB_BROWSER_CHOICE}")

                # Select browser function based on config
                browser_map = {
                    "chrome": browser_cookie3.chrome,
                    "firefox": browser_cookie3.firefox,
                    "safari": browser_cookie3.safari,
                    "edge": browser_cookie3.edge,
                    "all": browser_cookie3.load,
                }

                browser_func = browser_map.get(config.WEB_BROWSER_CHOICE.lower(), browser_cookie3.load)
                browser_name = config.WEB_BROWSER_CHOICE.capitalize()

                try:
                    # Extract base domain for sites like Medium (user.medium.com -> medium.com)
                    # This is important because authentication cookies are often stored on parent domain
                    parts = domain.split('.')
                    base_domain = None
                    if len(parts) >= 3:  # subdomain.example.com
                        base_domain = '.'.join(parts[-2:])  # example.com
                        logger.info(f"Detected subdomain, will also load cookies from parent: {base_domain}")

                    logger.info(f"Loading cookies from {browser_name}...")

                    # Load cookies for the specific domain
                    cookies = browser_func(domain_name=domain)

                    # If we have a subdomain, also load cookies from parent domain and merge
                    if base_domain and base_domain != domain:
                        # Try multiple domain formats since browsers store cookies differently
                        # e.g., "medium.com" vs ".medium.com" (with leading dot)
                        parent_domains_to_try = [
                            base_domain,           # medium.com
                            f".{base_domain}",     # .medium.com
                        ]

                        for parent_domain in parent_domains_to_try:
                            try:
                                logger.info(f"Loading additional cookies from parent domain: {parent_domain}")
                                parent_cookies = browser_func(domain_name=parent_domain)

                                # Check if we got any cookies (without exhausting the jar)
                                if parent_cookies and len(parent_cookies) > 0:
                                    # Count before merge
                                    parent_count = len(parent_cookies)
                                    logger.info(f"Found {parent_count} cookies from {parent_domain}")

                                    # Merge parent cookies into main cookie jar
                                    # http.cookiejar.CookieJar doesn't have .update(), so iterate manually
                                    for cookie in parent_cookies:
                                        cookies.set_cookie(cookie)

                                    logger.info(f"✓ Merged {parent_count} cookies from parent domain")
                                    # Success - no need to try other formats
                                    break
                                else:
                                    logger.info(f"Found 0 cookies from {parent_domain}")
                            except Exception as e:
                                logger.warning(f"Could not load cookies from {parent_domain}: {e}")
                                # Try next format

                    # Count cookies for debugging (don't modify cookies variable!)
                    cookie_list = list(cookies) if cookies else []
                    cookie_count = len(cookie_list)
                    logger.info(f"Loaded {cookie_count} cookies from {browser_name}")

                    # Debug: Log cookie names and important values (not sensitive data)
                    if cookie_count > 0:
                        cookie_names = [c.name for c in cookie_list]
                        logger.info(f"Cookie names: {', '.join(cookie_names[:10])}...")

                        # Check for Medium-specific authentication cookies
                        important_cookies = {'sid', 'uid', '__cfduid', 'lightstep_guid'}
                        found_auth = [name for name in cookie_names if name in important_cookies]
                        if found_auth:
                            logger.info(f"✓ Found authentication cookies: {', '.join(found_auth)}")

                        # NOTE: Keep cookies as RequestsCookieJar for httpx compatibility
                    else:
                        logger.warning(f"⚠️  NO COOKIES LOADED from {browser_name}!")
                        logger.warning("For Medium articles, you need to:")
                        logger.warning("1. Be logged into Medium in the selected browser")
                        logger.warning("2. On macOS: Grant Terminal access to browser cookies")
                        logger.warning("   (System Preferences → Security & Privacy → Full Disk Access)")
                        logger.info("Proceeding without authentication - only free content will be available")
                        cookies = None

                except Exception as e:
                    logger.warning(f"Failed to load cookies from {browser_name}: {e}")
                    cookies = None

            except Exception as e:
                logger.warning(f"Could not load browser cookies: {e}")
                logger.info("Proceeding without authentication")

        # Step 2: Fetch HTML
        # Enhanced headers to mimic real browser behavior (important for Medium)
        headers = {
            "User-Agent": config.WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

        # Add Referer for Medium to avoid anti-scraping measures
        if "medium.com" in domain:
            headers["Referer"] = "https://medium.com/"

        with httpx.Client(
            cookies=cookies,
            follow_redirects=True,
            timeout=config.WEB_REQUEST_TIMEOUT
        ) as client:
            logger.info(f"Fetching URL: {url}")
            response = client.get(url, headers=headers)
            response.raise_for_status()  # Raise exception for 4xx/5xx
            full_html = response.text

            # Log response details for debugging
            html_size = len(full_html)
            logger.info(f"Response: {response.status_code}, Size: {html_size:,} bytes, Encoding: {response.encoding}")

            # Check if response looks like a paywall (too small)
            if html_size < 5000:
                logger.warning(f"⚠️  HTML response is suspiciously small ({html_size} bytes)")
                logger.warning("This may indicate a paywall or authentication failure")

        # Save raw HTML for debugging (if enabled)
        if config.WEB_SAVE_RAW_HTML:
            from pathlib import Path
            debug_dir = config.MARKDOWN_OUTPUT_PATH / "_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)

            # Create safe filename from URL
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            safe_filename = f"{domain}_{url_hash}.html"
            debug_path = debug_dir / safe_filename

            debug_path.write_text(full_html, encoding="utf-8")
            logger.info(f"Saved raw HTML to: {debug_path}")

        # Step 3: Extract article content
        logger.info("Extracting article content...")

        # For Medium, use custom extraction that preserves all content
        # Medium has a complex React-based structure that readability often misinterprets
        if "medium.com" in domain:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(full_html, 'lxml')

            # Try to find the article element (Medium's main content container)
            article = soup.find('article')

            if article:
                logger.info("Using Medium-specific content extraction")
                article_title_elem = soup.find('h1')
                article_title = article_title_elem.get_text(strip=True) if article_title_elem else "Untitled"

                # Extract all text content from the article, preserving structure
                article_html = str(article)

                logger.info(f"Extracted Medium article HTML: {len(article_html):,} bytes")
            else:
                logger.warning("Could not find Medium article element, falling back to readability")
                doc = Document(full_html)
                article_title = doc.title()
                article_html = doc.summary()
        else:
            # For non-Medium sites, use readability-lxml
            doc = Document(full_html)
            article_title = doc.title()
            article_html = doc.summary()

        # Step 4: Convert to Markdown
        logger.info("Converting to Markdown...")
        markdown_text = md(article_html, heading_style="ATX")

        # Add title at the top
        final_markdown = f"# {article_title}\n\n{markdown_text}"

        logger.info(f"Final Markdown: {len(final_markdown):,} chars")

        # Validate extracted text
        if not final_markdown or len(final_markdown.strip()) < 100:
            raise ValueError(
                f"Extracted text is too short ({len(final_markdown)} chars). "
                "Page may be blocked or content extraction failed."
            )

        logger.info(f"Successfully extracted article: {article_title} ({len(final_markdown)} chars)")
        return final_markdown

    except ImportError as e:
        raise ImportError(
            "Web scraping libraries not installed. Run: pip install -r requirements.txt"
        ) from e
    except httpx.HTTPStatusError as e:
        raise Exception(
            f"Failed to fetch URL (HTTP {e.response.status_code}): {url}\n"
            f"The page may be restricted or require authentication."
        ) from e
    except Exception as e:
        raise Exception(f"Failed to extract article from {url}: {e}") from e


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
