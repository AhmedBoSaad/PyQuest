"""Tests for pyquest.services.commands."""
from pyquest.services.commands import parse_command


def test_check_answer():
    assert parse_command("check my answer") == ("check", {})


def test_run_code():
    assert parse_command("run the code") == ("run", {})


def test_show_hint():
    assert parse_command("show me a hint") == ("hint", {})


def test_next_lesson():
    assert parse_command("next lesson please") == ("next", {})


def test_go_back():
    assert parse_command("go back") == ("back", {})


def test_try_again():
    assert parse_command("try again") == ("retry", {})


def test_repeat():
    assert parse_command("repeat that") == ("repeat", {})


def test_quiz_pick_option_letter():
    assert parse_command("option B") == ("quiz_pick", {"index": 1})


def test_quiz_pick_ordinal():
    assert parse_command("pick the third one") == ("quiz_pick", {"index": 2})


def test_quiz_pick_number():
    assert parse_command("answer two") == ("quiz_pick", {"index": 1})


def test_quiz_pick_bare():
    assert parse_command("three") == ("quiz_pick", {"index": 2})


def test_yes_no():
    assert parse_command("yes please") == ("yes", {})
    assert parse_command("nope") == ("no", {})


def test_ask_tutor():
    assert parse_command("ask the tutor") == ("ask_tutor", {})
    assert parse_command("open chat") == ("ask_tutor", {})


def test_close_tutor():
    assert parse_command("close tutor") == ("close_tutor", {})


def test_explain_error():
    assert parse_command("explain the error") == ("explain_error", {})


def test_unknown_returns_none():
    assert parse_command("this is just chatter") is None


def test_empty_input():
    assert parse_command("") is None
    assert parse_command(None) is None  # type: ignore[arg-type]
