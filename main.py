#!/usr/bin/env python3
"""
Lokal-RAG - Local Knowledge Base Application (Toga Version)

Main entry point for the application with native UI.
This module:
1. Sets up logging
2. Creates the configuration
3. Initializes the storage layer
4. Creates the Toga GUI
5. Initializes the controller
6. Starts the application

Usage:
    python main.py              # Normal mode
    python main.py --debug      # Debug mode (detailed logs)
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

from app_config import create_config_from_settings, AppConfig
from app_controller_toga import TogaAppOrchestrator
from app_services import fn_check_ollama_availability
from app_storage import StorageService, fn_ensure_directories_exist
from app_view_toga import LokalRAGApp

# Suppress resource_tracker warnings
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")


def setup_logging(debug: bool = False) -> None:
    """
    Configure structured logging for the application.

    Args:
        debug: Enable DEBUG level logging (default: False = INFO level)
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
            logging.StreamHandler(sys.stdout),
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

    # Check Ollama availability if using Ollama
    if config.LLM_PROVIDER == "ollama":
        logger.info("Checking Ollama availability...")
        is_available, error = fn_check_ollama_availability(config)

        if not is_available:
            logger.warning(f"Ollama check failed: {error}")
            return False

        logger.info("✓ Ollama is available")
        return True

    return True  # Other providers don't need availability checks


def create_app_with_controller(
    config: AppConfig,
    storage: StorageService,
    ollama_available: bool,
    doc_count: int
) -> LokalRAGApp:
    """
    Create the Toga app and initialize the controller.

    Args:
        config: Application configuration
        storage: Storage service
        ollama_available: Whether Ollama is available
        doc_count: Initial document count

    Returns:
        LokalRAGApp: The configured Toga application
    """
    logger = logging.getLogger(__name__)

    # Create Toga app
    logger.info("Creating Toga UI...")
    app = LokalRAGApp()
    logger.info("✓ Toga app created")

    # Initialize controller (will be attached after app.startup)
    # We need to defer controller initialization until after Toga creates the UI
    def on_app_ready(widget):
        """
        Called when Toga app is fully started.

        Args:
            widget: The widget that triggered the callback (Toga passes this)
        """
        logger.info("Initializing controller...")
        orchestrator = TogaAppOrchestrator(app, config, storage)
        logger.info("✓ Controller initialized")

        # Load saved settings into UI (must be done in main thread)
        logger.info("Loading saved settings into UI...")
        orchestrator.load_settings_to_ui()
        logger.info("✓ Settings loaded")

        # Show initial status in logs
        if config.LLM_PROVIDER == "ollama":
            if not ollama_available:
                app.append_log("⚠️  WARNING: Ollama is not available!")
                app.append_log("Please ensure Ollama is running: ollama serve")
                app.append_log(f"And the model is downloaded: ollama pull {config.OLLAMA_MODEL}")
                app.append_log("=" * 50)
                app.append_log("")
            else:
                app.append_log("✓ Ollama is running and ready")
                app.append_log(f"✓ Model available: {config.OLLAMA_MODEL}")
                app.append_log(f"✓ Documents in database: {doc_count}")
                app.append_log("=" * 50)
                app.append_log("")
        else:
            # Other LLM providers
            app.append_log(f"✓ LLM Provider: {config.LLM_PROVIDER.upper()}")
            app.append_log(f"✓ Documents in database: {doc_count}")
            app.append_log("=" * 50)
            app.append_log("")

    # Schedule on_app_ready to run after UI is created
    # Toga doesn't have a direct "ready" callback, so we'll use add_background_task
    app.on_running = on_app_ready

    return app


def main() -> None:
    """
    Main application entry point.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Lokal-RAG - Local Knowledge Base Application (Toga Version)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG level logging"
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(debug=args.debug)
    logger = logging.getLogger(__name__)

    if args.debug:
        logger.debug("DEBUG mode enabled")

    try:
        # Create configuration
        logger.info("Loading configuration...")
        config = create_config_from_settings()
        logger.info(f"✓ Configuration loaded")
        logger.info(f"  - LLM Provider: {config.LLM_PROVIDER}")

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

        # Create app with controller
        app = create_app_with_controller(config, storage, ollama_available, doc_count)

        # Start the Toga application
        logger.info("Starting Toga main loop...")
        logger.info("=" * 60)

        # Run the app
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
