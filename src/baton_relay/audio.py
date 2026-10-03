"""Switch-alert audio — short loud chime, not a harsh beep."""

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

    path = Path(tempfile.gettempdir()) / "terminal_relay_switch_chime.wav"
    sample_rate = 44100
    # Two rising tones + soft decay — attention-getting, not screechy
    segments = [
        (523.25, 0.12),  # C5
        (0.0, 0.04),
        (783.99, 0.16),  # G5
        (0.0, 0.03),
        (1046.50, 0.22),  # C6
    ]
    frames = bytearray()
    for freq, dur in segments:
        n = int(sample_rate * dur)
        for i in range(n):
            t = i / sample_rate
            if freq <= 0:
                sample = 0.0
            else:
                # Envelope: quick attack, short sustain, decay
                env = min(1.0, i / (sample_rate * 0.01))
                env *= max(0.0, 1.0 - (i / max(1, n - 1)) ** 1.4)
                # Soft square-ish mix (fundamental + quiet odd harmonic)
                wave_ = math.sin(2 * math.pi * freq * t)
                wave_ += 0.25 * math.sin(2 * math.pi * freq * 2 * t)
                sample = 0.72 * env * wave_
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
            # Dedicated frequency / buffer for low latency on Windows + Linux
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            _mixer_ready = True
        if _sound is None:
            _sound = pygame.mixer.Sound(str(_ensure_chime()))
        vol = max(0.0, min(1.0, float(volume)))
        _sound.set_volume(vol)
        _sound.play()
    except Exception:
        # Never break the game for audio issues
        pass
