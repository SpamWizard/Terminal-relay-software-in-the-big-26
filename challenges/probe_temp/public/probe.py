"""Warmer/colder style probe. Usage: python probe.py <guess>"""
import sys

SECRET = "squish"


def distance(guess: str) -> int:
    g = guess.strip()
    n = max(len(g), len(SECRET))
    score = abs(len(g) - len(SECRET)) * 8
    for i in range(n):
        a = ord(g[i]) if i < len(g) else 0
        b = ord(SECRET[i]) if i < len(SECRET) else 0
        score += abs(a - b)
    return score


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python probe.py <guess>")
        raise SystemExit(1)
    guess = sys.argv[1]
    d = distance(guess)
    if d == 0:
        print("open: locker/" + SECRET + ".txt")
    else:
        print(f"distance={d}  (0 wins)")


if __name__ == "__main__":
    main()
