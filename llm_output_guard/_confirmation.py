from __future__ import annotations

import re
import unicodedata
from typing import Any, List

_NEGATORS = frozenset({
    # English
    "not", "no", "never", "without", "cannot", "dont", "don't", "doesnt",
    "doesn't", "didnt", "didn't", "cant", "can't", "wont", "won't",
    "shouldnt", "shouldn't", "mustnt", "mustn't", "neither", "nor",
    # Russian
    "не", "ни", "нет", "нельзя", "без", "никогда", "никак",
})

# Words that start a new clause: negation before them doesn't carry over
# ("don't open it but delete the file").
_CLAUSE_WORDS = frozenset({"but", "however", "instead", "но", "однако", "зато", "а"})

# Punctuation that ends a clause.
_CLAUSE_BREAK = re.compile(r"[.,;:!?\n\r()\[\]—–]")

_TOKEN = re.compile(r"[\w']+", re.UNICODE)

# How many words before a keyword are checked for a negator.
_NEGATION_WINDOW = 3

def normalize_text(value: Any) -> str:
    """NFKC + casefold + collapsed whitespace. Used for comparing strings."""
    text = unicodedata.normalize("NFKC", str(value)).replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().casefold()

def _is_negated(text: str, match_start: int) -> bool:
    """True if a negator sits right before `match_start` within the same clause."""
    before = text[:match_start]
    parts = _CLAUSE_BREAK.split(before)
    clause = parts[-1] if parts else ""
    tokens = _TOKEN.findall(clause)
    # A clause word (but/но) resets negation: only look at tokens after it.
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i] in _CLAUSE_WORDS:
            tokens = tokens[i + 1:]
            break
    return any(t in _NEGATORS for t in tokens[-_NEGATION_WINDOW:])

def is_confirmed_by_keywords(
    user_message: str,
    keywords: List[str],
    reject_negated: bool = False,
) -> bool:
    """
    True if any keyword appears in the message as a whole word.

    reject_negated: if True, an occurrence that is negated within the same
    clause ("don't delete", "не удаляй") does not count. A keyword confirms
    only if at least one of its occurrences is NOT negated.
    """
    text = (user_message or "").lower().replace("’", "'")
    for kw in keywords:
        for m in re.finditer(r"\b" + re.escape(kw.lower()) + r"\b", text):
            if not reject_negated or not _is_negated(text, m.start()):
                return True
    return False

def value_appears_in_text(value: Any, user_message: str) -> bool:
    if isinstance(value, (list, tuple)):
        return bool(value) and all(value_appears_in_text(v, user_message) for v in value)
    if isinstance(value, dict) or value is None:
        return False
    needle = normalize_text(value)
    if not needle:
        return False
    haystack = normalize_text(user_message or "")
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None