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
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app_config import (
    AppConfig,
    RAG_SYSTEM_PROMPT,
    TAGGING_SYSTEM_PROMPT,
    TRANSLATION_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
)


# Configure logging for this module
logger = logging.getLogger(__name__)


# ============================================================================
# LLM Interaction
# ============================================================================


def fn_call_llm(
    prompt: str,
    system_prompt: str,
    config: AppConfig,
) -> str:
    """
    Call the LLM API (Ollama or LM Studio) with a user prompt and system prompt.

    This function routes to the appropriate LLM provider based on config.LLM_PROVIDER.
    Supports both Ollama and LM Studio (OpenAI-compatible API).

    Args:
        prompt: The user's input text to send to the LLM
        system_prompt: The system instructions for the LLM
        config: Application configuration containing provider, URL, and model name

    Returns:
        str: The LLM's response text

    Raises:
        httpx.HTTPError: If the request to the LLM fails
        ValueError: If the response format is invalid or provider is unsupported

    Example:
        >>> config = AppConfig()
        >>> response = fn_call_llm("Hello", "You are helpful", config)
    """
    if config.LLM_PROVIDER == "ollama":
        return _call_ollama(prompt, system_prompt, config)
    elif config.LLM_PROVIDER == "lmstudio":
        return _call_lmstudio(prompt, system_prompt, config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.LLM_PROVIDER}")


def _call_ollama(
    prompt: str,
    system_prompt: str,
    config: AppConfig,
) -> str:
    """Call Ollama API."""
    url = f"{config.OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    with httpx.Client(timeout=config.LLM_REQUEST_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()

    # Extract the message content from the response
    if "message" not in data or "content" not in data["message"]:
        raise ValueError(f"Invalid Ollama response format: {data}")

    return data["message"]["content"].strip()


