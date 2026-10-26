"""Organizer password helpers.

Dev hashes use the `argon2$dev$` prefix. They are a stand-in, not Argon2id.
The config screen stores `password_hash` and does not ask for it.
"""

from __future__ import annotations


def hash_password(password: str) -> str:
    return f"argon2$dev${password}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("argon2$dev$"):
        return stored == hash_password(password)
    return False
