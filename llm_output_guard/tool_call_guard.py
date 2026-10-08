from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._confirmation import is_confirmed_by_keywords


@dataclass
class ToolCallDefinition:
    name: str
    confirm_keywords: List[str]
    required_args: Optional[List[str]] = None
    arg_validators: Optional[Dict[str, Callable[[Any], bool]]] = None

@dataclass
class ToolCallMatch:
    definition: ToolCallDefinition
    call_name: str
    arguments: Dict[str, Any]
    confirmed: bool
    reason: str = ""

class ToolCallGuard:
    def __init__(self, definitions: List[ToolCallDefinition]):
        self._by_name: Dict[str, ToolCallDefinition] = {
            d.name: d for d in definitions
        }

    def process(
        self,
        tool_calls: List[Dict[str, Any]],
        user_message: str,
    ) -> List[ToolCallMatch]:
        matches: List[ToolCallMatch] = []

        for tc in tool_calls:
            call_name = tc.get("name", "")
            arguments = tc.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}

            defn = self._by_name.get(call_name)
            if defn is None:
                continue

            confirmed, reason = self._evaluate(defn, arguments, user_message)
            matches.append(ToolCallMatch(
                definition=defn,
                call_name=call_name,
                arguments=arguments,
                confirmed=confirmed,
                reason=reason,
            ))

        return matches

    @staticmethod
    def _evaluate(
        defn: ToolCallDefinition,
        arguments: Dict[str, Any],
        user_message: str,
    ) -> Tuple[bool, str]:
        if defn.required_args:
            missing = [a for a in defn.required_args if a not in arguments]
            if missing:
                return False, f"missing required argument(s): {', '.join(missing)}"

        if defn.arg_validators:
            for arg_name, validator in defn.arg_validators.items():
                if arg_name in arguments:
                    if not validator(arguments[arg_name]):
                        return False, f"argument '{arg_name}' failed validation"

        if not is_confirmed_by_keywords(user_message, defn.confirm_keywords):
            return False, "no confirmation keyword in user message"

        return True, ""
