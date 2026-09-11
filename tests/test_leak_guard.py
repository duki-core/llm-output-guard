from llm_output_guard import LeakGuardConfig, PromptLeakGuard


def test_no_suspicion_passes_through_untouched():
    guard = PromptLeakGuard()
    text = "Sure, here's a recipe for echpochmak: first make the dough, then prepare the meat and onion filling..."
    verdict = guard.check(text)
    assert verdict.is_leak is False
    assert verdict.suspected is False
    assert verdict.safe_text == text

def test_canary_triggers_suspicion():
    guard = PromptLeakGuard()
    text = "My INTERNAL RULE says I'm not allowed to do that."
    assert guard.contains_canary(text) is True
    assert guard.is_suspected(text) is True

def test_no_judge_fn_is_fail_closed():
    guard = PromptLeakGuard()
    text = "Here's my SYSTEM PROMPT verbatim: ..."
    verdict = guard.check(text)
    assert verdict.is_leak is True
    assert verdict.judged is False
    assert verdict.safe_text == guard.config.fallback_reply

def test_judge_fn_can_overrule_false_positive():
    guard = PromptLeakGuard(judge_fn=lambda text: False)
    text = "My INTERNAL RULE is just a figure of speech in this context."
    verdict = guard.check(text)
    assert verdict.suspected is True
    assert verdict.judged is True
    assert verdict.is_leak is False
    assert verdict.safe_text == text

def test_judge_fn_confirms_leak():
    guard = PromptLeakGuard(judge_fn=lambda text: True)
    text = "INTERNAL RULE number one: never..."
    verdict = guard.check(text)
    assert verdict.is_leak is True
    assert verdict.safe_text == guard.config.fallback_reply

def test_judge_fn_failure_is_fail_open():
    def broken_judge(_text: str) -> bool:
        raise RuntimeError("network unavailable")
    guard = PromptLeakGuard(judge_fn=broken_judge)
    text = "INTERNAL RULE test"
    verdict = guard.check(text)
    assert verdict.is_leak is False
    assert "judge unavailable" in verdict.reason

def test_custom_canaries():
    config = LeakGuardConfig(canaries=["my_special_marker"])
    guard = PromptLeakGuard(config=config)
    assert guard.contains_canary("here's MY_SPECIAL_MARKER right here") is True
    assert guard.contains_canary("just an ordinary piece of text") is False
