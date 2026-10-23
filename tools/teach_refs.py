"""Make the pack's reference pictures from the game's own drawing, the way one would teach them on the state page: the
START and the PLAY AGAIN buttons (the screen state), and every digit of the score on the TIME UP card.

    python tools/teach_refs.py        -> pack/refs/meta/rule_templates/<state>/  (build.py copies them into the design)"""
import json
import os
import shutil
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))
sys.path.insert(0, os.environ.get("INSPECTOR_DIR", r"D:\code\inspector_platform"))
import numpy as np  # noqa: E402

import moles as M  # noqa: E402
from labeler import generic  # noqa: E402

OUT = os.path.join(HERE, "..", "pack", "refs")
STATES = {s["id"]: s for s in json.load(open(os.path.join(HERE, "..", "pack", "states.json"), encoding="utf-8"))["states"]}
clock = [1000.0]
M.time = types.SimpleNamespace(time=lambda: clock[0])         # the game's clock only


def over(score, **kw):
    g = M.Game(seed=1)
    g.screen, g.score, g.hits, g.missed, g.bombs = "over", score, kw.get("hits", score), kw.get("missed", 3), kw.get("bombs", 1)
    g.reactions = [0.4]
    return g


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    n = 0
    st = STATES["screen"]
    box = generic._box(st, st["source"]["params"]["roi"])
    for value, g in (("title", M.Game(seed=1)), ("over", over(17)), ("over", over(48, missed=12, bombs=4))):
        time.sleep(0.002)                                     # the platform names a reference by the millisecond
        generic.tpl_add(OUT, "screen", value, np.asarray(g.draw()), box, f"game:{value}:{g.score}")
        n += 1
    st = STATES["final_score"]
    box = generic._box(st, st["source"]["params"]["roi"])
    seen = {}
    for score in (10, 23, 45, 67, 89, 31, 52, 74, 96, 18, 30, 0):
        img = np.asarray(over(score).draw())
        gs = generic.glyphs(img, box, st["source"]["params"]["colors"])
        assert len(gs) == len(str(score)), (score, len(gs))
        for (b, _m), ch in zip(gs, str(score)):
            if seen.get(ch, 0) < 2:                           # two examples of each digit
                time.sleep(0.002)
                generic.glyph_add(OUT, "final_score", ch, img, b, f"game:over:{score}")
                seen[ch] = seen.get(ch, 0) + 1
                n += 1
    print(f"{n} references -> {os.path.abspath(OUT)}  digits: {''.join(sorted(seen))}")


if __name__ == "__main__":
    main()
