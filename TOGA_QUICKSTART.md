# Toga Version - Quick Start Guide

This guide helps you test the new Toga-based UI on macOS.

## Why Toga?

CustomTkinter has unfixable trackpad scrolling issues on macOS. After multiple failed attempts to fix it, we're migrating to **Toga** - a native UI framework that uses macOS Cocoa widgets under the hood.

**Key benefit:** Native scrolling that works perfectly with macOS trackpad gestures! ✨

---

## Installation

```bash
# Install Toga 0.5.2 (uses native macOS Cocoa backend)
pip install toga==0.5.2
```

On macOS, this will automatically use the Cocoa backend - no additional system dependencies needed!

---

## Running the Test Version

```bash
# Basic run
python main_toga.py

# With debug logging (useful for troubleshooting)
python main_toga.py --debug
```

This starts the Toga version of Lokal-RAG with the same functionality as the CustomTkinter version.

---

## What to Test

### 1️⃣ **Critical Test: Trackpad Scrolling**

This is THE primary reason for the migration!

1. Launch the app: `python main_toga.py`
2. Go to the **Settings** tab
3. Try scrolling with **two-finger swipe** on trackpad
4. Does it scroll smoothly? ✅

**Expected:** Scrolling should work perfectly on ALL tabs (Settings, Ingestion, Chat, Notes, Changelog)

### 2️⃣ **UI Rendering**

- Do all 5 tabs appear?
- Does the UI look native to macOS?
- Are all widgets visible and properly laid out?

### 3️⃣ **Basic Interactions**

- Click the **Browse...** button in Ingestion tab (native macOS file dialog should appear)
- Type in text fields
- Switch between tabs
- Click buttons (they won't do much yet - see Known Limitations)

---

## Known Limitations (Current Phase)

This is a **UI structure test** - the controller integration is not yet complete.

**What DOESN'T work yet:**

- ❌ Processing/Ingestion buttons (controller not integrated)
- ❌ Sending chat messages (controller not integrated)
- ❌ Saving settings (controller not integrated)
- ❌ Notes management (controller not integrated)

**What DOES work:**

- ✅ UI rendering
- ✅ Tab navigation
- ✅ Text input
- ✅ **Scrolling (CRITICAL TEST!)**
- ✅ File dialogs

---

## Reporting Results

After testing, please report:

1. **Does trackpad scrolling work?** (Most important!)
   - Which tabs did you test?
   - Any issues or glitches?

2. **UI Rendering:**
   - Does it look good?
   - Any visual bugs or layout issues?
   - How does it compare to the CustomTkinter version?

3. **Performance:**
   - Does it feel responsive?
   - Any lag or delays?

4. **Crashes or Errors:**
   - Did the app crash?
   - Any error messages in the console?

---

## File Structure

```
app_view_toga.py    # NEW: Toga UI implementation (~680 lines)
main_toga.py        # NEW: Test entry point for Toga version
app_view.py         # OLD: CustomTkinter UI (still exists for reference)
main.py             # OLD: Original entry point (still works)

# Unchanged (business logic - no UI dependencies)
app_services.py     # LLM operations, translation, tagging
app_storage.py      # ChromaDB, vector search
app_config.py       # Configuration
app_controller.py   # Orchestration (needs update for Toga)
```

---

## Next Steps (After Testing)

If scrolling works (which it should!), the next phase is:

1. **Controller Integration:** Adapt `app_controller.py` to work with Toga's event model
2. **Async Handling:** Toga uses native async patterns instead of threading
3. **Full Workflow Testing:** Test ingestion, chat, settings, etc.
4. **Polish:** Styling, error handling, loading indicators
5. **Replace CustomTkinter:** Remove old UI code once everything works

---

## Troubleshooting

### App won't start

```bash
# Make sure Toga is installed
pip install toga==0.5.2

# Try with debug logging
python main_toga.py --debug

# Check logs
cat logs/lokal_rag_toga.log
```

### Import errors

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### macOS Permission Dialogs

On first run, macOS might ask for permissions:
- **File Access:** Click "Allow" to let the app browse folders
- **Network:** Click "Allow" if you're using LLM APIs

---

## Questions?

See the full migration plan: `TOGA_MIGRATION_PLAN.md`

---

**Happy Testing! 🎉**

The most important thing to test is whether **trackpad scrolling works on macOS**. Everything else is secondary!
