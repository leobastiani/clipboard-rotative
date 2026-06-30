# clipboard-rotative

Paste a queue of strings on macOS — one per <kbd>Cmd</kbd>+<kbd>V</kbd>.

```
$ clipboard-rotative "a" "b" "c"
Cmd+V  -> pastes a
Cmd+V  -> pastes b
Cmd+V  -> pastes c
Cmd+V  -> pastes nothing
```

After the last item, one more <kbd>Cmd</kbd>+<kbd>V</kbd> pastes nothing and the
tool exits, restoring whatever was on your clipboard before. <kbd>Ctrl</kbd>+<kbd>C</kbd>
aborts early.

## Install (one line)

Requires [`pipx`](https://pipx.pypa.io) (`brew install pipx`).

```sh
pipx install "git+https://github.com/leobastiani/clipboard-rotative.git"
```

From a local clone instead:

```sh
pipx install .
```

## Accessibility permission

The tool watches keystrokes through a macOS event tap, which needs Accessibility
access. The first run will fail with an instruction if it isn't granted yet:

1. **System Settings → Privacy & Security → Accessibility**
2. Enable your terminal app (Terminal, iTerm2, Ghostty, …).
3. Re-run.

## How it works

A Quartz [`CGEventTap`](https://developer.apple.com/documentation/coregraphics/cgeventtapcreate)
sits at the session level and sees each key-down **before** the foreground app.
On <kbd>Cmd</kbd>+<kbd>V</kbd> it writes the next string to the general
pasteboard and passes the keystroke through; the app then pastes the value just
written.

This ordering is what makes it race-free:

- The tap runs earlier in the event pipeline than app delivery, so the
  pasteboard is updated before the app reads it for that keystroke.
- All state lives on the single run-loop thread — no background timers, no locks.
- A previous value is overwritten only on the *next* keystroke (seconds later),
  never while a paste is mid-flight. The original clipboard is restored only
  after the run loop stops, following a short settle delay.

## Develop

```sh
python -m clipboard_rotative "a" "b" "c"
```
