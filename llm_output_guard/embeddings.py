from __future__ import annotations

import threading
from typing import Optional

_lock = threading.Lock()
_cache: dict[str, object] = {}

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

def get_embedder(model_name: str) -> Optional["SentenceTransformer"]:
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None
    with _lock:
        if model_name not in _cache:
            _cache[model_name] = SentenceTransformer(model_name, device="cpu")
    return _cache[model_name]
