"""Record the demo GIF: the game while Inspector (already running with the pack) plays it.

    python tools/record_gif.py [--skip 30] [--seconds 16] [--out docs/demo.gif]

It only goes back to the title screen first; Inspector presses START and plays. The clip shows the start, then jumps
--skip seconds into the round (faster by then). The line at the bottom is the game's own tally (hits, missed, bombs
hit, reaction time)."""
import argparse
import io
import json
import os
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

GAME = "http://127.0.0.1:8820"


def get(path):
    with urllib.request.urlopen(GAME + path, timeout=10) as r:
        return r.read()


def font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shot(top, s):
    img = Image.new("RGB", (640, 430), (0, 0, 0))
    img.paste(Image.open(io.BytesIO(get("/snapshot.jpg"))).convert("RGB").resize((640, 360)), (0, 0))
    d = ImageDraw.Draw(img)
    d.text((14, 366), top, font=font(20), fill=(255, 255, 255))
    if s["screen"] == "playing":
        ms = f"{s['reaction_ms'] / 1000:.2f} s" if s["reaction_ms"] else "-"
        d.text((14, 396), f"Inspector: {s['hits']} hit · {s['missed']} missed · {s['bombs']} bombs hit · reaction {ms}",
               font=font(18), fill=(255, 205, 70))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", type=float, default=30, help="seconds of the round left out after the start")
    ap.add_argument("--seconds", type=float, default=16)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "docs", "demo.gif"))
    a = ap.parse_args()
    urllib.request.urlopen(urllib.request.Request(GAME + "/api/command", data=b'{"command": "title"}', method="POST",
                                                  headers={"Content-Type": "application/json"}), timeout=10).read()
    frames, t0, played = [], time.time(), None
    while True:
        s = json.loads(get("/api/state"))
        if s["screen"] == "playing" and played is None:
            played = time.time()
        if played and time.time() - played > a.skip + a.seconds:
            break
        if time.time() - t0 > 30 + a.skip + a.seconds:
            raise SystemExit("Inspector did not start the game: is it running with the pack?")
        if played and 1.5 < time.time() - played < a.skip:     # the calm start of the round is left out
            time.sleep(0.15)
            continue
        top = ("Inspector plays - nobody touches the mouse" if not played or time.time() - played < a.skip
               else f"{int(a.skip)} s in: faster, and bombs")
        frames.append(shot(top if played else "Title: Inspector presses START", s))
        time.sleep(0.15)
    frames += [frames[-1]] * 6
    pal = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pal[0].save(a.out, save_all=True, append_images=pal[1:], duration=220, loop=0, optimize=True)
    print(f"{len(pal)} frames -> {a.out} ({os.path.getsize(a.out) // 1024} KB)")


if __name__ == "__main__":
    main()
