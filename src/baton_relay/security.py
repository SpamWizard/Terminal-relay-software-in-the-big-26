"""Organizer password helpers (MVP stub; real Argon2 in a later phase)."""

from __future__ import annotations


def hash_password(password: str) -> str:
    """Dev placeholder. Replace with Argon2id before conference."""
    return f"argon2$dev${password}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("argon2$dev$"):
        return stored == hash_password(password)
    return False
