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
    """Each short challenge accepts its flag, and public/ does not contain it."""
    import base64
    import codecs
    import hashlib
    import re
    import zipfile

    expected = {
        "steghide": "TR{hidden_in_the_jpeg}",
        "photo_note": "TR{comment_section}",
        "anthem": "TR{not_an_mp3}",
        "unwrap": "TR{three_layers}",
        "wordlist": "TR{lantern}",
        "hashcat": "TR{spark}",
        "regex": "TR{kite4}",
        "crackme": "TR{rockme}",
        "gate": "TR{relay9x}",
        "telenet": "TR{virtual_circuit}",
        "xor": "TR{just_xor}",
        "hangman": "TR{spbgzlbac}",
    }
    for folder, flag in expected.items():
        qset = load_challenge_dir(ROOT / "challenges" / folder)
        q = qset.questions[0]
        assert isinstance(q, Desk)
        assert q.id == folder
        assert qset.set_id == folder
        assert q.score(flag, SCORING).correct
        assert not q.score("TR{nope}", SCORING).correct
        pub = Path(q.public_dir)
        for path in pub.rglob("*"):
            if path.is_file() and flag.encode() in path.read_bytes():
                raise AssertionError(f"{path} contains the flag")

    photo = (ROOT / "challenges" / "photo_note" / "public" / "photo.jpg").read_bytes()
    start = photo.find(b"\xff\xfe")
    assert start == 2
    length = int.from_bytes(photo[start + 2 : start + 4], "big")
    comment = photo[start + 4 : start + 2 + length]
    assert base64.b64decode(comment) == b"TR{comment_section}"
    exif_at = photo.find(b"\xff\xe1")
    assert exif_at > start
    exif_len = int.from_bytes(photo[exif_at + 2 : exif_at + 4], "big")
    exif_segment = photo[exif_at + 4 : exif_at + 2 + exif_len]
    assert exif_segment.startswith(b"Exif\x00\x00")
    assert comment in exif_segment

    secret = (ROOT / "challenges" / "unwrap" / "public" / "secret.txt").read_text(encoding="utf-8").strip()
    layer = base64.b64decode(secret)
    layer = bytes.fromhex(layer.decode("ascii"))
    assert codecs.decode(layer.decode("ascii"), "rot13") == "TR{three_layers}"

    word = "lantern"
    digest = hashlib.md5(word.encode()).hexdigest()
    assert (ROOT / "challenges" / "wordlist" / "public" / "hash.txt").read_text(encoding="utf-8").strip() == digest
    words = (ROOT / "challenges" / "wordlist" / "public" / "wordlist.txt").read_text(encoding="utf-8").split()
    assert word in words

    spark = "spark"
    spark_digest = hashlib.md5(spark.encode()).hexdigest()
    spark_words = (ROOT / "challenges" / "hashcat" / "public" / "wordlist.txt").read_text(encoding="utf-8").split()
    assert (ROOT / "challenges" / "hashcat" / "public" / "hash.txt").read_text(encoding="utf-8").strip() == spark_digest
    assert spark in spark_words
    assert len(spark_words) <= 12

    regex_lines = (ROOT / "challenges" / "regex" / "public" / "lines.txt").read_text(encoding="utf-8").split()
    assert len(regex_lines) >= 200
    assert [line for line in regex_lines if re.fullmatch(r"[a-z]+[0-9]", line)] == ["kite4"]

    with zipfile.ZipFile(ROOT / "challenges" / "anthem" / "public" / "anthem.mp3") as zf:
        assert zf.read("flag.txt", pwd=b"anthem") == b"TR{not_an_mp3}\n"

    source = (ROOT / "challenges" / "crackme" / "public" / "crackme.py").read_text(encoding="utf-8")
    assert 'pw[::-1] == "emkcor"' in source

    gate = (ROOT / "challenges" / "gate" / "public" / "bin" / "gate").read_bytes()
    assert gate.startswith(b"\x7fELF")
    table = bytes.fromhex("d5c3cdc9e2a3e5")
    assert table in gate
    assert bytes(((b - i) & 0xFF) ^ 0xA7 for i, b in enumerate(table)) == b"relay9x"
    assert b"relay9x" not in gate
    assert b"\x34\xa7" in gate

    telenet = (ROOT / "challenges" / "telenet" / "public" / "telenet.py").read_text(encoding="utf-8")
    assert 'count == str(len(text))' in telenet
    assert 'print("REJECTED")' in telenet
    assert "usage" not in telenet

    cipher = bytes.fromhex((ROOT / "challenges" / "xor" / "public" / "cipher.hex").read_text(encoding="utf-8"))
    hits = [key for key in range(256) if bytes(byte ^ key for byte in cipher).startswith(b"TR{")]
    assert hits == [0x37]
    assert not (ROOT / "challenges" / "xor" / "public" / "key.txt").exists()

    import subprocess
    import sys

    public = ROOT / "challenges" / "xor" / "public"
    bare = subprocess.run(
        [sys.executable, "xor.py"],
        cwd=public,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bare.returncode != 0
    assert "TR{just_xor}" not in bare.stdout
    solved = subprocess.run(
        [sys.executable, "xor.py", "37"],
        cwd=public,
        capture_output=True,
        text=True,
        check=True,
    )
    assert solved.stdout.strip() == "TR{just_xor}"

    hangman = (ROOT / "challenges" / "hangman" / "public" / "hangman.py").read_text(encoding="utf-8")
    phrase = "sly pygmy bugs gulp zyzzyva lymph by a chasm"
    assert phrase not in hangman
    assert "spbgzlbac" not in hangman
    won = subprocess.run(
        [sys.executable, "hangman.py"],
        cwd=ROOT / "challenges" / "hangman" / "public",
        input="\n".join(["a", "s", "h", "l", "u", "c", "m", "y", "p", "v", "b", "g", "z"]) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert phrase in won.stdout
    assert "TR{spbgzlbac}" not in won.stdout
    lost = subprocess.run(
        [sys.executable, "hangman.py"],
        cwd=ROOT / "challenges" / "hangman" / "public",
        input="\n".join(list("etoirdfwkx")) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Out of guesses" in lost.stdout
    assert phrase not in lost.stdout


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
    assert "cd '/challenges/steghide' && pwd\r" in written


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
    assert writes[-1] == " cd '/challenges/regex' && pwd\r"

    # A swallowed cd used to stick: opening the same challenge again does too.
    shell.ensure_challenge("regex", ROOT / "challenges" / "regex" / "public")
    again = _joined_writes(shell)
    assert again[-1] == " cd '/challenges/regex' && pwd\r"


def test_load_config_files():
    from baton_relay.config import load_config
    from baton_relay.questions.loader import load_all_question_files

    cfg = load_config(ROOT / "config" / "config.toml")
    sets = load_all_question_files(cfg.questions.files)
    types = {q.type for s in sets for q in s.questions}
    assert "desk" in types
    assert "multiple_choice" in types
    ids = {s.set_id for s in sets}
    assert "steghide" in ids
    assert "fake_logos" in ids or any("logo" in s.title.casefold() for s in sets)


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
