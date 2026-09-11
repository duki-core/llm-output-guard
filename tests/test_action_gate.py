import re

from llm_output_guard import ActionDefinition, ActionGate, is_safe_token

SHUTDOWN = ActionDefinition(
    name="shutdown",
    pattern=re.compile(r"\[\[SHUTDOWN\]\]"),
    confirm_keywords=["shut down", "close", "exit"],
)
OPEN_APP = ActionDefinition(
    name="open_app",
    pattern=re.compile(r"\[\[OPEN:([a-zA-Z0-9_\- ]+)\]\]"),
    confirm_keywords=["open", "launch"],
)

gate = ActionGate([SHUTDOWN, OPEN_APP])

def test_marker_is_always_stripped_from_text():
    cleaned, matches = gate.process("Okay, bye.\n[[SHUTDOWN]]", "please shut down")
    assert "[[SHUTDOWN]]" not in cleaned
    assert len(matches) == 1

def test_confirmed_action_when_keyword_present():
    cleaned, matches = gate.process("One sec.\n[[OPEN:notepad]]", "open notepad")
    assert matches[0].confirmed is True
    assert matches[0].group == "notepad"

def test_unconfirmed_action_when_no_keyword_in_real_message():
    cleaned, matches = gate.process("Okay.\n[[SHUTDOWN]]", "tell me a joke")
    assert matches[0].confirmed is False
    assert "[[SHUTDOWN]]" not in cleaned

def test_no_marker_no_matches():
    cleaned, matches = gate.process("Just a normal response, no markers.", "hi")
    assert matches == []
    assert cleaned == "Just a normal response, no markers."

def test_is_safe_token():
    assert is_safe_token("notepad") is True
    assert is_safe_token("task manager") is True
    assert is_safe_token("notebook") is True
    assert is_safe_token("notepad && rm -rf /") is False
    assert is_safe_token("app; malicious") is False