#!/usr/bin/env python3
"""Hangman. Ten wrong letters ends it. The phrase is not shown until you win."""

import sys

_DATA = bytes.fromhex(
    "447d230c1e4e7637554e55643d5f4e5064365c4e4d6820561741707a40175a6132"
    "0c0c4e313b0c0d5f702941"
)
_PAD = bytes((0x37, 0x11, 0x5A, 0x2C, 0x6E))
_MISSES = 10


def _phrase() -> str:
    return "".join(chr(b ^ _PAD[i % len(_PAD)]) for i, b in enumerate(_DATA))


def _gallows(misses: int) -> str:
    if misses >= 10:
        head = "X"
    elif misses >= 9:
        head = "@"
    elif misses >= 8:
        head = "0"
    elif misses >= 7:
        head = "o"
    elif misses >= 1:
        head = "O"
    else:
        head = " "
    body = "|" if misses >= 2 else " "
    left_arm = "/" if misses >= 3 else " "
    right_arm = "\\" if misses >= 4 else " "
    left_leg = "/" if misses >= 5 else " "
    right_leg = "\\" if misses >= 6 else " "
    return "\n".join(
        [
            "  +---+",
            "  |   |",
            f"  |   {head}",
            f"  |  {left_arm}{body}{right_arm}",
            f"  |  {left_leg} {right_leg}",
            "  |",
            "=========",
        ]
    )


def _board(phrase: str, known: set[str]) -> str:
    words = []
    for word in phrase.split(" "):
        words.append(" ".join(ch if ch in known else "_" for ch in word))
    return "   ".join(words)


def _frame(phrase: str, known: set[str], wrong: list[str]) -> str:
    tried = " ".join(wrong) if wrong else "-"
    return "\n".join(
        [
            "HANGMAN",
            f"Wrong {len(wrong)}/{_MISSES}",
            "",
            _gallows(len(wrong)),
            "",
            _board(phrase, known),
            "",
            f"Misses: {tried}",
        ]
    )


def main() -> None:
    phrase = _phrase()
    known: set[str] = set()
    wrong: list[str] = []
    while True:
        solved = all(ch == " " or ch in known for ch in phrase)
        if sys.stdout.isatty():
            sys.stdout.write("\033[H\033[2J")
        sys.stdout.write(_frame(phrase, known, wrong) + "\n")
        if solved:
            sys.stdout.write("\nSolved.\n\n" + phrase + "\n\n")
            sys.stdout.write(
                "Take the first letter of each word, in order. Put that inside TR{ }.\n"
            )
            return
        if len(wrong) >= _MISSES:
            sys.stdout.write("\nOut of guesses. Run it again.\n")
            return
        sys.stdout.write("Letter: ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            return
        guess = line.strip().lower()
        if len(guess) != 1 or not guess.isalpha():
            continue
        if guess in known or guess in wrong:
            continue
        if guess in phrase:
            known.add(guess)
        else:
            wrong.append(guess)


if __name__ == "__main__":
    main()
