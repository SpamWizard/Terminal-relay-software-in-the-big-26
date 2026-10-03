"""Switch-alert audio — quick soft blip."""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

_CACHE: Path | None = None
_mixer_ready = False
_sound = None


def _ensure_chime() -> Path:
    global _CACHE
    if _CACHE is not None and _CACHE.is_file():
        return _CACHE

    # Versioned filename so older cached chimes are not reused
    path = Path(tempfile.gettempdir()) / "terminal_relay_switch_chime_v2.wav"
    sample_rate = 44100
    # One soft mid tone + a quieter higher tick — ~180ms total
    segments = [
        (440.0, 0.09),   # A4
        (0.0, 0.02),
        (659.25, 0.07),  # E5, short
    ]
    frames = bytearray()
    for freq, dur in segments:
        n = int(sample_rate * dur)
        for i in range(n):
            t = i / sample_rate
            if freq <= 0:
                sample = 0.0
            else:
                # Fast attack, smooth exponential-ish decay (no harsh edge)
                attack = min(1.0, i / (sample_rate * 0.008))
                decay = math.exp(-3.2 * i / max(1, n - 1))
                env = attack * decay
                # Pure sine only — harmonics sound more annoying
                wave_ = math.sin(2 * math.pi * freq * t)
                sample = 0.55 * env * wave_
            frames += struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    _CACHE = path
    return path


def play_switch_chime(*, volume: float = 0.9) -> None:
    """Play the switch alert. Safe to call repeatedly; failures are silent."""
    global _mixer_ready, _sound
    try:
        import pygame

        if not _mixer_ready:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            _mixer_ready = True
        if _sound is None:
            _sound = pygame.mixer.Sound(str(_ensure_chime()))
        vol = max(0.0, min(1.0, float(volume)))
        _sound.set_volume(vol)
        _sound.play()
    except Exception:
        pass
