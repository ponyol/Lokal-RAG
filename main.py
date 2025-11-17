#!/usr/bin/env python3
"""
Lokal-RAG - Local Knowledge Base Application

Main entry point for the application.
This module:
1. Sets up logging
2. Creates the configuration
3. Initializes the storage layer
4. Creates the GUI
5. Initializes the controller
6. Starts the application

Usage:
    python main.py              # Normal mode
    python main.py --debug      # Debug mode (logs scroll events)
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

import customtkinter as ctk

from app_config import create_config_from_settings
from app_controller import AppOrchestrator
from app_services import fn_check_ollama_availability
from app_storage import StorageService, fn_ensure_directories_exist
from app_view import AppView

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
    Main application entry point.

    This function:
    1. Parses command-line arguments
    2. Sets up logging
    3. Creates configuration
    4. Checks prerequisites
    5. Initializes all components
    6. Starts the GUI main loop
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Lokal-RAG - Local Knowledge Base Application"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG level logging (useful for troubleshooting scroll events on macOS)"
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(debug=args.debug)
    logger = logging.getLogger(__name__)

    if args.debug:
        logger.debug("DEBUG mode enabled - scroll events will be logged")

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
        logger.info(f"  - Vector DB Path: {config.VECTOR_DB_PATH}")

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

        # Create GUI
        logger.info("Creating GUI...")
        root = ctk.CTk()
        view = AppView(root)
        logger.info("✓ GUI created")

        # Show LLM status in logs
        if config.LLM_PROVIDER == "ollama":
            if not ollama_available:
                view.append_log("⚠️  WARNING: Ollama is not available!")
                view.append_log("Please ensure Ollama is running: ollama serve")
                view.append_log(f"And the model is downloaded: ollama pull {config.OLLAMA_MODEL}")
                view.append_log("=" * 50)
                view.append_log("")
            else:
                view.append_log("✓ Ollama is running and ready")
                view.append_log(f"✓ Model available: {config.OLLAMA_MODEL}")
                view.append_log(f"✓ Documents in database: {doc_count}")
                view.append_log("=" * 50)
                view.append_log("")
        else:
            # LM Studio - assume it's configured correctly
            view.append_log(f"✓ LLM Provider: LM Studio ({config.LMSTUDIO_BASE_URL})")
            view.append_log(f"✓ Model: {config.LMSTUDIO_MODEL}")
            view.append_log(f"✓ Documents in database: {doc_count}")
            view.append_log("=" * 50)
            view.append_log("")

        # Initialize controller
        logger.info("Initializing controller...")
        orchestrator = AppOrchestrator(view, config, storage)
        logger.info("✓ Controller initialized")

        # Define cleanup handler for graceful shutdown
        def on_closing():
            """Handle application window close event."""
            logger.info("Application closing...")
            orchestrator.cleanup()
            root.destroy()
            logger.info("Application closed successfully")

        # Bind cleanup to window close event
        root.protocol("WM_DELETE_WINDOW", on_closing)

        # Start the application
        logger.info("Starting application main loop...")
        logger.info("=" * 60)

        root.mainloop()

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
