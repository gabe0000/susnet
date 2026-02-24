#!/home/codex/joe-cabot-lite/.venv/bin/python
import argparse
import json
import random
import sys
import time
from threading import Event

import paho.mqtt.client as mqtt


def run_query(broker, port, query_topic, reply_topic, sender, text, timeout, retries=2):
    rid = f"cli-{int(time.time())}-{random.randint(1000,9999)}"
    done = Event()
    chunks = {}
    chunk_count = {"value": None}

    def on_connect(client, userdata, flags, rc):
        if rc != 0:
            print(f"MQTT connect failed rc={rc}", file=sys.stderr)
            done.set()
            return
        client.subscribe(reply_topic, qos=0)
        payload = {
            "request_id": rid,
            "sender": sender,
            "text": text,
            "source": "ask-joe-cli",
        }
        client.publish(query_topic, json.dumps(payload), qos=0, retain=False)

    def on_message(client, userdata, msg):
        try:
            parsed = json.loads(msg.payload.decode("utf-8", errors="replace"))
        except Exception:
            return
        if parsed.get("request_id") != rid:
            return
        body = str(parsed.get("text", "")).strip()
        if not body:
            return
        try:
            idx = int(parsed.get("chunk_index", len(chunks) + 1))
        except Exception:
            idx = len(chunks) + 1
        chunks[idx] = body
        try:
            cc = int(parsed.get("chunk_count")) if parsed.get("chunk_count") is not None else None
        except Exception:
            cc = None
        if cc and cc > 0:
            chunk_count["value"] = cc
        if chunk_count["value"] and len(chunks) >= chunk_count["value"]:
            done.set()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    attempt = 0
    while attempt < max(1, retries):
        chunks.clear()
        chunk_count["value"] = None
        done.clear()
        client.connect(broker, port, keepalive=60)
        client.loop_start()

        start = time.time()
        while time.time() - start < timeout:
            if done.wait(0.2):
                break

        client.loop_stop()
        client.disconnect()

        if chunks:
            ordered = [chunks[i] for i in sorted(chunks.keys())]
            return " ".join(ordered)

        attempt += 1

    return None


def main():
    p = argparse.ArgumentParser(description="Query Joe Cabot over MQTT in one command")
    p.add_argument("text", nargs="*", help="Query text")
    p.add_argument("--broker", default="100.124.168.35", help="MQTT broker IP (MeshBox)")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--query-topic", default="susnet/agent/query")
    p.add_argument("--reply-topic", default="susnet/agent/reply")
    p.add_argument("--sender", default="!9e77f1a0")
    p.add_argument("--timeout", type=float, default=25.0)
    p.add_argument("--chat", action="store_true", help="Interactive chat mode")
    p.add_argument("--retries", type=int, default=2, help="Retry count when no reply")
    args = p.parse_args()

    if args.chat:
        print("ask-joe chat mode. Ctrl-C to exit.")
        while True:
            try:
                q = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not q:
                continue
            ans = run_query(args.broker, args.port, args.query_topic, args.reply_topic, args.sender, q, args.timeout, args.retries)
            if ans is None:
                print("joe> [no reply within timeout]")
            else:
                print(f"joe> {ans}")
        return 0

    if not args.text:
        p.error("Provide query text or use --chat")

    q = " ".join(args.text).strip()
    ans = run_query(args.broker, args.port, args.query_topic, args.reply_topic, args.sender, q, args.timeout, args.retries)
    if ans is None:
        print("No reply within timeout.", file=sys.stderr)
        return 2
    print(ans)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
