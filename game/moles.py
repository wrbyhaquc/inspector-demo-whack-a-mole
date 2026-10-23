"""Whack-a-mole, drawn as a cartoon picture - a small game in a window of its own, so Inspector can be tried on a screen
it has to watch and click quickly, without any other program.

A round lasts 60 seconds. Moles pop up from the nine holes, faster and faster as the round goes on; a click on one
scores a point, a mole that goes down again unhit is missed. Now and then a bomb pops up instead: clicking it costs
three points. When the time is up, the results and a PLAY AGAIN button show.

Everything is drawn at 1280x720 (window.py shows it at any size and maps the clicks back)."""
import math
import random
import threading
import time

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
ROUND = 60.0
XS, YS = (360, 640, 920), (300, 455, 610)
HOLES = [(x, y) for y in YS for x in XS]                    # hole 1..9, left to right, top to bottom
BUTTON = (490, 470, 300, 100)                               # START / PLAY AGAIN, x y w h
RISE = 0.12                                                 # seconds to come up and to go down


def _font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_BIG, F_MID, F_SMALL, F_BAR = _font(84), _font(40), _font(26), _font(34)
FUR, FUR_DARK, BELLY, NOSE = (150, 95, 55), (112, 70, 40), (214, 176, 132), (240, 130, 150)


