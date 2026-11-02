"""Minimal stand-in for pygame so UI/render code paths can be smoke-tested headlessly (no real drawing)."""
import sys
import types
from collections import defaultdict

mod = types.ModuleType("pygame")
SRCALPHA = 1
FULLSCREEN, RESIZABLE = 2, 4
KEYDOWN, KEYUP, QUIT, MOUSEMOTION, MOUSEBUTTONDOWN, MOUSEBUTTONUP, VIDEORESIZE = 2, 3, 256, 1024, 1025, 1026, 32769
MOUSEWHEEL, FINGERDOWN, FINGERUP, FINGERMOTION = 1027, 1792, 1793, 1794


class error(Exception):
    pass


class Rect:
    def __init__(self, x=0, y=0, w=0, h=0):
        if hasattr(x, "__len__"):
            x, y, w, h = x
        self.x, self.y, self.w, self.h = x, y, w, h

    width = property(lambda s: s.w)
    height = property(lambda s: s.h)
    left = property(lambda s: s.x)
    top = property(lambda s: s.y)
    right = property(lambda s: s.x + s.w, lambda s, v: setattr(s, "x", v - s.w))
    bottom = property(lambda s: s.y + s.h, lambda s, v: setattr(s, "y", v - s.h))
    centerx = property(lambda s: s.x + s.w / 2, lambda s, v: setattr(s, "x", v - s.w / 2))
    centery = property(lambda s: s.y + s.h / 2, lambda s, v: setattr(s, "y", v - s.h / 2))

    def _set(self, ax, ay, v):
        cx = {"l": 0, "c": .5, "r": 1}[ax]
        cy = {"t": 0, "c": .5, "b": 1}[ay]
        self.x, self.y = v[0] - self.w * cx, v[1] - self.h * cy

    def _get(self, ax, ay):
        return (self.x + self.w * {"l": 0, "c": .5, "r": 1}[ax], self.y + self.h * {"t": 0, "c": .5, "b": 1}[ay])


for _n, (_a, _b) in dict(topleft="lt", midtop="ct", topright="rt", midleft="lc", center="cc", midright="rc",
                         bottomleft="lb", midbottom="cb", bottomright="rb").items():
    setattr(Rect, _n, property(lambda s, a=_a, b=_b: s._get(a, b), lambda s, v, a=_a, b=_b: s._set(a, b, v)))
Rect.collidepoint = lambda s, p: s.x <= p[0] < s.x + s.w and s.y <= p[1] < s.y + s.h
Rect.move = lambda s, dx, dy: Rect(s.x + dx, s.y + dy, s.w, s.h)
Rect.__iter__ = lambda s: iter((s.x, s.y, s.w, s.h))
Rect.__getitem__ = lambda s, i: (s.x, s.y, s.w, s.h)[i]
Rect.__len__ = lambda s: 4


class Surface:
    def __init__(self, size=(1, 1), flags=0):
        self.size = (int(size[0]), int(size[1]))

    def fill(self, *a): pass
    def blit(self, img, dest, *a): return Rect(0, 0, 1, 1)
    def get_width(self): return self.size[0]
    def get_height(self): return self.size[1]
    def get_size(self): return self.size
    def get_rect(self, **kw):
        r = Rect(0, 0, *self.size)
        for k, v in kw.items():
            setattr(r, k, v)
        return r
    def set_at(self, p, c): pass
    def copy(self): return Surface(self.size)
    def set_alpha(self, a): pass


class Font:
    def __init__(self, size): self.size = size
    def render(self, s, aa, color): return Surface((max(1, len(str(s)) * self.size // 2), self.size))


class Sound:
    def __init__(self, buffer=None): pass
    def set_volume(self, v): pass
    def play(self, loops=0): pass


class Clock:
    def tick(self, fps=0): return 16


class Keys(defaultdict):
    def __init__(self): super().__init__(bool)


_display = Surface((1280, 720))
noop = lambda *a, **k: None
mod.__dict__.update(
    SRCALPHA=SRCALPHA, FULLSCREEN=FULLSCREEN, RESIZABLE=RESIZABLE, KEYDOWN=KEYDOWN, KEYUP=KEYUP, QUIT=QUIT,
    MOUSEMOTION=MOUSEMOTION, MOUSEBUTTONDOWN=MOUSEBUTTONDOWN, MOUSEBUTTONUP=MOUSEBUTTONUP, VIDEORESIZE=VIDEORESIZE,
    MOUSEWHEEL=MOUSEWHEEL, FINGERDOWN=FINGERDOWN, FINGERUP=FINGERUP, FINGERMOTION=FINGERMOTION, error=error, Rect=Rect,
    Surface=Surface, init=noop, quit=noop,
    font=types.SimpleNamespace(SysFont=lambda *a, **k: Font(a[1] if len(a) > 1 else 16)),
    display=types.SimpleNamespace(set_mode=lambda *a, **k: _display, set_caption=noop, get_surface=lambda: _display, flip=noop),
    draw=types.SimpleNamespace(**{n: noop for n in ("rect", "line", "lines", "circle", "polygon", "arc", "ellipse")}),
    transform=types.SimpleNamespace(scale=lambda s, size, *a: Surface(size), rotate=lambda s, a: Surface(s.size)),
    key=types.SimpleNamespace(key_code=lambda n: hash(n) % 5000 + 5000, name=lambda k: "x", get_pressed=lambda: Keys()),
    mouse=types.SimpleNamespace(get_pos=lambda: (640, 360), get_pressed=lambda: (0, 0, 0), set_visible=noop),
    event=types.SimpleNamespace(set_grab=noop, get=lambda: []),
    mixer=types.SimpleNamespace(pre_init=noop, init=noop, get_init=lambda: True, Sound=Sound),
    time=types.SimpleNamespace(Clock=Clock),
)
_k = {}
def _getattr(name):
    if name.startswith("K_"):
        return _k.setdefault(name, 1000 + len(_k))
    raise AttributeError(name)
mod.__getattr__ = _getattr


class Event:
    def __init__(self, type, **kw):
        self.type = type
        self.__dict__.update(kw)


mod.Event = Event
mod.event.Event = Event
sys.modules["pygame"] = mod
