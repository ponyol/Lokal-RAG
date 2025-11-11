"""
Application Controller - Orchestration Layer

This module contains the AppOrchestrator class, which is the central state machine
of the application. It coordinates between the View, Services, and Storage layers.

Key responsibilities:
1. Manage application state (idle, processing, etc.)
2. Handle user events from the View
3. Spawn worker threads for heavy operations
4. Update the View with results (via queue for thread safety)

The Controller is the only "imperative" part of the application.
It calls the pure functional services and manages side effects.
"""

import logging
import queue
import threading
from pathlib import Path
from typing import Optional

from app_config import AppConfig
from app_services import (
    fn_call_ollama,
    fn_cleanup_pdf_memory,
    fn_create_text_chunks,
    fn_expand_query_with_dates,
    fn_extract_markdown,
    fn_fetch_web_article,
    fn_find_pdf_files,
    fn_generate_tags,
    fn_get_rag_response,
    fn_translate_text,
)
from app_storage import StorageService, fn_save_markdown_to_disk
from app_view import AppView


# Configure logging
logger = logging.getLogger(__name__)


class AppOrchestrator:
    """
    The central orchestrator for the Lokal-RAG application.

    This class manages application state and coordinates all layers:
    - View: CustomTkinter GUI
    - Services: Pure functional business logic
    - Storage: ChromaDB and file I/O

    It uses threading and queues to ensure the GUI never freezes.
    """

    def __init__(self, view: AppView, config: AppConfig, storage: StorageService):
        """
        Initialize the orchestrator.

        Args:
            view: The application view (GUI)
            config: Application configuration
            storage: The storage service
        """
        self.view = view
        self.config = config
        self.storage = storage

        # State management
        self.is_processing = False
        self.is_chatting = False

        # Queue for worker threads to send messages to the GUI
        # This is the ONLY thread-safe way to update CustomTkinter widgets
        self.view_queue: queue.Queue = queue.Queue()

        # Bind events
        self.bind_events()

        # Load saved settings into UI
        self.load_settings_to_ui()

        # Start the queue checker
        self.check_view_queue()

    def bind_events(self) -> None:
        """
        Bind View widgets to Controller methods.

        This connects user interactions to business logic.
        """
        self.view.bind_start_button(self.on_start_ingestion)
        self.view.bind_send_button(self.on_send_chat_message)

        # Bind Settings tab buttons
        self.view.test_connection_button.configure(command=self.on_test_connection)
        self.view.save_settings_button.configure(command=self.on_save_settings)

        logger.info("Events bound successfully")

    def load_settings_to_ui(self) -> None:
        """Load saved settings from JSON into the UI."""
        from app_config import load_settings_from_json

        settings = load_settings_from_json()
        if settings:
            self.view.set_llm_settings(settings)
            logger.info("Loaded settings into UI")

    # ========================================================================
    # Queue Management (Thread-Safe GUI Updates)
    # ========================================================================

    def check_view_queue(self) -> None:
        """
        Check the view queue for messages from worker threads.

        This method is called every 100ms by the CustomTkinter main loop.
        It's the ONLY way to safely update the GUI from background threads.

        Messages can be:
        - "LOG: <message>" - Append to ingestion log
        - "CHAT: <role>: <message>" - Append to chat history
        - "STOP_PROCESSING" - Reset processing state
        - "STOP_CHATTING" - Reset chat state
        """
        try:
            while True:
                # Non-blocking get
                message = self.view_queue.get_nowait()

                if message == "STOP_PROCESSING":
                    self.is_processing = False
                    self.view.set_processing_state(False)

                elif message == "STOP_CHATTING":
                    self.is_chatting = False
                    self.view.set_chat_state(False)

                elif message.startswith("LOG: "):
                    log_message = message[5:]
                    self.view.append_log(log_message)

                elif message.startswith("CHAT: "):
                    # Format: "CHAT: role: message"
                    parts = message[6:].split(": ", 1)
                    if len(parts) == 2:
                        role, content = parts
                        self.view.append_chat_message(role, content)

        except queue.Empty:
            pass

        # Schedule next check
        self.view.master.after(100, self.check_view_queue)

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def on_start_ingestion(self) -> None:
        """
        Handle the "Start Processing" button click.

        This method:
        1. Validates input (PDFs or URLs)
        2. Sets processing state
        3. Spawns a worker thread to process content
        """
        # Prevent multiple simultaneous processing tasks
        if self.is_processing:
            logger.warning("Processing already in progress")
            return

        # Get settings from the view
        settings = self.view.get_ingestion_settings()
        source_type = settings["source_type"]

        # Validate input based on source type
        if source_type == "pdf":
            # Validate PDF folder
            folder_path = settings["folder_path"]
            if folder_path == "No folder selected" or not folder_path:
                self.view.show_warning("No Folder", "Please select a folder containing PDF files.")
                return

            folder = Path(folder_path)
            if not folder.exists():
                self.view.show_warning("Invalid Folder", f"Folder does not exist: {folder_path}")
                return

            # Find PDF and Markdown files
            files = fn_find_pdf_files(folder)
            if not files:
                self.view.show_warning("No Files", f"No PDF or Markdown files found in: {folder_path}")
                return

            items = files
            item_type = "file"

        else:  # web
            # Validate URLs
            web_urls = settings["web_urls"]
            if not web_urls:
                self.view.show_warning("No URLs", "Please enter at least one URL.")
                return

            items = web_urls
            item_type = "URL"

        # Set processing state
        self.is_processing = True
        self.view.set_processing_state(True)
        self.view.clear_log()

        # Log initial message
        self.view_queue.put(f"LOG: Found {len(items)} {item_type}(s)")
        self.view_queue.put(f"LOG: Source type: {source_type.upper()}")
        self.view_queue.put(f"LOG: Translation: {'ON' if settings['do_translation'] else 'OFF'}")
        self.view_queue.put(f"LOG: Auto-tagging: {'ON' if settings['do_tagging'] else 'OFF'}")
        self.view_queue.put(f"LOG: Extract images: {'ON' if settings['extract_images'] else 'OFF'}")
        if source_type == "web":
            self.view_queue.put(f"LOG: Use cookies: {'ON' if settings['use_cookies'] else 'OFF'}")
            if settings['use_cookies']:
                self.view_queue.put(f"LOG: Browser: {settings['browser_choice'].upper()}")
            self.view_queue.put(f"LOG: Save raw HTML: {'ON' if settings['save_raw_html'] else 'OFF'}")
        self.view_queue.put("LOG: " + "=" * 50)

        # Spawn worker thread
        worker = threading.Thread(
            target=processing_pipeline_worker,
            args=(items, settings, self.config, self.storage, self.view_queue),
            daemon=True,
        )
        worker.start()

        logger.info(f"Started processing {len(items)} {item_type}(s)")

    def on_send_chat_message(self) -> None:
        """
        Handle the "Send" button click in the chat interface.

        This method:
        1. Gets the user's query
        2. Validates input
        3. Spawns a worker thread to query the RAG system
        """
        # Prevent multiple simultaneous chat queries
        if self.is_chatting:
            logger.warning("Chat query already in progress")
            return

        # Get user input
        query = self.view.get_chat_input()

        # Validate input
        if not query or not query.strip():
            return

        # Clear input field
        self.view.clear_chat_input()

        # Set chat state
        self.is_chatting = True
        self.view.set_chat_state(True)

        # Display user message
        self.view.append_chat_message("user", query)

        # Spawn worker thread
        worker = threading.Thread(
            target=rag_chat_worker,
            args=(query, self.config, self.storage, self.view_queue),
            daemon=True,
        )
        worker.start()

        logger.info(f"Started chat query: {query[:50]}...")

    def on_save_settings(self) -> None:
        """
        Handle the "Save Settings" button click.

        Saves LLM configuration to ~/.lokal-rag/settings.json
        """
        try:
            from app_config import save_settings_to_json, create_config_from_settings
            from dataclasses import replace

            # Get settings from UI
            settings = self.view.get_llm_settings()

            # Save to JSON
            save_settings_to_json(settings)

            # Update the controller's config
            self.config = create_config_from_settings(settings)

            # Show success message
            self.view.show_settings_status("✓ Settings saved successfully!", is_error=False)
            logger.info(f"Settings saved: Provider={settings['llm_provider']}")

        except Exception as e:
            error_msg = f"Failed to save settings: {e}"
            self.view.show_settings_status(f"✗ {error_msg}", is_error=True)
            logger.error(error_msg, exc_info=True)

    def on_test_connection(self) -> None:
        """
        Handle the "Test Connection" button click.

        Tests connection to the selected LLM provider.
        """
        try:
            from app_config import create_config_from_settings

            # Get settings from UI
            settings = self.view.get_llm_settings()

            # Create temporary config
            test_config = create_config_from_settings(settings)

            # Show testing status
            self.view.show_settings_status("Testing connection...", is_error=False)
            self.view.master.update()  # Force UI update

            # Test based on provider
            if test_config.LLM_PROVIDER == "ollama":
                from app_services import fn_check_ollama_availability

                available, error = fn_check_ollama_availability(test_config)
                if available:
                    self.view.show_settings_status(
                        f"✓ Connected to Ollama! Model: {test_config.OLLAMA_MODEL}",
                        is_error=False
                    )
                    logger.info("Ollama connection test successful")
                else:
                    self.view.show_settings_status(
                        f"✗ Ollama not available: {error}",
                        is_error=True
                    )
                    logger.warning(f"Ollama connection test failed: {error}")

            elif test_config.LLM_PROVIDER == "lmstudio":
                # Test LM Studio connection
                import httpx
                url = f"{test_config.LMSTUDIO_BASE_URL}/models"

                try:
                    with httpx.Client(timeout=5) as client:
                        response = client.get(url)
                        response.raise_for_status()

                    self.view.show_settings_status(
                        f"✓ Connected to LM Studio! Model: {test_config.LMSTUDIO_MODEL}",
                        is_error=False
                    )
                    logger.info("LM Studio connection test successful")

                except Exception as e:
                    self.view.show_settings_status(
                        f"✗ LM Studio not available: {e}",
                        is_error=True
                    )
                    logger.warning(f"LM Studio connection test failed: {e}")

        except Exception as e:
            error_msg = f"Connection test failed: {e}"
            self.view.show_settings_status(f"✗ {error_msg}", is_error=True)
            logger.error(error_msg, exc_info=True)

    def cleanup(self) -> None:
        """
        Clean up resources held by the orchestrator.

        This method should be called when the application is shutting down.
        It ensures all threads are stopped and storage resources are freed.

        NOTE: This prevents the "leaked semaphore objects" warning.
        """
        try:
            logger.info("Cleaning up AppOrchestrator resources...")

            # Clean up storage service
            if self.storage:
                self.storage.cleanup()

            logger.info("AppOrchestrator cleanup complete")

        except Exception as e:
            logger.error(f"Error during AppOrchestrator cleanup: {e}")


