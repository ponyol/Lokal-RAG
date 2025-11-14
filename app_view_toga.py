#!/usr/bin/env python3
"""
Toga-based UI for Lokal-RAG Application

This module provides a native UI implementation using Toga (BeeWare).
It replaces CustomTkinter to fix macOS trackpad scrolling issues.

Architecture:
- Pure UI layer (no business logic)
- Same public API as app_view.py for compatibility with app_controller.py
- Native look & feel with platform-native styling
- Native scrolling works on macOS (trackpad, mousewheel, scroll gestures)
"""

import logging
from typing import Optional, Callable
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER
from toga.colors import rgb, TRANSPARENT

logger = logging.getLogger(__name__)

# ===== Light Theme Colors (Default) =====
class Theme:
    """Light theme color palette for Lokal-RAG."""
    # Background colors - use Toga defaults (None = platform default)
    BG_PRIMARY = None  # Main background (platform default)
    BG_SECONDARY = None  # Cards/containers (platform default)
    BG_TERTIARY = None  # Inputs/buttons (platform default)

    # Text colors - use platform defaults
    TEXT_PRIMARY = None  # Main text (platform default)
    TEXT_SECONDARY = None  # Secondary text (platform default)
    TEXT_DISABLED = None  # Disabled text (platform default)

    # Accent colors - keep for button colors
    ACCENT_BLUE = rgb(0, 122, 255)  # Primary actions (system blue)
    ACCENT_GREEN = rgb(52, 199, 89)  # Success (system green)
    ACCENT_ORANGE = rgb(255, 149, 0)  # Warning (system orange)
    ACCENT_RED = rgb(255, 59, 48)  # Error (system red)

    # UI elements
    BORDER = None  # Borders/separators (platform default)
    SCROLLBAR = None  # Scrollbar (platform default)


