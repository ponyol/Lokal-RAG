"""
Application View Layer - GUI

This module contains the AppView class, built with CustomTkinter.
The View is responsible for:
1. Rendering the UI
2. Capturing user input
3. Displaying output (logs, chat messages)

The View has NO business logic. It only:
- Provides getters for UI state
- Provides setters for updating the display
- Exposes widgets that the Controller can bind to

All heavy operations are delegated to the Controller.
"""

import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional


class AppView:
    """
    The main application view using CustomTkinter.

    This class creates a modern, tabbed interface with:
    - Ingestion tab: For processing PDF files
    - Chat tab: For querying the knowledge base
    """

    def __init__(self, master: ctk.CTk):
        """
        Initialize the application view.

        Args:
            master: The root CustomTkinter window
        """
        self.master = master
        self.master.title("Lokal-RAG - Local Knowledge Base")
        self.master.geometry("900x700")

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize state variables
        self.source_type_var = ctk.StringVar(value="pdf")  # "pdf" or "web"
        self.folder_path_var = ctk.StringVar(value="No folder selected")
        self.web_urls_var = ctk.StringVar(value="")
        self.translate_var = ctk.BooleanVar(value=False)
        self.tag_var = ctk.BooleanVar(value=True)
        self.use_cookies_var = ctk.BooleanVar(value=True)

        # Create the UI
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create all UI widgets and layout."""
        # Create tabview
        self.tabview = ctk.CTkTabview(self.master)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)

        # Add tabs
        self.tabview.add("Ingestion")
        self.tabview.add("Chat")

        # Setup each tab
        self._setup_ingestion_tab()
        self._setup_chat_tab()

    # ========================================================================
    # Ingestion Tab
    # ========================================================================

    def _setup_ingestion_tab(self) -> None:
        """Setup the Ingestion tab UI."""
        tab = self.tabview.tab("Ingestion")

        # Title
        title = ctk.CTkLabel(
            tab,
            text="📚 Content Ingestion",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(pady=(10, 20))

        # Source type selection frame
        source_type_frame = ctk.CTkFrame(tab)
        source_type_frame.pack(fill="x", padx=20, pady=10)

        source_label = ctk.CTkLabel(
            source_type_frame,
            text="Select Source Type:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        source_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.pdf_radio = ctk.CTkRadioButton(
            source_type_frame,
            text="📄 PDF Files (from folder)",
            variable=self.source_type_var,
            value="pdf",
            command=self._on_source_type_changed,
        )
        self.pdf_radio.pack(anchor="w", padx=20, pady=5)

        self.web_radio = ctk.CTkRadioButton(
            source_type_frame,
            text="🌐 Web Articles (URLs)",
            variable=self.source_type_var,
            value="web",
            command=self._on_source_type_changed,
        )
        self.web_radio.pack(anchor="w", padx=20, pady=5)

        # Create a container frame for source-specific inputs
        # This ensures consistent positioning when switching between sources
        self.source_container = ctk.CTkFrame(tab)
        self.source_container.pack(fill="x", padx=20, pady=10)

        # PDF: Folder selection frame
        self.folder_frame = ctk.CTkFrame(self.source_container)
        self.folder_frame.pack(fill="x", padx=0, pady=0)

        self.select_folder_button = ctk.CTkButton(
            self.folder_frame,
            text="Select Folder",
            command=self._on_select_folder_clicked,
            width=120,
        )
        self.select_folder_button.pack(side="left", padx=10, pady=10)

        folder_label = ctk.CTkLabel(
            self.folder_frame,
            textvariable=self.folder_path_var,
            anchor="w",
        )
        folder_label.pack(side="left", fill="x", expand=True, padx=10)

        # WEB: URL input frame
        self.url_frame = ctk.CTkFrame(self.source_container)
        # Don't pack yet - will be shown when web radio is selected

        url_label = ctk.CTkLabel(
            self.url_frame,
            text="Enter URLs (one per line):",
            font=ctk.CTkFont(size=12),
        )
        url_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.url_textbox = ctk.CTkTextbox(
            self.url_frame,
            height=100,
            wrap="word",
        )
        self.url_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # WEB: Authentication option
        self.cookies_checkbox = ctk.CTkCheckBox(
            self.url_frame,
            text="Use browser cookies for authentication (Medium, paywalled sites)",
            variable=self.use_cookies_var,
        )
        self.cookies_checkbox.pack(anchor="w", padx=20, pady=5)

        # Options frame
        options_frame = ctk.CTkFrame(tab)
        options_frame.pack(fill="x", padx=20, pady=10)

        options_title = ctk.CTkLabel(
            options_frame,
            text="Processing Options:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        options_title.pack(anchor="w", padx=10, pady=(10, 5))

        self.translate_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Translate to Russian",
            variable=self.translate_var,
        )
        self.translate_checkbox.pack(anchor="w", padx=20, pady=5)

        self.tag_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Auto-tag content (recommended)",
            variable=self.tag_var,
        )
        self.tag_checkbox.pack(anchor="w", padx=20, pady=5)

        # Start button
        self.start_button = ctk.CTkButton(
            tab,
            text="Start Processing",
            command=None,  # Will be set by controller
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.start_button.pack(pady=20)

        # Log textbox
        log_label = ctk.CTkLabel(
            tab,
            text="Processing Log:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        log_label.pack(anchor="w", padx=20, pady=(10, 5))

        self.log_textbox = ctk.CTkTextbox(
            tab,
            height=250,
            wrap="word",
            state="disabled",
        )
        self.log_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _on_select_folder_clicked(self) -> None:
        """Handle folder selection button click."""
        folder = filedialog.askdirectory(title="Select Folder Containing PDFs")
        if folder:
            self.folder_path_var.set(folder)

    def _on_source_type_changed(self) -> None:
        """Handle source type radio button change."""
        source_type = self.source_type_var.get()

        if source_type == "pdf":
            # Show PDF folder frame, hide URL frame
            self.url_frame.pack_forget()
            self.folder_frame.pack(fill="x", padx=0, pady=0)
        else:  # web
            # Hide PDF folder frame, show URL frame
            self.folder_frame.pack_forget()
            self.url_frame.pack(fill="x", padx=0, pady=0)

    # ========================================================================
    # Chat Tab
    # ========================================================================

    def _setup_chat_tab(self) -> None:
        """Setup the Chat tab UI."""
        tab = self.tabview.tab("Chat")

        # Title
        title = ctk.CTkLabel(
            tab,
            text="💬 Chat with Your Knowledge Base",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(pady=(10, 20))

        # Chat history textbox
        history_label = ctk.CTkLabel(
            tab,
            text="Conversation:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        history_label.pack(anchor="w", padx=20, pady=(0, 5))

        self.chat_history_textbox = ctk.CTkTextbox(
            tab,
            height=400,
            wrap="word",
            state="disabled",
        )
        self.chat_history_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Input frame
        input_frame = ctk.CTkFrame(tab)
        input_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.chat_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your question here...",
            height=40,
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)

        # Bind Enter key to send message
        self.chat_entry.bind("<Return>", lambda e: self._trigger_send_button())

        self.send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            command=None,  # Will be set by controller
            width=100,
            height=40,
        )
        self.send_button.pack(side="right", padx=(5, 10), pady=10)

    def _trigger_send_button(self) -> None:
        """Programmatically trigger the send button."""
        if self.send_button.cget("command"):
            self.send_button.cget("command")()

    # ========================================================================
    # Public API - Getters
    # ========================================================================

    def get_ingestion_settings(self) -> dict:
        """
        Get the current ingestion settings from the UI.

        Returns:
            dict: A dictionary containing:
                - source_type: str ("pdf" or "web")
                - folder_path: str (for PDF sources)
                - web_urls: list[str] (for web sources)
                - do_translation: bool
                - do_tagging: bool
                - use_cookies: bool (for web sources)

        Example:
            >>> settings = view.get_ingestion_settings()
            >>> print(settings['source_type'])
        """
        # Parse web URLs from textbox
        web_urls = []
        if self.source_type_var.get() == "web":
            urls_text = self.url_textbox.get("1.0", "end").strip()
            web_urls = [url.strip() for url in urls_text.split("\n") if url.strip()]

        return {
            "source_type": self.source_type_var.get(),
            "folder_path": self.folder_path_var.get(),
            "web_urls": web_urls,
            "do_translation": self.translate_var.get(),
            "do_tagging": self.tag_var.get(),
            "use_cookies": self.use_cookies_var.get(),
        }

    def get_chat_input(self) -> str:
        """
        Get the current text in the chat input field.

        Returns:
            str: The user's input text

        Example:
            >>> query = view.get_chat_input()
        """
        return self.chat_entry.get()

    def clear_chat_input(self) -> None:
        """
        Clear the chat input field.

        Example:
            >>> view.clear_chat_input()
        """
        self.chat_entry.delete(0, "end")

    # ========================================================================
    # Public API - Setters
    # ========================================================================

    def set_processing_state(self, is_processing: bool) -> None:
        """
        Update the UI to reflect processing state.

        When processing:
        - Disable input controls
        - Change button text to indicate progress

        Args:
            is_processing: True if processing is active, False otherwise

        Example:
            >>> view.set_processing_state(True)  # Start processing
            >>> view.set_processing_state(False)  # Done processing
        """
        if is_processing:
            self.start_button.configure(text="Processing...", state="disabled")
            self.select_folder_button.configure(state="disabled")
            self.translate_checkbox.configure(state="disabled")
            self.tag_checkbox.configure(state="disabled")
        else:
            self.start_button.configure(text="Start Processing", state="normal")
            self.select_folder_button.configure(state="normal")
            self.translate_checkbox.configure(state="normal")
            self.tag_checkbox.configure(state="normal")

    def set_chat_state(self, is_processing: bool) -> None:
        """
        Update the chat UI to reflect processing state.

        Args:
            is_processing: True if a query is being processed, False otherwise

        Example:
            >>> view.set_chat_state(True)  # Waiting for response
            >>> view.set_chat_state(False)  # Ready for new query
        """
        if is_processing:
            self.send_button.configure(text="Thinking...", state="disabled")
            self.chat_entry.configure(state="disabled")
        else:
            self.send_button.configure(text="Send", state="normal")
            self.chat_entry.configure(state="normal")

    def append_log(self, message: str) -> None:
        """
        Append a message to the ingestion log textbox.

        This method is thread-safe and can be called from worker threads
        via the controller's queue mechanism.

        Args:
            message: The log message to append

        Example:
            >>> view.append_log("Processing document.pdf...")
        """
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")  # Auto-scroll to bottom
        self.log_textbox.configure(state="disabled")

    def append_chat_message(self, role: str, message: str) -> None:
        """
        Append a message to the chat history textbox.

        Args:
            role: Either "user" or "assistant"
            message: The message content

        Example:
            >>> view.append_chat_message("user", "What is Python?")
            >>> view.append_chat_message("assistant", "Python is a programming language")
        """
        self.chat_history_textbox.configure(state="normal")

        # Format message with role prefix
        if role.lower() == "user":
            prefix = "You: "
            self.chat_history_textbox.insert("end", f"\n{prefix}", "user_tag")
        else:
            prefix = "Assistant: "
            self.chat_history_textbox.insert("end", f"\n{prefix}", "assistant_tag")

        self.chat_history_textbox.insert("end", f"{message}\n")

        # Configure tags for styling
        self.chat_history_textbox.tag_config("user_tag", foreground="#4A9EFF")
        self.chat_history_textbox.tag_config("assistant_tag", foreground="#7FFF7F")

        self.chat_history_textbox.see("end")  # Auto-scroll to bottom
        self.chat_history_textbox.configure(state="disabled")

    def clear_log(self) -> None:
        """
        Clear all text from the ingestion log.

        Example:
            >>> view.clear_log()
        """
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def show_warning(self, title: str, message: str) -> None:
        """
        Show a warning dialog to the user.

        Args:
            title: The dialog title
            message: The warning message

        Example:
            >>> view.show_warning("Error", "Ollama is not running")
        """
        from tkinter import messagebox
        messagebox.showwarning(title, message)

    def show_info(self, title: str, message: str) -> None:
        """
        Show an info dialog to the user.

        Args:
            title: The dialog title
            message: The info message

        Example:
            >>> view.show_info("Success", "Processing complete!")
        """
        from tkinter import messagebox
        messagebox.showinfo(title, message)

    # ========================================================================
    # Public API - Event Binding
    # ========================================================================

    def bind_start_button(self, callback: Callable) -> None:
        """
        Bind a callback to the start processing button.

        Args:
            callback: Function to call when button is clicked

        Example:
            >>> view.bind_start_button(controller.on_start_ingestion)
        """
        self.start_button.configure(command=callback)

    def bind_send_button(self, callback: Callable) -> None:
        """
        Bind a callback to the send chat message button.

        Args:
            callback: Function to call when button is clicked

        Example:
            >>> view.bind_send_button(controller.on_send_chat_message)
        """
        self.send_button.configure(command=callback)