# ============================================================================
# Worker Functions (Run in Separate Threads)
# ============================================================================


def processing_pipeline_worker(
    items: list,  # Can be list[Path] for PDFs or list[str] for URLs
    settings: dict,
    config: AppConfig,
    storage: StorageService,
    view_queue: queue.Queue,
) -> None:
    """
    Worker function to process content (PDFs or web articles).

    This function runs in a separate thread and performs:
    1. Content extraction (PDF → Markdown or URL → Markdown)
    2. (Optional) Translation
    3. (Optional) Tagging
    4. Save to disk
    5. Chunk and add to vector database

    Args:
        items: List of items to process (Path objects for PDFs, str URLs for web)
        settings: User settings (source_type, translation, tagging, use_cookies)
        config: Application configuration
        storage: Storage service instance
        view_queue: Queue for sending updates to the GUI

    NOTE: This function is imperative and orchestrates the pure functional services.
    """
    source_type = settings.get("source_type", "pdf")
    do_translation = settings.get("do_translation", False)
    do_tagging = settings.get("do_tagging", True)
    extract_images = settings.get("extract_images", False)
    use_cookies = settings.get("use_cookies", True)
    browser_choice = settings.get("browser_choice", "chrome")
    save_raw_html = settings.get("save_raw_html", False)

    # Update config with user settings
    from dataclasses import replace
    config = replace(
        config,
        VISION_ENABLED=extract_images,
        WEB_USE_BROWSER_COOKIES=use_cookies,
        WEB_BROWSER_CHOICE=browser_choice,
        WEB_SAVE_RAW_HTML=save_raw_html,
    )

    success_count = 0
    error_count = 0

    # Track processed items for changelog
    processed_items = []

    for item in items:
        try:
            # Step 1: Extract Markdown from source
            if source_type == "pdf":
                # File processing (PDF or MD)
                item_name = item.name
                view_queue.put(f"LOG: Processing {item_name}...")

                # Check file extension
                if item.suffix.lower() == '.md':
                    # Markdown file - read directly
                    from app_services import fn_read_markdown_file
                    markdown_text = fn_read_markdown_file(item)
                    view_queue.put(f"LOG:   ✓ Read Markdown file ({len(markdown_text)} chars)")
                else:
                    # PDF file - convert with marker-pdf
                    markdown_text = fn_extract_markdown(item, config)
                    view_queue.put(f"LOG:   ✓ Extracted Markdown ({len(markdown_text)} chars)")
            else:
                # Web article processing (HTML or MD URL)
                item_name = item.split("://")[-1][:50] + "..."  # Shortened URL for display
                view_queue.put(f"LOG: Fetching {item}...")

                # Check if URL ends with .md
                if item.lower().endswith('.md'):
                    # Raw Markdown URL - download directly
                    from app_services import fn_fetch_raw_markdown
                    markdown_text = fn_fetch_raw_markdown(item, config)
                    view_queue.put(f"LOG:   ✓ Downloaded Markdown ({len(markdown_text)} chars)")
                else:
                    # HTML article - extract and convert
                    markdown_text = fn_fetch_web_article(item, config)
                    view_queue.put(f"LOG:   ✓ Extracted article ({len(markdown_text)} chars)")

            # Step 2: Translation (optional)
            russian_text = None
            if do_translation:
                view_queue.put(f"LOG:   → Translating to Russian...")
                russian_text = fn_translate_text(markdown_text, config)
                view_queue.put(f"LOG:   ✓ Translation complete")

            # Step 3: Tagging (optional)
            # Use English text for tagging (tags are in English)
            tags = ["general"]
            if do_tagging:
                view_queue.put(f"LOG:   → Generating tags...")
                tags = fn_generate_tags(markdown_text, config)
                view_queue.put(f"LOG:   ✓ Tags: {', '.join(tags)}")

            # Step 4: Save to disk
            primary_tag = tags[0] if tags else "general"

            # Debug: Log markdown size before saving
            if extract_images:
                view_queue.put(f"LOG:   [DEBUG] Markdown size before save: {len(markdown_text)} chars")

            # Generate filename based on source type
            if source_type == "pdf":
                filename = item.stem
                source_name = item.name
            else:
                # Extract title from markdown (first # heading) or use URL
                import re
                title_match = re.search(r'^#\s+(.+)$', markdown_text, re.MULTILINE)
                if title_match:
                    filename = title_match.group(1)[:50]  # Limit to 50 chars
                    # Sanitize filename
                    filename = re.sub(r'[^\w\s-]', '', filename)
                    filename = re.sub(r'[-\s]+', '-', filename)
                else:
                    # Use domain + path as filename
                    from urllib.parse import urlparse
                    parsed = urlparse(item)
                    filename = f"{parsed.netloc}{parsed.path}".replace("/", "-")[:50]
                source_name = item

            # Save English version
            if do_translation:
                # When translation is enabled, save both languages
                saved_path_en = fn_save_markdown_to_disk(
                    text=markdown_text,
                    tag=primary_tag,
                    filename=f"{filename}_en",
                    config=config,
                )
                view_queue.put(f"LOG:   ✓ Saved English to: {saved_path_en}")

                saved_path_ru = fn_save_markdown_to_disk(
                    text=russian_text,
                    tag=primary_tag,
                    filename=f"{filename}_ru",
                    config=config,
                )
                view_queue.put(f"LOG:   ✓ Saved Russian to: {saved_path_ru}")
            else:
                # When translation is disabled, save only English
                saved_path = fn_save_markdown_to_disk(
                    text=markdown_text,
                    tag=primary_tag,
                    filename=filename,
                    config=config,
                )
                view_queue.put(f"LOG:   ✓ Saved to: {saved_path}")

            # Step 5: Create chunks and add to vector database
            if do_translation:
                # Bilingual storage: create chunks for both languages
                view_queue.put(f"LOG:   → Creating English chunks...")
                chunks_en = fn_create_text_chunks(
                    text=markdown_text,
                    source_file=source_name,
                    config=config,
                    language="en",
                )
                view_queue.put(f"LOG:   ✓ Created {len(chunks_en)} English chunks")

                view_queue.put(f"LOG:   → Creating Russian chunks...")
                chunks_ru = fn_create_text_chunks(
                    text=russian_text,
                    source_file=source_name,
                    config=config,
                    language="ru",
                )
                view_queue.put(f"LOG:   ✓ Created {len(chunks_ru)} Russian chunks")

                view_queue.put(f"LOG:   → Adding to vector database...")
                storage.add_documents(chunks_en)
                storage.add_documents(chunks_ru)
                view_queue.put(f"LOG:   ✓ Added {len(chunks_en)} + {len(chunks_ru)} chunks to database")
            else:
                # Monolingual storage: create chunks only for English
                view_queue.put(f"LOG:   → Creating chunks...")
                chunks = fn_create_text_chunks(
                    text=markdown_text,
                    source_file=source_name,
                    config=config,
                    language="en",
                )
                view_queue.put(f"LOG:   ✓ Created {len(chunks)} chunks")

                view_queue.put(f"LOG:   → Adding to vector database...")
                storage.add_documents(chunks)
                view_queue.put(f"LOG:   ✓ Added to database")

            view_queue.put(f"LOG: ✅ SUCCESS: {item_name}")

            # Generate summary for changelog
            view_queue.put(f"LOG:   → Generating summary for changelog...")
            try:
                from app_services import fn_generate_summary
                # Use Russian text if available, otherwise English
                text_for_summary = russian_text if do_translation and russian_text else markdown_text
                summary = fn_generate_summary(text_for_summary, config)
                view_queue.put(f"LOG:   ✓ Summary generated")

                # Add to processed items for changelog
                processed_items.append({
                    'name': str(item) if source_type == "web" else item_name,
                    'summary': summary,
                })
            except Exception as summary_error:
                logger.warning(f"Failed to generate summary (non-fatal): {summary_error}")
                view_queue.put(f"LOG:   ⚠️  Summary generation skipped")
                # Add with fallback summary
                processed_items.append({
                    'name': str(item) if source_type == "web" else item_name,
                    'summary': "Не удалось сгенерировать описание документа.",
                })

            view_queue.put("LOG: " + "-" * 50)

            success_count += 1

        except Exception as e:
            logger.error(f"Failed to process {item_name}: {e}", exc_info=True)
            view_queue.put(f"LOG: ❌ ERROR: {item_name}")
            view_queue.put(f"LOG:   {str(e)}")
            view_queue.put("LOG: " + "-" * 50)
            error_count += 1

    # Final summary
    view_queue.put("LOG: " + "=" * 50)
    view_queue.put(f"LOG: Processing complete!")
    view_queue.put(f"LOG: Success: {success_count} | Errors: {error_count}")

    # Get total document count
    total_docs = storage.get_document_count()
    view_queue.put(f"LOG: Total documents in database: {total_docs}")

    # Clean up memory after ALL PDFs (not between each PDF)
    # Doing it between PDFs causes crashes with marker-pdf models
    if config.CLEANUP_MEMORY_AFTER_PDF:
        try:
            view_queue.put("LOG: → Cleaning up memory...")
            fn_cleanup_pdf_memory()
            view_queue.put("LOG: ✓ Memory freed")
        except Exception as e:
            logger.warning(f"Memory cleanup failed (non-fatal): {e}")
            view_queue.put(f"LOG: ⚠️  Memory cleanup skipped (non-fatal error)")

    # Create changelog file with processed documents
    if processed_items:
        try:
            view_queue.put("LOG: → Creating changelog file...")
            from app_services import fn_create_changelog_file
            changelog_path = fn_create_changelog_file(processed_items, config)
            view_queue.put(f"LOG: ✓ Changelog created: {changelog_path.name}")
        except Exception as e:
            logger.warning(f"Changelog creation failed (non-fatal): {e}")
            view_queue.put(f"LOG: ⚠️  Changelog creation skipped (non-fatal error)")

    # Signal that processing is complete
    view_queue.put("STOP_PROCESSING")


