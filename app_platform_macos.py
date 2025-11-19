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
_swizzled_classes = set()


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
        from rubicon.objc import ObjCClass, objc_method, ObjCInstance
        from rubicon.objc.runtime import objc_id, SEL, libobjc, send_super, send_message

        global _keyboard_handler_callback, _keyboard_handler_mode, _swizzled_classes

        # Store callback globally
        _keyboard_handler_callback = send_callback
        _keyboard_handler_mode = send_key

        NSEvent = ObjCClass("NSEvent")
        NSObject = ObjCClass("NSObject")

        # Get the native widget
        native_widget = chat_input._impl.native
        logger.info(f"Native widget: {native_widget.className if hasattr(native_widget, 'className') else type(native_widget)}")

        # Get TogaTextView
        native_text_view = None
        if hasattr(native_widget, 'documentView'):
            native_text_view = native_widget.documentView
            class_name = native_text_view.className if hasattr(native_text_view, 'className') else 'unknown'
            logger.info(f"DocumentView: {class_name}")
        else:
            logger.warning("Could not find documentView")
            return

        # Get the class name for swizzle check
        toga_class_name = str(native_text_view.className)

        # Check if already swizzled
        if toga_class_name in _swizzled_classes:
            logger.info(f"{toga_class_name} already swizzled, updating callback only")
            return

        # Create helper class with our keyDown implementation
        class KeyDownHelper(NSObject):
            """Helper class to get IMP for our keyDown method."""

            @objc_method
            def lokal_rag_keyDown_(self, event):
                """Our custom keyDown implementation."""
                try:
                    global _keyboard_handler_callback, _keyboard_handler_mode

                    # Get key code
                    key_code = event.keyCode
                    # Enter key = 36, Return key = 76
                    if key_code in (36, 76):
                        # Check modifier flags
                        modifier_flags = int(event.modifierFlags)
                        shift_pressed = (modifier_flags & (1 << 17)) != 0

                        logger.info(f"🔑 Enter key! keyCode={key_code}, shift={shift_pressed}, mode={_keyboard_handler_mode}")

                        # Determine if we should send
                        should_send = False
                        if _keyboard_handler_mode == "shift_enter":
                            should_send = shift_pressed
                        else:  # "enter"
                            should_send = not shift_pressed

                        if should_send and _keyboard_handler_callback:
                            logger.info(f"🚀 Sending message via keyboard shortcut")
                            _keyboard_handler_callback()
                            return  # Don't call super (consume event)

                    # Not our event - call original implementation via super
                    send_super(__class__, self, 'lokal_rag_keyDown:', event, restype=None, argtypes=[objc_id])

                except Exception as e:
                    logger.error(f"Error in keyDown handler: {e}", exc_info=True)
                    # Fall back to super
                    send_super(__class__, self, 'lokal_rag_keyDown:', event, restype=None, argtypes=[objc_id])

        # Get class pointers
        helper_class_ptr = libobjc.object_getClass(KeyDownHelper.alloc().ptr)
        target_class_ptr = libobjc.object_getClass(native_text_view.ptr)

        logger.info(f"Helper class: {helper_class_ptr}, Target class: {target_class_ptr}")

        # Get our method from helper class
        our_method = libobjc.class_getInstanceMethod(
            helper_class_ptr,
            SEL(b'lokal_rag_keyDown:')
        )

        # Get original keyDown from target class
        original_method = libobjc.class_getInstanceMethod(
            target_class_ptr,
            SEL(b'keyDown:')
        )

        if not our_method:
            logger.warning("Could not find lokal_rag_keyDown: in helper class")
            return

        if not original_method:
            logger.warning("Could not find keyDown: in TogaTextView")
            return

        # Get IMP from our method
        our_imp = libobjc.method_getImplementation(our_method)

        # Try to add our method to target class with original name
        # This won't work if method exists, but we need to try
        added = libobjc.class_addMethod(
            target_class_ptr,
            SEL(b'lokal_rag_keyDown:'),
            our_imp,
            b'v@:@'  # void return, id self, SEL cmd, id event
        )

        if added:
            logger.info("Added lokal_rag_keyDown: to class")

            # Now swap implementations
            swizzled_method = libobjc.class_getInstanceMethod(
                target_class_ptr,
                SEL(b'lokal_rag_keyDown:')
            )

            if swizzled_method:
                libobjc.method_exchangeImplementations(original_method, swizzled_method)
                _swizzled_classes.add(toga_class_name)
                logger.info(f"✓ Successfully swizzled {toga_class_name}.keyDown: (mode: {send_key})")
            else:
                logger.warning("Could not get swizzled method back")
        else:
            logger.warning("Could not add method to class (may already exist)")

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
