"""
Usage::

    guard = StreamGuard(action_definitions, user_message="open notepad")

    for chunk in llm.stream("open notepad please"):
        result = guard.feed(chunk)
        print(result.text, end="", flush=True)
        for m in result.matches:
            if m.confirmed:
                execute(m.action.name, m.group)

    final = guard.flush()
    print(final.text, end="")

Limitations (read before using):

- Marker delimiters are configurable (``marker_start`` / ``marker_end``,
  default ``[[`` / ``]]``).  The guard has no way to detect markers that
  use *different* delimiters from the ones configured.
- ``max_marker_len`` caps the buffer size.  A marker longer than this is
  flushed as regular text (the assumption is that real markers are short).
- This module handles action markers only.  ``PromptLeakGuard`` operates
  on the complete response and cannot usefully run chunk-by-chunk (it
  needs the full text for canary / semantic / judge checks).  If you need
  leak detection on streamed output, accumulate the full text yourself
  and run ``PromptLeakGuard.check()`` after the stream ends.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .action_gate import ActionDefinition, ActionMatch, is_safe_token
from ._confirmation import is_confirmed_by_keywords


@dataclass
class StreamResult:
    text: str
    """Text safe to display right now (markers stripped)."""

    matches: List[ActionMatch] = field(default_factory=list)
    """Complete action markers found in this chunk (if any)."""

class StreamGuard:
    def __init__(
        self,
        actions: List[ActionDefinition],
        user_message: str,
        marker_start: str = "[[",
        marker_end: str = "]]",
        max_marker_len: int = 256,
    ):
        self._actions = actions
        self._user_message = user_message
        self._start = marker_start
        self._end = marker_end
        self._max = max_marker_len
        self._buf = ""
        self._buffering = False

    def feed(self, chunk: str) -> StreamResult:
        safe: list[str] = []
        matches: list[ActionMatch] = []

        self._buf += chunk

        while self._buf:
            if not self._buffering:
                idx = self._buf.find(self._start[0])
                if idx == -1:
                    safe.append(self._buf)
                    self._buf = ""
                    break

                if idx > 0:
                    safe.append(self._buf[:idx])
                    self._buf = self._buf[idx:]

                if len(self._buf) < len(self._start):
                    break

                if self._buf[: len(self._start)] == self._start:
                    self._buffering = True
                else:
                    safe.append(self._buf[0])
                    self._buf = self._buf[1:]
                    continue

            if self._buffering:
                end_idx = self._buf.find(self._end)

                if end_idx != -1:
                    end_pos = end_idx + len(self._end)
                    candidate = self._buf[:end_pos]
                    self._buf = self._buf[end_pos:]
                    self._buffering = False

                    matched = self._try_match(candidate)
                    if matched is not None:
                        matches.append(matched)
                    else:
                        safe.append(candidate)
                    continue

                if len(self._buf) > self._max:
                    safe.append(self._buf)
                    self._buf = ""
                    self._buffering = False
                    break
                break

        return StreamResult(text="".join(safe), matches=matches)

    def flush(self) -> StreamResult:
        text = self._buf
        self._buf = ""
        self._buffering = False
        return StreamResult(text=text)
    def _try_match(self, candidate: str) -> ActionMatch | None:
        for action in self._actions:
            m = action.pattern.search(candidate)
            if m:
                group = m.group(1) if m.groups() else None
                confirmed = is_confirmed_by_keywords(
                    self._user_message,
                    action.confirm_keywords,
                    reject_negated=action.reject_negated,
                )
                if confirmed and action.strict_tokens and group is not None:
                    if not is_safe_token(group.strip()):
                        confirmed = False
                return ActionMatch(
                    action=action,
                    raw_match=m.group(0),
                    group=group,
                    confirmed=confirmed,
                )
        return None
