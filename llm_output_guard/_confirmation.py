from __future__ import annotations

import re
from typing import List

def is_confirmed_by_keywords(user_message: str, keywords: List[str]) -> bool:
    text = (user_message or "").lower()
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text):
            return True
    return False
