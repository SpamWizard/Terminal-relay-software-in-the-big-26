#!/usr/bin/env python3
"""Short crackme. Read the check. Flag format is TR{password}."""
import sys


def ok(pw: str) -> bool:
    return pw[::-1] == "emkcor"


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python3 crackme.py <password>")
        return
    print("correct" if ok(sys.argv[1]) else "nope")


if __name__ == "__main__":
    main()
