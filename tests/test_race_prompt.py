import io
import os
import sys
import threading
import time

import pytest

import race_prompt
from providers.base import Provider
from race_prompt import prompt_for_race, read_line_until

RACES = [
    {"id": "100", "name": "Morning 5K", "date": "2026-08-07", "sport": "Running"},
    {"id": "200", "name": "Trail 10K", "date": "2026-08-07", "sport": "Running"},
]
CONFIG = {"api_id": "12345", "api_token": "secret-token-xyz"}


def _provider(list_races=None):
    return Provider(
        name="stub",
        required_secrets={"api_id": "WEBSCORER_API_ID", "api_token": "WEBSCORER_API_TOKEN"},
        requires_data_file=False,
        fetch=lambda c, s: None,
        normalize=lambda raw: raw,
        list_races=list_races or (lambda config, secrets: RACES),
    )


class Lines:
    """Stand-in reader: returns queued lines, then None (EOF)."""

    def __init__(self, *lines):
        self.lines = list(lines)
        self.calls = 0

    def __call__(self, stop, stdin, stdout):
        self.calls += 1
        if stop.is_set() or not self.lines:
            return None
        return self.lines.pop(0)


def _run(monkeypatch, reader, submit, stop=None, provider=None):
    monkeypatch.setattr(race_prompt, "read_line_until", reader)
    out = io.StringIO()
    stop = stop or threading.Event()
    prompt_for_race(provider or _provider(), CONFIG, submit, stop, io.StringIO(), out)
    return out.getvalue()


def test_cli_first_selection_persists_and_ends_prompt(monkeypatch):
    saved = {}

    def submit(race_id):
        saved["race_id"] = race_id
        return True

    reader = Lines("1", "2")
    out = _run(monkeypatch, reader, submit)
    assert saved == {"race_id": "100"}
    assert reader.calls == 1
    assert "1. [100] Morning 5K (2026-08-07) - Running" in out
    assert "Selected: Morning 5K" in out


def test_invalid_input_reprompts(monkeypatch):
    chosen = []
    reader = Lines("x", "9", "", "2")
    out = _run(monkeypatch, reader, lambda r: chosen.append(r) or True)
    assert chosen == ["200"]
    assert out.count("Please enter a number between 1 and 2") == 3


def test_rejected_submission_ends_prompt_quietly(monkeypatch):
    reader = Lines("1", "2")
    out = _run(monkeypatch, reader, lambda r: False)
    assert reader.calls == 1
    assert "already selected" in out
    assert "Selected:" not in out


def test_save_error_reports_and_reprompts(monkeypatch):
    from config import ConfigError
    attempts = []

    def submit(race_id):
        attempts.append(race_id)
        if len(attempts) == 1:
            raise ConfigError("disk full")
        return True

    out = _run(monkeypatch, Lines("1", "2"), submit)
    assert attempts == ["100", "200"]
    assert "Could not save race selection: disk full" in out


def test_eof_ends_prompt_without_repeating(monkeypatch):
    reader = Lines()
    out = _run(monkeypatch, reader, lambda r: pytest.fail("submitted"))
    assert reader.calls == 1
    assert "No terminal input" in out


def test_stop_before_list_returns_without_prompting(monkeypatch):
    stop = threading.Event()

    def list_races(config, secrets):
        stop.set()
        return RACES

    reader = Lines("1")
    out = _run(monkeypatch, reader, lambda r: pytest.fail("submitted"), stop, _provider(list_races))
    assert reader.calls == 0
    assert "Available races" not in out


def test_list_failure_is_credential_safe(monkeypatch):
    def list_races(config, secrets):
        raise RuntimeError("401 for url https://x/?apiid=12345&apipriv=secret-token-xyz")

    reader = Lines("1")
    out = _run(monkeypatch, reader, lambda r: pytest.fail("submitted"), provider=_provider(list_races))
    assert reader.calls == 0
    assert "secret-token-xyz" not in out and "12345" not in out
    assert "Failed to fetch race list" in out
    assert "admin page" in out


def test_empty_race_list_ends_prompt(monkeypatch):
    reader = Lines("1")
    out = _run(monkeypatch, reader, lambda r: pytest.fail("submitted"), provider=_provider(lambda c, s: []))
    assert reader.calls == 0
    assert "No posted races found" in out


