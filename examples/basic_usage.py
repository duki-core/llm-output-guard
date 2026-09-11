"""
Example: wiring llm-output-guard into any OpenAI-compatible client
(LM Studio, OpenAI, a local server, etc.).

To run (needs a running LM Studio on localhost:1234 with any model loaded):
    pip install -r ../requirements.txt
    python basic_usage.py
"""
import re
import threading

from openai import OpenAI

from llm_output_guard import (
    ActionDefinition,
    ActionGate,
    LeakGuardConfig,
    PromptLeakGuard,
    is_safe_token,
)

client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")
MODEL_NAME = "your-model-name-here"


# --- 1. LLM judge: a plain function calling your client ---
def judge_fn(candidate_text: str) -> bool:
    config = LeakGuardConfig()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": config.judge_system_prompt},
            {"role": "user", "content": config.judge_user_prompt_template.format(text=candidate_text)},
        ],
        temperature=0,
        max_tokens=5,
    )
    verdict = response.choices[0].message.content.strip().lower()
    return verdict.startswith("yes")


leak_guard = PromptLeakGuard(judge_fn=judge_fn)
# Warm up the embedding model in the background — call this once at app startup.
threading.Thread(target=leak_guard.warm_up, daemon=True).start()


# --- 2. Action gate: model markers -> real actions, only with confirmation ---
action_gate = ActionGate([
    ActionDefinition(
        name="shutdown",
        pattern=re.compile(r"\[\[SHUTDOWN\]\]"),
        confirm_keywords=["shut down", "close", "exit", "quit"],
    ),
    ActionDefinition(
        name="open_app",
        pattern=re.compile(r"\[\[OPEN:([a-zA-Z0-9_\- ]+)\]\]"),
        confirm_keywords=["open", "launch", "start"],
    ),
])


def handle_model_reply(model_output: str, user_message: str) -> str:
    # Step 1: strip and parse action markers, checking for real confirmation
    cleaned_text, action_matches = action_gate.process(model_output, user_message)

    for match in action_matches:
        if not match.confirmed:
            print(f"[SECURITY] Action '{match.action.name}' blocked — "
                  f"no explicit confirmation in the user's message.")
            continue

        if match.action.name == "open_app":
            app_name = (match.group or "").strip()
            if not is_safe_token(app_name):
                print(f"[SECURITY] Rejected suspicious application name: {app_name!r}")
                continue
            print(f"-> launching application: {app_name}")
        elif match.action.name == "shutdown":
            print("-> performing shutdown")

    # Step 2: check the final text for system prompt leakage
    verdict = leak_guard.check(cleaned_text)
    if verdict.suspected:
        print(f"[SECURITY] {verdict.reason}")

    return verdict.safe_text


if __name__ == "__main__":
    example_user_message = "open notepad"
    example_model_output = "Sure, here you go.\n[[OPEN:notepad]]"
    print(handle_model_reply(example_model_output, example_user_message))