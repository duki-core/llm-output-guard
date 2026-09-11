# llm-output-guard

A lightweight, vendor-agnostic library for two specific security problems in
local/self-hosted LLM applications:

1. **System prompt leakage** — the model discloses, paraphrases, translates,
   or quotes its internal instructions in response to a user's request
   ("repeat everything said above", roleplay-based jailbreaks, etc.).
2. **Unauthorized action execution** — the application interprets special
   markers in the model's output (`[[SHUTDOWN]]`, `[[OPEN:notepad]]`, etc.)
   as commands for real actions. The model can output such a marker not
   because the user asked for it, but due to a hallucination or a
   provoking instruction hidden somewhere in the context (a RAG document,
   chat history).

Grew out of a personal pet project (a local chat companion built on LM
Studio) — extracted into a standalone library because the underlying
problem is generic and has nothing to do with any specific character or
model.

## Architecture

### `PromptLeakGuard` — three layers, cheapest to most expensive

```
model's response text
        │
        ▼
[1] string matching ("canaries")          — instant
        │ didn't trigger
        ▼
[2] semantic similarity (embeddings)      — ~10-50ms on CPU
        │ didn't trigger
        ▼
shown as-is, judge is never called

        │ layer 1 OR 2 triggered
        ▼
[3] LLM judge: a separate model call      — seconds, only for suspicious text
    with a "leak / not a leak" classifier role
        │
        ▼
judge decides: show as-is, or replace with a safe fallback reply
```

Layers 1 and 2 are **pre-filtering heuristics**, not the final decision.
Their job is to avoid running the expensive judge on every single message —
only on suspicious ones.

### `ActionGate` — action markers require confirmation in the real message

A marker in the model's output (`[[OPEN:notepad]]`) is never executed on
its own. The action only fires if the **current message the user actually
typed** (not chat history, not RAG context, not a system-level trigger)
contains an explicit confirmation keyword. Otherwise the marker is silently
stripped from the text, but the action is never performed.

## Installation

```bash
pip install -e .                    # core functionality (layers 1 and 3)
pip install -e ".[semantic]"        # + semantic layer (layer 2)
pip install -e ".[dev]"             # + pytest for running tests
```

## Quick start

```python
from llm_output_guard import PromptLeakGuard

def judge_fn(text: str) -> bool:
    # Plug in a call to ANY model/API here — the library doesn't dictate which.
    return my_llm_client.classify_is_leak(text)

guard = PromptLeakGuard(judge_fn=judge_fn)
verdict = guard.check(model_output_text)

print(verdict.safe_text)   # what's safe to show the user
print(verdict.is_leak)     # True if flagged as a leak
```

A full example with a real OpenAI-compatible client (LM Studio, OpenAI,
etc.) and `ActionGate` is in [`examples/basic_usage.py`](examples/basic_usage.py).

## Honest limitations (read this before using it)

This is **not** a formal safety guarantee — it's a pragmatic set of
heuristics:

- **Layer 1 (string)** only catches literal matches. Paraphrased or
  translated-to-another-language text will slip through.
- **Layer 2 (embeddings)** catches semantic similarity better, but the
  similarity threshold (`semantic_threshold`) is an empirically chosen
  trade-off, not a rigorously derived number. Too low → false positives on
  harmless responses. Too high → misses.
- **Layer 3 (judge)** is the most reliable, but with a caveat: if `judge_fn`
  uses the **same model** that generated the suspicious text, independence
  of the evaluation isn't guaranteed — a model that decided to bypass the
  rules could theoretically "justify" itself in the judge role too. For
  stronger guarantees, use a separate (ideally simpler and more
  "obedient") model, or an external API dedicated to the judge role.
- **`ActionGate`** protects against an unconfirmed marker, but not against
  a situation where the user's own message happens to contain something
  that looks like confirmation, unrelated to the marker's actual intent
  (e.g. "turn off the light in the room" contains "turn off" — if the
  model happens to output `[[SHUTDOWN]]` in that same turn for an unrelated
  reason, the gate will let it through). Confirmation keywords are a crude
  intent heuristic, not real contextual understanding.
- **Regex patterns you write for `ActionDefinition`** run against the
  model's output, which is influenced by user input and can be
  adversarially shaped. A pattern with nested quantifiers (e.g. `(a+)+b`)
  can trigger catastrophic backtracking (ReDoS) — a crafted ~30-character
  input can hang the regex engine for tens of seconds. Keep patterns
  simple and test them against long adversarial inputs. See the
  `ActionDefinition` docstring for details.

Bottom line: this is **defense in depth**, not a single line of defense.
For truly critical actions (irreversible operations, access to sensitive
data), build in an additional explicit user confirmation (a confirm
dialog) on top of this library — don't rely on it alone.

## License

MIT
