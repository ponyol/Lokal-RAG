#!/usr/bin/env python3
"""
Toga-based UI for Lokal-RAG Application - V2 (FIXED)

This module provides a native UI implementation using Toga (BeeWare).
It replaces CustomTkinter to fix macOS trackpad scrolling issues.

Architecture:
- Pure UI layer (no business logic)
- 100% API-compatible with app_view.py for controller compatibility
- Native look & feel with platform-native styling
- Native scrolling works on macOS (trackpad, mousewheel, scroll gestures)

Version 2 Changes:
- Fixed API incompatibilities (web_urls, do_translation, do_tagging)
- Added missing web authentication settings
- Fixed vision mode and search type mappings
- Added Clear Chat button
- Added storage paths configuration
- Added translation chunk size setting
- Improved Changelog tab with file selection
"""

import logging
from typing import Optional, Callable
from pathlib import Path
import markdown

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER
from toga.colors import rgb, TRANSPARENT

# Import macOS-specific platform code
from app_platform_macos import setup_chat_input_keyboard_handler, update_chat_input_send_mode

logger = logging.getLogger(__name__)

# ===== Light Theme Colors (Default) =====
class LightTheme:
    """Light theme color palette for Lokal-RAG."""
    NAME = "light"

    # Background colors
    BG_PRIMARY = rgb(255, 255, 255)  # White background
    BG_SECONDARY = rgb(245, 245, 247)  # Light gray for containers
    BG_TERTIARY = rgb(255, 255, 255)  # White for inputs

    # Text colors
    TEXT_PRIMARY = rgb(0, 0, 0)  # Black text
    TEXT_SECONDARY = rgb(60, 60, 67)  # Dark gray text
    TEXT_PLACEHOLDER = rgb(142, 142, 147)  # Gray placeholder

    # Accent colors (Apple Human Interface Guidelines)
    ACCENT_BLUE = rgb(0, 122, 255)  # Primary actions
    ACCENT_GREEN = rgb(52, 199, 89)  # Success
    ACCENT_ORANGE = rgb(255, 149, 0)  # Warning
    ACCENT_RED = rgb(255, 59, 48)  # Error

    # UI elements
    BORDER = rgb(209, 209, 214)  # Light border
    SEPARATOR = rgb(209, 209, 214)  # Separator lines


# ===== Dark Theme Colors =====
class DarkTheme:
    """Dark theme color palette for Lokal-RAG (WCAG AAA compliant)."""
    NAME = "dark"

    # Background colors (based on macOS dark mode)
    BG_PRIMARY = rgb(30, 30, 30)  # Dark gray background (#1e1e1e)
    BG_SECONDARY = rgb(44, 44, 46)  # Slightly lighter gray (#2c2c2e)
    BG_TERTIARY = rgb(58, 58, 60)  # Input fields (#3a3a3c)

    # Text colors (high contrast for readability)
    TEXT_PRIMARY = rgb(255, 255, 255)  # White text
    TEXT_SECONDARY = rgb(235, 235, 245)  # Light gray text (#ebebf5)
    TEXT_PLACEHOLDER = rgb(142, 142, 147)  # Gray placeholder (same as light)

    # Accent colors (slightly brighter for dark theme)
    ACCENT_BLUE = rgb(10, 132, 255)  # Brighter blue (#0a84ff)
    ACCENT_GREEN = rgb(48, 209, 88)  # Brighter green (#30d158)
    ACCENT_ORANGE = rgb(255, 159, 10)  # Brighter orange (#ff9f0a)
    ACCENT_RED = rgb(255, 69, 58)  # Brighter red (#ff453a)

    # UI elements
    BORDER = rgb(72, 72, 74)  # Dark border (#48484a)
    SEPARATOR = rgb(72, 72, 74)  # Separator lines


# Current theme (will be set dynamically)
Theme = LightTheme  # Default to light theme


