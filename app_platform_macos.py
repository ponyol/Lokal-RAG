"""
macOS-specific platform code for Lokal-RAG.

This module provides macOS-specific functionality using native APIs
through Toga's platform interface.
"""

import sys
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

# Global storage for keyboard handler callback
_keyboard_handler_callback = None
_keyboard_handler_mode = None


def setup_chat_input_keyboard_handler(
    chat_input,
    send_callback: Callable[[], None],
    send_key: str = "shift_enter"
) -> None:
    """
    Set up keyboard handler for chat input on macOS.

    This function intercepts keyDown events in TogaTextView to handle
    Enter/Shift+Enter for sending messages.

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
        from rubicon.objc import ObjCClass, objc_method, ObjCInstance, Block
        from rubicon.objc.runtime import objc_id, SEL, libobjc
        from ctypes import c_void_p, c_bool

        global _keyboard_handler_callback, _keyboard_handler_mode

        # Store callback globally
        _keyboard_handler_callback = send_callback
        _keyboard_handler_mode = send_key

        NSEvent = ObjCClass("NSEvent")

        # Get the native widget
        native_widget = chat_input._impl.native
        logger.info(f"Native widget: {native_widget.className if hasattr(native_widget, 'className') else type(native_widget)}")

        # Get TogaTextView
        native_text_view = None
        if hasattr(native_widget, 'documentView'):
            native_text_view = native_widget.documentView
            logger.info(f"DocumentView: {native_text_view.className if hasattr(native_text_view, 'className') else type(native_text_view)}")
        else:
            logger.warning("Could not find documentView")
            return

        # Get TogaTextView class
        TogaTextView = ObjCClass(native_text_view.className)

        # Check if we already swizzled
        if hasattr(TogaTextView, '_lokal_rag_keydown_swizzled'):
            logger.info("TogaTextView already swizzled, updating callback")
            return

        # Store original keyDown implementation
        original_keydown = TogaTextView.instancemethod('keyDown:')

        @objc_method
        def lokal_rag_keyDown_(self, event):
            """
            Replacement keyDown: method that intercepts Enter key.
            """
            try:
                global _keyboard_handler_callback, _keyboard_handler_mode

                # Get key code
                key_code = event.keyCode
                # Enter key = 36, Return key = 76
                if key_code in (36, 76):
                    # Check modifier flags
                    modifier_flags = int(event.modifierFlags)
                    shift_pressed = (modifier_flags & (1 << 17)) != 0

                    logger.info(f"🔑 Enter key pressed! keyCode={key_code}, shift={shift_pressed}, mode={_keyboard_handler_mode}")

                    # Determine if we should send
                    should_send = False
                    if _keyboard_handler_mode == "shift_enter":
                        should_send = shift_pressed
                    else:  # "enter"
                        should_send = not shift_pressed

                    if should_send and _keyboard_handler_callback:
                        logger.info(f"🚀 Sending message via keyboard shortcut")
                        _keyboard_handler_callback()
                        return  # Don't call original (consume event)

                # Not our event or not sending - call original implementation
                original_keydown(self, event)

            except Exception as e:
                logger.error(f"Error in keyDown handler: {e}", exc_info=True)
                # Fall back to original
                original_keydown(self, event)

        # Swizzle the method
        try:
            # Add our method to the class
            TogaTextView.lokal_rag_keyDown_ = lokal_rag_keyDown_

            # Get method implementation pointers
            original_method = libobjc.class_getInstanceMethod(
                TogaTextView.ptr,
                SEL(b'keyDown:')
            )
            swizzled_method = libobjc.class_getInstanceMethod(
                TogaTextView.ptr,
                SEL(b'lokal_rag_keyDown:')
            )

            if original_method and swizzled_method:
                # Swap implementations
                libobjc.method_exchangeImplementations(original_method, swizzled_method)
                TogaTextView._lokal_rag_keydown_swizzled = True
                logger.info(f"✓ Successfully swizzled TogaTextView.keyDown: (mode: {send_key})")
            else:
                logger.warning(f"Could not get method pointers for swizzling")

        except Exception as e:
            logger.error(f"Failed to swizzle keyDown: {e}", exc_info=True)

    except ImportError as e:
        logger.warning(f"Could not import rubicon.objc: {e}")
    except Exception as e:
        logger.error(f"Failed to setup macOS keyboard handler: {e}", exc_info=True)


def update_chat_input_send_mode(
    chat_input,
    send_callback: Callable[[], None],
    send_key: str = "shift_enter"
) -> None:
    """
    Update the send mode for an already configured chat input.

    Args:
        chat_input: Toga MultilineTextInput widget
        send_callback: Function to call when send key is pressed
        send_key: "shift_enter" or "enter" - determines send behavior
    """
    global _keyboard_handler_callback, _keyboard_handler_mode

    _keyboard_handler_callback = send_callback
    _keyboard_handler_mode = send_key

    logger.info(f"Updated keyboard handler (mode: {send_key})")
