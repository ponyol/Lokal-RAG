# Toga UI Migration Plan

**Branch:** `feature/toga-ui`
**Goal:** Replace CustomTkinter with Toga (BeeWare) for native macOS trackpad support

---

## Why Toga?

### Problems with CustomTkinter
- ❌ Trackpad scrolling doesn't work on macOS
- ❌ MouseWheel events not received by widgets
- ❌ Multiple workarounds failed (bind_all, direct bind, recursive binding)
- ❌ Time wasted trying to fix fundamental platform issues

### Benefits of Toga
- ✅ **Native UI** on each platform (macOS Cocoa, Windows WinForms, Linux GTK)
- ✅ **Trackpad works out of the box** (native OS events)
- ✅ **Python-first** framework (BeeWare project philosophy)
- ✅ **Cross-platform** with native look & feel
- ✅ **Active development** (BeeWare team maintains it)

---

## 🚀 Testing the Toga Version (macOS)

**IMPORTANT:** The Toga UI is now ready for initial testing on macOS!

### Quick Start

```bash
# Install Toga 0.5.2 (will use native macOS Cocoa backend)
pip install toga==0.5.2

# Run the test version
python main_toga.py

# Or with debug logging
python main_toga.py --debug
```

### What to Test

1. **UI Rendering:** Does the app start? Do all 5 tabs appear?
2. **Trackpad Scrolling:** This is the CRITICAL test!
   - Go to Settings tab
   - Try scrolling with trackpad (two-finger swipe)
   - Does it work smoothly?
   - Try all tabs
3. **Basic Interactions:**
   - Click "Browse..." button (folder dialog should open)
   - Type in text fields
   - Switch between tabs
   - Click buttons

### Expected Behavior

- ✅ App starts with native macOS look & feel
- ✅ Trackpad scrolling works in ALL tabs (Settings, Ingestion, etc.)
- ✅ Native file dialogs (macOS style)
- ⚠️  Processing functionality NOT YET WORKING (controller integration pending)

### Known Limitations (Current Phase)

- Processing/Ingestion buttons do nothing (controller not integrated yet)
- Chat messages won't send (controller not integrated yet)
- Settings won't save (controller not integrated yet)
- This is a **UI structure test** to verify scrolling works!

### Report Back

Please test and report:
1. Does trackpad scrolling work? (Most important!)
2. Any UI rendering issues?
3. Any crashes or errors?
4. General look & feel feedback

---

## Architecture: What Changes?

### ✅ Unchanged (Business Logic Layer)
- `app_services.py` - All LLM operations, translation, tagging
- `app_storage.py` - ChromaDB, vector search, file operations
- `app_config.py` - Configuration dataclass

**These modules have ZERO UI dependencies!**

### 🔄 Minimal Changes (Orchestration Layer)
- `app_controller.py` - Update to work with Toga events instead of CustomTkinter
  - Change: Event binding syntax
  - Change: Threading model (Toga uses asyncio)
  - Keep: All business logic orchestration

### 🆕 Complete Rewrite (UI Layer)
- `app_view.py` → **NEW: app_view_toga.py**
  - Rewrite UI using Toga widgets
  - Keep same public API (getters/setters)
  - Same tab structure (Ingestion, Chat, Notes, Changelog, Settings)

- `main.py` → Update imports and initialization

---

## Toga Installation

```bash
pip install toga
```

Or add to requirements.txt:
```
# GUI
toga==0.5.2  # Native UI framework (replaces customtkinter)
```

---

## UI Components Mapping

### CustomTkinter → Toga Equivalents

| CustomTkinter | Toga | Notes |
|--------------|------|-------|
| `CTk()` | `toga.App` | Main application |
| `CTkTabview` | `toga.OptionContainer` | Tabs |
| `CTkFrame` | `toga.Box` | Container |
| `CTkLabel` | `toga.Label` | Text display |
| `CTkButton` | `toga.Button` | Clickable button |
| `CTkEntry` | `toga.TextInput` | Single-line text |
| `CTkTextbox` | `toga.MultilineTextInput` | Multi-line text |
| `CTkCheckBox` | `toga.Switch` | Toggle |
| `CTkOptionMenu` | `toga.Selection` | Dropdown |
| `CTkScrollableFrame` | `toga.ScrollContainer` | **WORKS ON macOS!** |

---

## Implementation Plan

