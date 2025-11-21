#!/usr/bin/env python3
"""
Lokal-RAG - Local Knowledge Base Application

Main entry point for the application.
This module:
1. Sets up logging
2. Creates the configuration
3. Initializes the storage layer
4. Creates the Toga GUI (native cross-platform UI)
5. Initializes the controller
6. Starts the application

Usage:
    python main.py              # Normal mode
    python main.py --debug      # Debug mode with verbose logging
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

from app_config import create_config_from_settings
from app_controller import TogaAppOrchestrator
from app_services import fn_check_ollama_availability
from app_storage import StorageService, fn_ensure_directories_exist
from app_view import LokalRAGApp

# Suppress resource_tracker warnings
# NOTE: ChromaDB 1.3+ and sentence-transformers (PyTorch) may still use multiprocessing
# internally for DataLoader/thread pools. Python's resource_tracker is overly aggressive
# and reports "leaked" semaphores even when they are properly cleaned up.
# These warnings are harmless - resources are freed when the process exits.
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")


def setup_logging(debug: bool = False) -> None:
    """
    Configure structured logging for the application.

    Args:
        debug: Enable DEBUG level logging (default: False = INFO level)

    Logs are output to both console and a file.
    Format: JSON-like structured format for production readiness.
    """
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Create logs directory if it doesn't exist
    Path("./logs").mkdir(exist_ok=True)

    # Configure root logger
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console handler
            logging.StreamHandler(sys.stdout),
            # File handler
            logging.FileHandler("./logs/lokal_rag.log", mode="a", encoding="utf-8"),
        ],
    )

    # Set levels for noisy third-party libraries (unless in debug mode)
    if not debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("chromadb").setLevel(logging.WARNING)
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        logging.getLogger("toga").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info(f"Lokal-RAG Application Starting (Log Level: {logging.getLevelName(log_level)})")
    logger.info("=" * 60)


def check_prerequisites(config) -> bool:
    """
    Check if all prerequisites are met.

    Args:
        config: Application configuration

    Returns:
        bool: True if all checks pass, False otherwise
    """
    logger = logging.getLogger(__name__)

    # Check Ollama availability
    logger.info("Checking Ollama availability...")
    is_available, error = fn_check_ollama_availability(config)

    if not is_available:
        logger.warning(f"Ollama check failed: {error}")
        return False

    logger.info("✓ Ollama is available")
    return True


def main() -> None:
    """
    Main application entry point for Toga version.

    This function:
    1. Parses command-line arguments
    2. Sets up logging
    3. Creates configuration
    4. Checks prerequisites
    5. Initializes all components
    6. Starts the Toga GUI main loop
    """
    # Suppress WebKit debug logs (macOS native logs)
    import os
    os.environ['WEBKIT_DISABLE_COMPOSITING_MODE'] = '1'

    # Redirect stderr to filter out WebKit logs
    import sys

    class WebKitLogFilter:
        """Filter to suppress WebKit native debug logs on macOS."""
        def __init__(self, stream):
            self.stream = stream
            self.buffer = ""

        def write(self, text):
            # Filter out WebKit frame policy logs and stack traces
            # Patterns to filter:
            # - Lines containing "WebKit::" (WebKit C++ namespaces)
            # - Lines containing "WebFramePolicyListenerProxy" (specific class)
            # - Stack trace lines (start with number + hex address)
            # - ctypes/PyObject calls related to WebKit
            if any(pattern in text for pattern in [
                'WebKit::',
                'WebFramePolicyListenerProxy',
                '_ctypes_callproc',
                'PyCFuncPtr_call',
                '_PyObject_Call',
                '_PyEval_EvalFrameDefault'
            ]):
                return  # Suppress this line

            # Also filter stack trace lines (e.g., "1   0x1c86a9414 ...")
            import re
            if re.match(r'^\s*\d+\s+0x[0-9a-fA-F]+\s+', text):
                return  # Suppress stack trace line

            # Pass through all other output
            self.stream.write(text)
            self.stream.flush()

        def flush(self):
            self.stream.flush()

    # Only filter stderr (WebKit logs go there)
    sys.stderr = WebKitLogFilter(sys.stderr)

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Lokal-RAG - Local Knowledge Base Application (Toga UI)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG level logging (useful for troubleshooting)"
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(debug=args.debug)
    logger = logging.getLogger(__name__)

    if args.debug:
        logger.debug("DEBUG mode enabled - verbose logging active")

    try:
        # Create configuration
        logger.info("Loading configuration...")
        config = create_config_from_settings()
        logger.info(f"✓ Configuration loaded")
        logger.info(f"  - LLM Provider: {config.LLM_PROVIDER}")
        if config.LLM_PROVIDER == "ollama":
            logger.info(f"  - Ollama Model: {config.OLLAMA_MODEL}")
        else:
            logger.info(f"  - LM Studio Model: {config.LMSTUDIO_MODEL}")
        logger.info(f"  - Embedding Model: {config.EMBEDDING_MODEL}")
        logger.info(f"  - English Vector DB Path: {config.VECTOR_DB_PATH_EN}")
        logger.info(f"  - Russian Vector DB Path: {config.VECTOR_DB_PATH_RU}")

        # Ensure required directories exist
        logger.info("Creating required directories...")
        fn_ensure_directories_exist(config)
        logger.info("✓ Directories created")

        # Check prerequisites
        ollama_available = check_prerequisites(config)

        # Initialize storage layer
        logger.info("Initializing storage layer...")
        logger.info("  (This may take a moment on first run - downloading models)")
        storage = StorageService(config)
        logger.info("✓ Storage layer initialized")

        # Get initial document count
        doc_count = storage.get_document_count()
        logger.info(f"  - Documents in database: {doc_count}")

        # Create Toga app
        logger.info("Creating Toga GUI V2...")
        app = LokalRAGApp()
        logger.info("✓ Toga GUI V2 created")

        # Initialize controller
        logger.info("Initializing controller...")
        orchestrator = TogaAppOrchestrator(
            view=app,
            config=config,
            storage=storage,
            ollama_available=ollama_available,
            doc_count=doc_count
        )
        logger.info("✓ Controller initialized")

        # Start the application
        logger.info("Starting Toga application main loop...")
        logger.info("=" * 60)

        # Run the Toga main loop
        app.main_loop()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Fatal error during startup: {e}", exc_info=True)
        print(f"\n❌ Fatal Error: {e}", file=sys.stderr)
        print("\nPlease check the logs for details: ./logs/lokal_rag.log", file=sys.stderr)
        sys.exit(1)

    finally:
        logger.info("Application shutdown")


if __name__ == "__main__":
    main()
