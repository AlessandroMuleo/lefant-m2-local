"""Local web page for the robot.

    python web_app.py            -> this PC only: http://127.0.0.1:8765
    python web_app.py --lan      -> also from the phone on the same wifi
                                    (needs "web_pin" in config.json)
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from lefant import LefantRobot, RobotError

HERE = Path(__file__).resolve().parent
app = FastAPI(title="Lefant M2")
_robot: LefantRobot | None = None
PIN: str | None = None


def robot() -> LefantRobot:
    global _robot
    if _robot is None:
        _robot = LefantRobot()
    return _robot


# wrong PIN: 5 tries per address, then 15 minutes locked out.
# a global cap too, so many addresses can't share the guessing.
MAX_TRIES = 5
GLOBAL_MAX = 20
LOCK_SECONDS = 15 * 60
_fails: dict[str, list[float]] = {}
_fails_lock = threading.Lock()


def _recent(times: list[float], now: float) -> list[float]:
    return [t for t in times if now - t < LOCK_SECONDS]


def check_pin(request: Request, x_pin: str | None = Header(default=None)) -> None:
    if not PIN:
        return
    ip = request.client.host if request.client else "?"
    now = time.time()
    with _fails_lock:
        mine = _recent(_fails.get(ip, []), now)
        everyone = sum(len(_recent(v, now)) for v in _fails.values())
        if len(mine) >= MAX_TRIES or everyone >= GLOBAL_MAX:
            raise HTTPException(429, "Too many wrong PINs, try again in 15 minutes")
        if x_pin and secrets.compare_digest(x_pin.encode(), PIN.encode()):
            return
        if x_pin:
            _fails[ip] = mine + [now]
    raise HTTPException(401, "Wrong PIN")


def call(fn, *args):
    try:
        return fn(*args)
    except RobotError as e:
        raise HTTPException(502, str(e))


class Value(BaseModel):
    value: str


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/status", dependencies=[Depends(check_pin)])
def status():
    return call(lambda: robot().status())


@app.get("/api/options", dependencies=[Depends(check_pin)])
def options():
    return call(lambda: robot().options())


ACTIONS = {"start": "start", "pause": "pause", "dock": "dock", "locate": "locate"}


@app.post("/api/action/{name}", dependencies=[Depends(check_pin)])
def action(name: str):
    if name not in ACTIONS:
        raise HTTPException(404, "unknown action")
    return call(getattr(robot(), ACTIONS[name]))


@app.post("/api/suction", dependencies=[Depends(check_pin)])
def suction(v: Value):
    return call(lambda: robot().set_suction(v.value))


@app.post("/api/mode", dependencies=[Depends(check_pin)])
def mode(v: Value):
    return call(lambda: robot().set_mode(v.value))


@app.post("/api/move", dependencies=[Depends(check_pin)])
def move(v: Value):
    return call(lambda: robot().move(v.value))


@app.post("/api/water", dependencies=[Depends(check_pin)])
def water(v: Value):
    return call(lambda: robot().set_water(v.value))


@app.post("/api/voice", dependencies=[Depends(check_pin)])
def voice(v: Value):
    return call(lambda: robot().set_voice(v.value.lower() in ("1", "true", "on")))


@app.post("/api/volume", dependencies=[Depends(check_pin)])
def volume(v: Value):
    try:
        n = int(v.value)
    except ValueError:
        raise HTTPException(400, "volume must be a number")
    return call(lambda: robot().set_volume(n))


class RoomsReq(BaseModel):
    rooms: list[str]
    times: int = 1


@app.get("/api/rooms", dependencies=[Depends(check_pin)])
def rooms():
    return call(lambda: robot().rooms())


@app.post("/api/rooms/clean", dependencies=[Depends(check_pin)])
def rooms_clean(r: RoomsReq):
    return call(lambda: robot().clean_rooms(r.rooms, r.times))


@app.post("/api/reset/{part}", dependencies=[Depends(check_pin)])
def reset(part: str):
    return call(lambda: robot().reset_consumable(part))


def main():
    global PIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", action="store_true", help="accept connections from the home network")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    host = "127.0.0.1"
    if a.lan:
        cfg_path = HERE / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        PIN = str(cfg.get("web_pin") or "")
        if len(PIN) < 6:
            sys.exit('For --lan put a "web_pin" of at least 6 characters in config.json.')
        host = "0.0.0.0"
    ip = "127.0.0.1"
    if a.lan:
        import socket
        try:
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.connect(("8.8.8.8", 80))
            ip = sk.getsockname()[0]
            sk.close()
        except OSError:
            ip = "PC-IP"
    print(f"Open http://{ip}:{a.port}", flush=True)
    uvicorn.run(app, host=host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
