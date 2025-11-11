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
from pathlib import Path
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
        self.extract_images_var = ctk.BooleanVar(value=False)
        self.use_cookies_var = ctk.BooleanVar(value=True)
        self.browser_choice_var = ctk.StringVar(value="chrome")
        self.save_raw_html_var = ctk.BooleanVar(value=False)

        # LLM Settings state variables
        self.llm_provider_var = ctk.StringVar(value="ollama")
        self.ollama_url_var = ctk.StringVar(value="http://localhost:11434")
        self.ollama_model_var = ctk.StringVar(value="qwen2.5:7b-instruct")
        self.lmstudio_url_var = ctk.StringVar(value="http://localhost:1234/v1")
        self.lmstudio_model_var = ctk.StringVar(value="meta-llama-3.1-8b-instruct")
        self.claude_api_key_var = ctk.StringVar(value="")
        self.claude_model_var = ctk.StringVar(value="claude-3-5-sonnet-20241022")
        self.gemini_api_key_var = ctk.StringVar(value="")
        self.gemini_model_var = ctk.StringVar(value="gemini-2.5-pro-preview-03-25")
        self.mistral_api_key_var = ctk.StringVar(value="")
        self.mistral_model_var = ctk.StringVar(value="mistral-small-latest")
        self.timeout_var = ctk.StringVar(value="300")
        self.translation_chunk_var = ctk.StringVar(value="2000")

        # Storage paths state variables
        self.vector_db_path_var = ctk.StringVar(value="./lokal_rag_db")
        self.markdown_output_path_var = ctk.StringVar(value="./output_markdown")
        self.changelog_path_var = ctk.StringVar(value="./changelog")

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
        self.tabview.add("Changelog")
        self.tabview.add("Settings")

        # Setup each tab
        self._setup_ingestion_tab()
        self._setup_chat_tab()
        self._setup_changelog_tab()
        self._setup_settings_tab()

    # ========================================================================
    # Ingestion Tab
    # ========================================================================

    def _setup_ingestion_tab(self) -> None:
        """Setup the Ingestion tab UI."""
        tab = self.tabview.tab("Ingestion")

        # Create scrollable frame for all content
        scrollable_frame = ctk.CTkScrollableFrame(tab)
        scrollable_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._enable_mousewheel_scrolling(scrollable_frame)

        # Title
        title = ctk.CTkLabel(
            scrollable_frame,
            text="📚 Content Ingestion",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(pady=(10, 20))

        # Source type selection frame
        source_type_frame = ctk.CTkFrame(scrollable_frame)
        source_type_frame.pack(fill="x", padx=20, pady=10)

        source_label = ctk.CTkLabel(
            source_type_frame,
            text="Select Source Type:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        source_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.pdf_radio = ctk.CTkRadioButton(
            source_type_frame,
            text="📄 PDF / Markdown Files (from folder)",
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
        self.source_container = ctk.CTkFrame(scrollable_frame)
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
        self._enable_mousewheel_scrolling(self.url_textbox)

        # WEB: Authentication options
        auth_frame = ctk.CTkFrame(self.url_frame)
        auth_frame.pack(fill="x", padx=10, pady=5)

        self.cookies_checkbox = ctk.CTkCheckBox(
            auth_frame,
            text="Use browser cookies for authentication",
            variable=self.use_cookies_var,
        )
        self.cookies_checkbox.pack(anchor="w", padx=10, pady=5)

        # Browser selection
        browser_frame = ctk.CTkFrame(auth_frame)
        browser_frame.pack(fill="x", padx=20, pady=5)

        browser_label = ctk.CTkLabel(
            browser_frame,
            text="Browser:",
            font=ctk.CTkFont(size=12),
        )
        browser_label.pack(side="left", padx=(0, 10))

        self.browser_dropdown = ctk.CTkOptionMenu(
            browser_frame,
            variable=self.browser_choice_var,
            values=["chrome", "firefox", "safari", "edge", "all"],
            width=120,
        )
        self.browser_dropdown.pack(side="left")

        browser_hint = ctk.CTkLabel(
            browser_frame,
            text="(Select where you're logged in to the site)",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        browser_hint.pack(side="left", padx=10)

        # Debug option
        self.raw_html_checkbox = ctk.CTkCheckBox(
            auth_frame,
            text="Save raw HTML for debugging (output_markdown/_debug/)",
            variable=self.save_raw_html_var,
        )
        self.raw_html_checkbox.pack(anchor="w", padx=10, pady=5)

        # Options frame
        options_frame = ctk.CTkFrame(scrollable_frame)
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

        self.extract_images_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Extract images with vision model (slower, requires vision-capable model)",
            variable=self.extract_images_var,
        )
        self.extract_images_checkbox.pack(anchor="w", padx=20, pady=5)

        # Start button
        self.start_button = ctk.CTkButton(
            scrollable_frame,
            text="Start Processing",
            command=None,  # Will be set by controller
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.start_button.pack(pady=20)

        # Log textbox
        log_label = ctk.CTkLabel(
            scrollable_frame,
            text="Processing Log:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        log_label.pack(anchor="w", padx=20, pady=(10, 5))

        self.log_textbox = ctk.CTkTextbox(
            scrollable_frame,
            height=250,
            wrap="word",
            state="disabled",
        )
        self.log_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._enable_mousewheel_scrolling(self.log_textbox)

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
        self._enable_mousewheel_scrolling(self.chat_history_textbox)

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
    # Changelog Tab
    # ========================================================================

    def _setup_changelog_tab(self) -> None:
        """Setup the Changelog tab UI with file list and content viewer."""
        tab = self.tabview.tab("Changelog")

        # Create main container with two panels
        main_frame = ctk.CTkFrame(tab)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel: File list
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.pack(side="left", fill="both", expand=False, padx=(0, 5))
        left_frame.configure(width=250)

        # Left panel title
        list_title = ctk.CTkLabel(
            left_frame,
            text="📋 История обработки",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        list_title.pack(pady=(10, 5))

        # Refresh button
        self.refresh_changelog_button = ctk.CTkButton(
            left_frame,
            text="🔄 Обновить",
            width=200,
            height=30,
            command=self._on_refresh_changelog,
        )
        self.refresh_changelog_button.pack(pady=5)

        # File list (scrollable)
        self.changelog_listbox = ctk.CTkScrollableFrame(left_frame, width=230, height=500)
        self.changelog_listbox.pack(fill="both", expand=True, pady=5)
        self._enable_mousewheel_scrolling(self.changelog_listbox)

        # Right panel: Content viewer
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Right panel title
        content_title = ctk.CTkLabel(
            right_frame,
            text="📄 Содержимое",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        content_title.pack(pady=(10, 5))

        # Content textbox
        self.changelog_content = ctk.CTkTextbox(
            right_frame,
            wrap="word",
            font=ctk.CTkFont(size=12),
        )
        self.changelog_content.pack(fill="both", expand=True, pady=(5, 10), padx=10)
        self._enable_mousewheel_scrolling(self.changelog_content)

        # Store selected file
        self.selected_changelog_file = None

        # Load initial changelog files
        self._load_changelog_files()

    def _on_refresh_changelog(self) -> None:
        """Handle refresh changelog button click."""
        self._load_changelog_files()

    def _load_changelog_files(self) -> None:
        """Load and display changelog files from the changelog directory."""
        from pathlib import Path

        # Clear existing items
        for widget in self.changelog_listbox.winfo_children():
            widget.destroy()

        # Get changelog path from config (we'll pass it from controller later)
        # For now, use default
        changelog_path = Path("./changelog")

        if not changelog_path.exists():
            no_files_label = ctk.CTkLabel(
                self.changelog_listbox,
                text="Нет файлов истории\n\nФайлы будут созданы\nпосле обработки\nдокументов",
                text_color="gray",
                font=ctk.CTkFont(size=11),
            )
            no_files_label.pack(pady=20)
            return

        # Find all .md files
        files = sorted(changelog_path.glob("*.md"), reverse=True)  # Newest first

        if not files:
            no_files_label = ctk.CTkLabel(
                self.changelog_listbox,
                text="Нет файлов истории",
                text_color="gray",
            )
            no_files_label.pack(pady=20)
            return

        # Create button for each file
        for file_path in files:
            # Extract date from filename (YYYY-MM-DD_HH-MM-SS.md)
            filename = file_path.stem
            try:
                date_part, time_part = filename.split('_')
                display_name = f"{date_part}\n{time_part.replace('-', ':')}"
            except:
                display_name = filename

            file_button = ctk.CTkButton(
                self.changelog_listbox,
                text=display_name,
                width=200,
                height=50,
                command=lambda fp=file_path: self._on_changelog_file_selected(fp),
            )
            file_button.pack(pady=2)

    def _on_changelog_file_selected(self, file_path: Path) -> None:
        """Handle changelog file selection."""
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Display in textbox
            self.changelog_content.delete("1.0", "end")
            self.changelog_content.insert("1.0", content)

            self.selected_changelog_file = file_path

        except Exception as e:
            error_text = f"Ошибка при чтении файла:\n{str(e)}"
            self.changelog_content.delete("1.0", "end")
            self.changelog_content.insert("1.0", error_text)

    # ========================================================================
    # Settings Tab
    # ========================================================================

    def _setup_settings_tab(self) -> None:
        """Setup the Settings tab UI."""
        tab = self.tabview.tab("Settings")

        # Create scrollable frame for all content
        scrollable_frame = ctk.CTkScrollableFrame(tab)
        scrollable_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._enable_mousewheel_scrolling(scrollable_frame)

        # Title
        title = ctk.CTkLabel(
            scrollable_frame,
            text="⚙️ LLM Settings",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(pady=(10, 20))

        # Provider selection
        provider_frame = ctk.CTkFrame(scrollable_frame)
        provider_frame.pack(fill="x", padx=20, pady=10)

        provider_label = ctk.CTkLabel(
            provider_frame,
            text="LLM Provider:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        provider_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.provider_dropdown = ctk.CTkOptionMenu(
            provider_frame,
            variable=self.llm_provider_var,
            values=["ollama", "lmstudio", "claude", "gemini", "mistral"],
            command=self._on_provider_changed,
        )
        self.provider_dropdown.pack(anchor="w", padx=20, pady=(0, 10))

        # Ollama settings frame
        ollama_frame = ctk.CTkFrame(scrollable_frame)
        ollama_frame.pack(fill="x", padx=20, pady=10)

        ollama_title = ctk.CTkLabel(
            ollama_frame,
            text="Ollama Settings:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        ollama_title.pack(anchor="w", padx=10, pady=(10, 5))

        ollama_url_label = ctk.CTkLabel(ollama_frame, text="Base URL:")
        ollama_url_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.ollama_url_entry = ctk.CTkEntry(
            ollama_frame,
            textvariable=self.ollama_url_var,
            width=300,
        )
        self.ollama_url_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ollama_model_label = ctk.CTkLabel(ollama_frame, text="Model Name:")
        ollama_model_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.ollama_model_entry = ctk.CTkEntry(
            ollama_frame,
            textvariable=self.ollama_model_var,
            width=300,
        )
        self.ollama_model_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # LM Studio settings frame
        lmstudio_frame = ctk.CTkFrame(scrollable_frame)
        lmstudio_frame.pack(fill="x", padx=20, pady=10)

        lmstudio_title = ctk.CTkLabel(
            lmstudio_frame,
            text="LM Studio Settings:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        lmstudio_title.pack(anchor="w", padx=10, pady=(10, 5))

        lmstudio_url_label = ctk.CTkLabel(lmstudio_frame, text="Base URL:")
        lmstudio_url_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.lmstudio_url_entry = ctk.CTkEntry(
            lmstudio_frame,
            textvariable=self.lmstudio_url_var,
            width=300,
        )
        self.lmstudio_url_entry.pack(anchor="w", padx=20, pady=(0, 10))

        lmstudio_model_label = ctk.CTkLabel(lmstudio_frame, text="Model Name:")
        lmstudio_model_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.lmstudio_model_entry = ctk.CTkEntry(
            lmstudio_frame,
            textvariable=self.lmstudio_model_var,
            width=300,
        )
        self.lmstudio_model_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # Claude settings frame
        claude_frame = ctk.CTkFrame(scrollable_frame)
        claude_frame.pack(fill="x", padx=20, pady=10)

        claude_title = ctk.CTkLabel(
            claude_frame,
            text="Claude (Anthropic) Settings:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        claude_title.pack(anchor="w", padx=10, pady=(10, 5))

        claude_api_key_label = ctk.CTkLabel(claude_frame, text="API Key:")
        claude_api_key_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.claude_api_key_entry = ctk.CTkEntry(
            claude_frame,
            textvariable=self.claude_api_key_var,
            width=400,
            show="*",  # Hide API key
        )
        self.claude_api_key_entry.pack(anchor="w", padx=20, pady=(0, 5))

        claude_hint = ctk.CTkLabel(
            claude_frame,
            text="Get your API key from: https://console.anthropic.com/",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        claude_hint.pack(anchor="w", padx=20, pady=(0, 10))

        claude_model_label = ctk.CTkLabel(claude_frame, text="Model:")
        claude_model_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.claude_model_dropdown = ctk.CTkOptionMenu(
            claude_frame,
            variable=self.claude_model_var,
            values=[
                "claude-3-5-sonnet-20241022",  # Claude 3.5 Sonnet (October 2024)
                "claude-3-7-sonnet-20250219",  # Claude 3.7 Sonnet (February 2025) - Latest
                "claude-3-opus-20240229",      # Claude 3 Opus
            ],
            width=400,
        )
        self.claude_model_dropdown.pack(anchor="w", padx=20, pady=(0, 10))

        # Gemini settings frame
        gemini_frame = ctk.CTkFrame(scrollable_frame)
        gemini_frame.pack(fill="x", padx=20, pady=10)

        gemini_title = ctk.CTkLabel(
            gemini_frame,
            text="Gemini (Google) Settings:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        gemini_title.pack(anchor="w", padx=10, pady=(10, 5))

        gemini_api_key_label = ctk.CTkLabel(gemini_frame, text="API Key:")
        gemini_api_key_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.gemini_api_key_entry = ctk.CTkEntry(
            gemini_frame,
            textvariable=self.gemini_api_key_var,
            width=400,
            show="*",  # Hide API key
        )
        self.gemini_api_key_entry.pack(anchor="w", padx=20, pady=(0, 5))

        gemini_hint = ctk.CTkLabel(
            gemini_frame,
            text="Get your API key from: https://makersuite.google.com/app/apikey",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        gemini_hint.pack(anchor="w", padx=20, pady=(0, 10))

        gemini_model_label = ctk.CTkLabel(gemini_frame, text="Model:")
        gemini_model_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.gemini_model_dropdown = ctk.CTkOptionMenu(
            gemini_frame,
            variable=self.gemini_model_var,
            values=[
                "gemini-2.5-pro-preview-03-25",        # Fast and versatile (recommended)
                "gemini-2.5-flash-preview-09-2025",    # More powerful, slower
                "gemini-2.5-pro-preview-03-25",        # Experimental 2.0 (if available)
            ],
            width=400,
        )
        self.gemini_model_dropdown.pack(anchor="w", padx=20, pady=(0, 10))

        # Mistral settings frame
        mistral_frame = ctk.CTkFrame(scrollable_frame)
        mistral_frame.pack(fill="x", padx=20, pady=10)

        mistral_title = ctk.CTkLabel(
            mistral_frame,
            text="Mistral AI Settings:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        mistral_title.pack(anchor="w", padx=10, pady=(10, 5))

        mistral_api_key_label = ctk.CTkLabel(mistral_frame, text="API Key:")
        mistral_api_key_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.mistral_api_key_entry = ctk.CTkEntry(
            mistral_frame,
            textvariable=self.mistral_api_key_var,
            width=400,
            show="*",
        )
        self.mistral_api_key_entry.pack(anchor="w", padx=20, pady=(0, 5))

        mistral_help = ctk.CTkLabel(
            mistral_frame,
            text="Get your API key from: https://console.mistral.ai/",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        mistral_help.pack(anchor="w", padx=20, pady=(0, 5))

        mistral_model_label = ctk.CTkLabel(mistral_frame, text="Model:")
        mistral_model_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.mistral_model_dropdown = ctk.CTkOptionMenu(
            mistral_frame,
            variable=self.mistral_model_var,
            values=[
                "mistral-small-latest",       # Small, fast (recommended)
                "mistral-large-2411",         # Large, powerful (Nov 2024)
                "mistral-small-2506",         # Small 3.2 (June 2025)
            ],
            width=400,
        )
        self.mistral_model_dropdown.pack(anchor="w", padx=20, pady=(0, 10))

        # Timeout setting
        timeout_frame = ctk.CTkFrame(scrollable_frame)
        timeout_frame.pack(fill="x", padx=20, pady=10)

        timeout_label = ctk.CTkLabel(
            timeout_frame,
            text="Request Timeout (seconds):",
            font=ctk.CTkFont(size=12),
        )
        timeout_label.pack(anchor="w", padx=10, pady=(10, 0))

        self.timeout_entry = ctk.CTkEntry(
            timeout_frame,
            textvariable=self.timeout_var,
            width=100,
        )
        self.timeout_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # Translation chunk size setting
        chunk_frame = ctk.CTkFrame(scrollable_frame)
        chunk_frame.pack(fill="x", padx=20, pady=10)

        chunk_label = ctk.CTkLabel(
            chunk_frame,
            text="Translation Chunk Size (characters):",
            font=ctk.CTkFont(size=12),
        )
        chunk_label.pack(anchor="w", padx=10, pady=(10, 0))

        chunk_help = ctk.CTkLabel(
            chunk_frame,
            text="Size of text chunks for translation. Smaller values = more API calls but better quality.",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        chunk_help.pack(anchor="w", padx=10, pady=(0, 5))

        self.translation_chunk_entry = ctk.CTkEntry(
            chunk_frame,
            textvariable=self.translation_chunk_var,
            width=100,
        )
        self.translation_chunk_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # Storage paths settings
        paths_frame = ctk.CTkFrame(scrollable_frame)
        paths_frame.pack(fill="x", padx=20, pady=10)

        paths_title = ctk.CTkLabel(
            paths_frame,
            text="📁 Storage Paths:",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        paths_title.pack(anchor="w", padx=10, pady=(10, 5))

        paths_help = ctk.CTkLabel(
            paths_frame,
            text="Paths for storing vector database and markdown files (relative to app directory).",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        paths_help.pack(anchor="w", padx=10, pady=(0, 10))

        # Vector DB path
        vector_db_label = ctk.CTkLabel(
            paths_frame,
            text="Vector Database Path:",
            font=ctk.CTkFont(size=12),
        )
        vector_db_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.vector_db_path_entry = ctk.CTkEntry(
            paths_frame,
            textvariable=self.vector_db_path_var,
            width=300,
        )
        self.vector_db_path_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # Markdown output path
        markdown_output_label = ctk.CTkLabel(
            paths_frame,
            text="Markdown Output Path:",
            font=ctk.CTkFont(size=12),
        )
        markdown_output_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.markdown_output_path_entry = ctk.CTkEntry(
            paths_frame,
            textvariable=self.markdown_output_path_var,
            width=300,
        )
        self.markdown_output_path_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # Changelog path
        changelog_path_label = ctk.CTkLabel(
            paths_frame,
            text="Changelog Path:",
            font=ctk.CTkFont(size=12),
        )
        changelog_path_label.pack(anchor="w", padx=20, pady=(5, 0))

        self.changelog_path_entry = ctk.CTkEntry(
            paths_frame,
            textvariable=self.changelog_path_var,
            width=300,
        )
        self.changelog_path_entry.pack(anchor="w", padx=20, pady=(0, 10))

        # Buttons frame
        buttons_frame = ctk.CTkFrame(scrollable_frame)
        buttons_frame.pack(fill="x", padx=20, pady=20)

        self.test_connection_button = ctk.CTkButton(
            buttons_frame,
            text="Test Connection",
            command=None,  # Will be set by controller
            width=150,
        )
        self.test_connection_button.pack(side="left", padx=10, pady=10)

        self.save_settings_button = ctk.CTkButton(
            buttons_frame,
            text="Save Settings",
            command=None,  # Will be set by controller
            width=150,
        )
        self.save_settings_button.pack(side="left", padx=10, pady=10)

        # Status label
        self.settings_status_label = ctk.CTkLabel(
            tab,
            text="",
            font=ctk.CTkFont(size=12),
        )
        self.settings_status_label.pack(padx=20, pady=10)

    def _on_provider_changed(self, choice: str) -> None:
        """Called when LLM provider dropdown changes."""
        # This callback is for future use if needed
        pass

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
                - browser_choice: str (for web sources - "chrome", "firefox", "safari", "edge", "all")
                - save_raw_html: bool (for web sources - save HTML for debugging)

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
            "extract_images": self.extract_images_var.get(),
            "use_cookies": self.use_cookies_var.get(),
            "browser_choice": self.browser_choice_var.get(),
            "save_raw_html": self.save_raw_html_var.get(),
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

    def get_llm_settings(self) -> dict:
        """
        Get the current LLM settings from the UI.

        Returns:
            dict: A dictionary containing LLM configuration

        Example:
            >>> settings = view.get_llm_settings()
            >>> print(settings['llm_provider'])
        """
        return {
            "llm_provider": self.llm_provider_var.get(),
            "ollama_base_url": self.ollama_url_var.get(),
            "ollama_model": self.ollama_model_var.get(),
            "lmstudio_base_url": self.lmstudio_url_var.get(),
            "lmstudio_model": self.lmstudio_model_var.get(),
            "claude_api_key": self.claude_api_key_var.get(),
            "claude_model": self.claude_model_var.get(),
            "gemini_api_key": self.gemini_api_key_var.get(),
            "gemini_model": self.gemini_model_var.get(),
            "mistral_api_key": self.mistral_api_key_var.get(),
            "mistral_model": self.mistral_model_var.get(),
            "timeout": int(self.timeout_var.get()),
            "translation_chunk_size": int(self.translation_chunk_var.get()),
            "vector_db_path": self.vector_db_path_var.get(),
            "markdown_output_path": self.markdown_output_path_var.get(),
            "changelog_path": self.changelog_path_var.get(),
        }

    def set_llm_settings(self, settings: dict) -> None:
        """
        Update the LLM settings UI with values from a dictionary.

        Args:
            settings: Dictionary containing LLM configuration

        Example:
            >>> settings = {"llm_provider": "ollama", "ollama_model": "llama3:8b"}
            >>> view.set_llm_settings(settings)
        """
        if "llm_provider" in settings:
            self.llm_provider_var.set(settings["llm_provider"])

        if "ollama_base_url" in settings:
            self.ollama_url_var.set(settings["ollama_base_url"])

        if "ollama_model" in settings:
            self.ollama_model_var.set(settings["ollama_model"])

        if "lmstudio_base_url" in settings:
            self.lmstudio_url_var.set(settings["lmstudio_base_url"])

        if "lmstudio_model" in settings:
            self.lmstudio_model_var.set(settings["lmstudio_model"])

        if "claude_api_key" in settings:
            self.claude_api_key_var.set(settings["claude_api_key"])

        if "claude_model" in settings:
            self.claude_model_var.set(settings["claude_model"])

        if "gemini_api_key" in settings:
            self.gemini_api_key_var.set(settings["gemini_api_key"])

        if "gemini_model" in settings:
            self.gemini_model_var.set(settings["gemini_model"])

        if "mistral_api_key" in settings:
            self.mistral_api_key_var.set(settings["mistral_api_key"])

        if "mistral_model" in settings:
            self.mistral_model_var.set(settings["mistral_model"])

        if "timeout" in settings:
            self.timeout_var.set(str(settings["timeout"]))

        if "translation_chunk_size" in settings:
            self.translation_chunk_var.set(str(settings["translation_chunk_size"]))

        if "vector_db_path" in settings:
            self.vector_db_path_var.set(settings["vector_db_path"])

        if "markdown_output_path" in settings:
            self.markdown_output_path_var.set(settings["markdown_output_path"])

        if "changelog_path" in settings:
            self.changelog_path_var.set(settings["changelog_path"])

    def show_settings_status(self, message: str, is_error: bool = False) -> None:
        """
        Display a status message in the Settings tab.

        Args:
            message: The message to display
            is_error: True if this is an error message (red text), False for success (green)

        Example:
            >>> view.show_settings_status("Settings saved!", is_error=False)
        """
        color = "red" if is_error else "green"
        self.settings_status_label.configure(text=message, text_color=color)

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
    # Utility Methods
    # ========================================================================

    def _enable_mousewheel_scrolling(self, widget) -> None:
        """
        Enable mouse wheel and trackpad scrolling for a scrollable widget.

        This method binds mouse wheel events to allow scrolling with:
        - macOS trackpad (two-finger swipe)
        - Windows/Linux mouse wheel
        - Linux touchpad scroll

        Args:
            widget: A CTkScrollableFrame or CTkTextbox widget

        Note:
            This is particularly important for macOS users where trackpad
            scrolling is not enabled by default in CustomTkinter widgets.

            CRITICAL FIX: For CTkScrollableFrame created inside a class,
            we must fix the master reference to enable mousewheel event
            propagation. See: https://github.com/TomSchimansky/CustomTkinter/issues/1816
        """
        import sys

        # Check if this is a CTkScrollableFrame with internal canvas
        if hasattr(widget, '_parent_canvas'):
            import logging
            logger = logging.getLogger(__name__)
            canvas = widget._parent_canvas

            logger.info(f"🔧 Setting up DIRECT mousewheel binding for CTkScrollableFrame")
            logger.info(f"   Platform: {sys.platform}")
            logger.info(f"   Canvas: {canvas}")

            # Track which widget has mouse focus
            mouse_over_canvas = [False]  # Use list to allow modification in nested functions

            def on_mousewheel(event):
                """Handle mousewheel event - only scroll if mouse is over THIS canvas."""
                logger.info(f"🖱️  MouseWheel event received: delta={event.delta}, widget={event.widget}, mouse_over={mouse_over_canvas[0]}")

                # CRITICAL: Only scroll if mouse is over THIS specific canvas
                if not mouse_over_canvas[0]:
                    logger.info(f"   ⏭️  Skipping - mouse not over this canvas")
                    return

                # Calculate scroll amount (macOS uses event.delta directly)
                if sys.platform == "darwin":
                    # macOS: delta is already in correct units
                    scroll_amount = -1 * int(event.delta)
                elif sys.platform == "win32":
                    # Windows: delta is in multiples of 120
                    scroll_amount = -1 * int(event.delta / 120)
                else:
                    # Linux: delta is typically +/-1
                    scroll_amount = -1 * int(event.delta)

                logger.info(f"   → Scrolling {scroll_amount} units")

                try:
                    canvas.yview_scroll(scroll_amount, "units")
                    logger.info(f"   ✓ Scroll executed successfully")
                except Exception as e:
                    logger.error(f"   ✗ Scroll failed: {e}")

                return "break"  # Prevent event propagation

            def on_enter(event):
                """Mouse entered the canvas area."""
                mouse_over_canvas[0] = True
                canvas.focus_set()  # Set focus to canvas for keyboard events
                logger.info(f"🔵 Mouse ENTERED canvas area (focus set)")

            def on_leave(event):
                """Mouse left the canvas area."""
                mouse_over_canvas[0] = False
                logger.info(f"🔴 Mouse LEFT canvas area")

            # Try multiple approaches for maximum compatibility

            # Approach 1: Direct binding to canvas (HIGHEST PRIORITY - no add="+")
            canvas.bind("<MouseWheel>", on_mousewheel)
            logger.info(f"✓ Bound <MouseWheel> DIRECTLY to canvas (replaced existing)")

            # Approach 2: Also use bind_all as fallback
            self.master.bind_all("<MouseWheel>", on_mousewheel, add="+")
            logger.info(f"✓ Bound <MouseWheel> with bind_all (added)")

            # Approach 3: Try Button-4/Button-5 for compatibility
            canvas.bind("<Button-4>", lambda e: on_mousewheel(type('Event', (), {'delta': 1, 'widget': e.widget})()))
            canvas.bind("<Button-5>", lambda e: on_mousewheel(type('Event', (), {'delta': -1, 'widget': e.widget})()))
            logger.info(f"✓ Bound <Button-4>/<Button-5> to canvas")

            # Bind Enter/Leave to track mouse position
            canvas.bind("<Enter>", on_enter, add="+")
            canvas.bind("<Leave>", on_leave, add="+")
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            logger.info(f"✓ Bound <Enter>/<Leave> to canvas and widget")

            logger.info(f"✓ Mousewheel setup complete for CTkScrollableFrame")

        else:
            # CTkTextbox - bind directly to the textbox
            def _on_mousewheel_textbox(event):
                """Handle mouse wheel scroll event for textbox."""
                if sys.platform == "darwin":  # macOS
                    widget.yview_scroll(-1 * int(event.delta), "units")
                elif sys.platform == "win32":  # Windows
                    widget.yview_scroll(-1 * int(event.delta / 120), "units")
                else:  # Linux
                    if event.num == 4:
                        widget.yview_scroll(-1, "units")
                    elif event.num == 5:
                        widget.yview_scroll(1, "units")

            if sys.platform != "linux":
                widget.bind("<MouseWheel>", _on_mousewheel_textbox, add="+")
            else:
                widget.bind("<Button-4>", _on_mousewheel_textbox, add="+")
                widget.bind("<Button-5>", _on_mousewheel_textbox, add="+")

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
