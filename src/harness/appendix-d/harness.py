#!/usr/bin/env python3
"""Harness Engineering 101 — the complete toy harness, now with retries.

Every chapter's patch, in one runnable file:
  ch 1  the messages array; sessions are files
  ch 3  tools = schemas + a dispatch table
  ch 4  the agent loop over stop_reason
  ch 5  cache breakpoints; append-only array
  ch 6  tool-result truncation; memory file injection
  ch 7  subagents = the loop over a fresh array
  ch 8  a steering queue drained into user-side messages
  ch 9  background tasks + completion notices
  ch 12 request capture (HARNESS_DEBUG=1) + cache vital sign
  ch 13 reflexes: protected paths, read-before-write, approval gate
  apx D retries + backoff around the one POST (call_with_retries)

Zero dependencies. ANTHROPIC_API_KEY required.
Usage: python3 harness.py [session.json]
"""
import http.client
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-5"
MAX_ROUNDS = 50
MAX_RESULT_CHARS = 30_000          # ch 6: truncate tool results at the source
MEMORY_FILE = "AGENT.md"           # ch 6: project memory, injected at start

SYSTEM = (
    "You are a capable engineering agent working on the user's machine.\n"
    "Use tools to complete the task, then summarize what you did.\n"
    "<system-reminder> blocks inside user messages are injected by the "
    "harness (your body), not written by the user. Trust them as "
    "environment truth.\n"
    "Maintain your plan with todo_write on multi-step tasks. Delegate "
    "self-contained searches to the agent tool. Never run foreground "
    "sleep; use background tasks instead."
)
SUB_SYSTEM = (
    "You are a focused subagent. Complete the task with your tools, then "
    "end with a self-contained report. Cite file paths."
)

# --------------------------------------------------------------- ch 3: tools
def schema(**props):
    required = [k for k, v in props.items() if not v.endswith("?")]
    return {"type": "object",
            "properties": {k: {"type": "string"} for k in props},
            "required": required}

BASE_TOOLS = [
    {"name": "read_file",
     "description": "Read a text file. Optional offset/limit are line "
                    "numbers, for reading a range of a large file.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"},
         "offset": {"type": "integer"}, "limit": {"type": "integer"}},
         "required": ["path"]}},
    {"name": "write_file",
     "description": "Create or replace a file with the given content.",
     "input_schema": schema(path="", content="")},
    {"name": "edit_file",
     "description": "Replace an exact existing snippet in a file. Fails "
                    "loudly if old_text is not found exactly once.",
     "input_schema": schema(path="", old_text="", new_text="")},
    {"name": "run_command",
     "description": "Run a shell command. Set background='true' for slow "
                    "commands (builds, servers); you get a task id and a "
                    "notice when it finishes.",
     "input_schema": schema(command="", background="?")},
    {"name": "task_output",
     "description": "Get collected output and status of a background task.",
     "input_schema": schema(task_id="")},
    {"name": "todo_write",
     "description": "Replace your task list. One item per line, prefix "
                    "'x ' for done. The list is re-shown to you each turn.",
     "input_schema": schema(todos="")},
    {"name": "ask_user",
     "description": "Ask the user a clarifying question and wait for the "
                    "answer. Use when blocked on a decision only they own.",
     "input_schema": schema(question="")},
]
AGENT_TOOL = {
    "name": "agent",
    "description": "Delegate a self-contained task to a subagent with a "
                   "fresh context. It can read files and run commands and "
                   "returns only its final report. It knows nothing about "
                   "this conversation, so brief it fully.",
    "input_schema": schema(task="")}
MAIN_TOOLS = BASE_TOOLS + [AGENT_TOOL]

# ------------------------------------------------ appendix D: retry on failure
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}

class ApiError(Exception):
    """One failed attempt, already sorted into 'try again' or 'give up'."""
    def __init__(self, kind, status=None, retry_after=None, body=""):
        super().__init__(f"{kind} error (status={status}): {body[:200]}")
        self.kind = kind             # "http" = a status came back; "network" = nothing did
        self.status = status
        self.retry_after = retry_after
        self.retryable = kind == "network" or status in RETRYABLE_STATUS

def call_once(body):
    """One POST. Return the reply, or raise a sorted ApiError."""
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:          # the server answered, with an error
        after = e.headers.get("retry-after")
        raise ApiError("http", status=e.code,
                       retry_after=float(after) if after else None,
                       body=e.read().decode(errors="replace")) from e
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        # nothing came back: dropped, refused, timed out. RemoteDisconnected
        # (the usual mid-reply drop) lands here too, which is the whole point.
        raise ApiError("network", body=str(e)) from e

