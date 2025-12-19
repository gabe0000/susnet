#!/usr/bin/env python3
import time
from aprs_helpers import (
    get_messages_to,
    speak,
)

DST_CALL = "W4VDX-9"
DAYS_BACK = 7


def main():
    now = int(time.time())
    cutoff = now - DAYS_BACK * 24 * 3600

    entries = get_messages_to(DST_CALL)

    recent = []
    for e in entries:
        try:
            t = int(e.get("time", 0))
        except Exception:
            continue
        if t >= cutoff:
            recent.append(e)

    if not recent:
        speak("There are no recent APRS messages for W 4 V D X dash 9.")
        return

    # Sort by time ascending so it’s like a conversation
    recent.sort(key=lambda e: int(e.get("time", 0)))

    speak("Here are the recent APRS messages for W 4 V D X dash 9.")

    for e in recent:
        src = e.get("srccall", "unknown")
        msg = e.get("message", "").strip()
        msg_clean = msg.replace("\r", " ").replace("\n", " ")
        text = f"From {src}: {msg_clean}"
        speak(text)


if __name__ == "__main__":
    main()

