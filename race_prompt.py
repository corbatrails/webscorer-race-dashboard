"""Terminal race prompt that can be cancelled when a race is chosen elsewhere.

No Flask imports: the app hands in a ``submit`` callback and a ``stop`` event.
"""
import _thread
import select
import sys

_POLL_SECONDS = 0.1
_NO_RACE_HINT = "choose a race in the admin page or set race_id in config.yaml."


def _use_msvcrt(stdin):
    return sys.platform == "win32" and _isatty(stdin)


def _msvcrt_keys():
    import msvcrt
    return msvcrt.kbhit, msvcrt.getwch


def _select(rlist, wlist, xlist, timeout):
    return select.select(rlist, wlist, xlist, timeout)


def _discard_pending(stdin):
    """Drop a partly typed line so it can't leak into later terminal input."""
    try:
        import termios
        termios.tcflush(stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


def _interrupt_main():
    _thread.interrupt_main()


def _isatty(stream):
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _write(stdout, text):
    stdout.write(text)
    stdout.flush()


def _read_console_line(stop, stdout):
    kbhit, getwch = _msvcrt_keys()
    buf = []
    while not stop.is_set():
        if not kbhit():
            stop.wait(_POLL_SECONDS)
            continue
        ch = getwch()
        if ch in ("\r", "\n"):
            _write(stdout, "\n")
            return "".join(buf)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x1a":
            return None
        if ch in ("\x00", "\xe0"):
            getwch()  # second half of an arrow/function key
        elif ch == "\x08":
            if buf:
                buf.pop()
                _write(stdout, "\b \b")
        elif ch.isprintable():
            buf.append(ch)
            _write(stdout, ch)
    return None


def read_line_until(stop, stdin, stdout):
    """Read one line, or return None on EOF or once ``stop`` is set.

    Never leaves a thread blocked in ``input()``: the Windows console is polled
    with msvcrt and POSIX terminals with a short ``select`` wait.
    """
    if stop.is_set():
        return None
    if _use_msvcrt(stdin):
        return _read_console_line(stop, stdout)
    if not _isatty(stdin):
        line = stdin.readline()
        return None if line == "" else line.rstrip("\r\n")
    while not stop.is_set():
        ready, _, _ = _select([stdin], [], [], _POLL_SECONDS)
        if ready:
            line = stdin.readline()
            return None if line == "" else line.rstrip("\r\n")
    _discard_pending(stdin)
    return None


def _redact(message, secrets):
    for value in secrets.values():
        if value:
            message = message.replace(str(value), "***")
    return message


def prompt_for_race(provider, config, submit, stop, stdin, stdout):
    """List races and submit the chosen race ID until a selection is accepted.

    ``submit(race_id)`` returns False when a race was already selected elsewhere.
    Ends quietly when ``stop`` is set, on EOF, or when the race list can't load.
    """
    try:
        _prompt(provider, config, submit, stop, stdin, stdout)
    except KeyboardInterrupt:
        _interrupt_main()


def _prompt(provider, config, submit, stop, stdin, stdout):
    secrets = {key: config.get(key) for key in provider.required_secrets}
    try:
        races = provider.list_races(config, secrets)
    except Exception as e:
        _write(stdout, f"\nERROR: Failed to fetch race list: {_redact(str(e), secrets)}\n")
        _write(stdout, f"Terminal race selection is unavailable; {_NO_RACE_HINT}\n")
        return
    if stop.is_set():
        return
    if not races:
        _write(stdout, f"No posted races found; {_NO_RACE_HINT}\n")
        return

    _write(stdout, "\nAvailable races:\n")
    for i, race in enumerate(races, 1):
        _write(stdout, f"  {i}. [{race['id']}] {race['name']} ({race['date']}) - {race['sport']}\n")

    while True:
        _write(stdout, f"\nSelect race [1-{len(races)}]: ")
        line = read_line_until(stop, stdin, stdout)
        if stop.is_set():
            _write(stdout, "\nTerminal race prompt closed: a race was selected.\n")
            return
        if line is None:
            _write(stdout, f"\nNo terminal input; {_NO_RACE_HINT}\n")
            return
        try:
            choice = int(line.strip())
        except ValueError:
            choice = 0
        if not 1 <= choice <= len(races):
            _write(stdout, f"Please enter a number between 1 and {len(races)}\n")
            continue
        selected = races[choice - 1]
        try:
            accepted = submit(selected["id"])
        except Exception as e:
            _write(stdout, f"Could not save race selection: {_redact(str(e), secrets)}\n")
            continue
        if accepted:
            _write(stdout, f"Selected: {selected['name']}\n")
        else:
            _write(stdout, "A race was already selected elsewhere; ignoring terminal choice.\n")
        return
