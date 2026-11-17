#!/usr/bin/env python3
"""Localhost web GUI for fizzctl (Redragon K617 Fizz).

Serves index.html and runs `fizzctl` with checked arguments.
Run:  python3 server.py   then open http://127.0.0.1:8617
"""
import json
import re
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8617
HERE = Path(__file__).resolve().parent
FIZZCTL = shutil.which("fizzctl") or str(Path.home() / ".local/bin/fizzctl")
TIMEOUT = 30
HEX = re.compile(r"^[0-9a-fA-F]{6}$")
ANIMATIONS = ["solid", "blink", "pulse", "chase", "wave", "rainbow", "drop"]
DEVICE_LOCK = threading.Lock()


class BadRequest(Exception):
    pass


def load_tables():
    """Read key and effect names from fizzctl's own Python environment."""
    with open(FIZZCTL) as f:
        shebang = f.readline()
    py = shebang[2:].strip() if shebang.startswith("#!") else sys.executable
    code = (
        "import json\n"
        "from fizzctl.protocol import LED_INDEX\n"
        "from fizzctl.macro import NAME_TO_HID\n"
        "from fizzctl.effects import EFFECT_ID, EFFECT_DEFAULTS\n"
        "print(json.dumps({'paint_keys': list(LED_INDEX.values()),"
        "'macro_keys': list(NAME_TO_HID),"
        "'effects': [[n, (s + 1 if s else 0), b] for n, (s, b) in EFFECT_DEFAULTS.items() if n in EFFECT_ID]}))\n"
    )
    out = subprocess.run([py, "-I", "-c", code], capture_output=True, text=True, timeout=TIMEOUT)
    if out.returncode != 0:
        sys.exit(f"could not read fizzctl tables:\n{out.stderr}")
    t = json.loads(out.stdout)
    t["animations"] = ANIMATIONS
    return t


TABLES = load_tables()
EFFECT_NAMES = {e[0] for e in TABLES["effects"]}


def color(v):
    v = str(v).lstrip("#")
    if not HEX.match(v):
        raise BadRequest(f"bad colour {v!r}: need 6 hex digits")
    return v.lower()


def num(v, lo, hi, name):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise BadRequest(f"{name} must be a whole number")
    if not lo <= n <= hi:
        raise BadRequest(f"{name} must be {lo}..{hi}")
    return str(n)


def opt_num(d, key, lo, hi, flag):
    v = d.get(key)
    return [] if v in (None, "") else [flag, num(v, lo, hi, key)]


def build(action, d):
    """Turn a request into a fizzctl argument list. Raises BadRequest."""
    if action == "rgb":
        return ["rgb", *opt_num(d, "brightness", 0, 4, "-b"), "--", color(d.get("color"))]

    if action == "effect":
        name = d.get("name")
        if name not in EFFECT_NAMES:
            raise BadRequest(f"unknown effect {name!r}")
        args = ["effect"]
        if d.get("color"):
            args += ["-c", color(d["color"])]
        args += opt_num(d, "speed", 1, 5, "-s") + opt_num(d, "brightness", 0, 4, "-b")
        return args + ["--", name]

    if action == "paint":
        keys = d.get("keys")
        if not isinstance(keys, dict) or not keys:
            raise BadRequest("no keys to paint")
        specs = []
        for k, c in keys.items():
            if k not in TABLES["paint_keys"]:
                raise BadRequest(f"unknown key {k!r}")
            specs.append(f"{k}={color(c)}")
        return ["paint", "--", *specs]

    if action == "animate":
        name = d.get("name")
        if name not in ANIMATIONS:
            raise BadRequest(f"unknown animation {name!r}")
        args = ["animate", "--daemon"]
        if d.get("color"):
            args += ["-c", color(d["color"])]
        if d.get("speed") not in (None, ""):
            try:
                s = float(d["speed"])
            except (TypeError, ValueError):
                raise BadRequest("speed must be a number")
            if not 0.1 <= s <= 10:
                raise BadRequest("speed must be 0.1..10")
            args += ["-s", str(s)]
        args += opt_num(d, "fps", 1, 60, "-f")
        return args + ["--", name]

    if action == "animate-stop":
        return ["animate", "stop"]

    if action == "macro":
        key = d.get("key")
        if key not in TABLES["macro_keys"]:
            raise BadRequest(f"unknown key {key!r}")
        text = d.get("text")
        if not isinstance(text, str) or not text or len(text) > 200:
            raise BadRequest("macro text must be 1..200 characters")
        args = ["macro", "-k", key]
        args += opt_num(d, "delay_ms", 0, 5000, "--delay-ms")
        args += opt_num(d, "cycles", 1, 255, "--cycles")
        if d.get("until_released"):
            args.append("--until-released")
        return args + ["--", text]

    if action == "macro-read":
        return ["macro", "--read"]
    if action == "macro-remove-all":
        return ["macro", "--remove-all"]
    if action == "restore":
        return ["restore"]

    raise BadRequest(f"unknown action {action!r}")


def run(args):
    with DEVICE_LOCK:
        try:
            p = subprocess.run([FIZZCTL, *args], capture_output=True, text=True,
                               timeout=TIMEOUT, stdin=subprocess.DEVNULL)
            out, err, code = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired:
            out, err, code = "", f"fizzctl timed out after {TIMEOUT}s", -1
    hint = ""
    text = (out + err).lower()
    if code != 0 and ("udev" in text or "permission" in text or "no device" in text
                      or "not found" in text):
        hint = "Keyboard not reachable. Is it plugged in? If so, run once: sudo fizzctl setup-udev"
    return {"cmd": "fizzctl " + " ".join(args), "code": code,
            "stdout": out, "stderr": err, "hint": hint}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/info":
            self._send(200, TABLES)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        # Block other websites from driving the keyboard via the browser.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            return self._send(403, {"error": "bad origin"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._send(415, {"error": "send application/json"})
        if not self.path.startswith("/api/"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
            if not isinstance(data, dict):
                raise BadRequest("body must be a JSON object")
            args = build(self.path[len("/api/"):], data)
        except (BadRequest, json.JSONDecodeError, ValueError) as e:
            return self._send(400, {"error": str(e)})
        result = run(args)
        self._send(200 if result["code"] == 0 else 500, result)

    def log_message(self, fmt, *a):
        sys.stderr.write("%s\n" % (fmt % a))


if __name__ == "__main__":
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        if e.errno == 98:
            sys.exit(f"Port {PORT} is already in use: the GUI is probably already running.\n"
                     f"Open http://{HOST}:{PORT}, or stop the other copy with:  fuser -k {PORT}/tcp")
        raise
    print(f"fizzctl GUI on http://{HOST}:{PORT}  (Ctrl+C to quit)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