def rag_chat_worker(
    query: str,
    config: AppConfig,
    storage: StorageService,
    view_queue: queue.Queue,
) -> None:
    """
    Worker function to handle RAG chat queries.

    This function runs in a separate thread and performs:
    1. Expand query with date variations (for better semantic search)
    2. Retrieve relevant documents from vector database
    3. Generate response using LLM with context

    Args:
        query: The user's question
        config: Application configuration
        storage: Storage service instance
        view_queue: Queue for sending updates to the GUI
    """
    try:
        # Step 1: Expand query with date variations for better search
        expanded_query = fn_expand_query_with_dates(query)
        if expanded_query != query:
            logger.info(f"Expanded query: '{query}' → '{expanded_query}'")

        # Step 2: Search for relevant documents
        logger.info(f"Searching for documents relevant to: {query[:50]}...")
        retrieved_docs = storage.search_similar_documents(expanded_query, k=config.RAG_TOP_K)

        if not retrieved_docs:
            response = "I don't have any relevant information in my knowledge base to answer this question."
        else:
            # Log retrieved document sources for debugging
            logger.info(f"Generating response with {len(retrieved_docs)} context documents")
            for i, doc in enumerate(retrieved_docs, 1):
                source = doc.metadata.get('source', 'unknown')
                preview = doc.page_content[:100].replace('\n', ' ')
                logger.info(f"  Doc {i}: {source} | Preview: {preview}...")

            # Step 3: Generate response with context
            response = fn_get_rag_response(query, retrieved_docs, config)

        # Send response to view
        view_queue.put(f"CHAT: assistant: {response}")

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        error_message = f"Sorry, an error occurred: {str(e)}"
        view_queue.put(f"CHAT: assistant: {error_message}")

    finally:
        # Signal that chat is complete
        view_queue.put("STOP_CHATTING")
