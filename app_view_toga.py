#!/usr/bin/env python3
"""
Toga-based UI for Lokal-RAG Application

This module provides a native UI implementation using Toga (BeeWare).
It replaces CustomTkinter to fix macOS trackpad scrolling issues.

Architecture:
- Pure UI layer (no business logic)
- Same public API as app_view.py for compatibility with app_controller.py
- Native look & feel on each platform (macOS Cocoa, Windows WinForms, Linux GTK)

Key Benefits:
- ✅ Native scrolling works on macOS (trackpad, mousewheel, scroll gestures)
- ✅ Cross-platform with native widgets
- ✅ Active development and maintenance
"""

import logging
from typing import Optional, Callable
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)


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

        logger.info("Toga app initialized")

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
        - Select a folder containing PDFs/Markdown files
        - Enter a web URL to scrape
        - Configure processing options (translation, tagging, vision)
        - Start the ingestion process
        - View processing logs

        Returns:
            toga.Widget: The ingestion tab content
        """
        # Main container (vertical layout)
        container = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Title
        title = toga.Label(
            "📚 Content Ingestion",
            style=Pack(padding_bottom=10, font_size=16, font_weight="bold")
        )
        container.add(title)

        # ---- Folder Selection ----
        folder_box = toga.Box(style=Pack(direction=ROW, padding=5))
        folder_label = toga.Label("PDF/Markdown Folder:", style=Pack(width=150))
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

        # ---- Web URL Input ----
        url_box = toga.Box(style=Pack(direction=ROW, padding=5))
        url_label = toga.Label("Web URL:", style=Pack(width=150))
        self.url_input = toga.TextInput(
            placeholder="https://example.com/article",
            style=Pack(flex=1)
        )
        url_box.add(url_label)
        url_box.add(self.url_input)
        container.add(url_box)

        # ---- Processing Options ----
        options_label = toga.Label(
            "Processing Options:",
            style=Pack(padding_top=10, padding_bottom=5, font_weight="bold")
        )
        container.add(options_label)

        # Translation checkbox
        self.translate_switch = toga.Switch(
            "Enable Translation (auto-detect language → English)",
            style=Pack(padding=3)
        )
        container.add(self.translate_switch)

        # Auto-tagging checkbox
        self.tagging_switch = toga.Switch(
            "Enable Auto-Tagging (extract topics/themes)",
            value=True,
            style=Pack(padding=3)
        )
        container.add(self.tagging_switch)

        # Vision mode selection
        vision_box = toga.Box(style=Pack(direction=ROW, padding=5))
        vision_label = toga.Label("Vision Mode:", style=Pack(width=150))
        self.vision_mode_selection = toga.Selection(
            items=["disabled", "auto", "local"],
            style=Pack(flex=1)
        )
        self.vision_mode_selection.value = "auto"
        vision_box.add(vision_label)
        vision_box.add(self.vision_mode_selection)
        container.add(vision_box)

        # ---- Action Buttons ----
        button_box = toga.Box(style=Pack(direction=ROW, padding_top=10, padding_bottom=10))
        self.start_button = toga.Button(
            "🚀 Start Processing",
            on_press=self._on_start_processing,
            style=Pack(padding_right=10, flex=1)
        )
        self.clear_log_button = toga.Button(
            "🗑️ Clear Log",
            on_press=self._on_clear_log,
            style=Pack(flex=1)
        )
        button_box.add(self.start_button)
        button_box.add(self.clear_log_button)
        container.add(button_box)

        # ---- Processing Log (Scrollable) ----
        log_label = toga.Label(
            "Processing Log:",
            style=Pack(padding_top=5, padding_bottom=5, font_weight="bold")
        )
        container.add(log_label)

        # MultilineTextInput for logs (readonly)
        self.log_output = toga.MultilineTextInput(
            readonly=True,
            placeholder="Processing logs will appear here...",
            style=Pack(flex=1, height=200)
        )
        container.add(self.log_output)

        # Wrap in ScrollContainer for native scrolling
        return toga.ScrollContainer(content=container)

    def _create_chat_tab(self) -> toga.Widget:
        """
        Create the Chat tab UI.

        Returns:
            toga.Widget: The chat tab content
        """
        container = toga.Box(style=Pack(direction=COLUMN, padding=10))

        title = toga.Label(
            "💬 Chat with Your Knowledge Base",
            style=Pack(padding_bottom=10, font_size=16, font_weight="bold")
        )
        container.add(title)

        # Chat history display
        self.chat_history = toga.MultilineTextInput(
            readonly=True,
            placeholder="Chat history will appear here...",
            style=Pack(flex=1, height=400)
        )
        container.add(self.chat_history)

        # Search type selection
        search_box = toga.Box(style=Pack(direction=ROW, padding_top=10, padding_bottom=5))
        search_label = toga.Label("Search Type:", style=Pack(width=100))
        self.search_type_selection = toga.Selection(
            items=["vector", "bm25", "ensemble"],
            style=Pack(flex=1)
        )
        self.search_type_selection.value = "vector"
        search_box.add(search_label)
        search_box.add(self.search_type_selection)
        container.add(search_box)

        # Message input
        input_box = toga.Box(style=Pack(direction=ROW, padding_top=5))
        self.chat_input = toga.TextInput(
            placeholder="Type your message here...",
            style=Pack(flex=1, padding_right=5)
        )
        self.send_button = toga.Button(
            "Send",
            on_press=self._on_send_message,
            style=Pack(width=100)
        )
        input_box.add(self.chat_input)
        input_box.add(self.send_button)
        container.add(input_box)

        return toga.ScrollContainer(content=container)

    def _create_notes_tab(self) -> toga.Widget:
        """
        Create the Notes tab UI.

        Returns:
            toga.Widget: The notes tab content
        """
        container = toga.Box(style=Pack(direction=COLUMN, padding=10))

        title = toga.Label(
            "📝 Notes",
            style=Pack(padding_bottom=10, font_size=16, font_weight="bold")
        )
        container.add(title)

        # Note text area
        self.note_text = toga.MultilineTextInput(
            placeholder="Create a new note...",
            style=Pack(flex=1, height=400)
        )
        container.add(self.note_text)

        # Action buttons
        button_box = toga.Box(style=Pack(direction=ROW, padding_top=10))
        save_button = toga.Button(
            "💾 Save Note",
            on_press=self._on_save_note,
            style=Pack(flex=1, padding_right=5)
        )
        clear_button = toga.Button(
            "🗑️ Clear",
            on_press=self._on_clear_note,
            style=Pack(flex=1)
        )
        button_box.add(save_button)
        button_box.add(clear_button)
        container.add(button_box)

        return toga.ScrollContainer(content=container)

    def _create_changelog_tab(self) -> toga.Widget:
        """
        Create the Changelog tab UI.

        Returns:
            toga.Widget: The changelog tab content
        """
        container = toga.Box(style=Pack(direction=COLUMN, padding=10))

        title = toga.Label(
            "📋 Changelog",
            style=Pack(padding_bottom=10, font_size=16, font_weight="bold")
        )
        container.add(title)

        # Changelog viewer (placeholder)
        changelog_text = toga.MultilineTextInput(
            readonly=True,
            placeholder="Changelog will appear here...",
            style=Pack(flex=1, height=400)
        )
        container.add(changelog_text)

        return toga.ScrollContainer(content=container)

    def _create_settings_tab(self) -> toga.Widget:
        """
        Create the Settings tab UI.

        This tab allows users to configure:
        - LLM provider (Ollama, LM Studio, Claude, Gemini, Mistral)
        - API keys
        - Model selection
        - Vector database paths
        - Other application settings

        Returns:
            toga.Widget: The settings tab content
        """
        container = toga.Box(style=Pack(direction=COLUMN, padding=10))

        title = toga.Label(
            "⚙️ Settings",
            style=Pack(padding_bottom=10, font_size=16, font_weight="bold")
        )
        container.add(title)

        # ---- LLM Provider Selection ----
        provider_label = toga.Label(
            "LLM Provider:",
            style=Pack(padding_top=5, padding_bottom=5, font_weight="bold")
        )
        container.add(provider_label)

        self.llm_provider_selection = toga.Selection(
            items=["ollama", "lmstudio", "claude", "gemini", "mistral"],
            style=Pack(padding=5)
        )
        self.llm_provider_selection.value = "ollama"
        container.add(self.llm_provider_selection)

        # ---- Ollama Settings ----
        ollama_label = toga.Label(
            "Ollama Settings:",
            style=Pack(padding_top=10, padding_bottom=5, font_weight="bold")
        )
        container.add(ollama_label)

        # Ollama model
        ollama_model_box = toga.Box(style=Pack(direction=ROW, padding=5))
        ollama_model_label = toga.Label("Model:", style=Pack(width=150))
        self.ollama_model_input = toga.TextInput(
            placeholder="mistral:latest",
            style=Pack(flex=1)
        )
        ollama_model_box.add(ollama_model_label)
        ollama_model_box.add(self.ollama_model_input)
        container.add(ollama_model_box)

        # ---- API Keys Section ----
        api_keys_label = toga.Label(
            "API Keys:",
            style=Pack(padding_top=10, padding_bottom=5, font_weight="bold")
        )
        container.add(api_keys_label)

        # Claude API key
        claude_key_box = toga.Box(style=Pack(direction=ROW, padding=5))
        claude_label = toga.Label("Claude API Key:", style=Pack(width=150))
        self.claude_api_key_input = toga.PasswordInput(
            placeholder="sk-ant-...",
            style=Pack(flex=1)
        )
        claude_key_box.add(claude_label)
        claude_key_box.add(self.claude_api_key_input)
        container.add(claude_key_box)

        # Gemini API key
        gemini_key_box = toga.Box(style=Pack(direction=ROW, padding=5))
        gemini_label = toga.Label("Gemini API Key:", style=Pack(width=150))
        self.gemini_api_key_input = toga.PasswordInput(
            placeholder="AIza...",
            style=Pack(flex=1)
        )
        gemini_key_box.add(gemini_label)
        gemini_key_box.add(self.gemini_api_key_input)
        container.add(gemini_key_box)

        # ---- Action Buttons ----
        button_box = toga.Box(style=Pack(direction=ROW, padding_top=20))
        save_button = toga.Button(
            "💾 Save Settings",
            on_press=self._on_save_settings,
            style=Pack(flex=1, padding_right=5)
        )
        test_button = toga.Button(
            "🧪 Test Connection",
            on_press=self._on_test_connection,
            style=Pack(flex=1)
        )
        button_box.add(save_button)
        button_box.add(test_button)
        container.add(button_box)

        return toga.ScrollContainer(content=container)

    # ========================================================================
    # Event Handlers (Internal)
    # ========================================================================

    def _on_select_folder(self, widget):
        """Handle folder selection button press."""
        try:
            folder_path = self.main_window.select_folder_dialog("Select PDF/Markdown Folder")
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
        # TODO: Implement note saving
        logger.info("Save note clicked (not yet implemented)")

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

    # ========================================================================
    # Public API (for app_controller.py)
    # ========================================================================

    def get_ingestion_settings(self) -> dict:
        """
        Get current ingestion settings from the UI.

        Returns:
            dict: Ingestion settings with keys:
                - folder_path: str
                - web_url: str
                - translate: bool
                - auto_tag: bool
                - vision_mode: str
        """
        return {
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
            dict: LLM settings
        """
        return {
            "llm_provider": self.llm_provider_selection.value,
            "ollama_model": self.ollama_model_input.value or "",
            "claude_api_key": self.claude_api_key_input.value or "",
            "gemini_api_key": self.gemini_api_key_input.value or "",
        }

    def set_llm_settings(self, settings: dict) -> None:
        """
        Set LLM settings in the UI.

        Args:
            settings: Dictionary of settings to populate
        """
        if "llm_provider" in settings:
            self.llm_provider_selection.value = settings["llm_provider"]
        if "ollama_model" in settings:
            self.ollama_model_input.value = settings["ollama_model"]
        if "claude_api_key" in settings:
            self.claude_api_key_input.value = settings["claude_api_key"]
        if "gemini_api_key" in settings:
            self.gemini_api_key_input.value = settings["gemini_api_key"]

    def set_processing_state(self, is_processing: bool) -> None:
        """
        Update UI to reflect processing state.

        Args:
            is_processing: True if processing is active
        """
        self.start_button.enabled = not is_processing
        if is_processing:
            self.start_button.text = "⏳ Processing..."
        else:
            self.start_button.text = "🚀 Start Processing"

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
        else:
            self.send_button.text = "Send"

    def append_log(self, message: str) -> None:
        """
        Append a message to the processing log.

        Args:
            message: The message to append
        """
        current = self.log_output.value or ""
        self.log_output.value = current + message + "\n"
        # TODO: Auto-scroll to bottom (Toga may need additional handling)

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
        # TODO: Auto-scroll to bottom

    def clear_log(self) -> None:
        """Clear the processing log."""
        self.log_output.value = ""


def main():
    """Entry point for running the Toga app standalone."""
    return LokalRAGApp()


if __name__ == "__main__":
    main().main_loop()
