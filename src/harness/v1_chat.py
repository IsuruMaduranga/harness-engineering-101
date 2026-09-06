#!/usr/bin/env python3
"""Harness v1: a chat loop. The array IS the conversation.

Chapter 1 of Harness Engineering 101.
Requires: ANTHROPIC_API_KEY in the environment. Zero dependencies.
"""
import json
import os
import urllib.request

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-4-5"
SYSTEM = "You are a concise assistant."


def call_llm(messages):
    body = {"model": MODEL, "max_tokens": 4096,
            "system": SYSTEM, "messages": messages}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    messages = []                                   # the entire "session"
    while True:
        user_text = input("\nyou> ").strip()
        if user_text in ("/quit", ""):
            break
        if user_text == "/clear":
            messages = []                           # "new conversation"
            continue
        messages.append({"role": "user", "content": user_text})
        reply = call_llm(messages)                  # resend EVERYTHING
        text = "".join(b["text"] for b in reply["content"]
                       if b["type"] == "text")
        messages.append({"role": "assistant", "content": reply["content"]})
        print(f"\nassistant> {text}")


if __name__ == "__main__":
    main()
