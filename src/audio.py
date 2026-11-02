import math
import random
from array import array
from pathlib import Path

RATE = 22050


def _synth(dur, f0, f1, noise, decay, vol=0.55, seed=1):
    rng = random.Random(seed)
    n = int(RATE * dur)
    out = array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += 2 * math.pi * (f0 + (f1 - f0) * t) / RATE
        s = (math.sin(phase) * (1 - noise) + (rng.random() * 2 - 1) * noise) * math.exp(-decay * t) * vol
        out.append(int(max(-1.0, min(1.0, s)) * 32767))
    return out


SPECS = {
    "shot_AR": (0.16, 180, 60, 0.7, 7), "shot_SMG": (0.10, 240, 90, 0.7, 9), "shot_LMG": (0.18, 140, 50, 0.65, 6),
    "shot_SG": (0.28, 110, 40, 0.8, 5), "shot_MARKSMAN": (0.24, 150, 45, 0.65, 6), "shot_SNIPER": (0.5, 90, 30, 0.6, 4),
    "shot_PISTOL": (0.12, 260, 100, 0.7, 8), "hitmarker": (0.05, 1500, 900, 0.1, 6), "death": (0.3, 200, 60, 0.4, 5),
    "explosion": (0.7, 70, 25, 0.85, 3.5), "ability": (0.3, 400, 900, 0.05, 3), "click": (0.04, 900, 700, 0.2, 5),
}


