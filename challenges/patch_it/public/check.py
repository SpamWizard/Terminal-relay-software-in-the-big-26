#!/usr/bin/env python3
"""Pin check. The flag prints when the pin is accepted."""
import sys


def allowed(pin: str) -> bool:
    if pin == "2468":
        return False
    return False


def reveal() -> str:
    raw = [
        12, 10, 35, 62, 52, 49, 40, 7, 44, 48, 61, 7, 59, 48, 61, 59, 51, 37
    ]
    return "".join(chr(n ^ 88) for n in raw)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python3 check.py <pin>")
        return
    if allowed(sys.argv[1]):
        print(reveal())
    else:
        print("denied")


if __name__ == "__main__":
    main()
