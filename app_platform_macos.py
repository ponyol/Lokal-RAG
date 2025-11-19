"""
macOS-specific platform code for Lokal-RAG.

This module provides macOS-specific functionality using native APIs
through Toga's platform interface.
"""

import sys
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


def setup_chat_input_keyboard_handler(
    chat_input,
    send_callback: Callable[[], None],
    send_key: str = "shift_enter"
) -> None:
    """
    Set up keyboard handler for chat input on macOS.

    This function uses native macOS NSTextView delegate to intercept
    keyboard events and trigger message sending based on user preference.

    Args:
        chat_input: Toga MultilineTextInput widget
        send_callback: Function to call when send key is pressed
        send_key: "shift_enter" or "enter" - determines send behavior
    """
    # Only run on macOS
    if sys.platform != "darwin":
        logger.info("Keyboard handler only available on macOS, skipping")
        return

    try:
        # Import macOS-specific modules
        from rubicon.objc import ObjCClass, objc_method
        from rubicon.objc.runtime import objc_id

        # Get NSTextView class
        NSTextView = ObjCClass("NSTextView")

        # Create custom delegate class
        class ChatTextViewDelegate:
            """
            Custom NSTextView delegate that intercepts keyboard events.

            Implements doCommandBySelector: to catch Return key presses
            and determine if message should be sent based on modifier keys.
            """

            def __init__(self, send_func: Callable[[], None], send_mode: str):
                self.send_func = send_func
                self.send_mode = send_mode  # "shift_enter" or "enter"

            @objc_method
            def textView_doCommandBySelector_(self, text_view, selector) -> bool:
                """
                Handle keyboard commands in NSTextView.

                This method is called for special key combinations.
                We intercept insertNewline: (Enter key) and check modifiers.

                Args:
                    text_view: The NSTextView instance
                    selector: The command selector (e.g., insertNewline:)

                Returns:
                    True if we handled the command, False to use default behavior
                """
                # Convert selector to string
                selector_name = str(selector)

                # We only care about Enter/Return key
                if selector_name != "insertNewline:":
                    return False

                # Get current event to check modifier flags
                NSEvent = ObjCClass("NSEvent")
                current_event = NSEvent.currentEvent()

                if current_event is None:
                    return False

                # Check modifier flags
                # NSEventModifierFlagShift = 1 << 17 (131072)
                modifier_flags = int(current_event.modifierFlags)
                shift_pressed = (modifier_flags & (1 << 17)) != 0

                # Determine if we should send based on mode
                should_send = False

                if self.send_mode == "shift_enter":
                    # Send on Shift+Enter, regular Enter adds newline
                    should_send = shift_pressed
                else:  # "enter"
                    # Send on Enter, Shift+Enter adds newline
                    should_send = not shift_pressed

                if should_send:
                    # Trigger send callback
                    logger.debug(f"Send key pressed (mode: {self.send_mode})")
                    self.send_func()
                    return True  # Consume the event
                else:
                    # Let default behavior happen (insert newline)
                    return False

        # Get the native NSTextView from Toga widget
        native_text_view = chat_input._impl.native

        if not isinstance(native_text_view, NSTextView):
            logger.warning(f"Expected NSTextView, got {type(native_text_view)}")
            return

        # Create and set delegate
        delegate = ChatTextViewDelegate(send_callback, send_key)
        native_text_view.delegate = delegate

        logger.info(f"✓ macOS keyboard handler installed (mode: {send_key})")

    except ImportError as e:
        logger.warning(f"Could not import rubicon.objc: {e}")
    except AttributeError as e:
        logger.warning(f"Could not access native widget: {e}")
    except Exception as e:
        logger.error(f"Failed to setup macOS keyboard handler: {e}", exc_info=True)


def update_chat_input_send_mode(
    chat_input,
    send_callback: Callable[[], None],
    send_key: str = "shift_enter"
) -> None:
    """
    Update the send mode for an already configured chat input.

    This re-applies the keyboard handler with new settings.
    Useful when user changes settings without restarting the app.

    Args:
        chat_input: Toga MultilineTextInput widget
        send_callback: Function to call when send key is pressed
        send_key: "shift_enter" or "enter" - determines send behavior
    """
    # Just re-run the setup (it will replace the delegate)
    setup_chat_input_keyboard_handler(chat_input, send_callback, send_key)
    logger.info(f"Updated chat input send mode to: {send_key}")
