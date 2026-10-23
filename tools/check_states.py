"""Many pictures the game can show: does every state of the pack answer what the game knows?
python tools/check_states.py   (run tools/teach_refs.py first: the screen and the score need their references)"""
import json
import os
import random
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))
sys.path.insert(0, os.environ.get("INSPECTOR_DIR", r"D:\code\inspector_platform"))
import numpy as np  # noqa: E402

import moles as M  # noqa: E402
from labeler import generic  # noqa: E402

schema = json.load(open(os.path.join(HERE, "..", "pack", "states.json"), encoding="utf-8"))
engine = generic.Engine(schema, os.path.join(HERE, "..", "pack", "refs"))
clock = [1000.0]
M.time = types.SimpleNamespace(time=lambda: clock[0])
total = bad = 0


def check(img, want, what):
    global total, bad
    values, scores, _f = engine.label(img, {})
    for sid, w in want.items():
        total += 1
        if not (values[sid] in w if isinstance(w, tuple) else values[sid] == w):
            bad += 1
            print("WRONG", sid, "want", w, "got", values[sid], scores[sid], what)


rng = random.Random(5)
for k in range(1500):                                         # playing: moles and bombs at every height, some hit
    clock[0] = 1000 + k * 7.31
    g = M.Game(seed=k)
    g.screen = "playing"
    g._reset()
    g.started = clock[0] - rng.uniform(0, 59)
    g.score, g.missed = rng.randint(0, 80), rng.randint(0, 30)
    want = {"screen": "playing"}
    for i in range(9):
        r = rng.random()
        if r < 0.45:
            want[f"mole{i + 1}"] = "no"
            continue
        kind = "bomb" if r < 0.6 else "mole"
        up = rng.uniform(0.6, 1.6)
        age = rng.uniform(0, up + 2 * M.RISE)                 # rising, up, or going down
        h = {"kind": kind, "t0": clock[0] - age, "up": up, "hit": None}
        if rng.random() < 0.2:
            h["hit"] = clock[0] - rng.uniform(0, 0.2)
        g.holes[i] = h
        height = g._height(h, clock[0])
        if kind == "bomb" or height < 0.05:
            want[f"mole{i + 1}"] = "no"
        elif height >= 0.6 and not h["hit"]:
            want[f"mole{i + 1}"] = "yes"
        else:
            want[f"mole{i + 1}"] = ("yes", "no", None)        # half up, or hit and going down: either is fine
    if rng.random() < 0.3:                                    # "+1" / "-3" floating up
        g.pops = [(clock[0] - rng.uniform(0, 0.6), M.HOLES[rng.randrange(9)][0], M.HOLES[rng.randrange(9)][1] - 150,
                   rng.choice(["+1", "-3"]), rng.choice([(255, 235, 90), (255, 90, 70)]))]
    check(np.asarray(g.draw()), want, f"playing #{k}")

for score in range(0, 100):                                   # the title and the TIME UP card (a round scores far below 100)
    g = M.Game(seed=score)
    check(np.asarray(g.draw()), {"screen": "title", **{f"mole{i}": "no" for i in range(1, 10)}}, "title")
    g.screen, g.score, g.hits, g.missed, g.bombs, g.reactions = "over", score, score + 3, score % 17, score % 5, [0.35]
    check(np.asarray(g.draw()), {"screen": "over", "final_score": score, **{f"mole{i}": "no" for i in range(1, 10)}}, f"over {score}")
print(f"checked {total}, wrong {bad}")
