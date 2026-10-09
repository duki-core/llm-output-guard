from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._confirmation import is_confirmed_by_keywords, value_appears_in_text


@dataclass
class ToolCallDefinition:
    name: str
    confirm_keywords: List[str]
    required_args: Optional[List[str]] = None
    arg_validators: Optional[Dict[str, Callable[[Any], bool]]] = None
    # Names of arguments whose value must literally appear in the user's
    # message (e.g. ["path"]: delete_file(path="/etc/passwd") is blocked
    # unless the user actually typed "/etc/passwd"). Only checked for
    # arguments that are present in the call.
    args_in_message: Optional[List[str]] = None
    # If True, a confirmation keyword that is negated in the same clause
    # ("don't delete it", "не удаляй") does not confirm the call.
    reject_negated: bool = True

@dataclass
class ToolCallMatch:
    # None only for calls denied by `default_deny` (no registered definition).
    definition: Optional[ToolCallDefinition]
    call_name: str
    arguments: Dict[str, Any]
    confirmed: bool
    reason: str = ""

class ToolCallGuard:
    """
    default_deny:
        False (default) — tool calls that are not registered are ignored by the
            guard (not returned from `process`); the application runs them freely.
        True — every tool call must be registered. An unregistered call is
            returned as a ToolCallMatch with confirmed=False and
            definition=None, so it can never be executed by mistake.
    """

    def __init__(
        self,
        definitions: List[ToolCallDefinition],
        default_deny: bool = False,
    ):
        self.default_deny = default_deny
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
                if self.default_deny:
                    matches.append(ToolCallMatch(
                        definition=None,
                        call_name=call_name,
                        arguments=arguments,
                        confirmed=False,
                        reason="tool not registered (default_deny)",
                    ))
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

        if defn.args_in_message:
            for arg_name in defn.args_in_message:
                if arg_name in arguments and not value_appears_in_text(
                    arguments[arg_name], user_message
                ):
                    return False, f"argument '{arg_name}' not found in user message"

        if not is_confirmed_by_keywords(
            user_message, defn.confirm_keywords, reject_negated=defn.reject_negated
        ):
            return False, "no confirmation keyword in user message"

        return True, ""
