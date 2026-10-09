"""
Ready-made validators for `ToolCallDefinition.arg_validators`.

Each function is a factory that returns a `Callable[[Any], bool]`:

    ToolCallDefinition(
        name="read_file",
        confirm_keywords=["read", "open"],
        required_args=["path"],
        arg_validators={"path": is_safe_path("/srv/app/files")},
        args_in_message=["path"],
    )

Validators never raise: anything unexpected (wrong type, malformed value)
is simply "not valid" (False).
"""
from __future__ import annotations

import os
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import urlparse


def is_safe_path(base_dir: str, allow_base: bool = False) -> Callable[[Any], bool]:
    """
    The path (relative to `base_dir`) must stay inside `base_dir` after
    resolving `..` and symlinks. Absolute paths are resolved on their own, so
    they are only valid if they happen to point inside `base_dir`.

    allow_base: whether the path may resolve to `base_dir` itself
    (e.g. "." or ""). Default False — you rarely want a tool to operate on
    the root directory itself (think `delete_file(path=".")`).

    Note: this checks the filesystem state at validation time. If another
    process can create symlinks inside `base_dir` between the check and the
    use, you still need OS-level isolation.
    """
    base = os.path.realpath(base_dir)

    def validator(value: Any) -> bool:
        if not isinstance(value, str) or not value or "\x00" in value:
            return False
        try:
            resolved = os.path.realpath(os.path.join(base, value))
            if os.path.commonpath([base, resolved]) != base:
                return False
        except (ValueError, OSError):  # e.g. different drives on Windows
            return False
        return allow_base or resolved != base

    return validator


def is_allowed_domain(
    domains: Iterable[str],
    allow_subdomains: bool = True,
    schemes: Sequence[str] = ("https",),
) -> Callable[[Any], bool]:
    """
    A URL must use one of `schemes` and point to one of `domains`.

    - `https://good.com@evil.com/` is judged by its real host (evil.com) and
      URLs carrying credentials (user:pass@) are rejected outright.
    - allow_subdomains=True: `docs.good.com` matches `good.com`, but
      `notgood.com` and `good.com.evil.com` do not.
    - Default schemes is https only; pass ("http", "https") to allow both.
    - Hosts are compared in lowercase as written; IDN/punycode forms are not
      converted — list the form your URLs actually use.
    """
    allowed = {d.lower().strip(".") for d in domains}
    allowed_schemes = {s.lower() for s in schemes}

    def validator(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            parsed = urlparse(value.strip())
            host = (parsed.hostname or "").lower().strip(".")
            _ = parsed.port  # raises ValueError on a malformed port
        except ValueError:
            return False
        if parsed.scheme.lower() not in allowed_schemes or not host:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if host in allowed:
            return True
        return allow_subdomains and any(host.endswith("." + d) for d in allowed)

    return validator


def max_len(limit: int) -> Callable[[Any], bool]:
    """A string no longer than `limit` characters."""
    def validator(value: Any) -> bool:
        return isinstance(value, str) and len(value) <= limit
    return validator


def one_of(*allowed: Any) -> Callable[[Any], bool]:
    """The value must be exactly one of `allowed` (compared with ==)."""
    options = list(allowed)
    def validator(value: Any) -> bool:
        return any(value == o and type(value) is type(o) for o in options)
    return validator
