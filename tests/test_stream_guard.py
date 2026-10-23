import re

from llm_output_guard import ActionDefinition, StreamGuard, StreamResult

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

ACTIONS = [SHUTDOWN, OPEN_APP]


# ---- basic passthrough ----

def test_plain_text_passes_through_immediately():
    g = StreamGuard(ACTIONS, user_message="hello")
    r = g.feed("Hello, world!")
    assert r.text == "Hello, world!"
    assert r.matches == []


def test_empty_chunk():
    g = StreamGuard(ACTIONS, user_message="hello")
    r = g.feed("")
    assert r.text == ""
    assert r.matches == []


# ---- single-chunk marker ----

def test_marker_in_single_chunk_is_stripped():
    g = StreamGuard(ACTIONS, user_message="shut down please")
    r = g.feed("Bye! [[SHUTDOWN]]")
    assert "[[SHUTDOWN]]" not in r.text
    assert "Bye!" in r.text
    assert len(r.matches) == 1
    assert r.matches[0].confirmed is True


def test_unconfirmed_marker_still_stripped():
    g = StreamGuard(ACTIONS, user_message="tell me a joke")
    r = g.feed("Ok [[SHUTDOWN]] done")
    assert "[[SHUTDOWN]]" not in r.text
    assert len(r.matches) == 1
    assert r.matches[0].confirmed is False


# ---- marker split across chunks ----

def test_marker_split_across_two_chunks():
    g = StreamGuard(ACTIONS, user_message="open notepad")
    r1 = g.feed("Hello [[OPEN:")
    r2 = g.feed("notepad]]")
    combined = r1.text + r2.text
    assert "[[OPEN:notepad]]" not in combined
    assert "Hello" in combined
    all_matches = r1.matches + r2.matches
    assert len(all_matches) == 1
    assert all_matches[0].group == "notepad"
    assert all_matches[0].confirmed is True


def test_marker_split_into_many_small_chunks():
    """Token-by-token streaming: each character is a separate chunk."""
    g = StreamGuard(ACTIONS, user_message="shut down")
    text = "OK [[SHUTDOWN]] bye"
    results = [g.feed(ch) for ch in text]
    final = g.flush()
    combined = "".join(r.text for r in results) + final.text
    all_matches = [m for r in results for m in r.matches] + final.matches
    assert "[[SHUTDOWN]]" not in combined
    assert "OK" in combined
    assert "bye" in combined
    assert len(all_matches) == 1
    assert all_matches[0].confirmed is True


# ---- flush at end of stream ----

def test_flush_emits_remaining_text():
    g = StreamGuard(ACTIONS, user_message="hello")
    g.feed("Hello wor")
    r = g.flush()
    # 'wor' isn't a marker prefix, so it was already emitted by feed.
    # flush with empty buffer returns empty.
    assert isinstance(r, StreamResult)


def test_partial_marker_flushed_as_text():
    """Stream ends mid-marker — the partial content is just text."""
    g = StreamGuard(ACTIONS, user_message="open something")
    r1 = g.feed("Stuff [[OPEN:note")
    final = g.flush()
    combined = r1.text + final.text
    # The partial marker should be emitted as regular text.
    assert "[[OPEN:note" in combined
    assert "Stuff" in combined
    # No matches because the marker was never completed.
    assert r1.matches == []
    assert final.matches == []


# ---- false-alarm brackets ----

def test_single_bracket_not_buffered():
    """A single [ that isn't [[ should pass through."""
    g = StreamGuard(ACTIONS, user_message="hello")
    r = g.feed("array[0] = 5")
    assert r.text == "array[0] = 5"
    assert r.matches == []


def test_bracket_content_not_matching_any_pattern():
    """[[something_unknown]] should pass through if no pattern matches."""
    g = StreamGuard(ACTIONS, user_message="hello")
    r = g.feed("See [[UNKNOWN_THING]] here")
    assert "[[UNKNOWN_THING]]" in r.text
    assert r.matches == []


# ---- multiple markers ----

def test_two_markers_in_one_chunk():
    g = StreamGuard(ACTIONS, user_message="open notepad and shut down")
    r = g.feed("[[OPEN:notepad]] then [[SHUTDOWN]]")
    assert "[[OPEN:notepad]]" not in r.text
    assert "[[SHUTDOWN]]" not in r.text
    assert len(r.matches) == 2