def _call_lmstudio(
    prompt: str,
    system_prompt: str,
    config: AppConfig,
) -> str:
    """Call LM Studio API (OpenAI-compatible)."""
    url = f"{config.LMSTUDIO_BASE_URL}/chat/completions"

    payload = {
        "model": config.LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": -1,  # LM Studio uses -1 for unlimited
        "stream": False,
    }

    with httpx.Client(timeout=config.LLM_REQUEST_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()

    # Extract the message content from OpenAI-compatible response
    if "choices" not in data or len(data["choices"]) == 0:
        raise ValueError(f"Invalid LM Studio response format: {data}")

    message = data["choices"][0].get("message", {})
    if "content" not in message:
        raise ValueError(f"Invalid LM Studio message format: {data}")

    return message["content"].strip()


# Backward compatibility alias
fn_call_ollama = fn_call_llm


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

        if config.OLLAMA_MODEL not in model_names:
            return (
                False,
                f"Model '{config.OLLAMA_MODEL}' not found. Available models: {', '.join(model_names)}",
            )

        return (True, None)

    except httpx.ConnectError:
        return (False, "Cannot connect to Ollama. Is it running?")
    except httpx.TimeoutException:
        return (False, "Ollama connection timeout")
    except Exception as e:
        return (False, f"Ollama error: {str(e)}")


# ============================================================================
# Vision (Image Processing)
# ============================================================================


def fn_describe_image(image_bytes: bytes, config: AppConfig) -> str:
    """
    Describe an image using a vision-capable LLM.

    This function sends an image to a multimodal LLM and receives a textual description.
    Works with both Ollama (llava, bakllava, etc.) and LM Studio (with vision models).

    Args:
        image_bytes: The image data as bytes (PNG, JPEG, etc.)
        config: Application configuration containing vision model settings

    Returns:
        str: A detailed description of the image content

    Raises:
        httpx.HTTPError: If the request to the vision API fails
        ValueError: If the response format is invalid

    Example:
        >>> with open("diagram.png", "rb") as f:
        ...     image_data = f.read()
        >>> config = AppConfig(VISION_ENABLED=True)
        >>> description = fn_describe_image(image_data, config)
    """
    import base64

    # Convert image to base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    # Determine which model to use
    # If VISION_MODEL is specified, use it; otherwise use the main LLM model
    vision_model = config.VISION_MODEL if config.VISION_MODEL else (
        config.OLLAMA_MODEL if config.LLM_PROVIDER == "ollama" else config.LMSTUDIO_MODEL
    )

    logger.info(f"Describing image using {config.LLM_PROVIDER} with model {vision_model}")

    if config.LLM_PROVIDER == "ollama":
        return _describe_image_ollama(base64_image, vision_model, config)
    elif config.LLM_PROVIDER == "lmstudio":
        return _describe_image_lmstudio(base64_image, vision_model, config)
    else:
        raise ValueError(f"Unsupported LLM provider for vision: {config.LLM_PROVIDER}")


def _describe_image_ollama(base64_image: str, model: str, config: AppConfig) -> str:
    """Describe image using Ollama vision API."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model,
        "prompt": VISION_SYSTEM_PROMPT,
        "images": [base64_image],
        "stream": False,
    }

    with httpx.Client(timeout=config.LLM_REQUEST_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()

    if "response" not in data:
        raise ValueError(f"Invalid Ollama vision response format: {data}")

    return data["response"].strip()


def _describe_image_lmstudio(base64_image: str, model: str, config: AppConfig) -> str:
    """Describe image using LM Studio vision API (OpenAI-compatible)."""
    url = f"{config.LMSTUDIO_BASE_URL}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_SYSTEM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False,
    }

    with httpx.Client(timeout=config.LLM_REQUEST_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()

    if "choices" not in data or len(data["choices"]) == 0:
        raise ValueError(f"Invalid LM Studio vision response format: {data}")

    message = data["choices"][0].get("message", {})
    if "content" not in message:
        raise ValueError(f"Invalid LM Studio vision message format: {data}")

    return message["content"].strip()


# ============================================================================
# Markdown File Processing
# ============================================================================


def fn_read_markdown_file(md_path: Path) -> str:
    """
    Read a Markdown file directly without any conversion.

    Args:
        md_path: Path to the Markdown file

    Returns:
        str: The content of the Markdown file

    Raises:
        FileNotFoundError: If the file doesn't exist
        Exception: If reading fails

    Example:
        >>> md_path = Path("document.md")
        >>> content = fn_read_markdown_file(md_path)
    """
    try:
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {md_path}")

        # Read the file content
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Validate content
        if not content or len(content.strip()) < 10:
            raise ValueError(
                f"Markdown file is too short ({len(content)} chars). "
                "File may be empty or corrupted."
            )

        logger.info(f"Read Markdown file: {md_path.name} ({len(content)} chars)")
        return content

    except FileNotFoundError as e:
        raise
    except Exception as e:
        raise Exception(f"Failed to read Markdown from {md_path}: {e}") from e


# ============================================================================
# PDF Processing
# ============================================================================


def fn_extract_markdown(pdf_path: Path, config: AppConfig) -> str:
    """
    Convert a PDF file to Markdown using marker-pdf.

    This function performs I/O (reading the PDF file) but is otherwise pure.

    IMPORTANT: This function uses aggressive OCR settings to handle PDFs with
    corrupted or missing text layers (common with Medium articles saved as PDF).

    If config.VISION_ENABLED is True, extracts images and describes them using
    a vision model, appending descriptions to the markdown.

    Args:
        pdf_path: Path to the PDF file to convert
        config: Application configuration (for vision settings)

    Returns:
        str: The Markdown content extracted from the PDF (with optional image descriptions)

    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        Exception: If marker-pdf fails to process the file

    Example:
        >>> pdf_path = Path("document.pdf")
        >>> config = AppConfig(VISION_ENABLED=True)
        >>> markdown = fn_extract_markdown(pdf_path, config)
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

        # Process images if vision is enabled
        if config.VISION_ENABLED and images:
            logger.info(f"Found {len(images)} images in PDF, processing with vision model...")

            # Limit number of images to process
            images_to_process = images[:config.VISION_MAX_IMAGES]

            if len(images) > config.VISION_MAX_IMAGES:
                logger.warning(
                    f"PDF contains {len(images)} images, but VISION_MAX_IMAGES is {config.VISION_MAX_IMAGES}. "
                    f"Only processing first {config.VISION_MAX_IMAGES} images."
                )

            image_descriptions = []
            for idx, (image_path, image_data) in enumerate(images_to_process.items(), 1):
                try:
                    logger.info(f"Processing image {idx}/{len(images_to_process)}: {image_path}")

                    # image_data is a PIL Image object, convert to bytes
                    from io import BytesIO
                    img_bytes = BytesIO()
                    image_data.save(img_bytes, format='PNG')
                    img_bytes_data = img_bytes.getvalue()

                    # Get description from vision model
                    description = fn_describe_image(img_bytes_data, config)

                    image_descriptions.append(f"### Image {idx}\n\n{description}\n")
                    logger.info(f"✓ Image {idx} processed successfully")

                except Exception as e:
                    logger.error(f"Failed to process image {idx}: {e}")
                    image_descriptions.append(f"### Image {idx}\n\n[Error: Could not process image - {str(e)}]\n")

            # Append image descriptions to the markdown
            if image_descriptions:
                text += "\n\n---\n\n## Images from Document\n\n"
                text += "\n".join(image_descriptions)
                logger.info(f"Added {len(image_descriptions)} image descriptions to markdown")
                logger.info(f"Final markdown size after adding images: {len(text)} chars")

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


def fn_fetch_raw_markdown(url: str, config: AppConfig) -> str:
    """
    Fetch a raw Markdown file from a URL without any conversion.

    This is used for URLs that directly point to .md files (like GitHub raw files).

    Args:
        url: The URL of the Markdown file
        config: Application configuration

    Returns:
        str: The content of the Markdown file

    Raises:
        Exception: If fetching fails

    Example:
        >>> config = AppConfig()
        >>> md = fn_fetch_raw_markdown("https://raw.githubusercontent.com/.../README.md", config)
    """
    try:
        logger.info(f"Fetching raw Markdown from: {url}")

        # Download the file
        with httpx.Client(timeout=config.WEB_REQUEST_TIMEOUT) as client:
            response = client.get(url, headers={"User-Agent": config.WEB_USER_AGENT})
            response.raise_for_status()
            content = response.text

        logger.info(f"Downloaded Markdown: {len(content)} chars")

        # Validate content
        if not content or len(content.strip()) < 10:
            raise ValueError(
                f"Downloaded Markdown is too short ({len(content)} chars). "
                "File may be empty or invalid."
            )

        return content

    except httpx.HTTPStatusError as e:
        raise Exception(
            f"Failed to fetch Markdown (HTTP {e.response.status_code}): {url}\n"
            f"The file may not exist or be restricted."
        ) from e
    except Exception as e:
        raise Exception(f"Failed to fetch Markdown from {url}: {e}") from e


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

            # Log response details for debugging
            content_type = response.headers.get("content-type", "")
            content_encoding = response.headers.get("content-encoding", "")
            logger.info(f"Response: {response.status_code}, Content-Type: {content_type}")
            logger.info(f"Content-Encoding: {content_encoding}")
            logger.info(f"Detected encoding: {response.encoding}")

            # Check if content needs decompression (httpx should auto-decompress, but sometimes fails)
            raw_content = response.content

            # Check Content-Encoding header to see what compression was used
            if content_encoding == 'br':
                # Brotli compression - need to decompress manually
                logger.warning("Detected Brotli compression, manually decompressing...")
                try:
                    import brotli
                    raw_content = brotli.decompress(raw_content)
                    logger.info(f"Successfully decompressed Brotli content: {len(raw_content)} bytes")
                except ImportError:
                    logger.error("brotli module not installed. Install with: pip install brotli")
                    logger.warning("Proceeding with compressed content (will likely fail)")
                except Exception as e:
                    logger.error(f"Failed to decompress Brotli: {e}")
            elif raw_content[:2] == b'\x1f\x8b':
                # Gzip magic bytes detected
                logger.warning("Detected gzip-compressed content, manually decompressing...")
                import gzip
                try:
                    raw_content = gzip.decompress(raw_content)
                    logger.info(f"Successfully decompressed gzip content: {len(raw_content)} bytes")
                except Exception as e:
                    logger.error(f"Failed to decompress gzip: {e}")

            # Get HTML content with proper encoding handling
            # Try to decode the raw content
            try:
                # Try UTF-8 first
                try:
                    full_html = raw_content.decode('utf-8')
                    logger.info("Decoded as UTF-8")
                except UnicodeDecodeError:
                    # Try to detect encoding
                    logger.warning("UTF-8 decode failed, trying chardet...")
                    try:
                        import chardet
                        detected = chardet.detect(raw_content)
                        if detected['encoding'] and detected['confidence'] > 0.7:
                            logger.info(f"chardet detected: {detected['encoding']} (confidence: {detected['confidence']})")
                            full_html = raw_content.decode(detected['encoding'])
                        else:
                            logger.warning("chardet confidence too low, falling back to latin-1")
                            full_html = raw_content.decode('latin-1')
                    except ImportError:
                        logger.warning("chardet not available, using latin-1")
                        full_html = raw_content.decode('latin-1')

            except Exception as e:
                logger.error(f"Error decoding response: {e}")
                # Last resort: use httpx default
                full_html = response.text

            html_size = len(full_html)
            logger.info(f"Final HTML size: {html_size:,} bytes")

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

        # Process images if vision is enabled
        if config.VISION_ENABLED:
            try:
                from bs4 import BeautifulSoup
                from urllib.parse import urljoin

                logger.info("Extracting images from article...")
                soup = BeautifulSoup(article_html, 'lxml')
                img_tags = soup.find_all('img')

                if img_tags:
                    logger.info(f"Found {len(img_tags)} images in article")

                    # Limit number of images to process
                    images_to_process = img_tags[:config.VISION_MAX_IMAGES]

                    if len(img_tags) > config.VISION_MAX_IMAGES:
                        logger.warning(
                            f"Article contains {len(img_tags)} images, but VISION_MAX_IMAGES is {config.VISION_MAX_IMAGES}. "
                            f"Only processing first {config.VISION_MAX_IMAGES} images."
                        )

                    image_descriptions = []
                    for idx, img_tag in enumerate(images_to_process, 1):
                        try:
                            # Get image URL (handle multiple lazy-loading patterns)
                            # Medium and other sites use various attributes for lazy loading
                            img_url = None

                            # Try standard attributes first
                            img_url = img_tag.get('src')

                            # Try lazy-loading attributes
                            if not img_url:
                                img_url = img_tag.get('data-src') or img_tag.get('data-lazy-src') or img_tag.get('data-original')

                            # Try srcset/srcSet (Medium uses this in <picture> elements)
                            if not img_url:
                                srcset = img_tag.get('srcset') or img_tag.get('srcSet')
                                if srcset:
                                    # srcset format: "url1 size1, url2 size2, ..."
                                    # Take the first URL
                                    first_src = srcset.split(',')[0].strip().split()[0]
                                    img_url = first_src

                            # For Medium <picture> elements, check parent for <source> tags
                            if not img_url and img_tag.parent and img_tag.parent.name == 'picture':
                                sources = img_tag.parent.find_all('source')
                                for source in sources:
                                    srcset = source.get('srcset') or source.get('srcSet')
                                    if srcset:
                                        # Take the first URL from srcSet
                                        first_src = srcset.split(',')[0].strip().split()[0]
                                        img_url = first_src
                                        logger.info(f"Found image URL in parent <picture> <source> tag")
                                        break

                            if not img_url:
                                # Debug: Log all attributes to understand what Medium is using
                                attrs = dict(img_tag.attrs)
                                logger.warning(f"Image {idx} has no src. Attributes: {attrs}")
                                # Also check parent if it's a picture element
                                if img_tag.parent and img_tag.parent.name == 'picture':
                                    logger.warning(f"Parent <picture> sources: {[dict(s.attrs) for s in img_tag.parent.find_all('source')]}")
                                continue

                            # Convert relative URLs to absolute
                            img_url = urljoin(url, img_url)

                            logger.info(f"Processing image {idx}/{len(images_to_process)}: {img_url[:100]}...")

                            # Download image
                            with httpx.Client(timeout=config.WEB_REQUEST_TIMEOUT) as client:
                                img_response = client.get(img_url, headers={"User-Agent": config.WEB_USER_AGENT})
                                img_response.raise_for_status()
                                img_bytes = img_response.content

                            # Get description from vision model
                            description = fn_describe_image(img_bytes, config)

                            image_descriptions.append(f"### Image {idx}\n\n**Source:** {img_url}\n\n{description}\n")
                            logger.info(f"✓ Image {idx} processed successfully")

                        except Exception as e:
                            logger.error(f"Failed to process image {idx}: {e}")
                            image_descriptions.append(f"### Image {idx}\n\n[Error: Could not process image - {str(e)}]\n")

                    # Append image descriptions to the markdown
                    if image_descriptions:
                        final_markdown += "\n\n---\n\n## Images from Article\n\n"
                        final_markdown += "\n".join(image_descriptions)
                        logger.info(f"Added {len(image_descriptions)} image descriptions to markdown")
                        logger.info(f"Final markdown size after adding images: {len(final_markdown)} chars")

            except Exception as e:
                logger.error(f"Error during image processing: {e}")
                # Don't fail the entire article extraction if image processing fails

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

    For long texts (>TRANSLATION_CHUNK_SIZE chars), splits into chunks by paragraphs to avoid
    LLM summarization instead of translation.

    Args:
        text: The English text to translate
        config: Application configuration (uses config.TRANSLATION_CHUNK_SIZE)

    Returns:
        str: The translated Russian text

    Example:
        >>> config = AppConfig()
        >>> russian = fn_translate_text("Hello world", config)
    """
    # If text is short enough, translate directly
    if len(text) <= config.TRANSLATION_CHUNK_SIZE:
        return fn_call_llm(
            prompt=text,
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            config=config,
        )

    # For long texts, split by paragraphs and translate in chunks
    logger.info(f"Text is long ({len(text)} chars), splitting into chunks for translation...")

    # Split by double newlines (Markdown paragraphs)
    paragraphs = text.split('\n\n')

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph would exceed chunk size, start a new chunk
        if len(current_chunk) + len(para) + 2 > config.TRANSLATION_CHUNK_SIZE and current_chunk:
            chunks.append(current_chunk)
            current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk)

    logger.info(f"Split into {len(chunks)} chunks")

    # Translate each chunk
    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Translating chunk {i}/{len(chunks)} ({len(chunk)} chars)...")
        translated = fn_call_llm(
            prompt=chunk,
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            config=config,
        )
        translated_chunks.append(translated)

    # Join translated chunks back together
    final_translation = "\n\n".join(translated_chunks)
    logger.info(f"Translation complete: {len(final_translation)} chars")

    return final_translation


def fn_generate_tags(text: str, config: AppConfig) -> list[str]:
    """
    Generate topic tags for the given text using the LLM.

    This function composes fn_call_llm and parses the response into a list.
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

    response = fn_call_llm(
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


def fn_create_text_chunks(
    text: str,
    source_file: str,
    config: AppConfig,
    language: str = "en"
) -> list[Document]:
    """
    Split text into chunks suitable for embedding and vector storage.

    This is a pure function that uses LangChain's text splitter.

    Args:
        text: The text to split into chunks
        source_file: The name of the source file (for metadata)
        config: Application configuration containing chunk size parameters
        language: Language code for the text ("en" or "ru")

    Returns:
        list[Document]: A list of LangChain Document objects with:
            - page_content: The chunk text
            - metadata: {"source": source_file, "language": language}

    Example:
        >>> config = AppConfig()
        >>> chunks = fn_create_text_chunks("Long text...", "doc.pdf", config, language="en")
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
            metadata={
                "source": source_file,
                "language": language,
            },
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
    response = fn_call_llm(
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
    Recursively find all PDF and Markdown files in a directory.

    This is a pure function (aside from the I/O of reading directory contents).

    Args:
        directory: The directory to search

    Returns:
        list[Path]: A sorted list of PDF and MD file paths

    Example:
        >>> files = fn_find_pdf_files(Path("./documents"))
        >>> print(len(files))
        15
    """
    if not directory.exists():
        return []

    # Find both PDF and Markdown files
    pdf_files = list(directory.rglob("*.pdf"))
    md_files = list(directory.rglob("*.md"))

    # Combine and sort
    all_files = sorted(pdf_files + md_files)
    return all_files


# ============================================================================
# Changelog Generation Functions
# ============================================================================


def fn_generate_summary(text: str, config: AppConfig) -> str:
    """
    Generate a concise Russian summary of a document using LLM.

    This uses the configured LLM to create a 1-2 sentence summary in Russian
    that captures the main topic and key information of the document.

    Args:
        text: The document text to summarize (markdown format)
        config: Application configuration

    Returns:
        str: A concise Russian summary (1-2 sentences)

    Raises:
        Exception: If LLM call fails

    Example:
        >>> summary = fn_generate_summary(markdown_text, config)
        >>> print(summary)
        'Статья о машинном обучении, рассматривает алгоритмы supervised learning.'
    """
    from app_config import SUMMARY_SYSTEM_PROMPT

    try:
        logger.info("Generating document summary...")

        # Truncate text if too long (take first 3000 chars to capture main content)
        truncated_text = text[:3000] if len(text) > 3000 else text

        # Call LLM with summary prompt
        summary = fn_call_llm(
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_message=truncated_text,
            config=config,
        )

        # Clean up summary (remove quotes, trim whitespace)
        summary = summary.strip().strip('"\'')

        logger.info(f"Generated summary: {summary[:100]}...")
        return summary

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        # Return fallback summary if LLM fails
        return "Не удалось сгенерировать описание документа."


def fn_create_changelog_file(
    processed_items: list[dict],
    config: AppConfig,
) -> Path:
    """
    Create a changelog markdown file with summaries of processed documents.

    Creates a timestamped file in the changelog directory with a list of all
    documents processed in this session, including their summaries.

    Args:
        processed_items: List of dicts with keys:
            - 'name': str (document name or URL)
            - 'summary': str (Russian summary of the document)
        config: Application configuration

    Returns:
        Path: Path to the created changelog file

    Raises:
        Exception: If file creation fails

    Example:
        >>> items = [
        ...     {'name': 'doc1.pdf', 'summary': 'Статья о ML'},
        ...     {'name': 'https://example.com', 'summary': 'Руководство по Docker'},
        ... ]
        >>> changelog_path = fn_create_changelog_file(items, config)
    """
    from datetime import datetime

    try:
        # Ensure changelog directory exists
        config.CHANGELOG_PATH.mkdir(parents=True, exist_ok=True)

        # Create filename with current timestamp
        timestamp = datetime.now()
        filename = timestamp.strftime("%Y-%m-%d_%H-%M-%S.md")
        filepath = config.CHANGELOG_PATH / filename

        # Format timestamp for display
        display_timestamp = timestamp.strftime("%d.%m.%Y %H:%M:%S")

        # Build markdown content
        lines = [
            f"# Обработка документов - {display_timestamp}\n",
            f"\nВсего обработано документов: {len(processed_items)}\n",
            "\n---\n",
        ]

        # Add each processed item
        for idx, item in enumerate(processed_items, 1):
            name = item.get('name', 'Unknown')
            summary = item.get('summary', 'Описание отсутствует')

            lines.append(f"\n## {idx}. {name}\n")
            lines.append(f"\n**Краткое содержание:** {summary}\n")

        # Write to file
        content = "\n".join(lines)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Changelog file created: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Failed to create changelog file: {e}")
        raise