class Audio:
    def __init__(self, settings):
        self.settings = settings
        self.ok = False
        self.sounds = {}
        self.music_sound = None
        self.menu_music_sound = None
        self.current_music = None
        self.menu_music_title = "PROCEDURAL SYNTH"
        try:
            import pygame
            self.pg = pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 1, 512)
            for i, (name, spec) in enumerate(SPECS.items()):
                self.sounds[name] = pygame.mixer.Sound(buffer=_synth(*spec, seed=i).tobytes())
            self.music_sound = pygame.mixer.Sound(buffer=self._music().tobytes())
            self.menu_music_sound = pygame.mixer.Sound(buffer=self._menu_music().tobytes())
            audio_dir = Path(__file__).resolve().parents[1] / "assets" / "audio"
            candidates = (
                ("menu.mp3", "MENU MUSIC"),
                ("menu.ogg", "MENU MUSIC"),
                ("menu.wav", "MENU MUSIC"),
            )
            for filename, title in candidates:
                track = audio_dir / filename
                if track.is_file():
                    try:
                        self.menu_music_sound = pygame.mixer.Sound(str(track))
                        self.menu_music_title = title
                        break
                    except Exception:
                        pass
            self.ok = True
        except Exception:
            self.ok = False

    def _music(self):
        bpm = 128
        beat = 60 / bpm
        eighth = beat / 2
        bars = 8
        duration = bars * 4 * beat
        sample_count = int(RATE * duration)
        melody = (69, 72, 74, 76, 79, 76, 74, 72, 69, 72, 76, 79, 81, 79, 76, 74,
                  74, 76, 79, 81, 84, 81, 79, 76, 72, 74, 76, 79, 76, 74, 72, 69)
        roots = (38, 45, 47, 43, 38, 47, 43, 45)
        rng = random.Random(84217)
        out = array("h")
        for i in range(sample_count):
            t = i / RATE
            beat_position = t / beat
            beat_index = int(beat_position)
            beat_phase = beat_position - beat_index
            eighth_index = int(t / eighth)
            note_index = eighth_index % len(melody)
            note_phase = (t - eighth_index * eighth) / eighth

            melody_hz = 440 * 2 ** ((melody[note_index] - 69) / 12)
            melody_envelope = min(1.0, note_phase * 18) * math.exp(-4.2 * note_phase)
            melody_wave = (math.sin(2 * math.pi * melody_hz * t) +
                           0.24 * math.sin(4 * math.pi * melody_hz * t))
            bass_hz = 440 * 2 ** ((roots[(beat_index // 4) % len(roots)] - 69) / 12)
            bass = math.sin(2 * math.pi * bass_hz * t) * math.exp(-1.8 * beat_phase)

            kick_phase = t - beat_index * beat
            kick = 0.0
            if kick_phase < 0.20:
                kick = math.sin(2 * math.pi * (82 - 48 * kick_phase / 0.20) * kick_phase)
                kick *= math.exp(-18 * kick_phase)

            snare = 0.0
            if beat_index % 4 in (1, 3) and beat_phase < 0.17:
                snare = (rng.random() * 2 - 1) * math.exp(-24 * beat_phase)

            hat = 0.0
            if eighth_index % 2 and note_phase < 0.035:
                hat = (rng.random() * 2 - 1) * (1 - note_phase / 0.035)

            sample = 0.23 * melody_wave * melody_envelope + 0.28 * bass + 0.48 * kick + 0.14 * snare + 0.035 * hat
            out.append(int(max(-0.95, min(0.95, sample)) * 32767))
        return out

    def _menu_music(self):
        bpm = 124
        beat = 60 / bpm
        eighth = beat / 2
        melody = (76, 79, 83, 86, 83, 79, 76, 79, 74, 78, 81, 86, 81, 78, 74, 78,
                  71, 74, 79, 83, 79, 74, 71, 74, 72, 76, 79, 84, 79, 76, 72, 76)
        roots = (48, 43, 45, 40, 48, 43, 45, 40)
        rng = random.Random(79124)
        out = array("h")
        for i in range(int(RATE * 8 * 4 * beat)):
            t = i / RATE
            beat_position = t / beat
            beat_index = int(beat_position)
            beat_phase = beat_position - beat_index
            eighth_index = int(t / eighth)
            note_phase = (t - eighth_index * eighth) / eighth
            frequency = 440 * 2 ** ((melody[eighth_index % len(melody)] - 69) / 12)
            envelope = min(1.0, note_phase * 15) * math.exp(-3.5 * note_phase)
            lead = math.sin(2 * math.pi * frequency * t) + 0.3 * math.sin(4 * math.pi * frequency * t)
            bass_hz = 440 * 2 ** ((roots[(beat_index // 4) % len(roots)] - 69) / 12)
            bass = math.sin(2 * math.pi * bass_hz * t) * math.exp(-2.4 * beat_phase)
            kick_phase = t - beat_index * beat
            kick = 0.0
            if kick_phase < 0.18:
                kick = math.sin(2 * math.pi * (92 - 52 * kick_phase / 0.18) * kick_phase)
                kick *= math.exp(-20 * kick_phase)
            snare = 0.0
            if beat_index % 4 in (1, 3) and beat_phase < 0.16:
                snare = (rng.random() * 2 - 1) * math.exp(-27 * beat_phase)
            hat = 0.0
            if eighth_index % 2 and note_phase < 0.03:
                hat = (rng.random() * 2 - 1) * (1 - note_phase / 0.03)
            sample = 0.25 * lead * envelope + 0.28 * bass + 0.45 * kick + 0.12 * snare + 0.03 * hat
            out.append(int(max(-0.95, min(0.95, sample)) * 32767))
        return out

    def start_music(self, theme="menu"):
        if not self.ok:
            return
        sound = self.menu_music_sound if theme == "menu" else self.music_sound
        if sound is None:
            return
        if self.current_music is sound:
            self.update_volumes()
            return
        if self.current_music:
            stop = getattr(self.current_music, "stop", None)
            if stop:
                stop()
        self.current_music = sound
        self.current_music.play(loops=-1)
        self.update_volumes()

    def update_volumes(self):
        if self.ok:
            volume = self.settings["master"] * self.settings["music"]
            if self.music_sound:
                self.music_sound.set_volume(volume)
            if self.menu_music_sound:
                self.menu_music_sound.set_volume(volume)

    def play(self, name, vol=1.0):
        s = self.sounds.get(name)
        if s and vol > 0.02:
            s.set_volume(min(1.0, vol * self.settings["master"] * self.settings["sfx"]))
            s.play()
