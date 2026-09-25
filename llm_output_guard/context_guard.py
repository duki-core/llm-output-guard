from __future__ import annotations

from typing import List

from .action_gate import ActionDefinition

def sanitize(text: str, actions: List[ActionDefinition], replacement: str = "[BLOCKED_MARKER]") -> str:
    cleaned = text
    for action in actions:
        cleaned = action.pattern.sub(replacement, cleaned)
    return cleaned

def sanitize_documents(documents: List[str], actions: List[ActionDefinition], replacement: str = "[BLOCKED_MARKER]") -> List[str]:
    return [sanitize(doc, actions, replacement) for doc in documents]
