# macOS Trackpad Scrolling - Debug Guide

## Problem

On macOS, scrolling with trackpad works in **Processing Log** (CTkTextbox) but doesn't work in **Settings tab** and other scrollable areas (CTkScrollableFrame).

## Debug Mode

We've added detailed logging to understand what's happening with scroll events.

### How to Run in Debug Mode

```bash
# Normal mode (INFO level logging)
python main.py

# Debug mode (DEBUG level logging - shows scroll events)
python main.py --debug
```

### What Gets Logged in Debug Mode

When you scroll, you'll see messages like:

```
2025-11-12 19:00:00 | DEBUG    | app_view | [SCROLL] Bound <MouseWheel> using _mouse_wheel_all for CTkScrollableFrame
2025-11-12 19:00:01 | DEBUG    | app_view | [SCROLL] Mouse entered CTkScrollableFrame
2025-11-12 19:00:02 | DEBUG    | app_view | [SCROLL] MouseWheel event on CTkScrollableFrame: delta=1, mouse_over=True
2025-11-12 19:00:03 | DEBUG    | app_view | [SCROLL] Bound <MouseWheel> directly to CTkTextbox (textbox)
2025-11-12 19:00:04 | DEBUG    | app_view | [SCROLL] MouseWheel event on CTkTextbox (textbox): delta=1, platform=darwin
```

## Testing Steps

1. **Start the app in debug mode:**
   ```bash
   python main.py --debug
   ```

2. **Test Processing Log (WORKING):**
   - Go to Ingestion tab
   - Scroll on the "Processing Log" textbox with trackpad
   - Watch the terminal/logs for `[SCROLL]` messages

3. **Test Settings tab (BROKEN):**
   - Go to Settings tab
   - Try to scroll with trackpad
   - Watch the terminal/logs for `[SCROLL]` messages

4. **Compare the output:**
   - Does `Mouse entered` trigger for Settings tab?
   - Does `MouseWheel event` trigger for Settings tab?
   - What are the `delta` values?
   - Is `mouse_over=True` when you scroll?

## What We're Looking For

### If Settings tab shows NO events:
- Events aren't reaching the widget at all
- Problem: `bind_all` on `self.master` doesn't work on macOS
- Solution: Use direct `bind` like textbox does

### If Settings tab shows events but mouse_over=False:
- Events arrive but mouse tracking is broken
- Problem: `<Enter>` / `<Leave>` events don't work on scrollable frame
- Solution: Different approach to detect mouse position

### If Settings tab shows events with mouse_over=True but wrong delta:
- Events arrive but delta calculation is wrong
- Problem: macOS delta values need different handling
- Solution: Adjust delta calculation for macOS (similar to textbox)

## Next Steps

After gathering the debug output:

1. Share the logs showing what happens when you scroll on:
   - Processing Log (working)
   - Settings tab (not working)

2. We'll compare and identify the exact difference

3. Fix the `_enable_mousewheel_scrolling` function based on findings

## Logs Location

All logs are saved to:
```
./logs/lokal_rag.log
```

You can also watch them in real-time in the terminal where you ran `python main.py --debug`.

## Example Debug Session

```bash
# Terminal 1: Run app in debug mode
python main.py --debug

# Terminal 2: Watch logs in real-time (optional)
tail -f ./logs/lokal_rag.log | grep "\[SCROLL\]"
```

Then interact with the app and observe the output!
