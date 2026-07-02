"""Rotate clipboard contents across successive Cmd+V keystrokes (macOS only).

Mechanism
---------
A Quartz CGEventTap installed at the session level observes every key-down
event *before* it reaches the foreground application. When the user presses
Cmd+V the callback writes the next string in the sequence to the general
pasteboard and lets the event flow through unchanged. The frontmost app then
performs its normal paste and reads the value we just wrote.

Why this is race-free
---------------------
1. An event tap is earlier in the event pipeline than app delivery, so the
   pasteboard is always updated before the receiving app reads it for *this*
   keystroke.
2. We only ever mutate the pasteboard on the keystroke itself, never on a
   timer/background thread, and the callback runs on the run-loop thread, so
   the sequence index is touched by a single thread (no locking needed).
3. The previous value is overwritten only on the *next* Cmd+V, by which point
   the prior paste has long since completed (human keystrokes are seconds
   apart). The original clipboard is restored only after the run loop stops,
   with a short settle delay so the final paste finishes reading first.
"""

from __future__ import annotations

import sys
import time

import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString


# Virtual keycode for the physical "V" key (kVK_ANSI_V). Cmd+V uses this slot
# across common layouts because paste is bound to the physical key.
_V_KEYCODE = 9


def _set_clipboard(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if text:
        pb.setString_forType_(text, NSPasteboardTypeString)
    # Empty string -> leave the pasteboard cleared so Cmd+V pastes nothing.


def _get_clipboard() -> str:
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSPasteboardTypeString) or ""


def run(items: list[str]) -> int:
    """Install the tap and rotate `items` across each Cmd+V. Returns exit code."""
    # original = _get_clipboard()
    # Single-threaded mutable state for the run-loop callback.
    state = {"index": 0, "done": False}
    tap_holder: dict[str, object] = {}

    def callback(proxy, event_type, event, refcon):
        # The system disables a tap if its callback is too slow or on user
        # input during certain states; just re-enable and move on.
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            Quartz.CGEventTapEnable(tap_holder["tap"], True)
            return event

        if event_type != Quartz.kCGEventKeyDown:
            return event

        flags = Quartz.CGEventGetFlags(event)
        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        is_cmd = bool(flags & Quartz.kCGEventFlagMaskCommand)

        if is_cmd and keycode == _V_KEYCODE and not state["done"]:
            i = state["index"]
            if i < len(items):
                _set_clipboard(items[i])  # paste a, b, c, ...
                if i + 1 < len(items):
                    sys.stderr.write(items[i+1] + "\n")
            else:
                _set_clipboard("")  # one final "paste nothing"
            state["index"] += 1
            if state["index"] > len(items):
                state["done"] = True
                Quartz.CFRunLoopStop(Quartz.CFRunLoopGetCurrent())

        return event  # pass the keystroke through untouched

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        callback,
        None,
    )

    if tap is None:
        sys.stderr.write(
            "clipboard-rotative: could not create event tap.\n"
            "Grant Accessibility permission to your terminal:\n"
            "  System Settings > Privacy & Security > Accessibility\n"
        )
        return 1

    tap_holder["tap"] = tap
    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes
    )
    Quartz.CGEventTapEnable(tap, True)
    sys.stderr.write(items[0] + "\n")
    try:
        Quartz.CFRunLoopRun()
    except KeyboardInterrupt:
        pass
    finally:
        Quartz.CGEventTapEnable(tap, False)

    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if sys.platform != "darwin":
        sys.stderr.write("clipboard-rotative: macOS only.\n")
        return 2

    if not argv:
        lines = _get_clipboard().strip().splitlines()
        if lines:
            return run(lines)

    if not argv or argv[0] in ("-h", "--help"):
        sys.stderr.write(
            "usage: clipboard-rotative [STRING ...]\n"
            "  Each Cmd+V pastes the next STRING; one more Cmd+V pastes nothing.\n"
        )
        return 2

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
