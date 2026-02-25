#!/usr/bin/env python3
"""
Generate an asciinema .cast file from demo.py output.

The .cast format is simple JSON lines — no Unix PTY needed.
The resulting file can be played with asciinema-player (JS widget)
on the landing page, or uploaded to asciinema.org.

Post-processes the raw capture to add natural pacing: each line gets
a small stagger, section breaks get longer pauses, and the dramatic
moments (delete, rollback) get the most breathing room.

Usage:
    python examples/record_demo.py
    # produces examples/demo.cast
"""
import io
import json
import os
import sys
import time


# Patch stdout to capture output with timestamps
class TimestampCapture:
    """Wraps stdout to capture (timestamp, text) pairs for .cast format."""

    def __init__(self):
        self.start = time.time()
        self.events: list[tuple[float, str]] = []
        self._real_stdout = sys.stdout

    def write(self, text: str):
        if text:
            elapsed = time.time() - self.start
            self.events.append((elapsed, text))
            self._real_stdout.write(text)
        return len(text)

    def flush(self):
        self._real_stdout.flush()

    def isatty(self):
        return True  # trick _supports_color() into enabling ANSI

    @property
    def encoding(self):
        return "utf-8"

    def reconfigure(self, **kwargs):
        pass  # absorb the Windows UTF-8 reconfigure call


def _pace_events(events: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """
    Post-process captured events to add natural terminal pacing.

    The raw capture has all prints at nearly the same timestamp (they're
    just Python print() calls — microseconds apart). This makes the
    recording unwatchable. We re-time them so:
      - Each line gets a small stagger (50ms per line)
      - Section breaks (act headers, dividers) get longer pauses (1.5s)
      - Dramatic moments (warning, rollback) get the most room (2s)
      - Real time.sleep() pauses from the demo are preserved
    """
    paced: list[tuple[float, str]] = []
    cursor = 0.5  # start half a second in

    # Line delay defaults — tuned for comfortable reading speed
    LINE_DELAY = 0.22       # 220ms per line of output
    SECTION_PAUSE = 2.5     # pause before act headers
    DRAMA_PAUSE = 3.5       # pause before "Wait..." and rollback
    BLANK_LINE_DELAY = 0.4  # blank lines get visual breathing room

    prev_real_time = events[0][0] if events else 0

    for real_time, text in events:
        # Detect real pauses from time.sleep() in demo.py (>0.3s gap)
        real_gap = real_time - prev_real_time
        if real_gap > 0.3:
            cursor += max(real_gap, DRAMA_PAUSE)

        # Detect section boundaries by content
        if "\u2501\u2501\u2501\u2501" in text:  # ━━━━ act headers
            cursor += SECTION_PAUSE
        elif "\u2550\u2550\u2550\u2550" in text:  # ════ top/bottom bars
            cursor += 0.3
        elif "\u26a0" in text:  # ⚠ warning lines
            cursor += DRAMA_PAUSE
        elif "enact.rollback" in text:
            cursor += 1.5
        elif "Verified" in text:
            cursor += 1.2
        elif text == "\n":
            cursor += BLANK_LINE_DELAY
        else:
            cursor += LINE_DELAY

        paced.append((round(cursor, 3), text))
        prev_real_time = real_time

    return paced


def main():
    # Fix Windows CP1252 on the real stdout before we wrap it
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Force ANSI color detection to succeed — demo.py checks this at import time
    os.environ["WT_SESSION"] = "1"

    capture = TimestampCapture()
    sys.stdout = capture

    # Import and run demo (output goes through our capture wrapper)
    from demo import run_demo
    run_demo()

    sys.stdout = capture._real_stdout

    # Post-process for natural pacing
    paced = _pace_events(capture.events)

    # Merge newline events into the preceding text event.
    # asciinema-player's terminal emulator needs \r\n (not bare \n) to
    # reset the cursor to column 0. Merging ensures the \r\n is part
    # of the same write as the text, which works reliably across players.
    merged: list[tuple[float, str]] = []
    for elapsed, text in paced:
        if text == "\n" and merged:
            # Append \r\n to the previous event instead of a separate event
            prev_t, prev_text = merged[-1]
            merged[-1] = (prev_t, prev_text + "\r\n")
        else:
            merged.append((elapsed, text))

    total_duration = merged[-1][0] if merged else 0

    # Write .cast file (asciicast v2 format)
    header = {
        "version": 2,
        "width": 85,
        "height": 16,  # compact — player scrolls naturally
        "timestamp": int(time.time()),
        "title": "Enact Demo — action firewall for AI agents",
        "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"},
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cast_path = os.path.join(script_dir, "demo.cast")
    with open(cast_path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(header) + "\n")
        for elapsed, text in merged:
            event = [elapsed, "o", text]
            f.write(json.dumps(event) + "\n")

    print(f"\nWrote {cast_path} ({len(paced)} events, {total_duration:.1f}s duration)")
    print(f"Play with: asciinema-player JS widget or asciinema.org")


if __name__ == "__main__":
    main()
