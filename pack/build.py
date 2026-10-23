"""Put the whack-a-mole pack's design into a running Inspector Studio through its API (every part is checked by
Inspector when it is saved), in English or Traditional Chinese.

    python pack/build.py --lang en    --url http://127.0.0.1:8772 --design <the pack's design folder>
    python pack/build.py --lang zh-TW --url http://127.0.0.1:8773 --design <...>

What it makes (the ids are the same in both languages; only the words differ):
  source        MOLE-GAME: the game's window ("App window"), clicked in the background (project.json "sources")
  run           look every 0.3 s, up to 60 clicks a minute, act on the first look (project.json "run"; this
                computer's settings win)
  states        pack/states.json - which screen it is, a mole in each of the nine holes, the final score; all
                judged by screen rules (no training); the references they need come from pack/refs/
  buttons       hole_1 .. hole_9, start, again: where to click
  setting       keep_playing: start a new round by itself
  sub-script    start_round (the panel's button)
  main script   Mole hunter: a mole in a hole -> click it (bombs are left alone); the title -> START; time up ->
                tell the score, then PLAY AGAIN
  panel         the game and how it is going, start a round, stop, keep playing, notifications"""
import argparse
import json
import os
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "MOLE-GAME"
TITLE = "Whack-a-Mole - Inspector demo"
XS, YS = (360, 640, 920), (300, 455, 610)
HOLES = [(x, y) for y in YS for x in XS]

T = {
    "en": {
        "project": ("Whack-a-mole", "A small game in a window: Inspector watches the screen and clicks the moles, never the bombs.",
                    {"device": "game", "item": "item"}),
        "states": {"screen": ("Screen", "Which screen the game shows: the START button (title), the PLAY AGAIN button (time up), or neither (playing).",
                              {"title": "Title", "playing": "Playing", "over": "Time up"}, "The button"),
                   "mole": ("Mole in hole {n}", "Brown fur above hole {n} (holes 1-3 are the top row, left to right). A bomb is black: not a mole.",
                            {"yes": "Yes", "no": "No"}, "Above hole {n}"),
                   "final_score": ("Final score", "The score on the TIME UP card.", {}, "Score on the card")},
        "source": "Whack-a-mole game",
        "buttons": {"hole": "Hole {n}", "start": "START", "again": "PLAY AGAIN"},
        "setting": ("Keep playing", "Start a new round by itself (from the title, and after time up)."),
        "sub": ("Start a round", "Started a round"),
        "main": ("Mole hunter", "Clicks every mole that pops up, never a bomb; starts the rounds.", "Playing", "Waiting for a mole"),
        "rules": {"hole": "Mole in hole {n}: click it", "start": "Title: press START", "again": "Time up: report, play again",
                  "again_note": "Round over: {final_score} points"},
        "panel": {"title": "Whack-a-mole", "pages": {"main": "Now", "notify": "Notifications"},
                  "sources_help": "Start the game first (python game/window.py), then pick its window: Whack-a-Mole - Inspector demo",
                  "blocks": {"w_devices": ("How the game is going", ""),
                             "play": ("Play", "Start a round now, or stop. With Keep playing on, a new round starts by itself."),
                             "w_log": ("What happened lately", ""),
                             "w_chat": ("Notifications and commands", "Get each round's score on your phone.")},
                  "controls": {"start_now": "Start a round", "stop_now": "Stop", "keep_playing": "Keep playing"}},
    },
    "zh-TW": {
        "project": ("打地鼠", "視窗裡的小遊戲:Inspector 看著畫面點地鼠,炸彈一個都不碰。", {"device": "遊戲", "item": "項目"}),
        "states": {"screen": ("畫面", "遊戲現在是哪個畫面:看得到 START 按鈕(開始畫面)、PLAY AGAIN 按鈕(時間到),或兩個都沒有(遊戲中)。",
                              {"title": "開始畫面", "playing": "遊戲中", "over": "時間到"}, "按鈕"),
                   "mole": ("第 {n} 洞有地鼠", "第 {n} 洞上方有棕色的毛(1~3 洞是最上排,由左到右)。炸彈是黑色的,不算地鼠。",
                            {"yes": "有", "no": "沒有"}, "第 {n} 洞上方"),
                   "final_score": ("最後得分", "TIME UP 卡片上的分數。", {}, "卡片上的分數")},
        "source": "打地鼠遊戲",
        "buttons": {"hole": "第 {n} 洞", "start": "START", "again": "PLAY AGAIN"},
        "setting": ("一直玩下去", "自己開始新的一局(開始畫面、時間到之後)。"),
        "sub": ("開始一局", "已開始一局"),
        "main": ("地鼠獵人", "點每一隻冒出來的地鼠,炸彈一個都不碰;自己開始每一局。", "遊戲中", "等地鼠出來"),
        "rules": {"hole": "第 {n} 洞有地鼠:點它", "start": "開始畫面:按 START", "again": "時間到:回報分數、再玩一局",
                  "again_note": "這一局結束:{final_score} 分"},
        "panel": {"title": "打地鼠", "pages": {"main": "現況", "notify": "通知"},
                  "sources_help": "先啟動遊戲(python game/window.py),再選它的視窗:Whack-a-Mole - Inspector demo",
                  "blocks": {"w_devices": ("遊戲現況", ""),
                             "play": ("玩", "現在開始一局,或停下來。打開「一直玩下去」,每一局結束後會自己開始下一局。"),
                             "w_log": ("最近發生的事", ""),
                             "w_chat": ("通知與指令", "每一局的分數傳到手機。")},
                  "controls": {"start_now": "開始一局", "stop_now": "停下來", "keep_playing": "一直玩下去"}},
    },
}