class LokalRAGApp(toga.App):
    """
    Main Toga application for Lokal-RAG.

    This class manages the UI and provides a public API for the controller
    to interact with the view layer.
    """

    def __init__(self):
        """Initialize the Toga application."""
        super().__init__(
            formal_name="Lokal-RAG",
            app_id="org.lokalrag.app",
            app_name="Lokal-RAG"
        )

        # Callback handlers (set by controller)
        self.on_ingest_callback: Optional[Callable] = None
        self.on_send_message_callback: Optional[Callable] = None
        self.on_save_settings_callback: Optional[Callable] = None
        self.on_save_note_callback: Optional[Callable] = None

        # Source type tracking
        self.source_type_value = "pdf"  # Default to PDF

        logger.info("Toga app initialized with native theme")

    def startup(self):
        """
        Build the UI when the app starts.

        This method is called automatically by Toga after __init__.
        It creates the main window and all tabs.
        """
        logger.info("Building Toga UI...")

        # Create main window
        self.main_window = toga.MainWindow(title=self.formal_name)

        # Create tabs
        self.tabs = toga.OptionContainer(
            style=Pack(),
            content=[
                ("📚 Ingestion", self._create_ingestion_tab()),
                ("💬 Chat", self._create_chat_tab()),
                ("📝 Notes", self._create_notes_tab()),
                ("📋 Changelog", self._create_changelog_tab()),
                ("⚙️ Settings", self._create_settings_tab()),
            ]
        )

        # Set main window content
        self.main_window.content = self.tabs

        # Show the window
        self.main_window.show()

        logger.info("✓ Toga UI created successfully")

    # ========================================================================
    # Tab Creation Methods
    # ========================================================================

    def _create_ingestion_tab(self) -> toga.Widget:
        """
        Create the Ingestion tab UI.

        This tab allows users to:
        - Select source type (PDF/Markdown or Web)
        - Select a folder containing PDFs/Markdown files
        - Enter a web URL to scrape
        - Configure processing options (translation, tagging, vision)
        - Start the ingestion process
        - View processing logs

        Returns:
            toga.Widget: The ingestion tab content
        """
        # Main container (vertical layout)
        container = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20
            )
        )

        # Title
        title = toga.Label(
            "📚 Content Ingestion",
            style=Pack(
                padding_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # ---- Source Type Selection ----
        source_label = toga.Label(
            "Source Type (choose one):",
            style=Pack(
                padding_top=10,
                padding_bottom=10,
                font_weight="bold"
            )
        )
        container.add(source_label)

        # Source type selector
        self.source_type_selection = toga.Selection(
            items=["PDF / Markdown Files", "Web URL"],
            style=Pack(padding=5)
        )
        self.source_type_selection.value = "PDF / Markdown Files"
        self.source_type_selection.on_change = self._on_source_type_changed
        container.add(self.source_type_selection)

        # ---- PDF/Folder Selection ----
        folder_box = toga.Box(style=Pack(direction=ROW, padding=5))
        folder_label = toga.Label(
            "PDF/Markdown Folder:",
            style=Pack(width=180)
        )
        self.folder_input = toga.TextInput(
            readonly=True,
            placeholder="No folder selected",
            style=Pack(flex=1, padding_right=5)
        )
        folder_button = toga.Button(
            "Browse...",
            on_press=self._on_select_folder,
            style=Pack(width=100)
        )
        folder_box.add(folder_label)
        folder_box.add(self.folder_input)
        folder_box.add(folder_button)
        container.add(folder_box)

        # ---- Web URL Input (Multiline for multiple URLs) ----
        url_label = toga.Label(
            "Web URLs (one per line):",
            style=Pack(padding=5, padding_bottom=2)
        )
        container.add(url_label)

        self.url_input = toga.MultilineTextInput(
            placeholder="https://example.com/article1\nhttps://example.com/article2\n...",
            style=Pack(height=100, padding=5)
        )
        container.add(self.url_input)

        # Helper text
        helper_text = toga.Label(
            "Note: Fill in either folder OR URLs based on selection above",
            style=Pack(padding=5, font_size=10)
        )
        container.add(helper_text)

        # ---- Processing Options ----
        options_label = toga.Label(
            "Processing Options:",
            style=Pack(
                padding_top=20,
                padding_bottom=10,
                font_weight="bold"
            )
        )
        container.add(options_label)

        # Translation checkbox
        self.translate_switch = toga.Switch(
            "Enable Translation (auto-detect language → English)",
            style=Pack(
                padding=5
            )
        )
        container.add(self.translate_switch)

        # Auto-tagging checkbox
        self.tagging_switch = toga.Switch(
            "Enable Auto-Tagging (extract topics/themes)",
            value=True,
            style=Pack(
                padding=5
            )
        )
        container.add(self.tagging_switch)

        # Vision mode selection
        vision_box = toga.Box(style=Pack(direction=ROW, padding=5))
        vision_label = toga.Label(
            "Vision Mode:",
            style=Pack(width=180)
        )
        self.vision_mode_selection = toga.Selection(
            items=["disabled", "auto", "local"],
            style=Pack(
                flex=1
            )
        )
        self.vision_mode_selection.value = "auto"
        vision_box.add(vision_label)
        vision_box.add(self.vision_mode_selection)
        container.add(vision_box)

        # ---- Action Buttons ----
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
                padding_top=20,
                padding_bottom=10
            )
        )
        self.start_button = toga.Button(
            "🚀 Start Processing",
            on_press=self._on_start_processing,
            style=Pack(
                padding_right=10,
                flex=1,
                background_color=Theme.ACCENT_GREEN
            )
        )
        self.clear_log_button = toga.Button(
            "🗑️ Clear Log",
            on_press=self._on_clear_log,
            style=Pack(
                flex=1,
                background_color=Theme.ACCENT_RED
            )
        )
        button_box.add(self.start_button)
        button_box.add(self.clear_log_button)
        container.add(button_box)

        # ---- Processing Log (Scrollable) ----
        log_label = toga.Label(
            "Processing Log:",
            style=Pack(
                padding_top=10,
                padding_bottom=5,
                font_weight="bold"
            )
        )
        container.add(log_label)

        # MultilineTextInput for logs (readonly)
        self.log_output = toga.MultilineTextInput(
            readonly=True,
            placeholder="Processing logs will appear here...",
            style=Pack(
                flex=1,
                height=250
            )
        )
        container.add(self.log_output)

        # Wrap in ScrollContainer for native scrolling
        return toga.ScrollContainer(
            content=container,
            style=Pack()
        )

    def _create_chat_tab(self) -> toga.Widget:
        """
        Create the Chat tab UI.

        Returns:
            toga.Widget: The chat tab content
        """
        container = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20
            )
        )

        title = toga.Label(
            "💬 Chat with Your Knowledge Base",
            style=Pack(
                padding_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # Chat history display
        self.chat_history = toga.MultilineTextInput(
            readonly=True,
            placeholder="Chat history will appear here...\n\nAsk questions about your documents!",
            style=Pack(
                flex=1,
                height=400
            )
        )
        container.add(self.chat_history)

        # Search type selection
        search_box = toga.Box(
            style=Pack(
                direction=ROW,
                padding_top=15,
                padding_bottom=10
            )
        )
        search_label = toga.Label(
            "Search Type:",
            style=Pack(width=120)
        )
        self.search_type_selection = toga.Selection(
            items=["vector", "bm25", "ensemble"],
            style=Pack(
                flex=1
            )
        )
        self.search_type_selection.value = "vector"
        search_box.add(search_label)
        search_box.add(self.search_type_selection)
        container.add(search_box)

        # Message input
        input_box = toga.Box(style=Pack(direction=ROW, padding_top=10))
        self.chat_input = toga.TextInput(
            placeholder="Type your message here...",
            style=Pack(
                flex=1,
                padding_right=10
            )
        )
        self.send_button = toga.Button(
            "Send",
            on_press=self._on_send_message,
            style=Pack(
                width=100,
                background_color=Theme.ACCENT_BLUE
            )
        )
        input_box.add(self.chat_input)
        input_box.add(self.send_button)
        container.add(input_box)

        return toga.ScrollContainer(
            content=container,
            style=Pack()
        )

    def _create_notes_tab(self) -> toga.Widget:
        """
        Create the Notes tab UI.

        Returns:
            toga.Widget: The notes tab content
        """
        container = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20
            )
        )

        title = toga.Label(
            "📝 Notes",
            style=Pack(
                padding_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # Note text area
        self.note_text = toga.MultilineTextInput(
            placeholder="Create a new note...\n\nYour note will be saved to the knowledge base.",
            style=Pack(
                flex=1,
                height=400
            )
        )
        container.add(self.note_text)

        # Action buttons
        button_box = toga.Box(style=Pack(direction=ROW, padding_top=15))
        save_button = toga.Button(
            "💾 Save Note",
            on_press=self._on_save_note,
            style=Pack(
                flex=1,
                padding_right=10,
                background_color=Theme.ACCENT_GREEN
            )
        )
        clear_button = toga.Button(
            "🗑️ Clear",
            on_press=self._on_clear_note,
            style=Pack(
                flex=1,
                background_color=Theme.ACCENT_RED
            )
        )
        button_box.add(save_button)
        button_box.add(clear_button)
        container.add(button_box)

        return toga.ScrollContainer(
            content=container,
            style=Pack()
        )

    def _create_changelog_tab(self) -> toga.Widget:
        """
        Create the Changelog tab UI.

        Returns:
            toga.Widget: The changelog tab content
        """
        container = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20
            )
        )

        title = toga.Label(
            "📋 Changelog",
            style=Pack(
                padding_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # Changelog viewer
        self.changelog_text = toga.MultilineTextInput(
            readonly=True,
            placeholder="Document processing history will appear here...",
            style=Pack(
                flex=1,
                height=500
            )
        )
        container.add(self.changelog_text)

        return toga.ScrollContainer(
            content=container,
            style=Pack()
        )

    def _create_settings_tab(self) -> toga.Widget:
        """
        Create the Settings tab UI.

        This tab allows users to configure:
        - LLM provider (Ollama, LM Studio, Claude, Gemini, Mistral)
        - API keys and endpoints
        - Model selection
        - Vision settings
        - Vector database paths

        Returns:
            toga.Widget: The settings tab content
        """
        container = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20
            )
        )

        title = toga.Label(
            "⚙️ LLM Settings",
            style=Pack(
                padding_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # ---- LLM Provider Selection ----
        provider_section = self._create_settings_section(
            "LLM Provider:",
            container
        )

        self.llm_provider_selection = toga.Selection(
            items=["ollama", "lmstudio", "claude", "gemini", "mistral"],
            style=Pack(
                padding=5
            )
        )
        self.llm_provider_selection.value = "ollama"
        provider_section.add(self.llm_provider_selection)

        # ---- Ollama Settings ----
        ollama_section = self._create_settings_section(
            "Ollama Settings:",
            container
        )

        ollama_url_box = self._create_input_row(
            "Base URL:",
            "http://localhost:11434"
        )
        self.ollama_url_input = ollama_url_box.children[1]
        ollama_section.add(ollama_url_box)

        ollama_model_box = self._create_input_row(
            "Model Name:",
            "mistral:latest"
        )
        self.ollama_model_input = ollama_model_box.children[1]
        ollama_section.add(ollama_model_box)

        # ---- LM Studio Settings ----
        lmstudio_section = self._create_settings_section(
            "LM Studio Settings:",
            container
        )

        lmstudio_url_box = self._create_input_row(
            "Base URL:",
            "http://localhost:1234/v1"
        )
        self.lmstudio_url_input = lmstudio_url_box.children[1]
        lmstudio_section.add(lmstudio_url_box)

        lmstudio_model_box = self._create_input_row(
            "Model Name:",
            "local-model"
        )
        self.lmstudio_model_input = lmstudio_model_box.children[1]
        lmstudio_section.add(lmstudio_model_box)

        # ---- Claude Settings ----
        claude_section = self._create_settings_section(
            "Claude (Anthropic) Settings:",
            container
        )

        claude_key_box = self._create_input_row(
            "API Key:",
            "sk-ant-...",
            is_password=True
        )
        self.claude_api_key_input = claude_key_box.children[1]
        claude_section.add(claude_key_box)

        claude_model_box = self._create_input_row(
            "Model:",
            "claude-3-5-sonnet-20241022"
        )
        self.claude_model_input = claude_model_box.children[1]
        claude_section.add(claude_model_box)

        # ---- Gemini Settings ----
        gemini_section = self._create_settings_section(
            "Gemini (Google) Settings:",
            container
        )

        gemini_key_box = self._create_input_row(
            "API Key:",
            "AIza...",
            is_password=True
        )
        self.gemini_api_key_input = gemini_key_box.children[1]
        gemini_section.add(gemini_key_box)

        gemini_model_box = self._create_input_row(
            "Model:",
            "gemini-1.5-flash"
        )
        self.gemini_model_input = gemini_model_box.children[1]
        gemini_section.add(gemini_model_box)

        # ---- Mistral Settings ----
        mistral_section = self._create_settings_section(
            "Mistral AI Settings:",
            container
        )

        mistral_key_box = self._create_input_row(
            "API Key:",
            "...",
            is_password=True
        )
        self.mistral_api_key_input = mistral_key_box.children[1]
        mistral_section.add(mistral_key_box)

        mistral_model_box = self._create_input_row(
            "Model:",
            "mistral-large-latest"
        )
        self.mistral_model_input = mistral_model_box.children[1]
        mistral_section.add(mistral_model_box)

        # ---- Vision Settings ----
        vision_section = self._create_settings_section(
            "Vision Settings:",
            container
        )

        vision_provider_box = self._create_input_row(
            "Vision Provider:",
            "ollama"
        )
        self.vision_provider_input = vision_provider_box.children[1]
        vision_section.add(vision_provider_box)

        vision_url_box = self._create_input_row(
            "Vision Base URL:",
            "http://localhost:11434"
        )
        self.vision_base_url_input = vision_url_box.children[1]
        vision_section.add(vision_url_box)

        vision_model_box = self._create_input_row(
            "Vision Model:",
            "granite-docling:258m"
        )
        self.vision_model_input = vision_model_box.children[1]
        vision_section.add(vision_model_box)

        # ---- General Settings ----
        general_section = self._create_settings_section(
            "General Settings:",
            container
        )

        timeout_box = self._create_input_row(
            "LLM Request Timeout (seconds):",
            "300"
        )
        self.timeout_input = timeout_box.children[1]
        general_section.add(timeout_box)

        # ---- Action Buttons ----
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
                padding_top=25,
                padding_bottom=10
            )
        )
        self.save_settings_button = toga.Button(
            "💾 Save Settings",
            on_press=self._on_save_settings,
            style=Pack(
                flex=1,
                padding_right=10,
                background_color=Theme.ACCENT_GREEN
            )
        )
        test_button = toga.Button(
            "🧪 Test Connection",
            on_press=self._on_test_connection,
            style=Pack(
                flex=1,
                background_color=Theme.ACCENT_BLUE
            )
        )
        button_box.add(self.save_settings_button)
        button_box.add(test_button)
        container.add(button_box)

        return toga.ScrollContainer(
            content=container,
            style=Pack()
        )

    # ========================================================================
    # Helper Methods for Settings UI
    # ========================================================================

    def _create_settings_section(self, title: str, parent: toga.Box) -> toga.Box:
        """
        Create a settings section with a title and container.

        Args:
            title: Section title
            parent: Parent container to add section to

        Returns:
            toga.Box: The section container
        """
        section = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=10
            )
        )

        section_title = toga.Label(
            title,
            style=Pack(
                padding_bottom=10,
                font_weight="bold"
            )
        )
        section.add(section_title)
        parent.add(section)

        return section

    def _create_input_row(
        self,
        label_text: str,
        placeholder: str,
        is_password: bool = False
    ) -> toga.Box:
        """
        Create an input row with label and text field.

        Args:
            label_text: Label text
            placeholder: Placeholder for input
            is_password: Whether to use password input

        Returns:
            toga.Box: The input row
        """
        row = toga.Box(style=Pack(direction=ROW, padding=5))

        label = toga.Label(
            label_text,
            style=Pack(width=150)
        )

        if is_password:
            input_field = toga.PasswordInput(
                placeholder=placeholder,
                style=Pack(
                    flex=1
                )
            )
        else:
            input_field = toga.TextInput(
                placeholder=placeholder,
                style=Pack(
                    flex=1
                )
            )

        row.add(label)
        row.add(input_field)

        return row

    # ========================================================================
    # Event Handlers (Internal)
    # ========================================================================

    def _on_source_type_changed(self, widget):
        """Handle source type selection change."""
        if self.source_type_selection.value == "PDF / Markdown Files":
            self.source_type_value = "pdf"
            logger.info("Source type changed to: pdf")
        else:  # "Web URL"
            self.source_type_value = "web"
            logger.info("Source type changed to: web")

    def _on_select_folder(self, widget):
        """Handle folder selection button press."""
        try:
            folder_path = self.main_window.select_folder_dialog(
                "Select PDF/Markdown Folder"
            )
            if folder_path:
                self.folder_input.value = str(folder_path)
                logger.info(f"Folder selected: {folder_path}")
        except Exception as e:
            logger.error(f"Error selecting folder: {e}")

    def _on_start_processing(self, widget):
        """Handle start processing button press."""
        if self.on_ingest_callback:
            self.on_ingest_callback()
        else:
            logger.warning("No ingest callback set")

    def _on_clear_log(self, widget):
        """Handle clear log button press."""
        self.clear_log()

    def _on_send_message(self, widget):
        """Handle send message button press."""
        if self.on_send_message_callback:
            self.on_send_message_callback()
        else:
            logger.warning("No send message callback set")

    def _on_save_note(self, widget):
        """Handle save note button press."""
        if self.on_save_note_callback:
            self.on_save_note_callback()
        else:
            logger.warning("No save note callback set")

    def _on_clear_note(self, widget):
        """Handle clear note button press."""
        self.clear_note_text()

    def _on_save_settings(self, widget):
        """Handle save settings button press."""
        if self.on_save_settings_callback:
            self.on_save_settings_callback()
        else:
            logger.warning("No save settings callback set")

    def _on_test_connection(self, widget):
        """Handle test connection button press."""
        # TODO: Implement connection testing
        logger.info("Test connection clicked (not yet implemented)")
        self.main_window.info_dialog(
            "Test Connection",
            "Connection testing will be implemented in the next phase."
        )

    # ========================================================================
    # Public API (for app_controller.py)
    # ========================================================================

    def get_ingestion_settings(self) -> dict:
        """
        Get current ingestion settings from the UI.

        Returns:
            dict: Ingestion settings with keys:
                - source_type: str ("pdf" or "web")
                - folder_path: str
                - web_url: str
                - translate: bool
                - auto_tag: bool
                - vision_mode: str
        """
        return {
            "source_type": self.source_type_value,
            "folder_path": self.folder_input.value or "",
            "web_url": self.url_input.value or "",
            "translate": self.translate_switch.value,
            "auto_tag": self.tagging_switch.value,
            "vision_mode": self.vision_mode_selection.value,
        }

    def get_chat_input(self) -> str:
        """Get the current chat input text."""
        return self.chat_input.value or ""

    def clear_chat_input(self) -> None:
        """Clear the chat input field."""
        self.chat_input.value = ""

    def get_search_type(self) -> Optional[str]:
        """Get the selected search type."""
        return self.search_type_selection.value

    def get_note_text(self) -> str:
        """Get the current note text."""
        return self.note_text.value or ""

    def clear_note_text(self) -> None:
        """Clear the note text area."""
        self.note_text.value = ""

    def get_llm_settings(self) -> dict:
        """
        Get current LLM settings from the UI.

        Returns:
            dict: LLM settings with all provider configurations
        """
        return {
            "llm_provider": self.llm_provider_selection.value,
            # Ollama
            "ollama_base_url": self.ollama_url_input.value or "",
            "ollama_model": self.ollama_model_input.value or "",
            # LM Studio
            "lmstudio_base_url": self.lmstudio_url_input.value or "",
            "lmstudio_model": self.lmstudio_model_input.value or "",
            # Claude
            "claude_api_key": self.claude_api_key_input.value or "",
            "claude_model": self.claude_model_input.value or "",
            # Gemini
            "gemini_api_key": self.gemini_api_key_input.value or "",
            "gemini_model": self.gemini_model_input.value or "",
            # Mistral
            "mistral_api_key": self.mistral_api_key_input.value or "",
            "mistral_model": self.mistral_model_input.value or "",
            # Vision
            "vision_mode": self.vision_mode_selection.value or "auto",
            "vision_provider": self.vision_provider_input.value or "",
            "vision_base_url": self.vision_base_url_input.value or "",
            "vision_model": self.vision_model_input.value or "",
            # General
            "timeout": self.timeout_input.value or "300",
        }

    def set_llm_settings(self, settings: dict) -> None:
        """
        Set LLM settings in the UI.

        Args:
            settings: Dictionary of settings to populate
        """
        logger.info(f"Loading settings into UI: {list(settings.keys())}")

        if "llm_provider" in settings:
            provider = settings["llm_provider"]
            logger.info(f"Setting LLM provider to: {provider}")
            self.llm_provider_selection.value = provider

        # Ollama
        if "ollama_base_url" in settings:
            self.ollama_url_input.value = settings["ollama_base_url"]
        if "ollama_model" in settings:
            self.ollama_model_input.value = settings["ollama_model"]

        # LM Studio
        if "lmstudio_base_url" in settings:
            self.lmstudio_url_input.value = settings["lmstudio_base_url"]
        if "lmstudio_model" in settings:
            self.lmstudio_model_input.value = settings["lmstudio_model"]

        # Claude
        if "claude_api_key" in settings:
            self.claude_api_key_input.value = settings["claude_api_key"]
        if "claude_model" in settings:
            self.claude_model_input.value = settings["claude_model"]

        # Gemini
        if "gemini_api_key" in settings:
            self.gemini_api_key_input.value = settings["gemini_api_key"]
        if "gemini_model" in settings:
            self.gemini_model_input.value = settings["gemini_model"]

        # Mistral
        if "mistral_api_key" in settings:
            self.mistral_api_key_input.value = settings["mistral_api_key"]
        if "mistral_model" in settings:
            self.mistral_model_input.value = settings["mistral_model"]

        # Vision
        if "vision_mode" in settings:
            vision_mode = settings["vision_mode"]
            logger.info(f"Setting vision mode to: {vision_mode}")
            self.vision_mode_selection.value = vision_mode
        if "vision_provider" in settings:
            self.vision_provider_input.value = settings["vision_provider"]
        if "vision_base_url" in settings:
            self.vision_base_url_input.value = settings["vision_base_url"]
        if "vision_model" in settings:
            self.vision_model_input.value = settings["vision_model"]

        # General
        if "timeout" in settings:
            timeout_val = str(settings["timeout"])
            logger.info(f"Setting timeout to: {timeout_val}")
            self.timeout_input.value = timeout_val

        logger.info("✓ Settings loaded into UI successfully")

    def set_processing_state(self, is_processing: bool) -> None:
        """
        Update UI to reflect processing state.

        Args:
            is_processing: True if processing is active
        """
        self.start_button.enabled = not is_processing
        if is_processing:
            self.start_button.text = "⏳ Processing..."
            self.start_button.style.update(background_color=Theme.ACCENT_ORANGE)
        else:
            self.start_button.text = "🚀 Start Processing"
            self.start_button.style.update(background_color=Theme.ACCENT_GREEN)

    def set_chat_state(self, is_processing: bool) -> None:
        """
        Update UI to reflect chat processing state.

        Args:
            is_processing: True if chat is processing
        """
        self.send_button.enabled = not is_processing
        self.chat_input.enabled = not is_processing
        if is_processing:
            self.send_button.text = "⏳ Thinking..."
            self.send_button.style.update(background_color=Theme.ACCENT_ORANGE)
        else:
            self.send_button.text = "Send"
            self.send_button.style.update(background_color=Theme.ACCENT_BLUE)

    def append_log(self, message: str) -> None:
        """
        Append a message to the processing log.

        Args:
            message: The message to append
        """
        current = self.log_output.value or ""
        self.log_output.value = current + message + "\n"
        # Auto-scroll to bottom by setting cursor to end
        # NOTE: Toga may handle this automatically

    def append_chat_message(self, role: str, message: str) -> None:
        """
        Append a message to the chat history.

        Args:
            role: The role (user/assistant)
            message: The message content
        """
        current = self.chat_history.value or ""

        # Format the message
        if role == "user":
            formatted = f"👤 You: {message}\n"
        elif role == "assistant":
            formatted = f"🤖 Assistant: {message}\n"
        else:
            formatted = f"{role}: {message}\n"

        self.chat_history.value = current + formatted + "\n"

    def clear_log(self) -> None:
        """Clear the processing log."""
        self.log_output.value = ""

    def show_error_dialog(self, title: str, message: str) -> None:
        """
        Show an error dialog to the user.

        Args:
            title: Dialog title
            message: Error message
        """
        self.main_window.error_dialog(title, message)

    def show_info_dialog(self, title: str, message: str) -> None:
        """
        Show an info dialog to the user.

        Args:
            title: Dialog title
            message: Info message
        """
        self.main_window.info_dialog(title, message)


def main():
    """Entry point for running the Toga app standalone."""
    return LokalRAGApp()


if __name__ == "__main__":
    main().main_loop()
