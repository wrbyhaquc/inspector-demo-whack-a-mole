"""The whack-a-mole game in a window of its own (Windows).

    python game/window.py [--scale 0.75] [--fps 30] [--seed 1] [--port 8820]

The window's title is "Whack-a-Mole - Inspector demo"; in Inspector add it under
Sources › + Add source › App window. It takes clicks both ways Inspector can send them: posted to the window in the
background (the real mouse stays put) or with the real mouse. A click's position is read from the click itself and
mapped back to the 1280x720 picture, whatever size the window has.

Also, only on this computer:
  http://127.0.0.1:8820/api/state      the game's own numbers (for checking: Inspector only sees the picture)
  http://127.0.0.1:8820/snapshot.jpg   the picture
  POST /api/command {"command": "start" | "title"}"""
import argparse
import ctypes
import ctypes.wintypes as W
import io
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moles import Game, H as GH, W as GW  # noqa: E402

TITLE = "Whack-a-Mole - Inspector demo"
u32, g32, k32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
WM_DESTROY, WM_PAINT, WM_ERASEBKGND, WM_TIMER, WM_LBUTTONDOWN, WM_SIZE = 0x0002, 0x000F, 0x0014, 0x0113, 0x0201, 0x0005
WS_OVERLAPPEDWINDOW, WS_VISIBLE, CW_USEDEFAULT = 0x00CF0000, 0x10000000, -2147483648
u32.DefWindowProcW.restype = LRESULT
u32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", W.HINSTANCE), ("hIcon", W.HICON), ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
                ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", W.HDC), ("fErase", W.BOOL), ("rcPaint", W.RECT), ("fRestore", W.BOOL), ("fIncUpdate", W.BOOL),
                ("rgbReserved", ctypes.c_byte * 32)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD), ("biBitCount", W.WORD),
                ("biCompression", W.DWORD), ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG),
                ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]


class GameWindow:
    def __init__(self, game, scale, fps):
        self.game, self.fps = game, fps
        self.frame = game.draw()
        self.jpeg = b""
        self.lock = threading.Lock()
        self._proc = WNDPROC(self._wndproc)                 # kept: Windows calls it for as long as the window lives
        hinst = k32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, hCursor=u32.LoadCursorW(None, ctypes.c_void_p(32512)),
                       lpszClassName="InspectorWhackAMole")
        u32.RegisterClassW(ctypes.byref(wc))
        r = W.RECT(0, 0, int(GW * scale), int(GH * scale))
        u32.AdjustWindowRect(ctypes.byref(r), WS_OVERLAPPEDWINDOW, False)
        u32.CreateWindowExW.restype = W.HWND
        self.hwnd = u32.CreateWindowExW(0, "InspectorWhackAMole", TITLE, WS_OVERLAPPEDWINDOW | WS_VISIBLE, CW_USEDEFAULT,
                                        CW_USEDEFAULT, r.right - r.left, r.bottom - r.top, None, None, hinst, None)
        u32.SetTimer(self.hwnd, 1, int(1000 / fps), None)

    @staticmethod
    def _client(hwnd):
        r = W.RECT()
        u32.GetClientRect(hwnd, ctypes.byref(r))
        return max(1, r.right), max(1, r.bottom)

    def _wndproc(self, hwnd, msg, wp, lp):
        if msg == WM_TIMER:
            self.game.step()
            img = self.game.draw()
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=85)
            with self.lock:
                self.frame, self.jpeg = img, buf.getvalue()
            u32.InvalidateRect(hwnd, None, False)
            return 0
        if msg == WM_PAINT:
            ps = PAINTSTRUCT()
            hdc = u32.BeginPaint(hwnd, ctypes.byref(ps))
            cw, ch = self._client(hwnd)
            with self.lock:
                img = self.frame
            img = img.resize((cw, ch), Image.BILINEAR) if (cw, ch) != img.size else img
            bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), cw, -ch, 1, 24, 0, 0, 0, 0, 0, 0)
            stride = (cw * 3 + 3) & ~3
            raw = img.tobytes("raw", "BGR", stride, 1)       # rows padded to 4 bytes, top to bottom
            g32.StretchDIBits(hdc, 0, 0, cw, ch, 0, 0, cw, ch, raw, ctypes.byref(bmi), 0, 0x00CC0020)
            u32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_LBUTTONDOWN:
            x, y = ctypes.c_short(lp & 0xFFFF).value, ctypes.c_short((lp >> 16) & 0xFFFF).value
            cw, ch = self._client(hwnd)
            self.game.click(x * GW / cw, y * GH / ch)
            return 0
        if msg == WM_DESTROY:
            u32.PostQuitMessage(0)
            return 0
        return u32.DefWindowProcW(hwnd, msg, wp, lp)

    def run(self):
        m = W.MSG()
        while u32.GetMessageW(ctypes.byref(m), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(m))
            u32.DispatchMessageW(ctypes.byref(m))


def serve(game, win, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, dict):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/state":
                return self._send(200, game.state())
            if path == "/snapshot.jpg":
                with win.lock:
                    return self._send(200, win.jpeg, "image/jpeg")
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/api/command":
                return self._send(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                game.command(body.get("command"))
            except (ValueError, TypeError) as e:
                return self._send(400, {"ok": False, "error": str(e)})
            self._send(200, {"ok": True, "state": game.state()})

    ThreadingHTTPServer.allow_reuse_address = False
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        print(f"Port {port} is in use: the game runs without its state page", flush=True)
        return
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description="Whack-a-mole in a window, for trying Inspector on a screen")
    ap.add_argument("--scale", type=float, default=0.75, help="window size: 1 = 1280x720")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--port", type=int, default=8820, help="the state page (0 = none)")
    a = ap.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # real pixels: what Inspector captures is what is drawn
    except (AttributeError, OSError):
        pass
    game = Game(seed=a.seed)
    win = GameWindow(game, a.scale, a.fps)
    if a.port:
        serve(game, win, a.port)
    print(f"Whack-a-mole: window \"{TITLE}\"" + (f", state http://127.0.0.1:{a.port}/api/state" if a.port else ""), flush=True)
    win.run()


if __name__ == "__main__":
    main()