def test_two_markers_across_chunks():
    g = StreamGuard(ACTIONS, user_message="exit")
    r1 = g.feed("first [[SHUT")
    r2 = g.feed("DOWN]] second [[SHUT")
    r3 = g.feed("DOWN]] end")
    combined = r1.text + r2.text + r3.text + g.flush().text
    all_matches = r1.matches + r2.matches + r3.matches
    assert combined.count("[[SHUTDOWN]]") == 0
    assert "first" in combined
    assert "second" in combined
    assert "end" in combined
    assert len(all_matches) == 2


# ---- max_marker_len ----

def test_buffer_flushed_on_max_len():
    """If the buffer grows past max_marker_len without ]], flush it."""
    g = StreamGuard(ACTIONS, user_message="hello", max_marker_len=20)
    r = g.feed("[[" + "A" * 30 + "]]")
    # The buffer overflows before ]] is found → flushed as text.
    combined = r.text + g.flush().text
    assert "[[" in combined
    assert r.matches == []


# ---- strict_tokens ----

def test_strict_tokens_blocks_unsafe_group():
    strict_open = ActionDefinition(
        name="open_app",
        pattern=re.compile(r"\[\[OPEN:([^\]]+)\]\]"),
        confirm_keywords=["open"],
        strict_tokens=True,
    )
    g = StreamGuard([strict_open], user_message="open it")
    r = g.feed("[[OPEN:notepad && rm -rf /]]")
    assert len(r.matches) == 1
    assert r.matches[0].confirmed is False  # unsafe token


def test_strict_tokens_allows_safe_group():
    strict_open = ActionDefinition(
        name="open_app",
        pattern=re.compile(r"\[\[OPEN:([a-zA-Z0-9_\- ]+)\]\]"),
        confirm_keywords=["open"],
        strict_tokens=True,
    )
    g = StreamGuard([strict_open], user_message="open notepad")
    r = g.feed("[[OPEN:notepad]]")
    assert r.matches[0].confirmed is True


# ---- reject_negated ----

def test_negated_keyword_not_confirmed():
    g = StreamGuard(ACTIONS, user_message="don't shut down")
    r = g.feed("[[SHUTDOWN]]")
    assert r.matches[0].confirmed is False


# ---- text around markers preserved ----

def test_surrounding_text_preserved():
    g = StreamGuard(ACTIONS, user_message="exit")
    r = g.feed("before [[SHUTDOWN]] after")
    assert "before" in r.text
    assert "after" in r.text
    assert "[[SHUTDOWN]]" not in r.text


# ---- combined feed + flush gives complete output ----

def test_full_stream_reconstructs_clean_text():
    """Simulate a realistic multi-chunk stream."""
    chunks = ["Sure, I'll ", "close ", "it now.\n[[SH", "UTDOWN", "]] Done!"]
    g = StreamGuard(ACTIONS, user_message="close the app")

    parts = []
    all_matches = []
    for c in chunks:
        r = g.feed(c)
        parts.append(r.text)
        all_matches.extend(r.matches)

    final = g.flush()
    parts.append(final.text)
    all_matches.extend(final.matches)

    full = "".join(parts)
    assert "[[SHUTDOWN]]" not in full
    assert "Sure, I'll close it now." in full
    assert "Done!" in full
    assert len(all_matches) == 1
    assert all_matches[0].confirmed is True


# ---- edge: marker_start at the very end of a chunk ----

def test_marker_start_at_chunk_boundary():
    g = StreamGuard(ACTIONS, user_message="exit")
    r1 = g.feed("text [[")
    r2 = g.feed("SHUTDOWN]]")
    combined = r1.text + r2.text
    assert "[[SHUTDOWN]]" not in combined
    assert "text" in combined
    all_matches = r1.matches + r2.matches
    assert len(all_matches) == 1


def test_single_bracket_at_chunk_end():
    """One [ at the end of a chunk — wait to see if next chunk has [."""
    g = StreamGuard(ACTIONS, user_message="exit")
    r1 = g.feed("text [")
    r2 = g.feed("just a bracket]")
    combined = r1.text + r2.text + g.flush().text
    assert "text" in combined
    assert "[just a bracket]" in combined
    assert r1.matches == []
    assert r2.matches == []
