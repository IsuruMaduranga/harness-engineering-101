#!/usr/bin/env python3
"""Harness v2: tools. A menu of functions + a dispatch table.

Chapter 3 of Harness Engineering 101.
Handles ONE tool call per user turn (the limitation chapter 4 fixes).
"""
import json
import os
import subprocess
import urllib.request

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-4-5"
SYSTEM = "You are a concise assistant with access to the local machine."

TOOLS = [                                            # NEW: the menu
    {"name": "read_file",
     "description": "Read a text file and return its contents.",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "run_command",
     "description": "Run a shell command and return stdout+stderr.",
     "input_schema": {"type": "object",
                      "properties": {"command": {"type": "string"}},
                      "required": ["command"]}},
]


def call_llm(messages):
    body = {"model": MODEL, "max_tokens": 4096, "system": SYSTEM,
            "messages": messages, "tools": TOOLS}   # NEW: send the menu
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def execute_tool(name, args):                        # NEW: the dispatch
    """Map the model's JSON request to a real function call."""
    try:
        if name == "read_file":
            return open(args["path"]).read()
        if name == "run_command":
            out = subprocess.run(args["command"], shell=True,
                                 capture_output=True, text=True, timeout=60)
            return out.stdout + out.stderr
        return f"ERROR: unknown tool {name}"
    except Exception as e:
        return f"ERROR: {e}"                         # errors go BACK to the model


def main():
    messages = []
    while True:
        user_text = input("\nyou> ").strip()
        if user_text in ("/quit", ""):
            break
        messages.append({"role": "user", "content": user_text})

        reply = call_llm(messages)
        messages.append({"role": "assistant", "content": reply["content"]})

        for block in reply["content"]:
            if block["type"] == "text":
                print(f"\nassistant> {block['text']}")
            elif block["type"] == "tool_use":        # NEW: honor ONE request
                print(f"\n[tool] {block['name']}({json.dumps(block['input'])})")
                result = execute_tool(block["name"], block["input"])
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": block["id"],
                     "content": result}]})
                reply2 = call_llm(messages)          # let the model react once
                messages.append({"role": "assistant",
                                 "content": reply2["content"]})
                for b2 in reply2["content"]:
                    if b2["type"] == "text":
                        print(f"\nassistant> {b2['text']}")
                # If reply2 asks for ANOTHER tool, v2 drops it. Chapter 4.


if __name__ == "__main__":
    main()
