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
        from rubicon.objc import ObjCClass, objc_method, py_from_ns
        from rubicon.objc.runtime import SEL

        # Get NSTextView class
        NSTextView = ObjCClass("NSTextView")
        NSEvent = ObjCClass("NSEvent")

        # Create custom delegate class
        # Using simple Python class - rubicon will bridge it automatically
        class ChatTextViewDelegate:
            """
            Custom NSTextView delegate that intercepts keyboard events.

            Implements textView:doCommandBySelector: to catch Return key presses
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
                try:
                    # Get selector name
                    # selector is a SEL object, need to check it carefully
                    selector_str = "insertNewline:"

                    # Try to get the selector name
                    try:
                        if hasattr(selector, 'name'):
                            selector_name = selector.name
                        else:
                            # Convert SEL to string using str()
                            selector_name = str(selector)
                    except:
                        selector_name = selector_str

                    logger.debug(f"Selector received: {selector_name}")

                    # We only care about Enter/Return key
                    if "insertNewline" not in selector_name:
                        return False

                    # Get current event to check modifier flags
                    current_event = NSEvent.currentEvent()

                    if current_event is None:
                        logger.debug("No current event")
                        return False

                    # Check modifier flags
                    # NSEventModifierFlagShift = 1 << 17 (131072)
                    modifier_flags = int(current_event.modifierFlags)
                    shift_pressed = (modifier_flags & (1 << 17)) != 0

                    logger.debug(f"Shift pressed: {shift_pressed}, mode: {self.send_mode}")

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
                        logger.info(f"🚀 Sending message via {self.send_mode} shortcut")
                        self.send_func()
                        return True  # Consume the event
                    else:
                        # Let default behavior happen (insert newline)
                        logger.debug("Allowing newline insertion")
                        return False

                except Exception as e:
                    logger.error(f"Error in keyboard handler: {e}", exc_info=True)
                    return False

        # Get the native widget from Toga - might be NSScrollView or NSTextView
        native_widget = chat_input._impl.native

        logger.info(f"Native widget type: {type(native_widget)}, class: {native_widget.__class__.__name__ if hasattr(native_widget, '__class__') else 'unknown'}")

        # MultilineTextInput uses NSScrollView containing NSTextView
        # Try to get the documentView which is the actual NSTextView
        native_text_view = None

        if hasattr(native_widget, 'documentView'):
            # This is an NSScrollView, get the text view inside
            native_text_view = native_widget.documentView
            logger.info(f"Found documentView: {type(native_text_view)}")
        elif hasattr(native_widget, 'delegate'):
            # This is already an NSTextView
            native_text_view = native_widget
            logger.info("Native widget is already NSTextView")
        else:
            logger.warning(f"Could not find NSTextView in widget hierarchy")
            return

        # Verify we have a text view with delegate support
        if not hasattr(native_text_view, 'delegate'):
            logger.warning(f"Text view doesn't have delegate property: {type(native_text_view)}")
            return

        # Create and set delegate
        delegate = ChatTextViewDelegate(send_callback, send_key)
        native_text_view.delegate = delegate

        logger.info(f"✓ macOS keyboard handler installed (mode: {send_key}, text_view: {native_text_view})")

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
