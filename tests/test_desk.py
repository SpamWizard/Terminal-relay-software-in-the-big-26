"""Desk sandbox, challenge folders, and WSL shell helpers (no live WSL required)."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from baton_relay.config import ScoringConfig
from baton_relay.desk.sandbox import SandboxError, resolve_in_public
from baton_relay.desk.shell import TeamShell, distro_name
from baton_relay.questions.loader import load_challenge_dir
from baton_relay.questions.registry import ensure_builtin_types_loaded
from baton_relay.questions.types import Desk


ROOT = Path(__file__).resolve().parents[1]
SCORING = ScoringConfig(partial_credit=True, wrong_answer_penalty=0, redo_multiplier=0.5)


@pytest.fixture(autouse=True)
def _types():
    ensure_builtin_types_loaded()


def test_hidden_public_names():
    from baton_relay.desk.sandbox import is_hidden_public_name

    assert is_hidden_public_name(".mail/note.txt")
    assert is_hidden_public_name("notes/.secret")
    assert not is_hidden_public_name("readme.txt")
    assert not is_hidden_public_name("mail/note.txt")


def test_resolve_blocks_escape(tmp_path: Path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "a.txt").write_text("x", encoding="utf-8")
    assert resolve_in_public(pub, "a.txt").name == "a.txt"
    with pytest.raises(SandboxError):
        resolve_in_public(pub, "../secret")
    with pytest.raises(SandboxError):
        resolve_in_public(pub, "C:/Windows/notepad.exe")


def test_distro_name_slug():
    assert distro_name("Red Team!").startswith("relay-")


def test_locked_shell_drops_keys():
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell.locked = True
    shell.write_keys("echo should-not-run\r")
    shell._pty.write.assert_not_called()

    shell.locked = False
    shell.write_keys("echo hi\r")
    shell._pty.write.assert_called_with("echo hi\r")


def test_short_desk_challenges_solve_clean():
    """Each desk challenge is 100 points, accepts its flag, and public/ does not contain it."""
    expected = {
        "backwards": "TR{too_long_to_read}",
        "dot": "TR{look_deeper}",
        "acrostic": "TR{quiet_margin}",
        "telnet": "TR{are_you_there}",
        "plus_one": "TR{onomatopoeia}",
        "binary": "TR{eight_bits}",
        "railroad": "TR{three_rails}",
        "whitespace": "TR{trailing_off}",
        "zero_width": "TR{thin_space}",
        "lsb": "TR{low_bits}",
        "broken_png": "TR{magic_bytes}",
        "log_hunt": "TR{marigold}",
        "patch_it": "TR{flip_the_check}",
        "identify": "TR{compass}",
    }
    for folder, flag in expected.items():
        qset = load_challenge_dir(ROOT / "challenges" / folder)
        q = qset.questions[0]
        assert isinstance(q, Desk)
        assert q.id == folder
        assert qset.set_id == folder
        assert q.points == 100
        assert q.score(flag, SCORING).correct
        assert not q.score("TR{nope}", SCORING).correct
        pub = Path(q.public_dir)
        for path in pub.rglob("*"):
            if not path.is_file() or flag.encode() not in path.read_bytes():
                continue
            rel = path.relative_to(pub).as_posix()
            hidden = any(part.startswith(".") for part in rel.split("/"))
            if folder == "dot" and hidden:
                continue
            raise AssertionError(f"{path} contains the flag")


def test_added_challenges_round_trip(tmp_path: Path):
    """The added tiles decode to their flags."""
    import hashlib
    import struct
    import subprocess
    import sys
    import zlib

    binary = (ROOT / "challenges" / "binary" / "public" / "bits.txt").read_text(encoding="ascii").strip()
    assert set(binary) <= {"0", "1"}
    assert len(binary) % 8 == 0
    assert "".join(chr(int(binary[i : i + 8], 2)) for i in range(0, len(binary), 8)) == "TR{eight_bits}"

    fence = (ROOT / "challenges" / "railroad" / "public" / "fence.txt").read_text(encoding="ascii")
    assert "\r" not in fence
    assert "TR{" not in fence
    lines = fence.splitlines()
    assert len(lines) == 3
    assert len({len(line) for line in lines}) == 1
    decoded = []
    for column in zip(*lines):
        letters = [ch for ch in column if ch != "."]
        assert len(letters) == 1
        decoded.append(letters[0])
    assert "".join(decoded) == "TR{three_rails}"

    letter = (ROOT / "challenges" / "whitespace" / "public" / "letter.txt").read_bytes()
    assert b"\r" not in letter
    assert b"TR{trailing_off}" not in letter
    rows = letter.split(b"\n")
    if rows[-1] == b"":
        rows.pop()
    hidden_chars = []
    for row in rows:
        assert row.endswith(b"    ") is False
        assert row[-5:-1] == b"    "
        assert row[-6] not in (0x20, 0x09)
        hidden_chars.append(chr(row[-1]))
    assert "".join(hidden_chars) == "TR{trailing_off}"

    memo = (ROOT / "challenges" / "zero_width" / "public" / "memo.txt").read_text(encoding="utf-8")
    assert "\r" not in memo
    assert "TR{thin_space}" not in memo
    assert "\u200c" not in memo
    marked = []
    for index, ch in enumerate(memo):
        if ch == "\u200b":
            marked.append(memo[index + 1])
        else:
            assert ch == "\n" or ord(ch) < 128
    assert "".join(marked) == "TR{thin_space}"

    png = (ROOT / "challenges" / "lsb" / "public" / "postcard.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"TR{low_bits}" not in png
    pos = 8
    width = height = 0
    idat = b""
    while pos + 12 <= len(png):
        length = int.from_bytes(png[pos : pos + 4], "big")
        tag = png[pos + 4 : pos + 8]
        chunk = png[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            assert (depth, color, comp, filt, interlace) == (8, 2, 0, 0, 0)
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
    raw = zlib.decompress(idat)
    stride = width * 3
    row_len = stride + 1
    assert len(raw) == row_len * height
    rgb = bytearray()
    for y in range(height):
        assert raw[y * row_len] == 0
        rgb.extend(raw[y * row_len + 1 : (y + 1) * row_len])
    acc = n = 0
    found = []
    for byte in rgb:
        acc = ((acc << 1) | (byte & 1)) & 0xFF
        n += 1
        if n == 8:
            if acc == 0:
                break
            found.append(chr(acc))
            acc = n = 0
    assert "".join(found) == "TR{low_bits}"

    broken = (ROOT / "challenges" / "broken_png" / "public" / "broken.png").read_bytes()
    assert broken[:8] == b"\x00" * 8
    assert b"TR{magic_bytes}" not in broken
    fixed = b"\x89PNG\r\n\x1a\n" + broken[8:]
    pos = 8
    comment = b""
    while pos + 12 <= len(fixed):
        length = int.from_bytes(fixed[pos : pos + 4], "big")
        tag = fixed[pos + 4 : pos + 8]
        chunk = fixed[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"zTXt":
            keyword, payload = chunk.split(b"\x00", 1)
            assert keyword == b"Comment"
            assert payload[:1] == b"\x00"
            comment = zlib.decompress(payload[1:])
        elif tag == b"IEND":
            break
    assert comment == b"TR{magic_bytes}"

    log_lines = (ROOT / "challenges" / "log_hunt" / "public" / "access.log").read_text(encoding="ascii").splitlines()
    assert len(log_lines) >= 500
    hits = [line for line in log_lines if line.split()[4:] == ["/admin", "200"]]
    assert len(hits) == 1
    assert hits[0].split()[1] == "marigold"
    assert sum("marigold" in line for line in log_lines) == 1
    assert any(line.split()[4:] == ["/administrator", "200"] for line in log_lines)
    assert any(line.split()[4] == "/admin" and line.split()[5] != "200" for line in log_lines)

    source = (ROOT / "challenges" / "patch_it" / "public" / "check.py").read_text(encoding="utf-8")
    assert "TR{flip_the_check}" not in source
    assert source.count("return False") == 2
    denied = subprocess.run(
        [sys.executable, "check.py", "2468"],
        cwd=ROOT / "challenges" / "patch_it" / "public",
        capture_output=True,
        text=True,
        check=True,
    )
    assert denied.stdout.strip() == "denied"
    patched = source.replace("return False", "return True", 1)
    script = tmp_path / "check.py"
    script.write_bytes(patched.encode("utf-8"))
    opened = subprocess.run(
        [sys.executable, str(script), "2468"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert opened.stdout.strip() == "TR{flip_the_check}"
    still_shut = subprocess.run(
        [sys.executable, str(script), "0000"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert still_shut.stdout.strip() == "denied"

    identify = load_challenge_dir(ROOT / "challenges" / "identify").questions[0]
    prompt = identify.prompt.lower()
    assert "sha" not in prompt
    assert "md5" not in prompt
    assert "hashcat" not in prompt
    assert "john" not in prompt
    digest = hashlib.sha1(b"compass").hexdigest()
    assert len(digest) == 40
    public = ROOT / "challenges" / "identify" / "public"
    assert (public / "hash.txt").read_text(encoding="ascii").strip() == digest
    assert "compass" in (public / "wordlist.txt").read_text(encoding="ascii").split()

    note = (ROOT / "challenges" / "backwards" / "public" / "note.txt").read_text(encoding="ascii")
    assert "\r" not in note
    body = note.strip()
    restored = body[::-1]
    assert len(body) >= 180
    assert "TR{too_long_to_read}" in restored
    assert "TR{too_long_to_read}" not in body

    dot = ROOT / "challenges" / "dot" / "public"
    visible = [path for path in dot.rglob("*") if path.is_file() and not any(part.startswith(".") for part in path.relative_to(dot).parts)]
    assert visible == []
    hidden = [path.relative_to(dot).as_posix() for path in dot.rglob("*") if path.is_file()]
    assert hidden == [".local/note.txt"]
    assert (dot / ".local" / "note.txt").read_text(encoding="ascii").strip() == "TR{look_deeper}"

    acrostic = load_challenge_dir(ROOT / "challenges" / "acrostic").questions[0]
    assert "Spaces are _." in acrostic.prompt
    poem = (ROOT / "challenges" / "acrostic" / "public" / "poem.txt").read_text(encoding="ascii")
    assert "\r" not in poem
    chunks = [chunk for chunk in poem.strip().split("\n\n")]
    assert chunks[0] == "Evening Post"
    assert chunks[-1].startswith("Signed")
    words = ["".join(line[0] for line in chunk.splitlines()) for chunk in chunks[1:-1]]
    assert words == ["QUIET", "MARGIN"]
    assert "TR{" + "_".join(word.lower() for word in words) + "}" == "TR{quiet_margin}"

    telnet_q = load_challenge_dir(ROOT / "challenges" / "telnet").questions[0]
    assert "are you there" in telnet_q.prompt.lower()
    telnet_py = ROOT / "challenges" / "telnet" / "public" / "telnet.py"
    source = telnet_py.read_text(encoding="utf-8")
    assert "\r" not in source
    assert "are_you_there" not in source
    assert not (ROOT / "challenges" / "telnet" / "public" / "door.py").exists()

    def _telnet(*args: str, stdin: str | None = None) -> str:
        done = subprocess.run(
            [sys.executable, str(telnet_py), *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout

    assert _telnet("AYT").strip() == "TR{are_you_there}"
    assert _telnet("Are you there?").strip() == "TR{are_you_there}"
    assert _telnet("246").strip() == "TR{are_you_there}"
    assert _telnet("NOP").strip() == "No operation."
    assert _telnet("241").strip() == "No operation."
    assert "TR{" not in _telnet("IP")
    assert "Unknown" in _telnet("hello")
    help_text = _telnet("help")
    assert "AYT" in help_text and "246" in help_text
    assert "TR{" not in help_text
    interactive = _telnet(stdin="AYT\nquit\n")
    assert "TR{are_you_there}" in interactive

    shifted = (ROOT / "challenges" / "plus_one" / "public" / "shift.txt").read_text(encoding="ascii").strip()
    assert "\r" not in shifted
    assert "onomatopoeia" not in shifted

    def _unshift(text: str) -> str:
        out = []
        for ch in text:
            if "a" <= ch <= "z":
                out.append(chr((ord(ch) - ord("a") - 1) % 26 + ord("a")))
            elif "A" <= ch <= "Z":
                out.append(chr((ord(ch) - ord("A") - 1) % 26 + ord("A")))
            else:
                out.append(ch)
        return "".join(out)

    assert _unshift(shifted) == "TR{onomatopoeia}"


def test_command_output_is_not_held_until_next_key():
    """A burst that arrives just after a flush must show before the next read blocks."""
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    saw_block = threading.Event()
    release = threading.Event()
    chunks = ["\x1b[1;70Hecho hi\x1b[2;9H", "hi\r\n"]

    def read(_size):
        if chunks:
            return chunks.pop(0)
        saw_block.set()
        assert release.wait(timeout=2)
        raise EOFError

    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell._pty.read.side_effect = read
    shown: list[str] = []
    shell.on_output = shown.append

    # 1ms steps: the old reader held this burst because it was inside 16ms
    # of the previous flush, then blocked until the next key.
    clock = {"t": 100.0}

    def monotonic():
        clock["t"] += 0.001
        return clock["t"]

    with patch("baton_relay.desk.shell.time.monotonic", monotonic):
        thread = threading.Thread(target=shell._read_loop, daemon=True)
        thread.start()
        assert saw_block.wait(timeout=2), "reader never reached the blocking read"
        try:
            assert shown == ["\x1b[1;70Hecho hi\x1b[2;9H", "hi\r\n"]
        finally:
            release.set()
            thread.join(timeout=2)
    assert not thread.is_alive()


def test_tab_is_sent_to_the_shell(qtbot):
    """Tab completes in bash; it must not move focus to the flag field."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    from baton_relay.ui.pty_terminal import PtyTerminalWidget

    root = QWidget()
    layout = QVBoxLayout(root)
    other = QLineEdit()
    term = PtyTerminalWidget()
    layout.addWidget(term)
    layout.addWidget(other)
    qtbot.addWidget(root)

    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    term.bind_shell(shell)
    root.show()
    term.setFocus()
    qtbot.waitUntil(term.hasFocus)

    qtbot.keyClick(term, Qt.Key.Key_Tab)
    shell._pty.write.assert_called_with("\t")
    assert term.hasFocus()