def test_ui_first_selection_cancels_partial_cli_input(monkeypatch):
    """The real reader is cancelled mid-line; the partial digit is never submitted."""
    stop = threading.Event()
    keys = iter(["1"])
    typed = threading.Event()

    def kbhit():
        return not typed.is_set()

    def getwch():
        typed.set()
        return next(keys)

    monkeypatch.setattr(race_prompt, "_use_msvcrt", lambda stdin: True)
    monkeypatch.setattr(race_prompt, "_msvcrt_keys", lambda: (kbhit, getwch))
    submitted = []
    out = io.StringIO()
    worker = threading.Thread(
        target=prompt_for_race,
        args=(_provider(), CONFIG, lambda r: submitted.append(r) or True, stop, io.StringIO(), out),
    )
    worker.start()
    assert typed.wait(2)
    stop.set()  # the admin UI selected a race
    worker.join(2)
    assert not worker.is_alive()
    assert submitted == []
    assert "closed" in out.getvalue()


# --- read_line_until: Windows console branch ---------------------------------

def _windows_reader(monkeypatch, keys):
    keys = list(keys)
    monkeypatch.setattr(race_prompt, "_use_msvcrt", lambda stdin: True)
    monkeypatch.setattr(race_prompt, "_msvcrt_keys", lambda: (lambda: bool(keys), lambda: keys.pop(0)))
    return keys


def test_windows_reads_line_with_backspace(monkeypatch):
    _windows_reader(monkeypatch, ["1", "2", "\x08", "\x08", "\x08", "2", "\r"])
    out = io.StringIO()
    assert read_line_until(threading.Event(), io.StringIO(), out) == "2"
    assert out.getvalue().endswith("2\n")


def test_windows_skips_special_keys(monkeypatch):
    _windows_reader(monkeypatch, ["\xe0", "H", "1", "\r"])
    assert read_line_until(threading.Event(), io.StringIO(), io.StringIO()) == "1"


def test_windows_ctrl_z_is_eof(monkeypatch):
    _windows_reader(monkeypatch, ["\x1a"])
    assert read_line_until(threading.Event(), io.StringIO(), io.StringIO()) is None


def test_windows_ctrl_c_raises_keyboard_interrupt(monkeypatch):
    _windows_reader(monkeypatch, ["\x03"])
    with pytest.raises(KeyboardInterrupt):
        read_line_until(threading.Event(), io.StringIO(), io.StringIO())


def test_windows_cancellation_discards_partial_input(monkeypatch):
    keys = _windows_reader(monkeypatch, ["1"])
    stop = threading.Event()
    result = []
    t = threading.Thread(target=lambda: result.append(read_line_until(stop, io.StringIO(), io.StringIO())))
    t.start()
    deadline = time.time() + 2
    while keys and time.time() < deadline:
        time.sleep(0.01)
    stop.set()
    t.join(2)
    assert result == [None]


def test_prompt_ctrl_c_interrupts_main(monkeypatch):
    calls = []
    monkeypatch.setattr(race_prompt, "_interrupt_main", lambda: calls.append(True))

    def reader(stop, stdin, stdout):
        raise KeyboardInterrupt

    _run(monkeypatch, reader, lambda r: pytest.fail("submitted"))
    assert calls == [True]


# --- read_line_until: POSIX / generic stream branches -------------------------

def test_non_console_stream_reads_line_and_eof(monkeypatch):
    monkeypatch.setattr(race_prompt, "_use_msvcrt", lambda stdin: False)
    stdin = io.StringIO("2\n")
    assert read_line_until(threading.Event(), stdin, io.StringIO()) == "2"
    assert read_line_until(threading.Event(), stdin, io.StringIO()) is None


def test_select_branch_waits_until_ready_and_cancels(monkeypatch):
    monkeypatch.setattr(race_prompt, "_use_msvcrt", lambda stdin: False)
    stop = threading.Event()
    polls = []

    def fake_select(r, w, x, timeout):
        polls.append(timeout)
        if len(polls) == 3:
            stop.set()
        return [], [], []

    flushed = []
    monkeypatch.setattr(race_prompt, "_select", fake_select)
    monkeypatch.setattr(race_prompt, "_discard_pending", lambda stdin: flushed.append(True))

    class Tty(io.StringIO):
        def isatty(self):
            return True

        def fileno(self):
            return 0

    assert read_line_until(stop, Tty("1\n"), io.StringIO()) is None
    assert all(0 < t <= 0.2 for t in polls)
    assert flushed == [True]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pseudo-terminal")
def test_posix_pty_reads_line_and_cancels():
    import pty

    master, slave = pty.openpty()
    try:
        stdin = os.fdopen(slave, "r", closefd=False)
        os.write(master, b"2\n")
        assert read_line_until(threading.Event(), stdin, io.StringIO()) == "2"

        stop = threading.Event()
        result = []
        t = threading.Thread(target=lambda: result.append(read_line_until(stop, stdin, io.StringIO())))
        t.start()
        os.write(master, b"1")  # partial line, no Enter
        time.sleep(0.2)
        stop.set()
        t.join(2)
        assert result == [None]
        assert not t.is_alive()
    finally:
        os.close(master)
        os.close(slave)
