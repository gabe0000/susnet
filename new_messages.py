#!/usr/bin/env python3
import time
from aprs_helpers import (
    get_messages_to,
    load_state,
    save_state,
    speak,
)

DST_CALL = "W4VDX-9"
DAYS_BACK = 7


def main():
    now = int(time.time())
    cutoff = now - DAYS_BACK * 24 * 3600

    state = load_state()
    last_id = int(state.get("last_messageid", 0))

    entries = get_messages_to(DST_CALL)

    # Filter to messages within last N days
    recent = []
    for e in entries:
        try:
            t = int(e.get("time", 0))
        except Exception:
            continue
        if t >= cutoff:
            recent.append(e)

    # Sort by messageid ascending so we read oldest first
    def mid(e):
        try:
            return int(e.get("messageid", 0))
        except Exception:
            return 0

    recent.sort(key=mid)

    new_entries = [e for e in recent if mid(e) > last_id]

    if not new_entries:
        speak("No new APRS messages for W 4 V D X dash 9.")
        return

    for e in new_entries:
        src = e.get("srccall", "unknown")
        msg = e.get("message", "").strip()
        # Basic sanitizing; APRS messages can be weird
        msg_clean = msg.replace("\r", " ").replace("\n", " ")
        text = f"New APRS message from {src}: {msg_clean}"
        speak(text)

    # Update state with highest messageid we've seen
    max_id = max(mid(e) for e in new_entries)
    state["last_messageid"] = max_id
    save_state(state)


if __name__ == "__main__":
    main()

