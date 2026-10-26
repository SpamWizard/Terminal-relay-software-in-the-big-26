"""Usage: python check.py <password>"""
import hashlib
import sys

PASSWORD = "baton"
REAL_SALT = "desk"
# BUG: hash uses the staging salt
STAGING_SALT = "ops"


def token(password: str, salt: str) -> str:
    digest = hashlib.sha256((password + salt).encode()).hexdigest()[:12]
    return "TR{" + digest + "}"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python check.py <password>")
        raise SystemExit(1)
    guess = sys.argv[1].strip()
    if guess != PASSWORD:
        print("nope")
        return
    # Intended path was salts/REAL_SALT.txt — this print is a decoy
    print(token(guess, STAGING_SALT))


if __name__ == "__main__":
    main()