### Phase 1: Basic Structure ✅ COMPLETED
- [x] Create branch `feature/toga-ui`
- [x] Add Toga 0.5.2 to dependencies
- [x] Create `app_view_toga.py` with basic skeleton
- [x] Implement main window with tabs
- [x] Create test entry point (`main_toga.py`)
- [ ] Test basic UI rendering on macOS (READY FOR TESTING)

### Phase 2: Core Tabs ✅ BASIC STRUCTURE COMPLETED
- [x] **Ingestion Tab** (UI complete, needs controller integration)
  - Folder selection (PDF/Markdown)
  - Web URL input
  - Processing options (translation, tagging, vision)
  - Start button
  - Log output

- [x] **Chat Tab** (UI complete, needs controller integration)
  - Chat history display
  - Message input
  - Send button
  - Search type selector

- [x] **Settings Tab** (UI complete, needs controller integration)
  - LLM provider selection
  - API keys input
  - Model selection
  - Paths configuration
  - Test/Save buttons

### Phase 3: Additional Features ✅ BASIC STRUCTURE COMPLETED
- [x] **Notes Tab** (UI complete, needs controller integration)
  - Notes list (placeholder)
  - Create/Edit/Delete (basic implementation)
  - Search notes (TODO)

- [x] **Changelog Tab** (UI complete, needs implementation)
  - File list (placeholder)
  - Content viewer (basic implementation)
  - Date display (TODO)

### Phase 4: Controller Integration (IN PROGRESS)
- [ ] Update `app_controller.py` for Toga
- [ ] Handle async event model (Toga uses native event loops)
- [ ] Thread-safe queue for worker → UI communication
- [ ] Test all workflows end-to-end
- [ ] Implement proper async/background task handling

### Phase 5: Polish & Testing
- [ ] Styling (colors, fonts, spacing)
- [ ] Error handling
- [ ] Loading indicators
- [ ] Keyboard shortcuts
- [ ] Cross-platform testing (macOS, Windows, Linux)

---

## Code Structure

```
lokal-rag/
├── app_view_toga.py          # NEW: Toga UI implementation
├── app_view.py               # OLD: Keep for reference, will be deleted later
├── app_controller.py         # UPDATE: Adapt for Toga events
├── main.py                   # UPDATE: Import Toga app
├── app_services.py           # UNCHANGED
├── app_storage.py            # UNCHANGED
├── app_config.py             # UNCHANGED
└── requirements.txt          # UPDATE: Add Toga
```

---

## Example: Basic Toga App Skeleton

```python
# app_view_toga.py
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

class LokalRAGApp(toga.App):
    def startup(self):
        """Build the UI when app starts."""
        # Main window
        self.main_window = toga.MainWindow(title=self.formal_name)

        # Create tabs
        self.tabs = toga.OptionContainer(
            content=[
                ("Ingestion", self._create_ingestion_tab()),
                ("Chat", self._create_chat_tab()),
                ("Notes", self._create_notes_tab()),
                ("Changelog", self._create_changelog_tab()),
                ("Settings", self._create_settings_tab()),
            ]
        )

        # Set main window content
        self.main_window.content = self.tabs
        self.main_window.show()

    def _create_ingestion_tab(self):
        """Create Ingestion tab UI."""
        container = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Title
        title = toga.Label(
            "📚 Content Ingestion",
            style=Pack(font_size=20, padding_bottom=10)
        )
        container.add(title)

        # Folder selection
        folder_box = toga.Box(style=Pack(direction=ROW, padding=5))
        folder_label = toga.Label("Folder:", style=Pack(width=100))
        self.folder_input = toga.TextInput(
            readonly=True,
            placeholder="No folder selected",
            style=Pack(flex=1)
        )
        folder_button = toga.Button(
            "Browse...",
            on_press=self.on_select_folder,
            style=Pack(width=100)
        )
        folder_box.add(folder_label)
        folder_box.add(self.folder_input)
        folder_box.add(folder_button)
        container.add(folder_box)

        # Scrollable container for logs
        self.log_output = toga.MultilineTextInput(
            readonly=True,
            placeholder="Processing logs will appear here...",
            style=Pack(flex=1)
        )
        container.add(self.log_output)

        return toga.ScrollContainer(content=container)

    def on_select_folder(self, widget):
        """Handle folder selection."""
        try:
            folder = self.main_window.select_folder_dialog("Select PDF Folder")
            if folder:
                self.folder_input.value = str(folder)
        except:
            pass

# main.py
def main():
    return LokalRAGApp(
        "Lokal-RAG",
        "org.example.lokalrag"
    )

if __name__ == '__main__':
    main().main_loop()
```

