#!/usr/bin/env python3
"""Pretend telnet. The command table is the one from RFC 854."""
import sys

# name, byte, words a player might type, reply (empty means the flag)
ROWS = [
    ("SE", 240, ("se", "subnegotiation end"), "End of subnegotiation."),
    ("NOP", 241, ("nop", "no operation"), "No operation."),
    ("DM", 242, ("dm", "data mark"), "Data mark."),
    ("BRK", 243, ("brk", "break"), "Break."),
    ("IP", 244, ("ip", "interrupt process"), "Interrupt process."),
    ("AO", 245, ("ao", "abort output"), "Abort output."),
    ("AYT", 246, ("ayt", "are you there"), ""),
    ("EC", 247, ("ec", "erase character"), "Erase character."),
    ("EL", 248, ("el", "erase line"), "Erase line."),
    ("GA", 249, ("ga", "go ahead"), "Go ahead."),
    ("SB", 250, ("sb", "subnegotiation begin"), "Begin subnegotiation."),
    ("WILL", 251, ("will",), "This side will use an option."),
    ("WONT", 252, ("wont", "won't"), "This side will not use an option."),
    ("DO", 253, ("do",), "Please start using an option."),
    ("DONT", 254, ("dont", "don't"), "Please stop using an option."),
    ("IAC", 255, ("iac", "interpret as command"), "Interpret as command."),
]


def flag() -> str:
    word = bytes((97, 114, 101, 95, 121, 111, 117, 95, 116, 104, 101, 114, 101)).decode()
    return "TR{" + word + "}"


def reply(row: tuple) -> str:
    if row[0] == "AYT":
        return flag()
    return row[3]


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("'", "").split()).rstrip("?")


def lookup(text: str) -> tuple | None | str:
    raw = text.strip()
    if not raw:
        return None
    first, _, _rest = raw.partition(" ")
    if first.isdigit():
        number = int(first)
        for row in ROWS:
            if row[1] == number:
                return row
        return None
    key = normalize(first)
    phrase = normalize(raw)
    exact = []
    prefixed = []
    for row in ROWS:
        names = {row[0].lower(), *row[2]}
        if key in names or phrase in names:
            exact.append(row)
        elif any(name.startswith(key) for name in names):
            prefixed.append(row)
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return "ambiguous"
    if len(prefixed) == 1:
        return prefixed[0]
    if len(prefixed) > 1:
        return "ambiguous"
    return None


def help_text() -> str:
    lines = ["Telnet commands:", "Name  Byte  Meaning"]
    for name, number, words, answer in ROWS:
        meaning = words[-1]
        if meaning == name.lower():
            meaning = answer
        lines.append("%-5s %-5s %s" % (name, number, meaning))
    return "\n".join(lines)


def handle(line: str) -> bool:
    text = line.strip()
    if not text:
        return True
    if normalize(text) in {"help", "?", "commands"}:
        print(help_text())
        return True
    if normalize(text) in {"quit", "exit"}:
        return False
    found = lookup(text)
    if found == "ambiguous":
        print("?Ambiguous command. Type help.")
        return True
    if found is None:
        print("?Unknown command. Type help.")
        return True
    print(reply(found))
    return True


def main() -> None:
    if len(sys.argv) > 1:
        handle(" ".join(sys.argv[1:]))
        return
    while True:
        try:
            line = input("telnet> ")
        except EOFError:
            print()
            return
        if not handle(line):
            return


if __name__ == "__main__":
    main()