def call(base, method, path, body, lang):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Lang": lang})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path}: {e.code} {e.read().decode('utf-8', 'replace')}")


def state(sid, op, value, secs=None):
    c = {"state": sid, "op": op, "value": value}
    if secs:
        c["for"] = secs
    return c


def tap(button):
    return {"type": "tap", "target": {"button": button}}


KEEP = {"kind": "compare", "left": {"setting": "keep_playing"}, "op": "is", "right": 1}


def states(t):
    out = json.load(open(os.path.join(HERE, "states.json"), encoding="utf-8"))["states"]
    for s in out:
        key = "mole" if s["id"].startswith("mole") else s["id"]
        n = s["id"][4:] if key == "mole" else ""
        name, desc, classes, roi = t["states"][key]
        s["name"], s["description"] = name.format(n=n), desc.format(n=n)
        for c in s.get("classes") or []:
            c["name"] = classes[c["value"]]
        s["rois"][0]["name"] = roi.format(n=n)
    return out


def main_script(t):
    r = t["rules"]
    name, desc, sit, nothing = t["main"]
    rules = [{"id": f"hole{n}", "name": r["hole"].format(n=n), "enabled": True, "cooldown": 0.4,
              "when": [[state(f"mole{n}", "is", "yes")]], "do": [tap(f"hole_{n}")]} for n in range(1, 10)]
    rules += [{"id": "start", "name": r["start"], "enabled": True, "cooldown": 5,
               "when": [[state("screen", "is", "title", 2), KEEP]], "do": [tap("start")]},
              {"id": "again", "name": r["again"], "enabled": True, "cooldown": 10,
               "when": [[state("screen", "is", "over", 4), KEEP]],
               "do": [{"type": "notify", "text": r["again_note"]}, tap("again")]}]
    return {"id": "mole_hunter", "name": name, "enabled": True, "devices": {"*": "off", SRC: "live"}, "description": desc,
            "otherwise": {"type": "none", "text": nothing}, "initial": "playing",
            "situations": [{"id": "playing", "name": sit, "rules": rules}]}


