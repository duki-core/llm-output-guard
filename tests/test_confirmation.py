from llm_output_guard._confirmation import is_confirmed_by_keywords, value_appears_in_text


def neg(msg, kws=("delete", "удали")):
    return is_confirmed_by_keywords(msg, list(kws), reject_negated=True)


# --- negation ---

def test_plain_keyword_confirms():
    assert neg("please delete the file") is True

def test_dont_blocks():
    assert neg("don't delete the file") is False

def test_do_not_blocks():
    assert neg("please do not delete anything") is False

def test_curly_apostrophe_blocks():
    assert neg("don’t delete it") is False

def test_never_blocks():
    assert neg("never delete my files") is False

def test_russian_negation_blocks():
    assert neg("не удали файл") is False

def test_russian_without_negation_confirms():
    assert neg("удали файл") is True

def test_negation_in_other_clause_does_not_block():
    assert neg("I don't know. Delete the file") is True
    assert neg("no problem, delete it") is True

def test_but_resets_negation():
    assert neg("don't open it but delete the file") is True

def test_russian_a_resets_negation():
    assert neg("не копируй а удали") is True

def test_negation_far_away_does_not_block():
    assert neg("not that I mind at all really, delete it") is True

def test_one_unnegated_occurrence_is_enough():
    assert neg("don't delete a. delete b") is True

def test_negation_ignored_when_flag_off():
    assert is_confirmed_by_keywords("don't delete it", ["delete"]) is True

def test_multi_word_keyword_negated():
    assert neg("do not shut down the server", ["shut down"]) is False

def test_word_boundary_still_applies():
    assert neg("I am quite delighted", ["delete"]) is False


# --- value_appears_in_text ---

def test_value_found():
    assert value_appears_in_text("a@b.com", "send it to a@b.com please") is True

def test_value_case_insensitive():
    assert value_appears_in_text("Notes.TXT", "delete notes.txt") is True

def test_value_not_found():
    assert value_appears_in_text("/etc/passwd", "delete my temp file") is False

def test_value_word_boundary():
    assert value_appears_in_text("bob", "email bobby") is False
    assert value_appears_in_text("bob", "email bob.") is True

def test_value_path_with_trailing_punctuation():
    assert value_appears_in_text("/tmp/x", "delete /tmp/x.") is True

def test_value_whitespace_normalized():
    assert value_appears_in_text("my  file.txt", "delete my file.txt") is True

def test_value_list_requires_all():
    assert value_appears_in_text(["a", "b"], "a and b") is True
    assert value_appears_in_text(["a", "c"], "a and b") is False

def test_value_empty_none_dict_never_match():
    assert value_appears_in_text("", "anything") is False
    assert value_appears_in_text(None, "anything") is False
    assert value_appears_in_text({"a": 1}, "a 1") is False
    assert value_appears_in_text([], "anything") is False

def test_value_number():
    assert value_appears_in_text(42, "delete item 42") is True

def test_value_none_message():
    assert value_appears_in_text("x", None) is False