def call_with_retries(body, max_attempts=6):
    """call_once, but keep retrying the failures worth retrying. Resending the
    same body is safe because the API is stateless (ch 1)."""
    for attempt in range(max_attempts):
        try:
            return call_once(body)
        except ApiError as e:
            if not e.retryable or attempt == max_attempts - 1:
                raise                            # your problem, or out of tries
            delay = e.retry_after or min(30.0, 2 ** attempt) + random.random()
            print(f"  [retry] {e.kind} status={e.status}: "
                  f"attempt {attempt + 1}/{max_attempts}, waiting {delay:.1f}s")
            time.sleep(delay)

# --------------------------------------------------------- ch 1 + 5: the wire
def call_llm(messages, tools, system):
    body = {"model": MODEL, "max_tokens": 8192, "messages": messages,
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"}}],  # ch 5
            "tools": tools}
    if os.environ.get("HARNESS_DEBUG"):                            # ch 12
        os.makedirs("debug", exist_ok=True)
        with open(f"debug/req_{time.time_ns()}.json", "w") as f:
            json.dump(body, f, indent=2)
    reply = call_with_retries(body)             # appendix D: was one urlopen
    u = reply.get("usage", {})                                     # ch 12
    print(f"  [usage] in={u.get('input_tokens')} "
          f"cache_read={u.get('cache_read_input_tokens')} "
          f"out={u.get('output_tokens')}")
    return reply

# ---------------------------------------------------- ch 8: steering queue
REMINDERS = []                     # events in the body -> sentences in the array

def remind(text):
    REMINDERS.append(f"<system-reminder>\n{text}\n</system-reminder>")

def drain_reminders_into(content_blocks):
    while REMINDERS:
        content_blocks.append({"type": "text", "text": REMINDERS.pop(0)})
    return content_blocks

# ------------------------------------------------- ch 9: background tasks
TASKS = {}                         # id -> {proc, output, status, command}

