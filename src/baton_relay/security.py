"""Organizer password helpers (reserved — CONFIG lock not wired yet).

Dev hashes use the `argon2$dev$` prefix. Swap for real Argon2id before any
event that needs a real password gate.
"""

from __future__ import annotations


def hash_password(password: str) -> str:
    return f"argon2$dev${password}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("argon2$dev$"):
        return stored == hash_password(password)
    return False
