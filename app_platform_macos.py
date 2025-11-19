"""
macOS-specific platform code for Lokal-RAG.

This module provides macOS-specific functionality using native APIs
through Toga's platform interface.
"""

import sys
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

# Global storage for delegate callbacks
# Using dict to map delegate instance ID to callback data
_delegate_callbacks = {}
_delegate_counter = 0


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
        from rubicon.objc import ObjCClass, objc_method, ObjCInstance
        from rubicon.objc.runtime import objc_id, send_super

        # Get required classes
        NSObject = ObjCClass("NSObject")
        NSEvent = ObjCClass("NSEvent")

        global _delegate_counter, _delegate_callbacks

        # Create custom delegate class as NSObject subclass
        class ChatTextViewDelegate(NSObject):
            """
            Custom NSTextView delegate that intercepts keyboard events.
            """

            @objc_method
            def init(self):
                """Initialize the delegate."""
                self = ObjCInstance(send_super(__class__, self, 'init', restype=objc_id, argtypes=[]))
                return self

            @objc_method
            def textView_doCommandBySelector_(self, text_view, selector) -> bool:
                """
                Handle keyboard commands in NSTextView.

                Returns:
                    True if we handled the command, False to use default behavior
                """
                try:
                    # Get callback data from global storage using self's address
                    delegate_id = id(self)
                    if delegate_id not in _delegate_callbacks:
                        logger.warning(f"Delegate {delegate_id} not found in callbacks")
                        return False

                    callback_data = _delegate_callbacks[delegate_id]
                    send_func = callback_data['send_func']
                    send_mode = callback_data['send_mode']

                    # Get selector name
                    selector_name = str(selector)
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

                    logger.debug(f"Shift pressed: {shift_pressed}, mode: {send_mode}")

                    # Determine if we should send based on mode
                    should_send = False

                    if send_mode == "shift_enter":
                        # Send on Shift+Enter, regular Enter adds newline
                        should_send = shift_pressed
                    else:  # "enter"
                        # Send on Enter, Shift+Enter adds newline
                        should_send = not shift_pressed

                    if should_send:
                        # Trigger send callback
                        logger.info(f"🚀 Sending message via {send_mode} shortcut")
                        send_func()
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

        # Create delegate instance
        delegate = ChatTextViewDelegate.alloc().init()

        # Store callback data in global dict
        delegate_id = id(delegate)
        _delegate_callbacks[delegate_id] = {
            'send_func': send_callback,
            'send_mode': send_key
        }

        # Set the delegate
        native_text_view.delegate = delegate

        logger.info(f"✓ macOS keyboard handler installed (mode: {send_key}, delegate_id: {delegate_id})")

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
