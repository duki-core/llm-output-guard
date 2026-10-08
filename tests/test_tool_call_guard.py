from llm_output_guard import ToolCallDefinition, ToolCallGuard, ToolCallMatch


SEND_EMAIL = ToolCallDefinition(
    name="send_email",
    confirm_keywords=["send", "email", "mail"],
    required_args=["to", "body"],
    arg_validators={"to": lambda v: isinstance(v, str) and "@" in v},
)

DELETE_FILE = ToolCallDefinition(
    name="delete_file",
    confirm_keywords=["delete", "remove"],
)

SHUTDOWN = ToolCallDefinition(
    name="shutdown_server",
    confirm_keywords=["shut down", "shutdown"],
)

guard = ToolCallGuard([SEND_EMAIL, DELETE_FILE, SHUTDOWN])

def test_confirmed_when_keyword_present():
    matches = guard.process(
        [{"name": "send_email", "arguments": {"to": "a@b.com", "body": "hi"}}],
        "send an email to alice",
    )
    assert len(matches) == 1
    assert matches[0].confirmed is True
    assert matches[0].reason == ""

def test_unconfirmed_when_no_keyword():
    matches = guard.process(
        [{"name": "delete_file", "arguments": {"path": "/tmp/x"}}],
        "tell me a joke",
    )
    assert len(matches) == 1
    assert matches[0].confirmed is False
    assert "no confirmation keyword" in matches[0].reason

def test_unregistered_tool_call_is_ignored():
    matches = guard.process(
        [{"name": "unknown_function", "arguments": {}}],
        "do something",
    )
    assert matches == []

def test_no_tool_calls_returns_empty():
    matches = guard.process([], "delete everything")
    assert matches == []

def test_missing_required_arg_blocks_even_with_keyword():
    matches = guard.process(
        [{"name": "send_email", "arguments": {"to": "a@b.com"}}],
        "send an email",
    )
    assert len(matches) == 1
    assert matches[0].confirmed is False
    assert "missing required argument" in matches[0].reason
    assert "body" in matches[0].reason

def test_all_required_args_present_passes():
    matches = guard.process(
        [{"name": "send_email", "arguments": {"to": "a@b.com", "body": "hi", "cc": "x@y.com"}}],
        "send email",
    )
    assert matches[0].confirmed is True

def test_arg_validator_failure_blocks_confirmation():
    matches = guard.process(
        [{"name": "send_email", "arguments": {"to": "not-an-email", "body": "hi"}}],
        "send an email",
    )
    assert len(matches) == 1
    assert matches[0].confirmed is False
    assert "failed validation" in matches[0].reason
    assert "'to'" in matches[0].reason

def test_arg_validator_not_invoked_for_absent_optional_arg():
    defn = ToolCallDefinition(
        name="my_fn",
        confirm_keywords=["go"],
        arg_validators={"optional_arg": lambda v: False},
    )
    g = ToolCallGuard([defn])
    matches = g.process(
        [{"name": "my_fn", "arguments": {}}],
        "go",
    )
    assert matches[0].confirmed is True

def test_word_boundary_prevents_false_confirmation():
    matches = guard.process(
        [{"name": "delete_file", "arguments": {}}],
        "I am quite delighted today",
    )
    assert matches[0].confirmed is False

def test_multi_word_keyword_confirmed():
    matches = guard.process(
        [{"name": "shutdown_server", "arguments": {}}],
        "please shut down the server",
    )
    assert matches[0].confirmed is True

def test_multiple_tool_calls_processed_independently():
    matches = guard.process(
        [
            {"name": "send_email", "arguments": {"to": "a@b.com", "body": "hi"}},
            {"name": "delete_file", "arguments": {"path": "/tmp/x"}},
        ],
        "send an email",
    )
    assert len(matches) == 2
    assert matches[0].confirmed is True
    assert matches[1].confirmed is False

def test_malformed_arguments_not_a_dict():
    matches = guard.process(
        [{"name": "delete_file", "arguments": "not a dict"}],
        "delete it",
    )
    assert len(matches) == 1
    assert matches[0].confirmed is True
    assert matches[0].arguments == {}

def test_missing_arguments_key_treated_as_empty():
    matches = guard.process(
        [{"name": "delete_file"}],
        "delete it",
    )
    assert matches[0].confirmed is True
    assert matches[0].arguments == {}

def test_arguments_preserved_in_match():
    matches = guard.process(
        [{"name": "send_email", "arguments": {"to": "a@b.com", "body": "hello world"}}],
        "send email",
    )
    assert matches[0].call_name == "send_email"
    assert matches[0].arguments == {"to": "a@b.com", "body": "hello world"}
    assert matches[0].definition is SEND_EMAIL

def test_empty_user_message_never_confirms():
    matches = guard.process(
        [{"name": "delete_file", "arguments": {}}],
        "",
    )
    assert matches[0].confirmed is False

def test_none_user_message_never_confirms():
    matches = guard.process(
        [{"name": "delete_file", "arguments": {}}],
        None,
    )
    assert matches[0].confirmed is False

def test_required_args_checked_before_keywords():
    matches = guard.process(
        [{"name": "send_email", "arguments": {}}],
        "send email now",
    )
    assert matches[0].confirmed is False
    assert "missing required argument" in matches[0].reason

def test_validator_checked_before_keywords():
    matches = guard.process(
        [{"name": "send_email", "arguments": {"to": "bad", "body": "hi"}}],
        "send email",
    )
    assert matches[0].confirmed is False
    assert "failed validation" in matches[0].reason
