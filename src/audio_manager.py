"""Audio manager: tiny synthesised sounds (no asset files required).

If a WAV with the same name exists in assets/sounds (target.wav, place.wav, invalid.wav,
win.wav, draw.wav, tick.wav, go.wav, warn.wav, match.wav, click.wav) it is used instead of the generated tone.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pygame

SOUND_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"
SAMPLE_RATE = 22050


def _tone(freq: float, dur: float, vol: float = 0.35) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t) * np.linspace(1.0, 0.0, n) ** 0.7
    return (wave * vol * 32767).astype(np.int16)


def _seq(*notes) -> np.ndarray:
    return np.concatenate([_tone(f, d) for f, d in notes])


class AudioManager:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1)
            self._build()
        except Exception as exc:                     # no audio device -> silent game
            print("Audio disabled:", exc)
            self.enabled = False

    def _make(self, samples: np.ndarray) -> pygame.mixer.Sound:
        channels = pygame.mixer.get_init()[2]
        if channels == 2:
            samples = np.column_stack([samples, samples])
        return pygame.sndarray.make_sound(np.ascontiguousarray(samples))

    def _build(self) -> None:
        synth = {
            "target": _tone(660, 0.05, 0.15),
            "place": _seq((520, 0.07), (780, 0.10)),
            "invalid": _seq((200, 0.12), (150, 0.18)),
            "win": _seq((523, 0.12), (659, 0.12), (784, 0.12), (1046, 0.30)),
            "draw": _seq((400, 0.15), (400, 0.15), (330, 0.25)),
            "tick": _tone(740, 0.07, 0.25),
            "go": _seq((880, 0.08), (1175, 0.22)),
            "warn": _tone(440, 0.06, 0.2),
            "match": _seq((523, 0.12), (659, 0.12), (784, 0.12), (1046, 0.12),
                          (784, 0.12), (1046, 0.12), (1318, 0.40)),
            "click": _tone(560, 0.04, 0.2),
        }
        for name, data in synth.items():
            wav = SOUND_DIR / f"{name}.wav"
            try:
                self.sounds[name] = pygame.mixer.Sound(str(wav)) if wav.exists() else self._make(data)
            except Exception:
                self.sounds[name] = self._make(data)

    def play(self, name: str) -> None:
        if self.enabled and name in self.sounds:
            self.sounds[name].play()
