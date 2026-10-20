"""Shared clock formatting."""

from __future__ import annotations


def format_duration(seconds: float) -> str:
    """Clock-style duration, matching the on-screen timers (truncated)."""
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"
