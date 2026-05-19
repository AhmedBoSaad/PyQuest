"""Tests for pyquest.core.ast_guard."""
from pyquest.core.ast_guard import check_code


# ---- allowed ----
def test_hello_world_allowed():
    assert check_code('print("hi")').ok


def test_input_allowed():
    assert check_code('name = input("?"); print(name)').ok


def test_loops_and_lists_allowed():
    assert check_code(
        'nums = [1, 2, 3]\nfor n in nums:\n    print(n * 2)'
    ).ok


def test_dunder_name_allowed():
    assert check_code('print(__name__)').ok


def test_syntax_errors_pass_through():
    # We let the real Python interpreter produce the friendly error.
    r = check_code("def broken(:")
    assert r.ok


# ---- blocked imports ----
def test_blocks_import_os():
    r = check_code("import os")
    assert not r.ok and "os" in r.reason


def test_blocks_from_subprocess():
    r = check_code("from subprocess import call")
    assert not r.ok


def test_blocks_socket():
    r = check_code("import socket")
    assert not r.ok


# ---- blocked builtins ----
def test_blocks_eval():
    r = check_code('eval("1+1")')
    assert not r.ok


def test_blocks_exec():
    r = check_code('exec("x=1")')
    assert not r.ok


def test_blocks_open():
    r = check_code('open("file.txt")')
    assert not r.ok


def test_blocks_getattr():
    r = check_code('getattr(int, "__abs__")')
    assert not r.ok


def test_blocks_breakpoint():
    r = check_code('breakpoint()')
    assert not r.ok


# ---- dunder bypass attempts ----
def test_blocks_bare_builtins():
    r = check_code('print(__builtins__)')
    assert not r.ok


def test_blocks_class_subclasses_chain():
    r = check_code('().__class__.__bases__[0].__subclasses__()')
    assert not r.ok


def test_blocks_globals_dunder():
    r = check_code('print(__globals__)')
    assert not r.ok


def test_blocks_loader():
    r = check_code('print(__loader__)')
    assert not r.ok