def test_shell_paste_strips_one_trailing_newline():
    from baton_relay.ui.pty_terminal import shell_paste_text

    assert shell_paste_text("TR{rockme}\n") == "TR{rockme}"
    assert shell_paste_text("TR{rockme}\r\n") == "TR{rockme}"
    assert shell_paste_text("one\ntwo") == "one\rtwo"


def test_double_click_copies_flag_for_the_answer_box(qtbot):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QApplication, QLineEdit

    from baton_relay.ui.pty_terminal import PtyTerminalWidget

    term = PtyTerminalWidget()
    flag = QLineEdit()
    qtbot.addWidget(term)
    qtbot.addWidget(flag)
    term.resize(800, 300)
    term.show()
    flag.show()
    qtbot.waitUntil(lambda: term._cell_w >= 6)
    term._stream.feed("see TR{rockme} now\r\n")
    line = term._screen.display[0]
    col = line.index("T")
    clip = QApplication.clipboard()
    previous = clip.text()
    try:
        qtbot.mouseDClick(
            term,
            Qt.MouseButton.LeftButton,
            pos=QPoint(col * term._cell_w + term._cell_w // 2, term._cell_h // 2),
        )
        assert term._selection_text() == "TR{rockme}"
        assert clip.text() == "TR{rockme}"

        flag.setFocus()
        qtbot.waitUntil(flag.hasFocus)
        qtbot.keyClick(flag, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        assert flag.text() == "TR{rockme}"
    finally:
        clip.setText(previous)


def test_ctrl_c_copies_selection_and_otherwise_interrupts(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from baton_relay.ui.pty_terminal import PtyTerminalWidget

    term = PtyTerminalWidget()
    qtbot.addWidget(term)
    term.resize(800, 300)
    term.show()
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    term.bind_shell(shell)
    term._stream.feed("TR{rockme}\r\n")
    term._select_word_at(0, 0)
    term.setFocus()
    qtbot.waitUntil(term.hasFocus)
    clip = QApplication.clipboard()
    previous = clip.text()
    try:
        qtbot.keyClick(term, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert clip.text() == "TR{rockme}"
        shell._pty.write.assert_not_called()

        term._anchor = None
        term._caret = None
        qtbot.keyClick(term, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        shell._pty.write.assert_called_with("\x03")
    finally:
        clip.setText(previous)


def test_ctrl_v_pastes_flag_into_the_shell(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from baton_relay.ui.pty_terminal import PtyTerminalWidget

    term = PtyTerminalWidget()
    qtbot.addWidget(term)
    term.show()
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    term.bind_shell(shell)
    term.setFocus()
    qtbot.waitUntil(term.hasFocus)
    clip = QApplication.clipboard()
    previous = clip.text()
    try:
        clip.setText("TR{rockme}\n")
        qtbot.keyClick(term, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        shell._pty.write.assert_called_with("TR{rockme}")
    finally:
        clip.setText(previous)


def test_terminal_feed_restores_per_challenge(qtbot):
    """Gate scrollback comes back when rebound; steghide stays separate."""
    from baton_relay.ui.pty_terminal import PtyTerminalWidget

    gate = PtyTerminalWidget()
    steg = PtyTerminalWidget()
    qtbot.addWidget(gate)
    qtbot.addWidget(steg)

    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True

    gate.bind_shell(shell)
    gate._queue_output("gate-hello\r\n")
    gate._flush_pending()
    saved_gate = gate.feed_log()
    assert "gate-hello" in saved_gate
    gate.detach_shell()

    steg.bind_shell(shell)
    steg._queue_output("steg-hello\r\n")
    steg._flush_pending()
    saved_steg = steg.feed_log()
    assert "steg-hello" in saved_steg
    assert "gate-hello" not in saved_steg
    steg.detach_shell()

    gate2 = PtyTerminalWidget()
    qtbot.addWidget(gate2)
    gate2.bind_shell(shell, restore=saved_gate)
    assert "gate-hello" in "".join(gate2._screen.display)
    assert "steg-hello" not in "".join(gate2._screen.display)


def test_show_question_keeps_same_desk_terminal(qtbot):
    from baton_relay.questions.types import Desk
    from baton_relay.ui.question_widgets import QuestionHost

    public = ROOT / "challenges" / "binary" / "public"
    q = Desk(
        id="binary",
        type="desk",
        prompt="Open the bits",
        points=1,
        public_dir=str(public),
        accepted=["TR{x}"],
        panes=["terminal"],
    )
    host = QuestionHost()
    qtbot.addWidget(host)
    host.set_locked(False)
    host.show_question(q)
    desk = host._desk
    assert desk is not None
    desk._term_pane.term._queue_output("still-here\r\n")
    desk._term_pane.term._flush_pending()

    host.show_question(q)
    assert host._desk is desk
    assert "still-here" in desk._term_pane.term.feed_log()


def test_flag_field_keeps_focus_across_lock_refresh(qtbot):
    """Timer re-renders call set_locked(False) often; that must not yank the flag box."""
    from baton_relay.questions.types import Desk
    from baton_relay.ui.question_widgets import QuestionHost

    public = ROOT / "challenges" / "binary" / "public"
    q = Desk(
        id="binary",
        type="desk",
        prompt="Open the bits",
        points=1,
        public_dir=str(public),
        accepted=["TR{x}"],
        panes=["terminal"],
    )
    host = QuestionHost()
    qtbot.addWidget(host)
    host.set_locked(False)
    host.show_question(q)
    desk = host._desk
    assert desk is not None
    host.show()
    qtbot.waitExposed(host)
    # First open focuses the shell once; let that settle, then use the flag box.
    qtbot.waitUntil(lambda: desk._term_pane.term.hasFocus())
    desk.flag_edit.setFocus()
    qtbot.waitUntil(desk.flag_edit.hasFocus)

    host.set_locked(False)
    desk.set_desk_locked(False)
    host.show_question(q)
    assert desk.flag_edit.hasFocus()
    qtbot.keyClicks(desk.flag_edit, "TR{x}")
    assert desk.flag_edit.text() == "TR{x}"


def test_mouse_wheel_scrolls_terminal_history(qtbot):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QWheelEvent

    from baton_relay.ui.pty_terminal import PtyTerminalWidget

    term = PtyTerminalWidget()
    qtbot.addWidget(term)
    term.resize(800, 400)
    term.show()
    qtbot.waitUntil(lambda: term._rows >= 8)
    rows = term._rows
    total = rows + 12
    for i in range(total):
        term._stream.feed(f"line-{i:02d}\r\n")
    joined = "".join(term._screen.display)
    assert "line-00" not in joined
    assert f"line-{total - 2:02d}" in joined

    pos = QPoint(term.width() // 2, term.height() // 2)
    global_pos = term.mapToGlobal(pos)
    wheel_up = QWheelEvent(
        pos,
        global_pos,
        QPoint(0, 0),
        QPoint(0, 120 * 40),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    term.wheelEvent(wheel_up)
    assert any("line-00" in row for row in term._screen.display)

    # Shift+PageDown pages toward the live prompt again.
    for _ in range(8):
        qtbot.keyClick(term, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ShiftModifier)
    assert "line-00" not in "".join(term._screen.display)


def _joined_writes(shell) -> list[str]:
    assert shell._cd_thread is not None
    shell._cd_thread.join(timeout=2)
    return [call.args[0] for call in shell._pty.write.call_args_list]


def test_cd_is_forced_while_locked():
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell.locked = True
    shell._copied.add("steghide")
    shell._cd_pause = 0
    shell.ensure_challenge("steghide", ROOT / "challenges" / "steghide" / "public")
    written = "".join(_joined_writes(shell))
    assert "cd '/challenges/steghide'" in written
    assert "&& pwd" not in written


def test_challenge_cd_is_hidden_from_the_terminal():
    """Folder switches still run in bash, but muted bytes never hit the GUI."""
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell._copied.add("steghide")
    shell._cd_pause = 0
    shell.ensure_challenge("steghide", ROOT / "challenges" / "steghide" / "public")
    written = "".join(_joined_writes(shell))
    assert "cd '/challenges/steghide'" in written
    assert "__relay_cd_" in written
    assert "&& pwd" not in written

    shown: list[str] = []
    shell.on_output = shown.append
    shell._output_muted = True
    chunks = [" cd '/challenges/steghide'\r\n__relay_cd_1__\r\n"]

    def read(_size):
        if chunks:
            return chunks.pop(0)
        raise EOFError

    shell._pty.read.side_effect = read
    shell._read_loop()
    assert shown == []
    assert "cd '/challenges/steghide'" in shell.transcript


def test_switching_challenges_leaves_the_previous_folder():
    """A leftover command or half-typed line must not keep the old directory."""
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell._copied.update({"crackme", "regex"})
    shell._cwd_challenge = "crackme"
    shell._cd_pause = 0
    shell.ensure_challenge("regex", ROOT / "challenges" / "regex" / "public")
    writes = _joined_writes(shell)
    assert writes[0] == "\x03"
    assert any("cd '/challenges/regex'" in w for w in writes)
    assert all("&& pwd" not in w for w in writes)
    # Quiet switch ends with a lone Enter so one clean prompt can paint.
    assert writes[-1] == "\r"

    # A swallowed cd used to stick: opening the same challenge again does too.
    shell.ensure_challenge("regex", ROOT / "challenges" / "regex" / "public")
    again = _joined_writes(shell)
    assert any("cd '/challenges/regex'" in w for w in again)
    assert again[-1] == "\r"


def test_python_repl_is_exited_before_changing_folder():
    """Bare python3 survives Ctrl-C; cd must not be typed into the REPL."""
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell._copied.add("xor")
    shell._cd_pause = 0.8
    shell.transcript = "Python 3.12.3 (main)\nType \"help\" for more information.\n>>> "
    shell._wait_for_prompt = lambda token: token == shell._cd_token
    shell._wait_for_marker = lambda token, marker: token == shell._cd_token
    shell.ensure_challenge("xor", ROOT / "challenges" / "xor" / "public")
    writes = _joined_writes(shell)
    joined = "".join(writes)
    assert writes[0] == "\x03"
    assert "exit()" in joined
    assert "cd '/challenges/xor'" in joined
    assert joined.index("exit()") < joined.index("cd '/challenges/xor'")


def test_shell_prompt_does_not_get_an_exit():
    shell = TeamShell(distro="relay-test", repo_root=ROOT)
    shell._pty = MagicMock()
    shell._pty.isalive.return_value = True
    shell._copied.update({"xor", "hangman"})
    shell._cd_pause = 0.8
    shell.transcript = "player@relay:/challenges/xor$ "
    shell._wait_for_prompt = lambda token: token == shell._cd_token
    shell._wait_for_marker = lambda token, marker: token == shell._cd_token
    shell.ensure_challenge("hangman", ROOT / "challenges" / "hangman" / "public")
    joined = "".join(_joined_writes(shell))
    assert "exit()" not in joined
    assert "cd '/challenges/hangman'" in joined


def test_load_config_files():
    from baton_relay.config import load_config
    from baton_relay.questions.loader import load_all_question_files

    cfg = load_config(ROOT / "config" / "config.toml")
    sets = load_all_question_files(cfg.questions.files)
    types = {q.type for s in sets for q in s.questions}
    assert types == {"desk"}
    ids = {s.set_id for s in sets}
    assert "binary" in ids
    assert "steghide" not in ids
    assert "fake_logos" not in ids
    desks = [q for s in sets for q in s.questions if q.type == "desk"]
    assert all(q.points == 100 for q in desks)


def test_claim_standby_moves_disk(tmp_path: Path):
    from baton_relay.desk.shell import (
        _claim_standby,
        ensure_standby_disk,
        standby_vhdx_path,
        team_vhdx_path,
    )

    gold = tmp_path / "images" / "relay-gold.vhdx"
    gold.parent.mkdir(parents=True)
    gold.write_bytes(b"GOLD-DISK")

    with (
        patch("baton_relay.desk.shell.require_desk_runtime"),
        patch("baton_relay.desk.shell._clear_readonly"),
    ):
        ready = ensure_standby_disk(tmp_path)
        assert ready == standby_vhdx_path(tmp_path)
        assert ready.read_bytes() == b"GOLD-DISK"

        claimed = _claim_standby(tmp_path, "Alpha")
        assert claimed == team_vhdx_path(tmp_path, "Alpha")
        assert claimed.is_file()
        assert claimed.read_bytes() == b"GOLD-DISK"
        assert not standby_vhdx_path(tmp_path).is_file()
        assert _claim_standby(tmp_path, "Beta") is None


def test_category_board_ignores_clicks_until_armed(qtbot):
    from PySide6.QtCore import Qt

    from baton_relay.ui.category_board import CategoryBoard, _CategoryTile

    board = CategoryBoard()
    qtbot.addWidget(board)
    picked: list[str] = []
    board.set_choose_handler(lambda sid: picked.append(sid))
    board.show_categories([("hashcat", "Hashcat"), ("steghide", "Steghide")])
    board.show()
    qtbot.waitExposed(board)

    tiles = board.findChildren(_CategoryTile)
    assert len(tiles) == 2
    # Fresh board is armed — ghost clicks must not open a category.
    qtbot.mouseClick(tiles[0], Qt.MouseButton.LeftButton)
    assert picked == []

    board.arm(0)
    qtbot.mouseClick(tiles[0], Qt.MouseButton.LeftButton)
    assert picked == ["hashcat"]
