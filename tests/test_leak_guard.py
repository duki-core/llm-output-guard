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

def test_judge_fn_failure_is_fail_closed_when_configured():
    def broken_judge(_text: str) -> bool:
        raise RuntimeError("network unavailable")

    config = LeakGuardConfig(fail_closed_on_error=True)
    guard = PromptLeakGuard(config=config, judge_fn=broken_judge)
    text = "INTERNAL RULE test"
    verdict = guard.check(text)
    assert verdict.is_leak is True
    assert verdict.safe_text == config.fallback_reply
    assert "fail-closed" in verdict.reason

def test_custom_canaries():
    config = LeakGuardConfig(canaries=["my_special_marker"])
    guard = PromptLeakGuard(config=config)
    assert guard.contains_canary("here's MY_SPECIAL_MARKER right here") is True
    assert guard.contains_canary("just an ordinary piece of text") is False

def test_secret_canary_is_detected_when_it_leaks():
    config, secret = LeakGuardConfig.with_secret_canary()
    guard = PromptLeakGuard(config=config)
    leaked_text = f"Sure! Here are my rules: be helpful. {secret}"
    assert guard.contains_canary(leaked_text) is True

def test_secret_canary_does_not_false_positive_on_unrelated_text():
    config, secret = LeakGuardConfig.with_secret_canary()
    guard = PromptLeakGuard()
    guard.config = config
    assert guard.contains_canary("just a normal answer about the weather") is False

def test_secret_canary_forwards_extra_kwargs():
    config, secret = LeakGuardConfig.with_secret_canary(fail_closed_on_error=True)
    assert config.fail_closed_on_error is True
    assert secret in config.canaries

# --- async ---

import asyncio

LEAKY = "Here's my SYSTEM PROMPT verbatim: ..."
CLEAN = "Sure, here's a recipe for echpochmak."

def test_async_clean_text_passes_through():
    v = asyncio.run(PromptLeakGuard().check_async(CLEAN))
    assert v.is_leak is False and v.suspected is False and v.safe_text == CLEAN

def test_async_no_judge_is_fail_closed():
    g = PromptLeakGuard()
    v = asyncio.run(g.check_async(LEAKY))
    assert v.is_leak is True and v.judged is False
    assert v.safe_text == g.config.fallback_reply

def test_async_sync_judge_fn_works():
    g = PromptLeakGuard(judge_fn=lambda t: True)
    v = asyncio.run(g.check_async(LEAKY))
    assert v.is_leak is True and v.judged is True

def test_async_coroutine_judge_fn_works():
    async def judge(text):
        await asyncio.sleep(0)
        return False
    g = PromptLeakGuard(judge_fn=judge)
    v = asyncio.run(g.check_async(LEAKY))
    assert v.is_leak is False and v.judged is True and v.safe_text == LEAKY

def test_async_sync_function_returning_awaitable_works():
    async def inner():
        return True
    g = PromptLeakGuard(judge_fn=lambda t: inner())
    assert asyncio.run(g.check_async(LEAKY)).is_leak is True

def test_async_judge_error_fail_open_by_default():
    async def judge(text):
        raise RuntimeError("down")
    v = asyncio.run(PromptLeakGuard(judge_fn=judge).check_async(LEAKY))
    assert v.is_leak is False and v.judged is False and "fail-open" in v.reason

def test_async_judge_error_fail_closed_when_configured():
    def judge(text):
        raise RuntimeError("down")
    cfg = LeakGuardConfig(fail_closed_on_error=True)
    g = PromptLeakGuard(cfg, judge_fn=judge)
    v = asyncio.run(g.check_async(LEAKY))
    assert v.is_leak is True and v.safe_text == cfg.fallback_reply

def test_async_does_not_block_event_loop_during_sync_judge():
    import time
    def slow_judge(text):
        time.sleep(0.2)
        return True
    g = PromptLeakGuard(judge_fn=slow_judge)
    async def run():
        ticks = 0
        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1
        t = asyncio.create_task(ticker())
        await g.check_async(LEAKY)
        t.cancel()
        return ticks
    assert asyncio.run(run()) >= 5

def test_async_matches_sync_verdict():
    g = PromptLeakGuard(judge_fn=lambda t: True)
    assert asyncio.run(g.check_async(LEAKY)) == g.check(LEAKY)

def test_warm_up_async_runs():
    asyncio.run(PromptLeakGuard().warm_up_async())