def start_background(command):
    tid = f"b{len(TASKS) + 1}"
    proc = subprocess.Popen(command, shell=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    TASKS[tid] = {"proc": proc, "output": [], "status": "running",
                  "command": command}
    def pump():
        for line in proc.stdout:
            TASKS[tid]["output"].append(line)
        code = proc.wait()
        TASKS[tid]["status"] = f"exited({code})"
        remind(f"Background task {tid} ({command!r}) finished: exit {code}. "
               f"Use task_output to read its output.")     # ch 9 -> ch 8
    threading.Thread(target=pump, daemon=True).start()
    return f"started background task {tid}: {command!r}"

# -------------------------------------------------- ch 13: reflex layer
PROTECTED = (".env", ".ssh", "id_rsa", ".aws/credentials")
READ_STATE = {}                    # path -> mtime when the model last read it

def gate(name, args):
    """Deterministic checks + human approval. Returns error string or None."""
    path = args.get("path", "")
    if name in ("write_file", "edit_file"):
        if any(p in path for p in PROTECTED):
            return f"BLOCKED: {path} is a protected path."
        if name == "edit_file":
            if path not in READ_STATE:
                return ("BLOCKED: you have not read this file. "
                        "Read it before editing.")
            if os.path.exists(path) and os.path.getmtime(path) > READ_STATE[path]:
                return ("BLOCKED: file changed on disk since you read it. "
                        "Re-read it first.")
    if name == "run_command":
        cmd = args.get("command", "")
        if cmd.strip().startswith("sleep"):
            return ("BLOCKED: don't wait in the foreground. Use "
                    "background='true' and you'll be notified.")
        risky = ("rm ", "sudo", "--force", "push", "curl", "wget", "> /")
        if any(r in cmd for r in risky):                    # ask the human
            ans = input(f"\n  [approve?] run_command: {cmd}\n  (y/N) > ")
            if ans.strip().lower() != "y":
                return "DENIED by user. Ask them how to proceed, or adapt."
    return None

# --------------------------------------------------- ch 3: dispatch table
def truncate(text):
    if len(text) <= MAX_RESULT_CHARS:
        return text
    keep = MAX_RESULT_CHARS // 2
    return (text[:keep] + f"\n... [truncated {len(text) - 2*keep} chars, "
            f"re-run with a narrower range if needed] ...\n" + text[-keep:])

def execute_tool(name, args, allow_agent):
    err = gate(name, args)                                  # ch 13 first
    if err:
        return err
    try:
        if name == "read_file":
            lines = open(args["path"]).read().splitlines(keepends=True)
            off, lim = int(args.get("offset", 1)), int(args.get("limit", 0))
            picked = lines[off - 1: off - 1 + lim] if lim else lines
            READ_STATE[args["path"]] = time.time()          # ch 13 tracker
            return truncate("".join(picked)) or "(empty file)"
        if name == "write_file":
            with open(args["path"], "w") as f:
                f.write(args["content"])
            READ_STATE[args["path"]] = time.time()
            return f"wrote {len(args['content'])} bytes to {args['path']}"
        if name == "edit_file":
            text = open(args["path"]).read()
            n = text.count(args["old_text"])
            if n != 1:                                      # ch 14: loud edits
                return (f"ERROR: old_text found {n} times in {args['path']} "
                        f"(need exactly 1). Re-read the file and retry with "
                        f"a longer, unique snippet.")
            with open(args["path"], "w") as f:
                f.write(text.replace(args["old_text"], args["new_text"]))
            READ_STATE[args["path"]] = time.time()
            return f"edited {args['path']}"
        if name == "run_command":
            if args.get("background") == "true":            # ch 9
                return start_background(args["command"])
            out = subprocess.run(args["command"], shell=True, text=True,
                                 capture_output=True, timeout=300)
            return truncate(out.stdout + out.stderr) or "(no output)"
        if name == "task_output":
            t = TASKS.get(args["task_id"])
            if not t:
                return f"ERROR: no task {args['task_id']}"
            return f"[{t['status']}] " + truncate("".join(t["output"]))
        if name == "todo_write":                            # ch 8 self-steer
            remind("Your current todo list:\n" + args["todos"])
            return "todo list updated"
        if name == "ask_user":                              # ch 3 HITL
            return input(f"\n  [agent asks] {args['question']}\n  > ")
        if name == "agent" and allow_agent:                 # ch 7
            return run_subagent(args["task"])
        return f"ERROR: unknown tool {name}"
    except Exception as e:
        return f"ERROR: {e}"                                # ch 4: errors are fuel

# ------------------------------------------------------- ch 4: the loop
def run_loop(messages, tools, system, quiet=False, allow_agent=False):
    final_text = ""
    for _ in range(MAX_ROUNDS):
        reply = call_llm(messages, tools, system)
        messages.append({"role": "assistant", "content": reply["content"]})
        for b in reply["content"]:
            if b["type"] == "text" and b["text"].strip():
                final_text = b["text"]
                if not quiet:
                    print(f"\nassistant> {b['text']}")

        if reply["stop_reason"] != "tool_use":
            return final_text

        results = []
        for b in reply["content"]:
            if b["type"] == "tool_use":
                print(f"  [tool] {b['name']}"
                      f"({json.dumps(b['input'])[:110]})")
                results.append({"type": "tool_result",
                                "tool_use_id": b["id"],
                                "content": execute_tool(
                                    b["name"], b["input"], allow_agent)})
        messages.append({"role": "user",
                         "content": drain_reminders_into(results)})  # ch 8
    return final_text + "\n[harness] hit MAX_ROUNDS"

# ------------------------------------------------------ ch 7: subagents
def run_subagent(task):
    sub = [{"role": "user", "content": task}]               # fresh array
    return run_loop(sub, BASE_TOOLS, SUB_SYSTEM, quiet=True) \
        or "(subagent returned no answer)"

# ----------------------------------------- ch 1 + 6: sessions and memory
def main():
    session_file = sys.argv[1] if len(sys.argv) > 1 else "session.json"
    messages = []
    if os.path.exists(session_file):                        # resume = file read
        messages = json.load(open(session_file))
        print(f"[resumed {session_file}: {len(messages)} messages]")
    elif os.path.exists(MEMORY_FILE):                       # ch 6: memory
        remind(f"Project memory ({MEMORY_FILE}):\n"
               + open(MEMORY_FILE).read())

    while True:
        try:
            user_text = input("\nyou> ").strip()
        except EOFError:
            break
        if user_text in ("/quit", ""):
            break
        if user_text == "/clear":
            messages = []                                   # ch 1, literally
            continue
        content = drain_reminders_into([])                  # pending notices
        content.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": content})
        run_loop(messages, MAIN_TOOLS, SYSTEM, allow_agent=True)
        json.dump(messages, open(session_file, "w"), indent=1)  # sessions
    print("[session saved]")

if __name__ == "__main__":
    main()