---

## Threading Model

### CustomTkinter (Current)
```python
# UI thread
worker_thread = threading.Thread(target=processing_pipeline_worker)
worker_thread.start()

# Worker thread updates UI via queue
view_queue.put("LOG: Processing...")
```

### Toga (Async)
```python
# Use Toga's async support
async def process_documents(self):
    await toga.sleep(0.1)  # Yield to UI
    result = await asyncio.to_thread(fn_extract_markdown, pdf_path, config)
    self.log_output.value += f"Processed: {result}\n"

# Or use traditional threading with invoke_on_main_thread
def worker():
    result = fn_extract_markdown(pdf_path, config)
    app.invoke_on_main_thread(lambda: update_ui(result))
```

---

## Testing Strategy

### Unit Tests
- Test Toga widgets creation
- Test event handlers
- Mock `app_controller` calls

### Integration Tests
- Test full workflows (PDF ingestion, chat, notes)
- Verify thread-safe UI updates
- Test on macOS primarily (target platform)

### Manual Testing
- Trackpad scrolling in all tabs
- Keyboard navigation
- Window resize behavior
- Dark/light theme switching

---

## Migration Checklist

### Pre-Migration ✅ COMPLETED
- [x] Create new branch
- [x] Document current CustomTkinter API (public methods identified)
- [x] List all UI components used (widget mapping table created)
- [x] Identify threading patterns (documented in plan)

### During Migration (IN PROGRESS)
- [x] Install Toga (0.5.2 in requirements.txt)
- [x] Create basic app structure (app_view_toga.py)
- [x] Migrate all tabs (UI structure complete)
- [ ] Test each tab on macOS (READY FOR USER TESTING)
- [ ] Update controller incrementally (NEXT STEP)

### Post-Migration
- [ ] Remove CustomTkinter dependency
- [ ] Delete old `app_view.py`
- [ ] Update README with Toga instructions
- [ ] Update screenshots
- [ ] Create release notes

---

## Rollback Plan

If Toga doesn't work out:
1. Keep `feature/toga-ui` branch for future reference
2. Return to main branch with CustomTkinter
3. Consider alternative: **wxPython** or **PyQt6**

---

## Timeline

**Optimistic:** 2-3 weeks
**Realistic:** 3-4 weeks
**Pessimistic:** 5-6 weeks (if major issues found)

---

## Next Steps

1. **Install Toga:** `pip install toga`
2. **Create skeleton:** Basic Toga app with tabs
3. **Test scrolling:** Verify trackpad works on macOS
4. **Migrate Ingestion tab:** Most complex tab, do first
5. **Iterate:** One tab at a time

---

## Questions to Answer

- [ ] Does Toga support custom styling (dark theme)?
- [ ] How does Toga handle file dialogs on macOS?
- [ ] Can we use threading or must use async?
- [ ] What's the memory footprint compared to CustomTkinter?
- [ ] Are there any macOS permissions needed (file access, etc.)?

---

## Resources

- **Toga Docs:** https://toga.readthedocs.io/
- **BeeWare Tutorial:** https://beeware.org/
- **Toga Examples:** https://github.com/beeware/toga/tree/main/examples
- **API Reference:** https://toga.readthedocs.io/en/stable/reference/api/

---

**Status:** ✅ Phase 1-3 Complete | ⏳ Phase 4 (Controller Integration) In Progress | 🧪 READY FOR macOS TESTING
**Last Updated:** 2025-11-13
**Author:** Claude + Ponyol

---

## ✨ Current Status Summary

**What's Done:**
- ✅ Toga 0.5.2 installed in requirements.txt
- ✅ Complete UI skeleton in `app_view_toga.py` (680+ lines)
- ✅ All 5 tabs implemented (Ingestion, Chat, Notes, Changelog, Settings)
- ✅ Same public API as CustomTkinter version (drop-in replacement)
- ✅ Test entry point created (`main_toga.py`)

**What's Next:**
- 🧪 **USER ACTION REQUIRED:** Test on macOS (run `python main_toga.py`)
- ⏳ Controller integration (app_controller.py modifications)
- ⏳ Async/threading model adaptation
- ⏳ Full workflow testing

**Critical Test:**
Does trackpad scrolling work on macOS Settings tab? This is the PRIMARY goal of this migration!
