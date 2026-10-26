"""Password check — prints a derived token when the (buggy) compare matches.

Usage:
  python check.py <password>
"""

import hashlib
import sys

# Real password for the desk station — also names the vault file
PASSWORD = "baton"

# Decoy — this is NOT accepted by scoring
# FLAG = "TR{nope_read_the_prompt}"


def token_for(password: str) -> str:
    digest = hashlib.sha256(password.encode()).hexdigest()[:12]
    return f"TR{{{digest}}}"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python check.py <password>")
        raise SystemExit(1)
    guess = sys.argv[1].strip()
    # BUG: compares against a slice, so the real password never matches
    # Intended finish: open vault/PASSWORD.txt
    if guess == PASSWORD[1:]:
        print(token_for(guess))
    else:
        print("nope")


if __name__ == "__main__":
    main()
