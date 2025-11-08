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
    fn_create_text_chunks,
    fn_extract_markdown,
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

        # Start the queue checker
        self.check_view_queue()

    def bind_events(self) -> None:
        """
        Bind View widgets to Controller methods.

        This connects user interactions to business logic.
        """
        self.view.bind_start_button(self.on_start_ingestion)
        self.view.bind_send_button(self.on_send_chat_message)

        logger.info("Events bound successfully")

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
        1. Validates input
        2. Sets processing state
        3. Spawns a worker thread to process PDFs
        """
        # Prevent multiple simultaneous processing tasks
        if self.is_processing:
            logger.warning("Processing already in progress")
            return

        # Get settings from the view
        settings = self.view.get_ingestion_settings()
        folder_path = settings["folder_path"]

        # Validate folder selection
        if folder_path == "No folder selected" or not folder_path:
            self.view.show_warning("No Folder", "Please select a folder containing PDF files.")
            return

        folder = Path(folder_path)
        if not folder.exists():
            self.view.show_warning("Invalid Folder", f"Folder does not exist: {folder_path}")
            return

        # Find PDF files
        pdf_files = fn_find_pdf_files(folder)
        if not pdf_files:
            self.view.show_warning("No PDFs", f"No PDF files found in: {folder_path}")
            return

        # Set processing state
        self.is_processing = True
        self.view.set_processing_state(True)
        self.view.clear_log()

        # Log initial message
        self.view_queue.put(f"LOG: Found {len(pdf_files)} PDF file(s)")
        self.view_queue.put(f"LOG: Translation: {'ON' if settings['do_translation'] else 'OFF'}")
        self.view_queue.put(f"LOG: Auto-tagging: {'ON' if settings['do_tagging'] else 'OFF'}")
        self.view_queue.put("LOG: " + "=" * 50)

        # Spawn worker thread
        worker = threading.Thread(
            target=processing_pipeline_worker,
            args=(pdf_files, settings, self.config, self.storage, self.view_queue),
            daemon=True,
        )
        worker.start()

        logger.info(f"Started processing {len(pdf_files)} PDF files")

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


# ============================================================================
# Worker Functions (Run in Separate Threads)
# ============================================================================


def processing_pipeline_worker(
    pdf_files: list[Path],
    settings: dict,
    config: AppConfig,
    storage: StorageService,
    view_queue: queue.Queue,
) -> None:
    """
    Worker function to process PDF files.

    This function runs in a separate thread and performs:
    1. PDF to Markdown conversion
    2. (Optional) Translation
    3. (Optional) Tagging
    4. Save to disk
    5. Chunk and add to vector database

    Args:
        pdf_files: List of PDF file paths to process
        settings: User settings (translation, tagging)
        config: Application configuration
        storage: Storage service instance
        view_queue: Queue for sending updates to the GUI

    NOTE: This function is imperative and orchestrates the pure functional services.
    """
    do_translation = settings.get("do_translation", False)
    do_tagging = settings.get("do_tagging", True)

    success_count = 0
    error_count = 0

    for pdf_path in pdf_files:
        try:
            # Step 1: Extract Markdown from PDF
            view_queue.put(f"LOG: Processing {pdf_path.name}...")
            markdown_text = fn_extract_markdown(pdf_path)
            view_queue.put(f"LOG:   ✓ Extracted Markdown ({len(markdown_text)} chars)")

            # Step 2: Translation (optional)
            final_text = markdown_text
            if do_translation:
                view_queue.put(f"LOG:   → Translating to Russian...")
                final_text = fn_translate_text(markdown_text, config)
                view_queue.put(f"LOG:   ✓ Translation complete")

            # Step 3: Tagging (optional)
            tags = ["general"]
            if do_tagging:
                view_queue.put(f"LOG:   → Generating tags...")
                tags = fn_generate_tags(final_text, config)
                view_queue.put(f"LOG:   ✓ Tags: {', '.join(tags)}")

            # Step 4: Save to disk
            primary_tag = tags[0] if tags else "general"
            saved_path = fn_save_markdown_to_disk(
                text=final_text,
                tag=primary_tag,
                filename=pdf_path.stem,
                config=config,
            )
            view_queue.put(f"LOG:   ✓ Saved to: {saved_path}")

            # Step 5: Create chunks and add to vector database
            view_queue.put(f"LOG:   → Creating chunks...")
            chunks = fn_create_text_chunks(
                text=final_text,
                source_file=pdf_path.name,
                config=config,
            )
            view_queue.put(f"LOG:   ✓ Created {len(chunks)} chunks")

            view_queue.put(f"LOG:   → Adding to vector database...")
            storage.add_documents(chunks)
            view_queue.put(f"LOG:   ✓ Added to database")

            view_queue.put(f"LOG: ✅ SUCCESS: {pdf_path.name}")
            view_queue.put("LOG: " + "-" * 50)

            success_count += 1

        except Exception as e:
            logger.error(f"Failed to process {pdf_path.name}: {e}", exc_info=True)
            view_queue.put(f"LOG: ❌ ERROR: {pdf_path.name}")
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
    1. Retrieve relevant documents from vector database
    2. Generate response using LLM with context

    Args:
        query: The user's question
        config: Application configuration
        storage: Storage service instance
        view_queue: Queue for sending updates to the GUI
    """
    try:
        # Step 1: Search for relevant documents
        logger.info(f"Searching for documents relevant to: {query[:50]}...")
        retrieved_docs = storage.search_similar_documents(query, k=config.RAG_TOP_K)

        if not retrieved_docs:
            response = "I don't have any relevant information in my knowledge base to answer this question."
        else:
            # Step 2: Generate response with context
            logger.info(f"Generating response with {len(retrieved_docs)} context documents")
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