def panel(t):
    p = t["panel"]
    b, c = p["blocks"], p["controls"]

    def block(bid, page, items=(), widget=None):
        out = {"id": bid, "title": b[bid][0], "help": b[bid][1], "items": list(items), "page": page}
        if widget:
            out["widget"] = widget
        return out

    return {
        "title": p["title"], "devices": [SRC],
        "pages": [{"id": k, "title": v} for k, v in p["pages"].items()],
        "sources": {"kinds": ["window/*"], "help": p["sources_help"], "new_mode": "live"},
        "blocks": [
            block("w_devices", "main", widget={"kind": "devices", "show_step": True, "show_alerts": True, "show_image": True}),
            block("play", "main", ["start_now", "stop_now", "keep_playing"]),
            block("w_log", "main", widget={"kind": "log", "limit": 20, "panel_changes": True}),
            block("w_chat", "notify", widget={"kind": "chat", "setup": True, "pair": True}),
        ],
        "controls": [
            {"id": "start_now", "label": c["start_now"], "type": "action", "scope": "device", "bind": {"kind": "act_sub", "sub": "start_round"}},
            {"id": "stop_now", "label": c["stop_now"], "type": "action", "scope": "device", "bind": {"kind": "act_stop"}},
            {"id": "keep_playing", "label": c["keep_playing"], "type": "toggle", "scope": "global",
             "bind": {"kind": "setting", "setting": "keep_playing"}},
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(T), default="en")
    ap.add_argument("--url", default="http://127.0.0.1:8772")
    ap.add_argument("--design", help="the pack's design folder: the project's name, words and the game window (project.json), "
                                     "and the reference pictures the states need")
    a = ap.parse_args()
    t, lang, b = T[a.lang], a.lang, a.url.rstrip("/")
    if a.design:
        p = os.path.join(a.design, "project.json")
        pj = json.load(open(p, encoding="utf-8"))
        pj.update({"name": t["project"][0], "description": t["project"][1], "words": t["project"][2],
                   "screen": {"width": 1280, "height": 720}, "plugins": [],
                   # a fast game: look every 0.3 s, up to 60 clicks a minute, act on the first look
                   # (Inspector: project.json "run")
                   "run": {"interval": 0.3, "max_per_min": 60, "confirm": 1},
                   # the window this pack watches, made so on a new computer (Inspector: project.json "sources")
                   "sources": {SRC: {"kind": "window/any", "name": t["source"],
                                     "params": {"title": TITLE, "title_mode": "exact", "fit": "contain"}}}})
        with open(p, "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=1)
        pk = os.path.join(os.path.dirname(os.path.abspath(a.design)), "pack.json")      # the pack's own name too
        if os.path.exists(pk):
            info = json.load(open(pk, encoding="utf-8"))
            info.update({"name": t["project"][0], "description": t["project"][1], "license": "Apache-2.0",
                         "homepage": "https://github.com/wrbyhaquc/inspector-demo-whack-a-mole"})
            with open(pk, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=1)
        dst = os.path.join(a.design, "meta", "rule_templates")         # the taught references (tools/teach_refs.py)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(os.path.join(HERE, "refs", "meta", "rule_templates"), dst)
    call(b, "POST", "/api/states", {"states": states(t), "note": "whack-a-mole"}, lang)
    bt = t["buttons"]
    for n, (x, y) in enumerate(HOLES, 1):
        call(b, "POST", "/api/buttons", {"button": {"id": f"hole_{n}", "label": bt["hole"].format(n=n), "x": x, "y": y - 60}}, lang)
    for bid in ("start", "again"):
        call(b, "POST", "/api/buttons", {"button": {"id": bid, "label": bt[bid], "x": 640, "y": 520}}, lang)
    s = t["setting"]
    call(b, "POST", "/api/settings", {"settings": [{"id": "keep_playing", "label": s[0], "description": s[1], "type": "bool",
                                                    "scope": "shared", "default": True}]}, lang)
    name, text = t["sub"]
    call(b, "POST", "/api/subscripts", {"sub": {"id": "start_round", "name": name, "description": name, "timeout": 30, "params": [],
                                                "say": name, "steps": [tap("start"), {"type": "notify", "text": text}],   # START and PLAY AGAIN are in the same place
                                                "cleanup": []}, "note": "whack-a-mole"}, lang)
    call(b, "POST", "/api/scripts", {"script": main_script(t), "note": "whack-a-mole"}, lang)
    call(b, "POST", "/api/panel/definition", {"panel": panel(t)}, lang)
    print(f"done ({lang}): states, 11 buttons, setting, sub-script, main script, panel")


if __name__ == "__main__":
    main()
