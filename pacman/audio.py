"""Small synthesized mono arcade sounds, built from standard-library arrays."""

from array import array
import math

import pygame


class Audio:
    RATE = 22050

    def __init__(self, muted: bool = False):
        self.muted = muted
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.dot_variant = 0
        self.loop_name: str | None = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.RATE, -16, 1, 512)
            pygame.mixer.set_num_channels(8)
            self.available = True
            self.sounds["dot0"] = self._sweep(420, 900, .075, .22)
            self.sounds["dot1"] = self._sweep(900, 420, .075, .22)
            self.sounds["power"] = self._sweep(200, 1200, .3, .20)
            self.sounds["ghost"] = self._sweep(500, 2100, .3, .25)
            self.sounds["fruit"] = self._notes(((880, .08), (1174, .08), (1568, .16)))
            self.sounds["extra"] = self._notes(((523, .09), (659, .09), (784, .09), (1047, .25)))
            self.sounds["clear"] = self._notes(((523, .12), (659, .12), (784, .12), (1047, .24)))
            self.sounds["death"] = self._sweep(950, 70, .85, .24, wobble=80)
            self.sounds["ready"] = self._notes(((494, .12), (988, .12), (740, .12), (622, .12),
                                                 (988, .08), (740, .2), (622, .22), (523, .12),
                                                 (1047, .12), (784, .12), (659, .12), (1047, .08),
                                                 (784, .2), (659, .22)))
            self.sounds["siren"] = self._sweep(180, 350, .32, .065, loop=True)
            self.sounds["fright"] = self._sweep(140, 90, .22, .065, loop=True)
            self.sounds["eyes"] = self._sweep(750, 1200, .18, .055, loop=True)
        except pygame.error:
            # A missing audio device must never prevent a playable game.
            self.available = False

    def _samples(self, start: float, end: float, duration: float,
                 volume: float, wobble: float = 0, loop: bool = False) -> array:
        count = max(1, int(duration * self.RATE))
        data = array("h")
        phase = 0.0
        for i in range(count):
            t = i / count
            ramp = (1 - abs(2 * t - 1)) if loop else t
            frequency = start + (end - start) * ramp + wobble * math.sin(28 * math.pi * t)
            phase += frequency / self.RATE
            triangle = 1 - 4 * abs((phase % 1) - .5)
            edge = min(1., i / 100, (count - 1 - i) / 150)
            envelope = edge * (1. if loop else (1 - t) ** .4)
            data.append(round(32767 * volume * triangle * envelope))
        return data

    def _sweep(self, start: float, end: float, duration: float, volume: float,
               wobble: float = 0, loop: bool = False) -> pygame.mixer.Sound:
        return pygame.mixer.Sound(buffer=self._samples(start, end, duration, volume, wobble, loop))

    def _notes(self, notes: tuple[tuple[float, float], ...]) -> pygame.mixer.Sound:
        data = array("h")
        for frequency, duration in notes:
            data.extend(self._samples(frequency, frequency, duration, .18))
        return pygame.mixer.Sound(buffer=data)

    def play(self, event: str) -> None:
        if not self.available or self.muted:
            return
        if event == "dot":
            event = f"dot{self.dot_variant}"
            self.dot_variant ^= 1
            channel = 1
        else:
            channel = 2 if event in ("power", "fruit", "ghost", "extra") else 3
        if event in self.sounds:
            pygame.mixer.Channel(channel).play(self.sounds[event])

    def ambience(self, name: str | None) -> None:
        if not self.available:
            return
        name = None if self.muted else name
        if name != self.loop_name:
            channel = pygame.mixer.Channel(0)
            channel.stop()
            if name in self.sounds:
                channel.play(self.sounds[name], loops=-1)
            self.loop_name = name

    def toggle(self) -> None:
        self.muted = not self.muted
        if self.available and self.muted:
            pygame.mixer.stop()
            self.loop_name = None
