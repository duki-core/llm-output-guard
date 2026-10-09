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


# --- default_deny ---

def test_default_deny_false_ignores_unregistered():
    g = ToolCallGuard([DELETE_FILE], default_deny=False)
    assert g.process([{"name": "get_weather", "arguments": {}}], "weather") == []

def test_default_deny_is_off_by_default():
    assert ToolCallGuard([DELETE_FILE]).default_deny is False

def test_default_deny_blocks_unregistered():
    g = ToolCallGuard([DELETE_FILE], default_deny=True)
    matches = g.process([{"name": "get_weather", "arguments": {"city": "X"}}], "weather")
    assert len(matches) == 1
    assert matches[0].confirmed is False
    assert matches[0].definition is None
    assert matches[0].call_name == "get_weather"
    assert matches[0].arguments == {"city": "X"}
    assert "default_deny" in matches[0].reason

def test_default_deny_blocks_call_without_name():
    g = ToolCallGuard([DELETE_FILE], default_deny=True)
    matches = g.process([{"arguments": {}}], "delete it")
    assert len(matches) == 1 and matches[0].confirmed is False

def test_default_deny_does_not_affect_registered_calls():
    g = ToolCallGuard([DELETE_FILE], default_deny=True)
    matches = g.process(
        [{"name": "delete_file", "arguments": {}}, {"name": "other", "arguments": {}}],
        "delete it",
    )
    assert [m.confirmed for m in matches] == [True, False]


# --- args_in_message ---

DELETE_BOUND = ToolCallDefinition(
    name="delete_file",
    confirm_keywords=["delete", "remove"],
    args_in_message=["path"],
)
bound_guard = ToolCallGuard([DELETE_BOUND])

def test_bound_arg_present_in_message_confirms():
    m = bound_guard.process(
        [{"name": "delete_file", "arguments": {"path": "/tmp/x.txt"}}],
        "delete /tmp/x.txt",
    )
    assert m[0].confirmed is True

def test_bound_arg_not_in_message_blocks():
    m = bound_guard.process(
        [{"name": "delete_file", "arguments": {"path": "/etc/passwd"}}],
        "delete my temp file",
    )
    assert m[0].confirmed is False
    assert "not found in user message" in m[0].reason
    assert "'path'" in m[0].reason

def test_bound_arg_absent_from_call_is_skipped():
    m = bound_guard.process(
        [{"name": "delete_file", "arguments": {}}],
        "delete it",
    )
    assert m[0].confirmed is True

def test_bound_arg_empty_string_blocks():
    m = bound_guard.process(
        [{"name": "delete_file", "arguments": {"path": ""}}],
        "delete it",
    )
    assert m[0].confirmed is False

def test_bound_arg_is_checked_before_keywords():
    m = bound_guard.process(
        [{"name": "delete_file", "arguments": {"path": "/etc/passwd"}}],
        "tell me a joke",
    )
    assert "not found in user message" in m[0].reason

def test_bound_arg_partial_name_does_not_match():
    m = bound_guard.process(
        [{"name": "delete_file", "arguments": {"path": "bob"}}],
        "delete bobby",
    )
    assert m[0].confirmed is False

def test_unbound_definition_unaffected():
    m = guard.process(
        [{"name": "delete_file", "arguments": {"path": "/etc/passwd"}}],
        "delete my temp file",
    )
    assert m[0].confirmed is True


# --- reject_negated ---

def test_negated_keyword_blocks_by_default():
    m = guard.process(
        [{"name": "delete_file", "arguments": {}}],
        "don't delete the file",
    )
    assert m[0].confirmed is False
    assert "no confirmation keyword" in m[0].reason

def test_negated_keyword_allowed_when_disabled():
    defn = ToolCallDefinition(
        name="delete_file", confirm_keywords=["delete"], reject_negated=False,
    )
    m = ToolCallGuard([defn]).process(
        [{"name": "delete_file", "arguments": {}}], "don't delete the file",
    )
    assert m[0].confirmed is True

def test_russian_negation_blocks_tool_call():
    defn = ToolCallDefinition(name="delete_file", confirm_keywords=["удали"])
    m = ToolCallGuard([defn]).process(
        [{"name": "delete_file", "arguments": {}}], "не удали файл",
    )
    assert m[0].confirmed is False
