import os
import sys

import pytest

from llm_output_guard import (
    ToolCallDefinition, ToolCallGuard,
    is_allowed_domain, is_safe_path, max_len, one_of,
)


# --- is_safe_path ---

@pytest.fixture
def base(tmp_path):
    root = tmp_path / "files"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("x")
    return str(root)

def test_path_inside_base_ok(base):
    v = is_safe_path(base)
    assert v("a.txt") and v("sub/b.txt") and v("sub/../a.txt")

def test_path_traversal_blocked(base):
    v = is_safe_path(base)
    assert not v("../secret.txt")
    assert not v("sub/../../secret.txt")
    assert not v("../files_evil/x")      # shares the prefix string, not the dir

def test_absolute_path_outside_blocked(base):
    v = is_safe_path(base)
    assert not v("/etc/passwd")

def test_absolute_path_inside_ok(base):
    assert is_safe_path(base)(os.path.join(base, "a.txt"))

def test_base_itself_blocked_by_default(base):
    assert not is_safe_path(base)(".")
    assert not is_safe_path(base)("sub/..")
    assert is_safe_path(base, allow_base=True)(".")

def test_empty_nonstr_and_nullbyte_blocked(base):
    v = is_safe_path(base)
    assert not v("") and not v(None) and not v(123) and not v(["a.txt"])
    assert not v("a.txt\x00.png")

@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlink_escape_blocked(base, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, os.path.join(base, "link"))
    assert not is_safe_path(base)("link/secret.txt")


# --- is_allowed_domain ---

def test_domain_exact_and_subdomain():
    v = is_allowed_domain(["example.com"])
    assert v("https://example.com/x?y=1")
    assert v("https://docs.example.com/")
    assert v("https://EXAMPLE.com:8443/path")

def test_domain_lookalikes_blocked():
    v = is_allowed_domain(["example.com"])
    assert not v("https://notexample.com")
    assert not v("https://example.com.evil.com")
    assert not v("https://evil.com/example.com")
    assert not v("https://evil.com?u=example.com")

def test_domain_userinfo_trick_blocked():
    v = is_allowed_domain(["example.com"])
    assert not v("https://example.com@evil.com/")
    assert not v("https://user:pw@example.com/")

def test_domain_no_subdomains_option():
    v = is_allowed_domain(["example.com"], allow_subdomains=False)
    assert v("https://example.com") and not v("https://docs.example.com")

def test_domain_scheme_rules():
    assert not is_allowed_domain(["example.com"])("http://example.com")
    assert is_allowed_domain(["example.com"], schemes=("http", "https"))("http://example.com")
    assert not is_allowed_domain(["example.com"])("ftp://example.com")
    assert not is_allowed_domain(["example.com"])("javascript:alert(1)")

def test_domain_garbage_never_raises():
    v = is_allowed_domain(["example.com"])
    for bad in [None, 5, "", "not a url", "https://", "https://example.com:notaport", "//example.com"]:
        assert v(bad) is False


# --- max_len / one_of ---

def test_max_len():
    assert max_len(3)("abc") and not max_len(3)("abcd") and not max_len(3)(None)

def test_one_of():
    v = one_of("r", "w")
    assert v("r") and not v("x")
    assert not one_of(1)(True)       # bool is not int here
    assert not one_of(1)("1")


# --- integration with ToolCallGuard ---

def test_validator_plugs_into_guard(base):
    g = ToolCallGuard([ToolCallDefinition(
        name="read_file",
        confirm_keywords=["read", "open"],
        arg_validators={"path": is_safe_path(base)},
        args_in_message=["path"],
    )])
    ok = g.process([{"name": "read_file", "arguments": {"path": "a.txt"}}], "read a.txt")
    assert ok[0].confirmed is True
    bad = g.process([{"name": "read_file", "arguments": {"path": "../x"}}], "read ../x")
    assert bad[0].confirmed is False and "failed validation" in bad[0].reason