class LokalRAGApp(toga.App):
    """
    Main Toga application for Lokal-RAG.

    This class manages the UI and provides a public API for the controller
    to interact with the view layer.

    V2: 100% API-compatible with CustomTkinter version (app_view.py)
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
        self.on_load_settings_callback: Optional[Callable] = None
        self.on_save_note_callback: Optional[Callable] = None
        self.on_add_notes_from_folder_callback: Optional[Callable] = None
        self.on_clear_chat_callback: Optional[Callable] = None  # NEW
        self.on_ui_ready_callback: Optional[Callable] = None  # NEW: Called when UI is ready

        # Source type tracking
        self.source_type_value = "web"  # Default to WEB

        # Changelog file mapping (for file selection)
        self.changelog_files_map = {}

        # Note templates management
        self.note_templates = []  # Will be loaded from settings

        # Chat messages storage (for markdown rendering)
        self._chat_messages = []  # List of tuples: (role, message)

        # Theme management
        self.current_theme = LightTheme  # Default to light theme
        self.theme_widgets = {
            "containers": [],  # Boxes that need background color
            "labels": [],  # Labels that need text color
            "inputs": [],  # Text inputs that need background/text color
            "buttons": [],  # Buttons (keep accent colors)
        }

        # Window size (will be set from settings)
        self.window_width = 1280  # Default
        self.window_height = 800

        logger.info("Toga app V2 initialized with native theme and fixed API")

    def _get_container_style(self, **kwargs):
        """
        Get Pack style for containers with theme background color.

        This ensures containers use the theme's background color.
        """
        return Pack(background_color=Theme.BG_PRIMARY, **kwargs)

    def _get_secondary_container_style(self, **kwargs):
        """
        Get Pack style for secondary containers (cards, panels).

        This ensures secondary containers use a slightly different background.
        """
        return Pack(background_color=Theme.BG_SECONDARY, **kwargs)

    def _load_theme_preference(self):
        """
        Load theme preference from settings file BEFORE creating UI.

        This is critical because Toga widgets get their colors at creation time
        and can't be easily changed afterwards.
        """
        global Theme

        try:
            from pathlib import Path
            import json

            # Try to load settings from home directory first
            home_settings = Path.home() / ".lokal-rag" / "settings.json"
            project_settings = Path(".lokal-rag") / "settings.json"

            logger.info(f"🔍 Looking for theme settings...")
            logger.info(f"   Home: {home_settings} (exists: {home_settings.exists()})")
            logger.info(f"   Project: {project_settings} (exists: {project_settings.exists()})")

            settings_path = None
            if home_settings.exists():
                settings_path = home_settings
                logger.info(f"📂 Using home settings: {settings_path}")
            elif project_settings.exists():
                settings_path = project_settings
                logger.info(f"📂 Using project settings: {settings_path}")

            if settings_path:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                theme_pref = settings.get("theme", "light")
                logger.info(f"Loaded theme preference from settings: {theme_pref}")

                if theme_pref == "dark":
                    self.current_theme = DarkTheme
                    Theme = DarkTheme
                    logger.info("✓ Dark theme will be applied to UI")
                else:
                    self.current_theme = LightTheme
                    Theme = LightTheme
                    logger.info("✓ Light theme will be applied to UI")

                # Load window size preference
                window_size_pref = settings.get("window_size", "1280x800 (MacBook Air)")
                logger.info(f"📐 Loading window size preference: '{window_size_pref}'")
                # Parse: "1280x800 (MacBook Air)" -> width=1280, height=800
                try:
                    dimensions = window_size_pref.split(" ")[0]  # Get "1280x800"
                    width, height = dimensions.split("x")
                    self.window_width = int(width)
                    self.window_height = int(height)
                    logger.info(f"✓ Parsed window size: {self.window_width}x{self.window_height}")
                except Exception as e:
                    logger.warning(f"Failed to parse window size '{window_size_pref}': {e}")
                    # Keep defaults
                    logger.info(f"Using default window size: {self.window_width}x{self.window_height}")

            else:
                logger.info("No settings file found, using default Light theme")
                self.current_theme = LightTheme
                Theme = LightTheme

        except Exception as e:
            logger.warning(f"Failed to load theme preference: {e}")
            self.current_theme = LightTheme
            Theme = LightTheme

    def startup(self):
        """
        Build the UI when the app starts.

        This method is called automatically by Toga after __init__.
        It creates the main window and all tabs.
        """
        logger.info("Building Toga UI V2...")

        # Load theme preference BEFORE creating UI
        self._load_theme_preference()

        # Create main window
        self.main_window = toga.MainWindow(title=self.formal_name)

        # Set window size from preferences
        try:
            # Note: In Toga, window size is set as a tuple (width, height)
            self.main_window.size = (self.window_width, self.window_height)
            logger.info(f"✓ Window size set to: {self.window_width}x{self.window_height}")
        except Exception as e:
            logger.warning(f"Failed to set window size: {e}")

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

        logger.info("✓ Toga UI V2 created successfully")

        # Notify controller that UI is ready
        if self.on_ui_ready_callback:
            logger.info("Calling UI ready callback...")
            self.on_ui_ready_callback()

    # ========================================================================
    # Tab Creation Methods
    # ========================================================================

    def _create_ingestion_tab(self) -> toga.Widget:
        """
        Create the Ingestion tab UI.

        This tab allows users to:
        - Select source type (PDF/Markdown or Web)
        - Select a folder containing PDFs/Markdown files
        - Enter web URLs to scrape (with auth options)
        - Configure processing options (translation, tagging, vision)
        - Start the ingestion process
        - View processing logs

        V2: Added web authentication settings (use_cookies, browser_choice, save_raw_html)
        V2: Fixed vision_mode to use display text + mapping

        Returns:
            toga.Widget: The ingestion tab content
        """
        # Main container (vertical layout) - Apply theme background
        container = toga.Box(
            style=self._get_container_style(
                direction=COLUMN,
                margin=20
            )
        )

        # Title
        title = toga.Label(
            "📚 Content Ingestion",
            style=Pack(
                margin_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # ---- Source Type Selection ----
        source_label = toga.Label(
            "Source Type (choose one):",
            style=Pack(
                margin_top=10,
                margin_bottom=10,
                font_weight="bold"
            )
        )
        container.add(source_label)

        # Source type selector
        self.source_type_selection = toga.Selection(
            items=["Web URLs", "PDF / Markdown Files"],
            style=Pack(margin=5)
        )
        self.source_type_selection.value = "Web URLs"
        self.source_type_selection.on_change = self._on_source_type_changed
        container.add(self.source_type_selection)

        # ---- PDF/Folder Selection ----
        folder_box = toga.Box(style=Pack(direction=ROW, margin=5))
        folder_label = toga.Label(
            "PDF/Markdown Folder:",
            style=Pack(width=180)
        )
        self.folder_input = toga.TextInput(
            readonly=True,
            placeholder="No folder selected",
            style=Pack(flex=1, margin_right=5)
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
            style=Pack(margin=5, margin_bottom=2)
        )
        container.add(url_label)

        self.url_input = toga.MultilineTextInput(
            placeholder="https://example.com/article1\nhttps://example.com/article2\n...",
            style=Pack(height=100, margin=5)
        )
        container.add(self.url_input)

        # ---- V2: Web Authentication Options ----
        auth_label = toga.Label(
            "Web Authentication Options:",
            style=Pack(
                margin_top=10,
                margin_bottom=5,
                font_weight="bold"
            )
        )
        container.add(auth_label)

        # Use cookies
        self.use_cookies_switch = toga.Switch(
            "Use browser cookies for authentication",
            value=True,
            style=Pack(margin=5)
        )
        container.add(self.use_cookies_switch)

        # Browser selection
        browser_box = toga.Box(style=Pack(direction=ROW, margin=5))
        browser_label = toga.Label(
            "Browser:",
            style=Pack(width=180)
        )
        self.browser_selection = toga.Selection(
            items=["firefox", "chrome", "safari", "edge", "all"],
            style=Pack(flex=1)
        )
        self.browser_selection.value = "firefox"
        browser_box.add(browser_label)
        browser_box.add(self.browser_selection)
        container.add(browser_box)

        browser_hint = toga.Label(
            "(Select where you're logged in to the site)",
            style=Pack(margin_left=185, margin_bottom=5, font_size=10)
        )
        container.add(browser_hint)

        # Save raw HTML for debugging
        self.save_html_switch = toga.Switch(
            "Save raw HTML for debugging (output_markdown/_debug/)",
            value=False,
            style=Pack(margin=5)
        )
        container.add(self.save_html_switch)

        # ---- Processing Options ----
        options_label = toga.Label(
            "Processing Options:",
            style=Pack(
                margin_top=20,
                margin_bottom=10,
                font_weight="bold"
            )
        )
        container.add(options_label)

        # Translation checkbox
        self.translate_switch = toga.Switch(
            "Enable Translation (auto-detect language → Russian)",
            value=False,
            style=Pack(margin=5)
        )
        container.add(self.translate_switch)

        # Auto-tagging checkbox
        self.tagging_switch = toga.Switch(
            "Enable Auto-Tagging (extract topics/themes)",
            value=True,
            style=Pack(margin=5)
        )
        container.add(self.tagging_switch)

        # V2: Vision mode selection (FIXED - display text + mapping)
        vision_box = toga.Box(style=Pack(direction=ROW, margin=5))
        vision_label = toga.Label(
            "Image Extraction Mode:",
            style=Pack(width=180)
        )
        self.vision_mode_selection = toga.Selection(
            items=["Disabled", "Auto (Smart Fallback)", "Local Vision Model"],
            style=Pack(flex=1)
        )
        self.vision_mode_selection.value = "Auto (Smart Fallback)"
        vision_box.add(vision_label)
        vision_box.add(self.vision_mode_selection)
        container.add(vision_box)

        # ---- Action Buttons ----
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_top=20,
                margin_bottom=10
            )
        )
        self.start_button = toga.Button(
            "🚀 Start Processing",
            on_press=self._on_start_processing,
            style=Pack(
                margin_right=10,
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
                margin_top=10,
                margin_bottom=5,
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

        V2: Fixed search_type values ("Всё", "Документы", "Заметки" + mapping)
        V2: Added Clear Chat button

        Returns:
            toga.Widget: The chat tab content
        """
        container = toga.Box(
            style=self._get_container_style(
                direction=COLUMN,
                margin=20
            )
        )

        title = toga.Label(
            "💬 Chat with Your Knowledge Base",
            style=Pack(
                margin_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # V2: Search type selection (FIXED - correct values + Clear button)
        search_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=10
            )
        )
        search_label = toga.Label(
            "Искать в:",
            style=Pack(width=120)
        )
        self.search_type_selection = toga.Selection(
            items=["Всё", "Документы", "Заметки"],
            style=Pack(flex=1, margin_right=10)
        )
        self.search_type_selection.value = "Всё"

        # V2: Clear Chat button
        self.clear_chat_button = toga.Button(
            "Очистить историю",
            on_press=self._on_clear_chat,
            style=Pack(width=150)
        )

        search_box.add(search_label)
        search_box.add(self.search_type_selection)
        search_box.add(self.clear_chat_button)
        container.add(search_box)

        # Chat history display (WebView for markdown rendering)
        self.chat_history = toga.WebView(
            style=Pack(
                flex=1,
                height=400
            )
        )
        # Set initial empty state with placeholder message
        self._render_chat_html()
        container.add(self.chat_history)

        # Message input
        input_box = toga.Box(style=Pack(direction=ROW, margin_top=10))
        self.chat_input = toga.MultilineTextInput(
            placeholder="Type your message here...\n(Press Send button or use keyboard shortcut)",
            style=Pack(
                flex=1,
                margin_right=10,
                height=80
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

        # Set up macOS keyboard handler for chat input (default: Shift+Enter)
        # This will be updated when settings are loaded
        self._setup_chat_keyboard_handler("shift_enter")

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
            style=self._get_container_style(
                direction=COLUMN,
                margin=20
            )
        )

        title = toga.Label(
            "📝 Заметки",
            style=Pack(
                margin_bottom=10,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        desc = toga.Label(
            "Создавайте заметки, которые будут доступны для поиска в чате",
            style=Pack(margin_bottom=10, font_size=12)
        )
        container.add(desc)

        # Template selection
        template_box = toga.Box(style=Pack(direction=ROW, margin_bottom=15))
        template_label = toga.Label(
            "Template:",
            style=Pack(width=100)
        )
        self.note_template_selection = toga.Selection(
            items=["None"],
            on_change=self._on_note_template_selected,
            style=Pack(flex=1)
        )
        self.note_template_selection.value = "None"
        template_box.add(template_label)
        template_box.add(self.note_template_selection)
        container.add(template_box)

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
        button_box = toga.Box(style=Pack(direction=ROW, margin_top=15))
        save_button = toga.Button(
            "💾 Сохранить заметку",
            on_press=self._on_save_note,
            style=Pack(
                flex=1,
                margin_right=10,
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

        # Bulk import section - folder selection
        bulk_label = toga.Label(
            "Bulk Import from Folder:",
            style=Pack(margin_top=15, margin_bottom=5, font_weight="bold")
        )
        container.add(bulk_label)

        folder_box = toga.Box(style=Pack(direction=ROW, margin=5))
        folder_label = toga.Label(
            "Folder with .md files:",
            style=Pack(width=150)
        )
        self.notes_folder_input = toga.TextInput(
            readonly=True,
            placeholder="No folder selected",
            style=Pack(flex=1, margin_right=5)
        )
        folder_button = toga.Button(
            "Browse...",
            on_press=self._on_select_notes_folder,
            style=Pack(width=100)
        )
        folder_box.add(folder_label)
        folder_box.add(self.notes_folder_input)
        folder_box.add(folder_button)
        container.add(folder_box)

        # Import button
        import_button_box = toga.Box(style=Pack(direction=ROW, margin_top=5))
        import_button = toga.Button(
            "📁 Import Notes",
            on_press=self._on_import_notes,
            style=Pack(
                flex=1,
                background_color=Theme.ACCENT_GREEN
            )
        )
        import_button_box.add(import_button)
        container.add(import_button_box)

        # Status label (for showing save success/error messages)
        self.note_status_label = toga.Label(
            "",
            style=Pack(
                margin_top=10,
                font_size=12
            )
        )
        container.add(self.note_status_label)

        return toga.ScrollContainer(
            content=container,
            style=Pack()
        )

    def _create_changelog_tab(self) -> toga.Widget:
        """
        Create the Changelog tab UI.

        V2: Improved implementation with file selection dropdown + content viewer
        (Similar to CustomTkinter's two-panel design, but simplified for Toga)

        Returns:
            toga.Widget: The changelog tab content
        """
        container = toga.Box(
            style=self._get_container_style(
                direction=COLUMN,
                margin=20
            )
        )

        title = toga.Label(
            "📋 История обработки",
            style=Pack(
                margin_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # File selection row
        file_box = toga.Box(style=Pack(direction=ROW, margin=5))
        file_label = toga.Label("Select File:", style=Pack(width=120))
        self.changelog_file_selection = toga.Selection(
            items=[],  # Will be populated by _load_changelog_files()
            style=Pack(flex=1, margin_right=10)
        )
        self.changelog_file_selection.on_change = self._on_changelog_file_changed
        refresh_button = toga.Button(
            "🔄 Обновить",
            on_press=self._on_refresh_changelog,
            style=Pack(width=100)
        )
        file_box.add(file_label)
        file_box.add(self.changelog_file_selection)
        file_box.add(refresh_button)
        container.add(file_box)

        # Content label
        content_label = toga.Label(
            "Содержимое:",
            style=Pack(
                margin_top=10,
                margin_bottom=5,
                font_weight="bold"
            )
        )
        container.add(content_label)

        # Content viewer (WebView for markdown rendering)
        self.changelog_content = toga.WebView(
            style=Pack(
                flex=1,
                height=500
            )
        )
        # Initialize with empty placeholder
        self._render_changelog_html("")
        container.add(self.changelog_content)

        # Load files on startup
        self._load_changelog_files()

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
        - General settings (timeout, translation chunk size)
        - Storage paths (vector DB, markdown output, changelog)

        V2: Added translation_chunk_size
        V2: Added storage paths (vector_db_path, markdown_output_path, changelog_path)

        Returns:
            toga.Widget: The settings tab content
        """
        container = toga.Box(
            style=self._get_container_style(
                direction=COLUMN,
                margin=20
            )
        )

        title = toga.Label(
            "⚙️ LLM Settings",
            style=Pack(
                margin_bottom=20,
                font_size=20,
                font_weight="bold"
            )
        )
        container.add(title)

        # ---- Settings File Location ----
        settings_file_section = self._create_settings_section(
            "Settings File Location:",
            container
        )

        config_location_box = toga.Box(style=Pack(direction=ROW, margin=5))
        config_location_label = toga.Label(
            "Config Path:",
            style=Pack(width=150)
        )
        self.config_location_selection = toga.Selection(
            items=["Home (~/.lokal-rag/settings.json)", "Project (.lokal-rag/settings.json)"],
            style=Pack(flex=1, margin_right=10)
        )
        self.config_location_selection.value = "Home (~/.lokal-rag/settings.json)"

        self.load_settings_button = toga.Button(
            "Load Settings",
            on_press=self._on_load_settings,
            style=Pack(
                width=120,
                background_color=Theme.ACCENT_BLUE
            )
        )

        config_location_box.add(config_location_label)
        config_location_box.add(self.config_location_selection)
        config_location_box.add(self.load_settings_button)
        settings_file_section.add(config_location_box)

        # ---- Appearance Settings (Theme Selection) ----
        appearance_section = self._create_settings_section(
            "Appearance Settings:",
            container
        )

        theme_box = toga.Box(style=Pack(direction=ROW, margin=5))
        theme_label = toga.Label(
            "Theme:",
            style=Pack(width=150)
        )
        self.theme_selection = toga.Selection(
            items=["Light", "Dark"],
            on_change=self._on_theme_changed,
            style=Pack(flex=1)
        )
        self.theme_selection.value = "Light"  # Default to light theme

        theme_box.add(theme_label)
        theme_box.add(self.theme_selection)
        appearance_section.add(theme_box)

        # Window size selection
        window_size_box = toga.Box(style=Pack(direction=ROW, margin=5))
        window_size_label = toga.Label(
            "Window Size:",
            style=Pack(width=150)
        )
        self.window_size_selection = toga.Selection(
            items=[
                "1024x768 (4:3 Classic)",
                "1280x720 (HD 720p)",
                "1280x800 (MacBook Air)",
                "1440x900 (16:10 Wide)",
                "1920x1080 (Full HD)"
            ],
            style=Pack(flex=1)
        )
        self.window_size_selection.value = "1280x800 (MacBook Air)"  # Default

        window_size_box.add(window_size_label)
        window_size_box.add(self.window_size_selection)
        appearance_section.add(window_size_box)

        # ---- Database Language Selection ----
        db_section = self._create_settings_section(
            "Database Settings:",
            container
        )

        db_language_box = toga.Box(style=Pack(direction=ROW, margin=5))
        db_language_label = toga.Label(
            "Database Language:",
            style=Pack(width=150)
        )
        self.db_language_selection = toga.Selection(
            items=["English", "Russian"],
            style=Pack(flex=1)
        )
        self.db_language_selection.value = "English"

        db_language_box.add(db_language_label)
        db_language_box.add(self.db_language_selection)
        db_section.add(db_language_box)

        # Info label
        db_info_label = toga.Label(
            "Note: Database language affects which ChromaDB is used for search. Documents are always added to both databases.",
            style=Pack(margin=5, font_size=10)
        )
        db_section.add(db_info_label)

        # ---- LLM Provider Selection ----
        provider_section = self._create_settings_section(
            "LLM Provider:",
            container
        )

        self.llm_provider_selection = toga.Selection(
            items=["ollama", "lmstudio", "claude", "gemini", "mistral"],
            style=Pack(
                margin=5
            )
        )
        self.llm_provider_selection.value = "ollama"
        provider_section.add(self.llm_provider_selection)

        # ---- Ollama Settings ----
        ollama_section = self._create_settings_section(
            "Ollama Settings:",
            container
        )

        ollama_url_box, self.ollama_url_input = self._create_input_row(
            "Base URL:",
            "http://localhost:11434"
        )
        ollama_section.add(ollama_url_box)

        ollama_model_box, self.ollama_model_input = self._create_input_row(
            "Model Name:",
            "qwen2.5:7b-instruct"
        )
        ollama_section.add(ollama_model_box)

        # ---- LM Studio Settings ----
        lmstudio_section = self._create_settings_section(
            "LM Studio Settings:",
            container
        )

        lmstudio_url_box, self.lmstudio_url_input = self._create_input_row(
            "Base URL:",
            "http://localhost:1234/v1"
        )
        lmstudio_section.add(lmstudio_url_box)

        lmstudio_model_box, self.lmstudio_model_input = self._create_input_row(
            "Model Name:",
            "meta-llama-3.1-8b-instruct"
        )
        lmstudio_section.add(lmstudio_model_box)

        # ---- Claude Settings ----
        claude_section = self._create_settings_section(
            "Claude (Anthropic) Settings:",
            container
        )

        claude_key_box, self.claude_api_key_input = self._create_input_row(
            "API Key:",
            "sk-ant-...",
            is_password=True
        )
        claude_section.add(claude_key_box)

        claude_help = toga.Label(
            "Get your API key from: https://console.anthropic.com/",
            style=Pack(margin=5, font_size=10)
        )
        claude_section.add(claude_help)

        claude_model_box, self.claude_model_input = self._create_input_row(
            "Model:",
            "claude-3-5-sonnet-20241022"
        )
        claude_section.add(claude_model_box)

        # ---- Gemini Settings ----
        gemini_section = self._create_settings_section(
            "Gemini (Google) Settings:",
            container
        )

        gemini_key_box, self.gemini_api_key_input = self._create_input_row(
            "API Key:",
            "AIza...",
            is_password=True
        )
        gemini_section.add(gemini_key_box)

        gemini_help = toga.Label(
            "Get your API key from: https://makersuite.google.com/app/apikey",
            style=Pack(margin=5, font_size=10)
        )
        gemini_section.add(gemini_help)

        gemini_model_box, self.gemini_model_input = self._create_input_row(
            "Model:",
            "gemini-2.5-pro-preview-03-25"
        )
        gemini_section.add(gemini_model_box)

        # ---- Mistral Settings ----
        mistral_section = self._create_settings_section(
            "Mistral AI Settings:",
            container
        )

        mistral_key_box, self.mistral_api_key_input = self._create_input_row(
            "API Key:",
            "...",
            is_password=True
        )
        mistral_section.add(mistral_key_box)

        mistral_help = toga.Label(
            "Get your API key from: https://console.mistral.ai/",
            style=Pack(margin=5, font_size=10)
        )
        mistral_section.add(mistral_help)

        mistral_model_box, self.mistral_model_input = self._create_input_row(
            "Model:",
            "mistral-small-latest"
        )
        mistral_section.add(mistral_model_box)

        # ---- Vision Settings ----
        vision_section = self._create_settings_section(
            "👁️ Vision Settings (Image Extraction):",
            container
        )

        vision_help = toga.Label(
            "Configure local vision provider for image extraction from PDFs (separate from main LLM).",
            style=Pack(margin=5, font_size=10)
        )
        vision_section.add(vision_help)

        vision_provider_box, self.vision_provider_input = self._create_input_row(
            "Vision Provider:",
            "ollama"
        )
        vision_section.add(vision_provider_box)

        vision_url_box, self.vision_base_url_input = self._create_input_row(
            "Vision Base URL:",
            "http://localhost:11434"
        )
        vision_section.add(vision_url_box)

        vision_model_box, self.vision_model_input = self._create_input_row(
            "Vision Model:",
            "granite-docling:258m"
        )
        vision_section.add(vision_model_box)

        vision_model_help = toga.Label(
            "Recommended: granite-docling:258m (lightweight, document-specialized)",
            style=Pack(margin_left=155, font_size=10)
        )
        vision_section.add(vision_model_help)

        # ---- PDF Conversion Settings ----
        pdf_section = self._create_settings_section(
            "📄 PDF Conversion Settings:",
            container
        )

        pdf_help = toga.Label(
            "Choose method for extracting text from PDF files.",
            style=Pack(margin=5, font_size=10)
        )
        pdf_section.add(pdf_help)

        # PDF conversion method selection
        pdf_method_box = toga.Box(style=Pack(direction=ROW, margin=5))
        pdf_method_label = toga.Label(
            "Conversion Method:",
            style=Pack(width=150)
        )
        self.pdf_conversion_method = toga.Selection(
            items=["marker-pdf", "llm-studio-ocr"],
            style=Pack(flex=1)
        )
        self.pdf_conversion_method.value = "marker-pdf"
        pdf_method_box.add(pdf_method_label)
        pdf_method_box.add(self.pdf_conversion_method)
        pdf_section.add(pdf_method_box)

        # LLM Studio OCR settings (shown only when llm-studio-ocr is selected)
        self.llm_ocr_settings_box = toga.Box(style=Pack(direction=COLUMN, margin_left=155))

        llm_ocr_url_box, self.llm_ocr_url_input = self._create_input_row(
            "OCR Base URL:",
            "http://localhost:1234/v1"
        )
        self.llm_ocr_settings_box.add(llm_ocr_url_box)

        llm_ocr_model_box, self.llm_ocr_model_input = self._create_input_row(
            "OCR Model:",
            "ocrflux-3b"
        )
        self.llm_ocr_settings_box.add(llm_ocr_model_box)

        llm_ocr_model_help = toga.Label(
            "Models: ocrflux-3b, deepseek-ocr, or any vision model in LM Studio",
            style=Pack(margin_left=155, font_size=10)
        )
        self.llm_ocr_settings_box.add(llm_ocr_model_help)

        llm_ocr_key_box, self.llm_ocr_api_key_input = self._create_input_row(
            "API Key (optional):",
            ""
        )
        self.llm_ocr_settings_box.add(llm_ocr_key_box)

        # Hide LLM OCR settings by default
        self.llm_ocr_settings_box.style.display = "none"
        pdf_section.add(self.llm_ocr_settings_box)

        # Set on_change handler AFTER creating llm_ocr_settings_box
        # (to avoid AttributeError when handler is triggered during init)
        self.pdf_conversion_method.on_change = self._on_pdf_method_changed

        # ---- General Settings ----
        general_section = self._create_settings_section(
            "General Settings:",
            container
        )

        timeout_box, self.timeout_input = self._create_input_row(
            "LLM Request Timeout (seconds):",
            "300"
        )
        general_section.add(timeout_box)

        # V2: Translation chunk size (ADDED)
        chunk_box, self.translation_chunk_input = self._create_input_row(
            "Translation Chunk Size (characters):",
            "2000"
        )
        general_section.add(chunk_box)

        chunk_help = toga.Label(
            "Size of text chunks for translation. Smaller values = more API calls but better quality.",
            style=Pack(margin_left=155, margin_bottom=5, font_size=10)
        )
        general_section.add(chunk_help)

        # ---- V2: Storage Paths (ADDED) ----
        paths_section = self._create_settings_section(
            "📁 Storage Paths:",
            container
        )

        paths_help = toga.Label(
            "Paths for storing vector databases and markdown files (relative to app directory).",
            style=Pack(margin=5, font_size=10)
        )
        paths_section.add(paths_help)

        # English Vector DB path
        vector_db_en_box, self.vector_db_path_en_input = self._create_input_row(
            "English Vector DB Path:",
            "./chroma_db_en"
        )
        paths_section.add(vector_db_en_box)

        # Russian Vector DB path
        vector_db_ru_box, self.vector_db_path_ru_input = self._create_input_row(
            "Russian Vector DB Path:",
            "./chroma_db_ru"
        )
        paths_section.add(vector_db_ru_box)

        # Markdown output path
        markdown_output_box, self.markdown_output_path_input = self._create_input_row(
            "Markdown Output Path:",
            "./output_markdown"
        )
        paths_section.add(markdown_output_box)

        # Changelog path
        changelog_box, self.changelog_path_input = self._create_input_row(
            "Changelog Path:",
            "./changelog"
        )
        paths_section.add(changelog_box)

        # Notes path
        notes_box, self.notes_path_input = self._create_input_row(
            "Notes Path:",
            "./notes"
        )
        paths_section.add(notes_box)

        # ---- Chat Settings ----
        chat_section = self._create_settings_section(
            "💬 Chat Settings:",
            container
        )

        chat_help = toga.Label(
            "Configure chat behavior and context management.",
            style=Pack(margin=5, font_size=10)
        )
        chat_section.add(chat_help)

        # Chat context messages limit
        context_box, self.chat_context_input = self._create_input_row(
            "Context Messages:",
            "10"
        )
        chat_section.add(context_box)

        context_desc = toga.Label(
            "Number of messages to keep in chat history (higher = more context, more tokens)",
            style=Pack(margin_left=5, margin_bottom=10, font_size=9)
        )
        chat_section.add(context_desc)

        # RAG Top K setting
        rag_topk_box, self.rag_topk_input = self._create_input_row(
            "RAG Top K:",
            "20"
        )
        chat_section.add(rag_topk_box)

        rag_topk_desc = toga.Label(
            "Number of document chunks to retrieve (higher = more context for full documents)",
            style=Pack(margin_left=5, margin_bottom=10, font_size=9)
        )
        chat_section.add(rag_topk_desc)

        # Send key preference
        send_key_box = toga.Box(style=Pack(direction=ROW, margin=5))
        send_key_label = toga.Label(
            "Send Message With:",
            style=Pack(width=200)
        )
        self.chat_send_key_selection = toga.Selection(
            items=["Shift+Enter", "Enter"],
            style=Pack(flex=1)
        )
        self.chat_send_key_selection.value = "Shift+Enter"
        send_key_box.add(send_key_label)
        send_key_box.add(self.chat_send_key_selection)
        chat_section.add(send_key_box)

        send_key_desc = toga.Label(
            "Choose how to send chat messages (Enter alone will add new line if Shift+Enter is selected)",
            style=Pack(margin_left=5, margin_bottom=10, font_size=9)
        )
        chat_section.add(send_key_desc)

        # ---- Note Templates (NEW) ----
        templates_section = self._create_settings_section(
            "📝 Note Templates:",
            container
        )

        templates_help = toga.Label(
            "Create reusable templates for notes. Templates are inserted after the date stamp.",
            style=Pack(margin=5, font_size=10)
        )
        templates_section.add(templates_help)

        # Template selection (for editing/deleting)
        template_select_box = toga.Box(style=Pack(direction=ROW, margin=5))
        template_select_label = toga.Label(
            "Select Template:",
            style=Pack(width=150)
        )
        self.template_selection = toga.Selection(
            items=["None"],
            on_change=self._on_template_selected,
            style=Pack(flex=1)
        )
        self.template_selection.value = "None"
        template_select_box.add(template_select_label)
        template_select_box.add(self.template_selection)
        templates_section.add(template_select_box)

        # Template name input
        template_name_box, self.template_name_input = self._create_input_row(
            "Template Name:",
            "Meeting Notes"
        )
        templates_section.add(template_name_box)

        # Template content input
        content_label = toga.Label(
            "Template Content:",
            style=Pack(margin=5, margin_bottom=2, font_weight="bold")
        )
        templates_section.add(content_label)

        # Content + Buttons in a horizontal row
        content_and_buttons_box = toga.Box(style=Pack(direction=ROW, margin=5))

        # Text input on the left (takes most space)
        self.template_content_input = toga.MultilineTextInput(
            placeholder="Template content...\n\nUse \\n for new lines.",
            style=Pack(flex=1, height=120, margin_right=10)
        )
        content_and_buttons_box.add(self.template_content_input)

        # Buttons on the right (vertical stack)
        template_buttons_column = toga.Box(style=Pack(direction=COLUMN))

        self.add_template_button = toga.Button(
            "➕ Add",
            on_press=self._on_add_template,
            style=Pack(width=100, margin_bottom=5, background_color=Theme.ACCENT_GREEN)
        )
        self.delete_template_button = toga.Button(
            "🗑️ Delete",
            on_press=self._on_delete_template,
            style=Pack(width=100, background_color=Theme.ACCENT_RED)
        )
        self.delete_template_button.enabled = False  # Disabled until template selected

        template_buttons_column.add(self.add_template_button)
        template_buttons_column.add(self.delete_template_button)

        content_and_buttons_box.add(template_buttons_column)
        templates_section.add(content_and_buttons_box)

        # ---- Action Buttons ----
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_top=25,
                margin_bottom=10
            )
        )
        self.save_settings_button = toga.Button(
            "💾 Save Settings",
            on_press=self._on_save_settings,
            style=Pack(
                flex=1,
                margin_right=10,
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
                margin=10
            )
        )

        section_title = toga.Label(
            title,
            style=Pack(
                margin_bottom=10,
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
    ) -> tuple[toga.Box, toga.Widget]:
        """
        Create an input row with label and text field.

        Args:
            label_text: Label text
            placeholder: Placeholder for input
            is_password: Whether to use password input

        Returns:
            tuple: (row_box, input_field) for easy access to both
        """
        row = toga.Box(style=Pack(direction=ROW, margin=5))

        label = toga.Label(
            label_text,
            style=Pack(width=150)
        )

        if is_password:
            input_field = toga.PasswordInput(
                placeholder=placeholder,
                style=Pack(flex=1)
            )
        else:
            input_field = toga.TextInput(
                placeholder=placeholder,
                style=Pack(flex=1)
            )

        row.add(label)
        row.add(input_field)

        return row, input_field

    # ========================================================================
    # Changelog Helper Methods
    # ========================================================================

    def _render_changelog_html(self, markdown_text: str) -> None:
        """
        Render changelog markdown as HTML.

        This method converts markdown to beautifullyformatted HTML with theme-aware styling.

        Args:
            markdown_text: Markdown content to render (empty string for placeholder)
        """
        # Helper function to convert Toga color to hex string
        def color_to_hex(color):
            """Convert Toga color object to hex string."""
            if hasattr(color, 'hex'):
                return color.hex
            elif hasattr(color, 'rgba'):
                rgba = color.rgba
                if hasattr(rgba, 'r'):
                    r = int(rgba.r * 255) if rgba.r <= 1 else int(rgba.r)
                    g = int(rgba.g * 255) if rgba.g <= 1 else int(rgba.g)
                    b = int(rgba.b * 255) if rgba.b <= 1 else int(rgba.b)
                    return f"#{r:02x}{g:02x}{b:02x}"
            return "#000000"

        # Get current theme colors
        theme = self.current_theme

        # Base HTML structure
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: {color_to_hex(theme.TEXT_PRIMARY)};
            background-color: {color_to_hex(theme.BG_PRIMARY)};
            margin: 0;
            padding: 20px;
        }}

        h1 {{
            color: {color_to_hex(theme.ACCENT_BLUE)};
            border-bottom: 2px solid {color_to_hex(theme.ACCENT_BLUE)};
            padding-bottom: 10px;
        }}

        h2 {{
            color: {color_to_hex(theme.ACCENT_GREEN)};
            margin-top: 30px;
        }}

        h3 {{
            color: {color_to_hex(theme.TEXT_PRIMARY)};
        }}

        ul, ol {{
            margin: 10px 0;
            padding-left: 30px;
        }}

        li {{
            margin: 5px 0;
        }}

        code {{
            background-color: rgba(0, 0, 0, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
            font-size: 13px;
        }}

        pre {{
            background-color: rgba(0, 0, 0, 0.1);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 10px 0;
        }}

        pre code {{
            background-color: transparent;
            padding: 0;
        }}

        blockquote {{
            border-left: 4px solid {color_to_hex(theme.ACCENT_BLUE)};
            margin: 10px 0;
            padding-left: 20px;
            color: {color_to_hex(theme.TEXT_SECONDARY)};
        }}

        a {{
            color: {color_to_hex(theme.ACCENT_BLUE)};
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        .placeholder {{
            text-align: center;
            color: {color_to_hex(theme.TEXT_SECONDARY)};
            padding: 60px 20px;
            font-style: italic;
            font-size: 16px;
        }}
    </style>
</head>
<body>
"""

        if not markdown_text or not markdown_text.strip():
            # Show placeholder
            html += """
    <div class="placeholder">
        Select a changelog file to view...<br><br>
        📋 История обработки документов
    </div>
"""
        else:
            # Convert markdown to HTML
            import markdown as md
            html_content = md.markdown(
                markdown_text,
                extensions=['fenced_code', 'codehilite', 'tables', 'nl2br']
            )
            html += html_content

        # Close HTML
        html += """
</body>
</html>
"""

        # Set WebView content
        self.changelog_content.set_content("", html)

    def _load_changelog_files(self):
        """Load changelog files and populate selection."""
        changelog_path = Path("./changelog")
        if not changelog_path.exists():
            self.changelog_file_selection.items = []
            self._render_changelog_html("# No changelog directory found\n\nFiles will be created after processing documents.")
            return

        files = sorted(changelog_path.glob("*.md"), reverse=True)
        if not files:
            self.changelog_file_selection.items = []
            self._render_changelog_html("# No changelog files found\n\nFiles will be created after processing documents.")
            return

        # Create display names
        file_items = []
        self.changelog_files_map = {}  # Map display name -> Path

        for file_path in files:
            filename = file_path.stem
            try:
                date_part, time_part = filename.split('_')
                display_name = f"{date_part} {time_part.replace('-', ':')}"
            except:
                display_name = filename

            file_items.append(display_name)
            self.changelog_files_map[display_name] = file_path

        self.changelog_file_selection.items = file_items
        if file_items:
            self.changelog_file_selection.value = file_items[0]
            self._on_changelog_file_changed(None)

        logger.info(f"Loaded {len(file_items)} changelog files")

    def _on_changelog_file_changed(self, widget):
        """Handle changelog file selection change."""
        selected = self.changelog_file_selection.value
        if not selected or selected not in self.changelog_files_map:
            self._render_changelog_html("")
            return

        file_path = self.changelog_files_map[selected]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._render_changelog_html(content)
            logger.info(f"Loaded changelog file: {file_path.name}")
        except Exception as e:
            self._render_changelog_html(f"# Error reading file\n\n{str(e)}")
            logger.error(f"Error loading changelog file: {e}")

    def _on_refresh_changelog(self, widget):
        """Handle refresh button click."""
        logger.info("Refreshing changelog files...")
        self._load_changelog_files()

    # ========================================================================
    # Event Handlers (Internal)
    # ========================================================================

    def _on_source_type_changed(self, widget):
        """Handle source type selection change."""
        if self.source_type_selection.value == "PDF / Markdown Files":
            self.source_type_value = "pdf"
            logger.info("Source type changed to: pdf")
        else:  # "Web URLs"
            self.source_type_value = "web"
            logger.info("Source type changed to: web")

    def _on_select_folder(self, widget):
        """Handle folder selection button press."""
        import asyncio
        asyncio.create_task(self._select_folder_async())

    async def _select_folder_async(self):
        """Async helper for folder selection dialog."""
        try:
            folder_path = await self.main_window.dialog(
                toga.SelectFolderDialog(title="Select PDF/Markdown Folder")
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

    def _on_clear_chat(self, widget):
        """Handle clear chat button press."""
        if self.on_clear_chat_callback:
            self.on_clear_chat_callback()
        else:
            logger.warning("No clear chat callback set")

    def _setup_chat_keyboard_handler(self, send_key: str = "shift_enter") -> None:
        """
        Set up macOS keyboard handler for chat input.

        This method configures platform-specific keyboard shortcuts for sending
        messages in the chat. On macOS, it intercepts Enter/Shift+Enter keypresses.
        On other platforms, this is a no-op.

        Args:
            send_key: "shift_enter" or "enter" - determines send behavior
        """
        # Create wrapper callback that triggers send
        def send_callback():
            if self.on_send_message_callback:
                self.on_send_message_callback()

        # Set up macOS handler (no-op on other platforms)
        # DISABLED: Keyboard handler causes issues with Settings fields
        # Will revisit in the future - for now, use Send button
        # setup_chat_input_keyboard_handler(
        #     self.chat_input,
        #     send_callback,
        #     send_key
        # )

    def _on_save_note(self, widget):
        """Handle save note button press."""
        if self.on_save_note_callback:
            self.on_save_note_callback()
        else:
            logger.warning("No save note callback set")

    def _on_clear_note(self, widget):
        """Handle clear note button press."""
        self.clear_note_text()

    def _on_select_notes_folder(self, widget):
        """Handle notes folder selection button press."""
        import asyncio
        asyncio.create_task(self._select_notes_folder_async())

    async def _select_notes_folder_async(self):
        """Async helper for notes folder selection dialog."""
        try:
            folder_path = await self.main_window.dialog(
                toga.SelectFolderDialog(title="Select folder with markdown files")
            )
            if folder_path:
                self.notes_folder_input.value = str(folder_path)
                logger.info(f"Notes folder selected: {folder_path}")
        except Exception as e:
            logger.error(f"Error selecting notes folder: {e}")

    def _on_import_notes(self, widget):
        """Handle import notes button press."""
        folder_path = self.notes_folder_input.value

        if not folder_path or folder_path == "No folder selected":
            self.show_note_status("Please select a folder first", is_error=True)
            logger.warning("Import attempted without folder selection")
            return

        if self.on_add_notes_from_folder_callback:
            # Call controller callback with folder path
            self.on_add_notes_from_folder_callback(folder_path)
        else:
            logger.warning("No add notes from folder callback set")

    def _on_pdf_method_changed(self, widget):
        """Handle PDF conversion method selection change."""
        method = self.pdf_conversion_method.value
        logger.info(f"PDF conversion method changed to: {method}")

        # Show/hide LLM OCR settings based on selection
        # NOTE: Toga display property only accepts "pack" or "none" (not "flex")
        if method == "llm-studio-ocr":
            self.llm_ocr_settings_box.style.display = "pack"
        else:
            self.llm_ocr_settings_box.style.display = "none"

    def _on_theme_changed(self, widget):
        """Handle theme selection change."""
        theme_name = self.theme_selection.value
        logger.info(f"Theme changed to: {theme_name}")

        # Update current theme (for saving to settings)
        if theme_name == "Dark":
            self.current_theme = DarkTheme
        else:
            self.current_theme = LightTheme

        # Show info that restart is needed
        logger.info("ℹ️  Theme will be applied after saving settings and restarting the app")
        # Note: We don't call apply_theme() here because Toga can't change
        # widget colors after they're created. The theme will be applied
        # on next app launch via _load_theme_preference() in startup()

    def apply_theme(self):
        """
        Apply the current theme to all UI elements.

        This method updates the colors of all widgets based on the current theme.
        NOTE: Toga has limited styling support, so we focus on background colors
        and button accent colors. Text colors are harder to change dynamically.
        """
        global Theme
        Theme = self.current_theme

        logger.info(f"Applying {self.current_theme.NAME} theme...")

        try:
            # Update main window background
            if hasattr(self, 'main_window') and self.main_window.content:
                # Toga doesn't easily allow changing the main window background
                # But we can change tab container backgrounds
                pass

            # Update button colors (they use Theme.ACCENT_*)
            # The buttons will use the new theme's accent colors on next interaction
            # We can't easily re-render them, but new buttons will use new colors

            # For now, we'll need to recreate the UI to fully apply the theme
            # This is a limitation of Toga's styling system
            logger.info(f"✓ {self.current_theme.NAME.capitalize()} theme applied")
            logger.info("ℹ️  Note: Some elements may need app restart for full theme change")

        except Exception as e:
            logger.error(f"Failed to apply theme: {e}", exc_info=True)

    def _on_load_settings(self, widget):
        """Handle load settings button press."""
        if self.on_load_settings_callback:
            self.on_load_settings_callback()
        else:
            logger.warning("No load settings callback set")

    def _on_save_settings(self, widget):
        """Handle save settings button press."""
        # Update chat keyboard handler with current setting before saving
        send_key_display = self.chat_send_key_selection.value
        send_key = "shift_enter" if send_key_display == "Shift+Enter" else "enter"
        self._setup_chat_keyboard_handler(send_key)

        if self.on_save_settings_callback:
            self.on_save_settings_callback()
        else:
            logger.warning("No save settings callback set")

    def _on_test_connection(self, widget):
        """Handle test connection button press."""
        # TODO: Implement connection testing
        logger.info("Test connection clicked (not yet implemented)")
        self.show_info_dialog(
            "Test Connection",
            "Connection testing will be implemented in the next phase."
        )

    def _on_template_selected(self, widget):
        """Handle template selection change."""
        # Check if UI is fully initialized (may be called during settings load)
        if not hasattr(self, 'template_name_input'):
            return

        selected = self.template_selection.value
        if selected and selected != "None":
            # Find template by name
            template = next((t for t in self.note_templates if t["name"] == selected), None)
            if template:
                self.template_name_input.value = template["name"]
                self.template_content_input.value = template["content"]
                self.delete_template_button.enabled = True
                logger.info(f"Template selected: {selected}")
        else:
            # Clear fields
            self.template_name_input.value = ""
            self.template_content_input.value = ""
            self.delete_template_button.enabled = False

    def _on_add_template(self, widget):
        """Handle add template button press."""
        name = self.template_name_input.value or ""
        content = self.template_content_input.value or ""

        if not name.strip():
            self.show_error_dialog("Error", "Template name cannot be empty")
            return

        if not content.strip():
            self.show_error_dialog("Error", "Template content cannot be empty")
            return

        # Check if template with this name already exists
        existing = next((t for t in self.note_templates if t["name"] == name), None)
        if existing:
            # Update existing template
            existing["content"] = content
            logger.info(f"Updated template: {name}")
        else:
            # Add new template
            self.note_templates.append({"name": name, "content": content})
            logger.info(f"Added new template: {name}")

        # Update template selection dropdown
        self._update_template_selection()

        # Clear fields
        self.template_name_input.value = ""
        self.template_content_input.value = ""
        self.template_selection.value = "None"

        self.show_info_dialog("Success", f"Template '{name}' saved successfully")

    def _on_delete_template(self, widget):
        """Handle delete template button press."""
        selected = self.template_selection.value
        if selected and selected != "None":
            # Remove template
            self.note_templates = [t for t in self.note_templates if t["name"] != selected]
            logger.info(f"Deleted template: {selected}")

            # Update template selection dropdown
            self._update_template_selection()

            # Clear fields
            self.template_name_input.value = ""
            self.template_content_input.value = ""
            self.template_selection.value = "None"
            self.delete_template_button.enabled = False

            self.show_info_dialog("Success", f"Template '{selected}' deleted successfully")

    def _update_template_selection(self):
        """Update template selection dropdown with current templates."""
        template_names = ["None"] + [t["name"] for t in self.note_templates]
        self.template_selection.items = template_names
        # Also update Notes tab template selection
        if hasattr(self, 'note_template_selection'):
            self.note_template_selection.items = template_names
        logger.info(f"Updated template selection: {len(self.note_templates)} templates")

    def _on_note_template_selected(self, widget):
        """Handle note template selection change."""
        # This handler is called when user selects a template in Notes tab
        # The template will be applied when saving the note
        selected = self.note_template_selection.value
        if selected and selected != "None":
            logger.info(f"Note template selected: {selected}")
        else:
            logger.info("No note template selected")

    # ========================================================================
    # Public API (for app_controller.py) - V2: 100% Compatible with CustomTkinter
    # ========================================================================

    def get_ingestion_settings(self) -> dict:
        """
        Get current ingestion settings from the UI.

        V2: FIXED API - 100% compatible with CustomTkinter version
        - web_url → web_urls (list)
        - translate → do_translation
        - auto_tag → do_tagging
        - Added: use_cookies, browser_choice, save_raw_html
        - Fixed: vision_mode mapping

        Returns:
            dict: Ingestion settings with keys:
                - source_type: str ("pdf" or "web")
                - folder_path: str
                - web_urls: list[str]  ← FIXED (was web_url: str)
                - do_translation: bool  ← FIXED (was translate)
                - do_tagging: bool  ← FIXED (was auto_tag)
                - vision_mode: str  ← FIXED (mapped from display text)
                - use_cookies: bool  ← NEW
                - browser_choice: str  ← NEW
                - save_raw_html: bool  ← NEW
        """
        # Parse web URLs from multiline input (FIXED: returns list, not string)
        web_urls = []
        if self.source_type_value == "web":
            urls_text = self.url_input.value or ""
            web_urls = [url.strip() for url in urls_text.split("\n") if url.strip()]

        # Map vision mode display text to config values (FIXED)
        vision_mode_map = {
            "Disabled": "disabled",
            "Auto (Smart Fallback)": "auto",
            "Local Vision Model": "local",
        }
        vision_mode = vision_mode_map.get(self.vision_mode_selection.value, "auto")

        return {
            "source_type": self.source_type_value,
            "folder_path": self.folder_input.value or "",
            "web_urls": web_urls,  # ← FIXED: list, not string
            "do_translation": self.translate_switch.value,  # ← FIXED: "do_" prefix
            "do_tagging": self.tagging_switch.value,  # ← FIXED: "do_" prefix
            "vision_mode": vision_mode,  # ← FIXED: mapped value
            "use_cookies": self.use_cookies_switch.value,  # ← NEW
            "browser_choice": self.browser_selection.value,  # ← NEW
            "save_raw_html": self.save_html_switch.value,  # ← NEW
        }

    def get_chat_input(self) -> str:
        """Get the current chat input text."""
        return self.chat_input.value or ""

    def clear_chat_input(self) -> None:
        """Clear the chat input field."""
        self.chat_input.value = ""

    def get_search_type(self) -> Optional[str]:
        """
        Get the selected search type.

        V2: FIXED - Correct mapping to CustomTkinter values
        - "Всё" → None (means "all")
        - "Документы" → "document"
        - "Заметки" → "note"

        Returns:
            Optional[str]: "document", "note", or None (for "all")
        """
        mapping = {
            "Всё": "all",
            "Документы": "document",
            "Заметки": "note",
        }
        value = mapping.get(self.search_type_selection.value, "all")
        if value == "all":
            return None  # ← IMPORTANT: None means "all"
        return value

    def get_note_text(self) -> str:
        """Get the current note text."""
        return self.note_text.value or ""

    def get_selected_note_template(self) -> Optional[str]:
        """
        Get the content of the selected note template.

        Returns:
            Optional[str]: Template content if selected, None otherwise
        """
        selected = self.note_template_selection.value
        if selected and selected != "None":
            template = next((t for t in self.note_templates if t["name"] == selected), None)
            if template:
                return template["content"]
        return None

    def clear_note_text(self) -> None:
        """Clear the note text area."""
        self.note_text.value = ""

    def show_note_status(self, message: str, is_error: bool = False) -> None:
        """
        Display a status message for note operations.

        Args:
            message: The status message to display
            is_error: Whether this is an error message (red text vs green)
        """
        self.note_status_label.text = message
        # Toga doesn't support text color on labels easily, but message emojis (✓/✗) help

    def get_llm_settings(self) -> dict:
        """
        Get current LLM settings from the UI.

        V2: FIXED API - Added missing fields
        - Added: translation_chunk_size
        - Added: vision_mode (from ingestion tab)
        - Added: vector_db_path_en (English vector database)
        - Added: vector_db_path_ru (Russian vector database)
        - Added: markdown_output_path
        - Added: changelog_path
        - Added: notes_path
        - Added: note_templates (list of template dicts)

        V3: Added chat settings
        - Added: chat_context_messages (int)
        - Added: chat_send_key ("enter" or "shift_enter")

        Returns:
            dict: LLM settings with all provider configurations
        """
        # Map UI display text to internal values
        db_lang_map = {
            "English": "en",
            "Russian": "ru"
        }
        db_language = db_lang_map.get(self.db_language_selection.value, "en")

        # Get vision_mode from ingestion settings (for compatibility)
        vision_mode_map = {
            "Disabled": "disabled",
            "Auto (Smart Fallback)": "auto",
            "Local Vision Model": "local",
        }
        vision_mode = vision_mode_map.get(self.vision_mode_selection.value, "auto")

        return {
            "llm_provider": self.llm_provider_selection.value,
            # Ollama
            "ollama_base_url": self.ollama_url_input.value or "http://localhost:11434",
            "ollama_model": self.ollama_model_input.value or "qwen2.5:7b-instruct",
            # LM Studio
            "lmstudio_base_url": self.lmstudio_url_input.value or "http://localhost:1234/v1",
            "lmstudio_model": self.lmstudio_model_input.value or "meta-llama-3.1-8b-instruct",
            # Claude
            "claude_api_key": self.claude_api_key_input.value or "",
            "claude_model": self.claude_model_input.value or "claude-3-5-sonnet-20241022",
            # Gemini
            "gemini_api_key": self.gemini_api_key_input.value or "",
            "gemini_model": self.gemini_model_input.value or "gemini-2.5-pro-preview-03-25",
            # Mistral
            "mistral_api_key": self.mistral_api_key_input.value or "",
            "mistral_model": self.mistral_model_input.value or "mistral-small-latest",
            # Vision
            "vision_mode": vision_mode,  # ← NEW (from ingestion)
            "vision_provider": self.vision_provider_input.value or "ollama",
            "vision_base_url": self.vision_base_url_input.value or "http://localhost:11434",
            "vision_model": self.vision_model_input.value or "granite-docling:258m",
            # PDF Conversion
            "pdf_conversion_method": self.pdf_conversion_method.value or "marker-pdf",  # ← NEW: marker-pdf or llm-studio-ocr
            "llm_ocr_url": self.llm_ocr_url_input.value or "http://localhost:1234/v1",  # ← NEW: LLM Studio OCR URL
            "llm_ocr_model": self.llm_ocr_model_input.value or "ocrflux-3b",  # ← NEW: OCR model name
            "llm_ocr_api_key": self.llm_ocr_api_key_input.value or "",  # ← NEW: Optional API key
            # General
            "timeout": int(self.timeout_input.value or "300"),
            "translation_chunk_size": int(self.translation_chunk_input.value or "2000"),  # ← NEW
            # Storage Paths (NEW)
            "vector_db_path_en": self.vector_db_path_en_input.value or "./chroma_db_en",  # ← NEW (English DB)
            "vector_db_path_ru": self.vector_db_path_ru_input.value or "./chroma_db_ru",  # ← NEW (Russian DB)
            "markdown_output_path": self.markdown_output_path_input.value or "./output_markdown",  # ← NEW
            "changelog_path": self.changelog_path_input.value or "./changelog",  # ← NEW
            "notes_path": self.notes_path_input.value or "./notes",  # ← NEW (notes directory)
            # Note Templates (NEW)
            "note_templates": self.note_templates,  # ← NEW: list of template dicts
            # Chat Settings (NEW)
            "chat_context_messages": int(self.chat_context_input.value or "10"),  # ← NEW: chat context limit
            "rag_top_k": int(self.rag_topk_input.value or "20"),  # ← NEW: RAG retrieval count
            "chat_send_key": "shift_enter" if self.chat_send_key_selection.value == "Shift+Enter" else "enter",  # ← NEW: send key preference
            # Database
            "database_language": db_language,
            # Appearance
            "theme": self.theme_selection.value.lower(),  # ← NEW: "light" or "dark"
            "window_size": self.window_size_selection.value,  # ← NEW: window size
        }

    def get_config_location(self) -> str:
        """
        Get the selected config file location.

        Returns:
            str: Either "home" or "project"
        """
        if "Project" in self.config_location_selection.value:
            return "project"
        return "home"

    def set_llm_settings(self, settings: dict) -> None:
        """
        Set LLM settings in the UI.

        V2: Updated to handle new fields (translation_chunk_size, storage paths including notes_path, vision_mode)
        V3: Added chat settings (chat_context_messages, chat_send_key)

        Args:
            settings: Dictionary of settings to populate
        """
        logger.info(f"Loading settings into UI V2: {list(settings.keys())}")

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

        # Vision (V2: Added vision_mode mapping)
        if "vision_mode" in settings:
            vision_mode_reverse_map = {
                "disabled": "Disabled",
                "auto": "Auto (Smart Fallback)",
                "local": "Local Vision Model",
            }
            display_value = vision_mode_reverse_map.get(settings["vision_mode"], "Auto (Smart Fallback)")
            self.vision_mode_selection.value = display_value
            logger.info(f"Setting vision mode to: {display_value}")

        if "vision_provider" in settings:
            self.vision_provider_input.value = settings["vision_provider"]
        if "vision_base_url" in settings:
            self.vision_base_url_input.value = settings["vision_base_url"]
        if "vision_model" in settings:
            self.vision_model_input.value = settings["vision_model"]

        # PDF Conversion (NEW)
        if "pdf_conversion_method" in settings:
            self.pdf_conversion_method.value = settings["pdf_conversion_method"]
            logger.info(f"Setting PDF conversion method to: {settings['pdf_conversion_method']}")
            # Trigger UI update to show/hide LLM OCR settings
            # NOTE: Toga display property only accepts "pack" or "none" (not "flex")
            if settings["pdf_conversion_method"] == "llm-studio-ocr":
                self.llm_ocr_settings_box.style.display = "pack"
            else:
                self.llm_ocr_settings_box.style.display = "none"

        if "llm_ocr_url" in settings:
            self.llm_ocr_url_input.value = settings["llm_ocr_url"]
        if "llm_ocr_model" in settings:
            self.llm_ocr_model_input.value = settings["llm_ocr_model"]
        if "llm_ocr_api_key" in settings:
            self.llm_ocr_api_key_input.value = settings["llm_ocr_api_key"]

        # General
        if "timeout" in settings:
            timeout_val = str(settings["timeout"])
            logger.info(f"Setting timeout to: {timeout_val}")
            self.timeout_input.value = timeout_val

        # V2: Translation chunk size (NEW)
        if "translation_chunk_size" in settings:
            chunk_val = str(settings["translation_chunk_size"])
            logger.info(f"Setting translation chunk size to: {chunk_val}")
            self.translation_chunk_input.value = chunk_val

        # V2: Storage paths (NEW)
        if "vector_db_path_en" in settings:
            self.vector_db_path_en_input.value = settings["vector_db_path_en"]
            logger.info(f"Setting English vector DB path to: {settings['vector_db_path_en']}")

        if "vector_db_path_ru" in settings:
            self.vector_db_path_ru_input.value = settings["vector_db_path_ru"]
            logger.info(f"Setting Russian vector DB path to: {settings['vector_db_path_ru']}")

        if "markdown_output_path" in settings:
            self.markdown_output_path_input.value = settings["markdown_output_path"]
            logger.info(f"Setting markdown output path to: {settings['markdown_output_path']}")

        if "changelog_path" in settings:
            self.changelog_path_input.value = settings["changelog_path"]
            logger.info(f"Setting changelog path to: {settings['changelog_path']}")

        if "notes_path" in settings:
            self.notes_path_input.value = settings["notes_path"]
            logger.info(f"Setting notes path to: {settings['notes_path']}")

        # Note templates (NEW)
        if "note_templates" in settings:
            self.note_templates = settings["note_templates"]
            self._update_template_selection()  # Update both dropdowns
            logger.info(f"Loaded {len(self.note_templates)} note templates")

        # Chat settings (NEW)
        if "chat_context_messages" in settings:
            context_val = str(settings["chat_context_messages"])
            self.chat_context_input.value = context_val
            logger.info(f"Setting chat context messages to: {context_val}")

        if "rag_top_k" in settings:
            rag_top_k_val = str(settings["rag_top_k"])
            self.rag_topk_input.value = rag_top_k_val
            logger.info(f"Setting RAG top K to: {rag_top_k_val}")

        if "chat_send_key" in settings:
            send_key = settings["chat_send_key"]
            display_value = "Shift+Enter" if send_key == "shift_enter" else "Enter"
            self.chat_send_key_selection.value = display_value
            logger.info(f"Setting chat send key to: {display_value}")
            # Update macOS keyboard handler with new setting
            self._setup_chat_keyboard_handler(send_key)

        # Database language
        if "database_language" in settings:
            db_lang = settings["database_language"]
            # Map internal values to UI display text
            db_lang_reverse_map = {
                "en": "English",
                "ru": "Russian"
            }
            display_value = db_lang_reverse_map.get(db_lang, "English")
            self.db_language_selection.value = display_value
            logger.info(f"Setting database language to: {display_value}")

        # Appearance (V2: Theme)
        if "theme" in settings:
            theme = settings["theme"]
            # Map internal values to UI display text
            theme_reverse_map = {
                "light": "Light",
                "dark": "Dark"
            }
            display_value = theme_reverse_map.get(theme, "Light")
            self.theme_selection.value = display_value
            logger.info(f"Setting theme to: {display_value}")

            # Note: Theme is already applied in startup() before UI creation
            # We just update the selection to reflect the current theme
            if theme == "dark":
                self.current_theme = DarkTheme
            else:
                self.current_theme = LightTheme

        # Window size
        if "window_size" in settings:
            window_size = settings["window_size"]
            self.window_size_selection.value = window_size
            logger.info(f"Setting window size to: {window_size}")

            # Apply window size immediately
            try:
                # Parse: "1440x900 (16:10 Wide)" -> width=1440, height=900
                dimensions = window_size.split(" ")[0]  # Get "1440x900"
                width, height = dimensions.split("x")
                width, height = int(width), int(height)

                if hasattr(self, 'main_window'):
                    # Note: In Toga, window size is set as a tuple (width, height)
                    self.main_window.size = (width, height)
                    logger.info(f"✓ Window resized to: {width}x{height}")
            except Exception as e:
                logger.warning(f"Failed to apply window size: {e}", exc_info=True)

        logger.info("✓ Settings loaded into UI V2 successfully")

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
            message: The message to append (can contain newlines for batch updates)

        OPTIMIZATION: For large logs, we limit the buffer size to prevent slowdowns
        """
        current = self.log_output.value or ""

        # Add message (may already contain newlines from batching)
        new_text = current + message + "\n"

        # Limit log buffer to last 10,000 lines to prevent UI slowdown
        lines = new_text.split("\n")
        if len(lines) > 10000:
            # Keep only the last 10,000 lines
            new_text = "\n".join(lines[-10000:])

        self.log_output.value = new_text
        # Auto-scroll to bottom by setting cursor to end
        # NOTE: Toga may handle this automatically

    def _render_chat_html(self) -> None:
        """
        Render chat messages as HTML with markdown formatting.

        This method converts the stored chat messages into beautifully
        formatted HTML with proper markdown rendering, syntax highlighting,
        and theme-aware styling.
        """
        # Helper function to convert Toga color to hex string
        def color_to_hex(color):
            """Convert Toga color object to hex string."""
            # Try the most common methods first
            if hasattr(color, 'hex'):
                return color.hex
            # Toga's rgb() returns an object with rgba property that has r, g, b, a attributes
            elif hasattr(color, 'rgba'):
                rgba = color.rgba
                # rgba is an object with r, g, b, a attributes (not a tuple)
                if hasattr(rgba, 'r'):
                    r = int(rgba.r * 255) if rgba.r <= 1 else int(rgba.r)
                    g = int(rgba.g * 255) if rgba.g <= 1 else int(rgba.g)
                    b = int(rgba.b * 255) if rgba.b <= 1 else int(rgba.b)
                    return f"#{r:02x}{g:02x}{b:02x}"
            # Last resort: convert to string and try to parse
            color_str = str(color)
            if color_str.startswith('rgb('):
                # Parse "rgb(255, 255, 255)"
                values = color_str.replace('rgb(', '').replace(')', '').split(',')
                if len(values) >= 3:
                    r, g, b = [int(v.strip()) for v in values[:3]]
                    return f"#{r:02x}{g:02x}{b:02x}"
            # Default fallback
            return "#000000"

        # Get current theme colors
        theme = self.current_theme

        # Base HTML structure with embedded CSS
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: {color_to_hex(theme.TEXT_PRIMARY)};
            background-color: {color_to_hex(theme.BG_PRIMARY)};
            margin: 0;
            padding: 16px;
        }}

        .message {{
            margin-bottom: 20px;
            padding: 12px 16px;
            border-radius: 8px;
            background-color: {color_to_hex(theme.BG_SECONDARY)};
        }}

        .message-header {{
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
        }}

        .user-message .message-header {{
            color: {color_to_hex(theme.ACCENT_BLUE)};
        }}

        .assistant-message .message-header {{
            color: {color_to_hex(theme.ACCENT_GREEN)};
        }}

        .system-message .message-header {{
            color: {color_to_hex(theme.TEXT_SECONDARY)};
            font-style: italic;
        }}

        .message-content {{
            color: {color_to_hex(theme.TEXT_PRIMARY)};
        }}

        .message-content p {{
            margin: 0 0 8px 0;
        }}

        .message-content p:last-child {{
            margin-bottom: 0;
        }}

        .message-content ul, .message-content ol {{
            margin: 8px 0;
            padding-left: 24px;
        }}

        .message-content li {{
            margin: 4px 0;
        }}

        .message-content code {{
            background-color: rgba(0, 0, 0, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
            font-size: 13px;
        }}

        .message-content pre {{
            background-color: rgba(0, 0, 0, 0.1);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 8px 0;
        }}

        .message-content pre code {{
            background-color: transparent;
            padding: 0;
        }}

        .message-content blockquote {{
            border-left: 4px solid {color_to_hex(theme.ACCENT_BLUE)};
            margin: 8px 0;
            padding-left: 16px;
            color: {color_to_hex(theme.TEXT_SECONDARY)};
        }}

        .message-content strong {{
            font-weight: 600;
        }}

        .message-content em {{
            font-style: italic;
        }}

        .message-content a {{
            color: {color_to_hex(theme.ACCENT_BLUE)};
            text-decoration: none;
        }}

        .message-content a:hover {{
            text-decoration: underline;
        }}

        .placeholder {{
            text-align: center;
            color: {color_to_hex(theme.TEXT_SECONDARY)};
            padding: 40px 20px;
            font-style: italic;
        }}
    </style>
</head>
<body>
"""

        # If no messages, show placeholder
        if not self._chat_messages:
            html += """
    <div class="placeholder">
        Chat history will appear here...<br><br>
        Ask questions about your documents!
    </div>
"""
        else:
            # Render each message
            for role, message in self._chat_messages:
                # Convert markdown to HTML
                message_html = markdown.markdown(
                    message,
                    extensions=['fenced_code', 'codehilite', 'tables', 'nl2br']
                )

                # Determine message class and header
                if role == "user":
                    message_class = "user-message"
                    header = "👤 You"
                elif role == "assistant":
                    message_class = "assistant-message"
                    header = "🤖 Assistant"
                else:
                    message_class = "system-message"
                    header = role

                # Add message div
                html += f"""
    <div class="message {message_class}">
        <div class="message-header">{header}</div>
        <div class="message-content">
            {message_html}
        </div>
    </div>
"""

        # Close HTML with auto-scroll JavaScript
        html += """
    <script>
        // Automatically scroll to bottom when page loads
        window.onload = function() {
            window.scrollTo(0, document.body.scrollHeight);
        };
    </script>
</body>
</html>
"""

        # Set WebView content
        self.chat_history.set_content("", html)

    def append_chat_message(self, role: str, message: str) -> None:
        """
        Append a message to the chat history with markdown rendering.

        Args:
            role: The role (user/assistant/system)
            message: The message content (supports markdown formatting)
        """
        # Add message to internal storage
        self._chat_messages.append((role, message))

        # Re-render the chat HTML
        self._render_chat_html()

    def clear_chat_history(self) -> None:
        """
        Clear the chat history display.

        This method clears all messages from the chat display.
        """
        self._chat_messages.clear()
        self._render_chat_html()

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
        # V2: Use new dialog API (Toga 0.4+)
        try:
            import asyncio
            asyncio.create_task(
                self.main_window.dialog(toga.InfoDialog(title, message))
            )
        except Exception:
            # Fallback to deprecated API if async fails
            self.main_window.info_dialog(title, message)

    # V2: Compatibility aliases for CustomTkinter API
    def show_warning(self, title: str, message: str) -> None:
        """Alias for show_error_dialog (for CustomTkinter compatibility)."""
        self.show_error_dialog(title, message)

    def show_info(self, title: str, message: str) -> None:
        """Alias for show_info_dialog (for CustomTkinter compatibility)."""
        self.show_info_dialog(title, message)


def main():
    """Entry point for running the Toga app standalone."""
    return LokalRAGApp()


if __name__ == "__main__":
    main().main_loop()
