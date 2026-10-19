# Chapter 3: Tools: JSON Mapped to Functions

*Harness Engineering 101, Part I — The Wire.
[Series index](index.html) · [Prev](02-the-brain.md) ·
[Next: The Agent Loop](04-the-agent-loop.md)*

---

**The failure:** the brain can only emit text. Ask it to "check whether the
tests pass" and the best it can do is guess. It cannot run, read or touch
anything.

**The patch:** let the model emit a structured request, and have your
program execute it. That is the entire idea behind tools, and more of
modern AI rests on it than on any other trick. This chapter shows that it is
just JSON on both ends.

## The contract

Tool use is a three-step contract between brain and body:

1. You tell the model what functions exist (names, descriptions, parameter
   schemas). This goes in the request, next to your messages.
2. The model, instead of answering in prose, may reply with a **tool call**:
   a block that names a function and provides arguments as JSON.
3. Your program runs the real function, puts the output back into the array
   as a **tool result**, and calls the API again so the model can continue.

```mermaid
sequenceDiagram
    participant B as Brain (model)
    participant H as Harness (your code)
    participant W as World (filesystem, shell, ...)
    H->>B: messages + tool definitions
    B-->>H: tool_use: read_file {"path": "main.py"}
    H->>W: open("main.py").read()
    W-->>H: file contents
    H->>B: messages + tool_result: "import sys\n..."
    B-->>H: "The bug is on line 12: ..."
```

**The model never executes anything; it only asks.** The tool call is a
polite, machine-readable request. Your harness decides whether to honor it,
runs the code, and reports back. Every capability an agent has is a function
you wrote and chose to expose. This is also why safety lives in the harness
(chapter 13): the body owns the hands.

## What it looks like on the wire

You define tools with a name, a description, and a JSON Schema for the
arguments:

```json
{
  "name": "read_file",
  "description": "Read a file from the local filesystem and return its contents.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Path to the file"}
    },
    "required": ["path"]
  }
}
```

The description is the only documentation the model gets, and writing good
tool descriptions is real prompt engineering. A vague description leads to
wrong usage.

When the model wants the tool, its reply contains a `tool_use` block instead
of (or alongside) text:

```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "Let me look at the file first."},
    {"type": "tool_use", "id": "toolu_01A", "name": "read_file",
     "input": {"path": "main.py"}}
  ]
}
```

You run the function, then append the result as the next `user` message:

```json
{
  "role": "user",
  "content": [
    {"type": "tool_result", "tool_use_id": "toolu_01A",
     "content": "import sys\n\ndef main():\n    ..."}
  ]
}
```

Then you POST the whole array again. Two details are worth noting here.
First, the tool result travels in a `user` message, so from the model's
point of view the world answers on the user's channel. Second, this is
chapter 1's loop with one new block type, and nothing about the wire
changed.

The model produces clean, schema-matching JSON because, as chapter 2
explained, it was RL-trained on millions of tool-call examples. You are not
parsing free text and hoping. Modern providers even guarantee the arguments
parse as JSON. (In the GPT-3.5 days, we begged the model in the prompt to
"respond ONLY with JSON" and wrote regex fallbacks for when it apologized
first. Function calling moved that trick into training, and that is the
entire difference.)

## The toy harness, v2

[`harness/v2_tools.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/src/harness/v2_tools.py) adds two tools to v1. The new
parts are marked:

```python
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
```

And `call_llm` now sends `"tools": TOOLS` in the body. The whole patch is a
menu and a dispatch table from names to functions. "Tool" sounds like
infrastructure, but it is a dict lookup.

One detail in `execute_tool` matters more than it looks: it catches
exceptions and returns an error *string* instead of raising. That error
string goes back to the model as the tool result. Chapter 2 said models are
trained to react to failure; chapter 4 builds the loop that lets them.
Swallowing a tool error, or crashing on it, throws away the model's best
recovery signal.

v2 handles exactly one tool call per turn, then returns to the prompt. Try
it: ask "what files are in this directory?" and watch the model call
`run_command` with `ls`. Then ask something that needs two steps, like
"read the largest file here," and watch it fail: it needs the result of
`ls` before it can call `read_file`, but our program hands control back to
you after one call. That failure is chapter 4.

## The user is a tool too

Once you see tools as "the model requests, the world responds," you can
treat the human as part of that world too.

Production agents expose a tool that looks like this:

```json
{
  "name": "ask_user_question",
  "description": "Ask the user a clarifying question when you are blocked on a decision only they can make.",
  "input_schema": {
    "type": "object",
    "properties": {
      "question": {"type": "string"},
      "options": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["question"]
  }
}
```

The implementation renders the question, waits for input, and returns the
answer as an ordinary tool result. That is **human-in-the-loop** at its
simplest. The person is one more thing the body can consult, on the same
wire format as the filesystem. Claude Code's multiple-choice question
dialogs are exactly this tool, with no special mechanism or separate
channel. The model learned when to ask a person the same way it learned when
to read a file.

There is a second, more important place humans enter the loop: approval.
"The model asked to run `rm -rf`; should the body obey?" That is a harness
decision, not a tool, and it gets its own chapter (13).

> **Sidebar: structured output.** Sometimes you do not want actions; you
> want the model's *answer* as machine-readable data, like
> `{"sentiment": "negative", "score": 0.87}`. Providers offer JSON modes
> for this. But the oldest reliable trick still works: define one tool
> named `report_answer` whose input schema is your desired output format,
> and force the model to call it. The tool executes nothing; its arguments
> *are* the output. Structured output and tool calling are the same trained
> skill pointed at different goals: one asks for action, the other for
> shape.

> **Sidebar: server-side tools.** Some tools run without any harness code.
> Ask Anthropic's API for `web_search` and the *provider's* infrastructure
> executes the search during the request, splices the results into the
> conversation, and bills you for the tokens. The array you get back shows
> the tool round already resolved. The contract is the same, but the
> provider's body did the work, with limbs you did not build. The tradeoff
> is control: you cannot gate, log, or modify a server-side tool call, and
> your permission system (chapter 13) never sees it. It's convenient for
> search; think twice before accepting it for anything that touches your
> systems.

## What you now know

- A tool is three pieces of JSON: a schema in the request, a `tool_use`
  block in the reply, and a `tool_result` block in the next message.
- The model asks and the harness acts, so capability and safety both live in
  the harness.
- Return tool errors as text in the tool result, not as exceptions.

v2 can act only once, but real tasks need the model to act, look at the
result, and act again, without a human pressing enter between steps. That
is the next failure. The loop that fixes it has a grand name, but it is four
lines of code.

*[Next: Chapter 4 — The Agent Loop](04-the-agent-loop.md)*
