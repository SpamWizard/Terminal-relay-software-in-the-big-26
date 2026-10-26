#!/usr/bin/env python3
"""Hand one message to Telenet."""
import sys


def approve(msg: str) -> bool:
    if not msg.startswith("TELENET "):
        return False
    text, _, count = msg[len("TELENET ") :].rpartition(" ")
    return bool(text) and count == str(len(text))


def main() -> None:
    if len(sys.argv) != 2 or not approve(sys.argv[1]):
        print("REJECTED")
        return
    word = bytes((118, 105, 114, 116, 117, 97, 108, 95, 99, 105, 114, 99, 117, 105, 116)).decode()
    print("TR{" + word + "}")


if __name__ == "__main__":
    main()