class Game:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        self.screen = "title"                               # title / playing / over
        self.best = 0
        self._reset()

    def _reset(self):
        self.holes = [None] * 9                             # {"kind": mole | bomb, "t0", "up", "hit"}
        self.started = time.time()
        self.next_spawn = self.started + 0.8
        self.score = self.hits = self.missed = self.bombs = 0
        self.reactions = []
        self.pops = []                                      # (time, x, y, text, colour) floating "+1" / "-3"

    # ---------------- the model ----------------
    def left(self):
        return max(0.0, ROUND - (time.time() - self.started)) if self.screen == "playing" else 0.0

    def _pace(self):
        """0 at the start of a round, 1 at its end."""
        return min(1.0, (time.time() - self.started) / ROUND)

    def step(self):
        now = time.time()
        with self.lock:
            if self.screen != "playing":
                return
            for i, h in enumerate(self.holes):
                if h and now > h["t0"] + h["up"] + RISE * 2 + (0.25 if h["hit"] else 0):
                    if h["kind"] == "mole" and not h["hit"]:
                        self.missed += 1
                    self.holes[i] = None
            if now >= self.started + ROUND:
                self.screen = "over"
                self.best = max(self.best, self.score)
                return
            if now >= self.next_spawn:
                free = [i for i, h in enumerate(self.holes) if h is None]
                if free:
                    p = self._pace()
                    i = self.rng.choice(free)
                    kind = "bomb" if self.rng.random() < 0.18 else "mole"
                    self.holes[i] = {"kind": kind, "t0": now, "up": (1.7 - 0.6 * p) * self.rng.uniform(0.85, 1.15), "hit": None}
                self.next_spawn = now + (1.4 - 0.5 * self._pace()) * self.rng.uniform(0.6, 1.3)

    def _height(self, h, now):
        """How far up a mole / bomb is: 0..1."""
        t = now - h["t0"]
        if h["hit"]:
            return max(0.0, 1 - (now - h["hit"]) / RISE)
        if t < RISE:
            return t / RISE
        if t < RISE + h["up"]:
            return 1.0
        return max(0.0, 1 - (t - RISE - h["up"]) / RISE)

    def click(self, x, y):
        """A click at (x, y) in the 1280x720 picture."""
        now = time.time()
        with self.lock:
            bx, by, bw, bh = BUTTON
            if self.screen in ("title", "over"):
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    self.screen = "playing"
                    self._reset()
                return
            for i, (hx, hy) in enumerate(HOLES):
                h = self.holes[i]
                if not h or h["hit"] or self._height(h, now) < 0.3:
                    continue
                if abs(x - hx) <= 75 and hy - 130 <= y <= hy + 30:
                    h["hit"] = now
                    if h["kind"] == "mole":
                        self.score += 1
                        self.hits += 1
                        self.reactions.append(now - h["t0"])
                        self.pops.append((now, hx, hy - 150, "+1", (255, 235, 90)))
                    else:
                        self.score = max(0, self.score - 3)
                        self.bombs += 1
                        self.pops.append((now, hx, hy - 150, "-3", (255, 90, 70)))
                    return

    def command(self, cmd):
        """For the recorder and the demo: start / title."""
        with self.lock:
            if cmd == "start":
                self.screen = "playing"
                self._reset()
            elif cmd == "title":
                self.screen = "title"
            else:
                raise ValueError(f"unknown command: {cmd}")

    def state(self):
        now = time.time()
        with self.lock:
            return {"screen": self.screen, "left": round(self.left(), 1), "score": self.score, "hits": self.hits,
                    "missed": self.missed, "bombs": self.bombs, "best": self.best,
                    "reaction_ms": round(1000 * sum(self.reactions) / len(self.reactions)) if self.reactions else None,
                    "holes": [None if not h else (h["kind"] + ("_hit" if h["hit"] else "")) for h in self.holes],
                    "up": [bool(h and not h["hit"] and self._height(h, now) >= 0.5 and h["kind"] == "mole") for h in self.holes]}

    # ---------------- the picture ----------------
    def draw(self):
        with self.lock:
            return self._draw(time.time())

    def _mole(self, img, x, y, up, hit, t):
        """A mole (or nothing) rising from the hole at (x, y): only what is above the hole's edge shows."""
        layer = Image.new("RGBA", (180, 190), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        top = 25 + (1 - up) * 160
        d.ellipse((30, top, 150, top + 175), fill=FUR)                      # body
        d.ellipse((52, top + 70, 128, top + 175), fill=BELLY)               # belly
        d.ellipse((38, top + 6, 62, top + 30), fill=FUR_DARK)               # ears
        d.ellipse((118, top + 6, 142, top + 30), fill=FUR_DARK)
        if hit:
            for ex in (68, 112):                                            # dizzy: x eyes
                d.line((ex - 8, top + 40, ex + 8, top + 56), fill=(30, 20, 15), width=4)
                d.line((ex - 8, top + 56, ex + 8, top + 40), fill=(30, 20, 15), width=4)
        else:
            for ex in (68, 112):
                d.ellipse((ex - 9, top + 38, ex + 9, top + 58), fill=(255, 255, 255))
                d.ellipse((ex - 4, top + 44, ex + 5, top + 55), fill=(20, 15, 10))
        d.ellipse((80, top + 60, 100, top + 76), fill=NOSE)                 # nose
        d.line((90, top + 76, 90, top + 86), fill=(80, 50, 30), width=3)
        d.rectangle((78, top + 86, 102, top + 98), fill=(250, 250, 245))    # teeth
        mask = Image.new("L", layer.size, 0)
        ImageDraw.Draw(mask).rectangle((0, 0, 180, 158), fill=255)          # cut at the hole's edge
        img.paste(layer, (int(x - 90), int(y - 152)), Image.composite(layer, Image.new("RGBA", layer.size), mask))

    def _bomb(self, img, x, y, up, hit, t):
        layer = Image.new("RGBA", (180, 190), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        top = 40 + (1 - up) * 160
        if hit:                                                             # bang
            for k in range(12):
                a = k * math.pi / 6
                d.line((90, top + 60, 90 + math.cos(a) * 80, top + 60 + math.sin(a) * 70), fill=(255, 150, 40), width=10)
            d.ellipse((40, top + 15, 140, top + 105), fill=(255, 220, 80))
        else:
            d.ellipse((35, top + 20, 145, top + 130), fill=(38, 38, 44))
            d.ellipse((60, top + 40, 80, top + 60), fill=(110, 110, 120))
            d.rectangle((80, top + 6, 100, top + 24), fill=(90, 90, 95))
            d.line((90, top + 6, 104, top - 14), fill=(200, 180, 140), width=4)
            if int(t * 10) % 2 == 0:
                d.ellipse((98, top - 26, 114, top - 10), fill=(255, 200, 40))
        mask = Image.new("L", layer.size, 0)
        ImageDraw.Draw(mask).rectangle((0, 0, 180, 158), fill=255)
        img.paste(layer, (int(x - 90), int(y - 152)), Image.composite(layer, Image.new("RGBA", layer.size), mask))

    def _draw(self, now):
        img = Image.new("RGB", (W, H), (95, 170, 70))
        d = ImageDraw.Draw(img, "RGBA")
        rng = random.Random(3)
        for _ in range(220):                                                # tufts of grass (fixed places)
            gx, gy = rng.randint(0, W), rng.randint(100, H)
            d.line((gx, gy, gx - 3, gy - 10), fill=(70, 140, 55), width=2)
            d.line((gx, gy, gx + 3, gy - 9), fill=(70, 140, 55), width=2)
        # the top bar: score, missed, time
        d.rectangle((0, 0, W, 90), fill=(28, 38, 78))
        if self.screen == "playing":
            d.text((40, 24), f"SCORE {self.score}", font=F_BAR, fill=(255, 255, 255))
            d.text((470, 24), f"MISSED {self.missed}", font=F_BAR, fill=(255, 190, 120))
            d.text((1020, 24), f"TIME {int(math.ceil(self.left()))}", font=F_BAR, fill=(160, 220, 255))
        else:
            d.text((40, 24), "WHACK-A-MOLE", font=F_BAR, fill=(255, 255, 255))
            d.text((1000, 24), f"BEST {self.best}", font=F_BAR, fill=(160, 220, 255))
        # holes and what is in them
        for i, (x, y) in enumerate(HOLES):
            d.ellipse((x - 95, y - 30, x + 95, y + 45), fill=(196, 168, 120))    # the mound
            d.ellipse((x - 75, y - 22, x + 75, y + 26), fill=(46, 32, 26))       # the hole
            h = self.holes[i] if self.screen == "playing" else None
            if h:
                up = self._height(h, now)
                (self._mole if h["kind"] == "mole" else self._bomb)(img, x, y, up, h["hit"], now)
                d = ImageDraw.Draw(img, "RGBA")
            d.chord((x - 95, y - 10, x + 95, y + 45), 0, 180, fill=(196, 168, 120))   # the mound's front edge
            d.arc((x - 75, y - 22, x + 75, y + 26), 0, 180, fill=(120, 95, 65), width=4)
        for t0, x, y, text, col in [p for p in self.pops if now - p[0] < 0.7]:
            d.text((x - 24, y - (now - t0) * 80), text, font=F_MID, fill=col)
        self.pops = [p for p in self.pops if now - p[0] < 0.7]
        # title / results with the button
        bx, by, bw, bh = BUTTON
        if self.screen == "title":
            d.rounded_rectangle((300, 150, 980, 610), 28, fill=(255, 250, 235, 235))
            d.text((640, 245), "WHACK-A-MOLE", font=F_BIG, fill=(40, 110, 60), anchor="mm")
            d.text((640, 340), "Hit the moles, not the bombs.", font=F_SMALL, fill=(80, 80, 80), anchor="mm")
            d.text((640, 380), "60 seconds. It gets faster.", font=F_SMALL, fill=(80, 80, 80), anchor="mm")
            d.rounded_rectangle((bx, by, bx + bw, by + bh), 20, fill=(46, 160, 80))
            d.text((bx + bw / 2, by + bh / 2), "START", font=F_MID, fill=(255, 255, 255), anchor="mm")
        elif self.screen == "over":
            d.rectangle((0, 90, W, H), fill=(10, 15, 30, 150))
            d.rounded_rectangle((300, 130, 980, 610), 28, fill=(255, 250, 235, 245))
            d.text((640, 195), "TIME UP", font=F_BIG, fill=(180, 60, 40), anchor="mm")
            ms = round(1000 * sum(self.reactions) / len(self.reactions)) if self.reactions else 0
            for k, (label, v) in enumerate((("Score", self.score), ("Moles hit", self.hits), ("Missed", self.missed),
                                            ("Bombs hit", self.bombs), ("Average reaction", f"{ms} ms"))):
                d.text((420, 270 + k * 36), label, font=F_SMALL, fill=(70, 70, 70))
                d.text((860, 270 + k * 36), str(v), font=F_SMALL, fill=(30, 30, 30), anchor="ra")
            d.rounded_rectangle((bx, by, bx + bw, by + bh), 20, fill=(40, 110, 200))
            d.text((bx + bw / 2, by + bh / 2), "PLAY AGAIN", font=F_MID, fill=(255, 255, 255), anchor="mm")
        return img
