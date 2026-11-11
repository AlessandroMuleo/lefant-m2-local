"""LAN control of a Lefant/Tuya robot vacuum through tinytuya.

The DP map isn't hardcoded. It's read from devices.json (made by the tinytuya
wizard or get_key.py) and each function is looked up by its Tuya code
(power_go, switch_charge, suction...), so other models with different DP
numbers should work too. config.json can force a DP by hand.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from pathlib import Path
from typing import Any

import tinytuya

ROOT = Path(__file__).resolve().parent.parent

# function -> possible Tuya codes, first one found wins
CODE_CANDIDATES: dict[str, list[str]] = {
    "power": ["power", "switch"],
    "start": ["power_go", "switch_go"],
    "pause": ["pause"],
    "mode": ["mode"],
    "dock": ["switch_charge"],
    "status": ["status"],
    "battery": ["electricity_left", "residual_electricity", "battery_percentage"],
    "suction": ["suction"],
    "locate": ["seek"],
    "direction": ["direction_control"],
    "clean_time": ["clean_time"],
    "clean_area": ["clean_area"],
    "fault": ["fault"],
    "water": ["cistern", "water_control"],
    # consumables: remaining life in % and reset command
    "edge_brush": ["edge_brush", "edge_brush_life"],
    "roll_brush": ["roll_brush", "roll_brush_life"],
    "filter": ["filter", "filter_life"],
    "reset_edge_brush": ["reset_edge_brush"],
    "reset_roll_brush": ["reset_roll_brush"],
    "reset_filter": ["reset_filter"],
    # voice: codes aren't standard, try the common ones
    "voice": ["voice_switch", "switch_voice", "voice"],
    "volume": ["volume_set", "volume"],
}

CONSUMABLES = ["edge_brush", "roll_brush", "filter"]

STATUS_TEXT = {
    "standby": "standby",
    "smart": "cleaning",
    "smart_clean": "cleaning",
    "cleaning": "cleaning",
    "wall_follow": "edge cleaning",
    "spiral": "spot cleaning",
    "chargego": "going to dock",
    "goto_charge": "going to dock",
    "charging": "charging",
    "charge_done": "charged",
    "chargecompleted": "charged",
    "paused": "paused",
    "pause": "paused",
    "sleep": "sleeping",
    "fault": "error",
    "relocating": "relocating",
    "zone_clean": "zone cleaning",
    "part_clean": "room cleaning",
}

CLEANING_STATES = {"cleaning", "smart", "smart_clean", "zone_clean", "part_clean",
                   "relocating", "goto_pos", "wall_follow", "spiral"}
ROOM_CMD_DP = "15"  # command_trans, Tuya laser robot protocol


def _frame(cmd: int, data: list[int]) -> bytes:
    body = bytes([cmd]) + bytes(data)
    return bytes([0xAA]) + len(body).to_bytes(2, "big") + body + bytes([sum(body) & 0xFF])


class RobotError(RuntimeError):
    pass


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class LefantRobot:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or ROOT
        self.config = _load_json(self.base_dir / "config.json") or {}
        self.entry = self._find_device_entry()
        self.dev_id: str = self.config.get("device_id") or self.entry.get("id", "")
        self.local_key: str = self.config.get("local_key") or self.entry.get("key", "")
        self.ip: str = self.config.get("ip") or self.entry.get("ip") or "Auto"
        ver = self.config.get("version") or self.entry.get("version") or 3.3
        self.version = float(ver)
        if not self.dev_id or not self.local_key:
            raise RobotError(
                "No device_id or local_key. Run get_key.py first (see README) "
                "or fill in config.json."
            )
        # mapping: {"dp": {"code":..., "type":..., "values":...}}
        self.mapping: dict[str, dict] = {
            str(k): v for k, v in (self.entry.get("mapping") or {}).items()
        }
        self.dp_for: dict[str, str] = self._resolve_functions()
        self._lock = threading.Lock()
        self._dev: tinytuya.Device | None = None

    # ------------------------------------------------------------------ setup
    def _find_device_entry(self) -> dict:
        devices = _load_json(self.base_dir / "devices.json") or []
        wanted_id = self.config.get("device_id")
        wanted_name = (self.config.get("device_name") or "").lower()
        if wanted_id:
            for d in devices:
                if d.get("id") == wanted_id:
                    return d
            return {}
        if wanted_name:
            for d in devices:
                if wanted_name in (d.get("name") or "").lower():
                    return d
        # otherwise the first device with category "sd" (robot vacuum)
        for d in devices:
            if d.get("category") == "sd":
                return d
        for d in devices:
            text = f"{d.get('name','')} {d.get('product_name','')}".lower()
            if any(w in text for w in ("lefant", "robot", "vacuum")):
                return d
        return devices[0] if len(devices) == 1 else {}

    def _resolve_functions(self) -> dict[str, str]:
        by_code = {v.get("code"): dp for dp, v in self.mapping.items()}
        result: dict[str, str] = {}
        for func, codes in CODE_CANDIDATES.items():
            for c in codes:
                if c in by_code:
                    result[func] = by_code[c]
                    break
        # manual overrides from config.json: {"dps": {"start": "2"}}
        for func, dp in (self.config.get("dps") or {}).items():
            result[func] = str(dp)
        return result

    def _device(self) -> tinytuya.Device:
        if self._dev is None:
            dev = tinytuya.Device(
                self.dev_id,
                address=self.ip,
                local_key=self.local_key,
                version=self.version,
                connection_timeout=5,
                connection_retry_limit=2,
                connection_retry_delay=1,
            )
            dev.set_socketPersistent(False)
            self._dev = dev
        return self._dev

    # ------------------------------------------------------------ low level
    def _check(self, resp: Any) -> Any:
        if isinstance(resp, dict) and "Error" in resp:
            self._dev = None  # reconnect next time
            raise RobotError(
                f"The robot doesn't answer ({resp.get('Error')}). "
                "Check that it's on the same network and that ip, local_key "
                "and version are right. The key changes every time the robot is paired again."
            )
        return resp

    def raw_dps(self) -> dict[str, Any]:
        with self._lock:
            resp = self._check(self._device().status())
        return {str(k): v for k, v in (resp or {}).get("dps", {}).items()}

    def set_dp(self, dp: str | int, value: Any) -> dict:
        dp = str(dp)
        with self._lock:
            resp = self._check(self._device().set_value(dp, value))
        return {"ok": True, "dp": dp, "value": value, "response": resp}

    def _set_func(self, func: str, value: Any) -> dict:
        dp = self.dp_for.get(func)
        if dp is None:
            raise RobotError(
                f"This robot has no DP for '{func}'. "
                "See capabilities() for what is there."
            )
        return self.set_dp(dp, value)

    def _enum_values(self, func: str) -> list[str]:
        dp = self.dp_for.get(func)
        if dp is None:
            return []
        vals = (self.mapping.get(dp) or {}).get("values") or {}
        if isinstance(vals, dict):
            return list(vals.get("range") or [])
        return []

    # ------------------------------------------------------------ high level
    def capabilities(self) -> dict:
        caps = {}
        for func, dp in sorted(self.dp_for.items()):
            info = self.mapping.get(dp, {})
            caps[func] = {
                "dp": dp,
                "code": info.get("code"),
                "type": info.get("type"),
                "values": info.get("values"),
            }
        return {
            "device_id": self.dev_id,
            "ip": self.ip,
            "protocol_version": self.version,
            "functions": caps,
            "unmapped_dps": {
                dp: v.get("code")
                for dp, v in self.mapping.items()
                if dp not in self.dp_for.values()
            },
        }

    def status(self) -> dict:
        dps = self.raw_dps()
        by_func = {f: dps.get(dp) for f, dp in self.dp_for.items() if dp in dps}
        raw_state = by_func.get("status")
        out = {
            "state": STATUS_TEXT.get(str(raw_state), raw_state),
            "state_raw": raw_state,
            "battery": by_func.get("battery"),
            "suction": by_func.get("suction"),
            "mode": by_func.get("mode"),
            "cleaning": str(raw_state) in CLEANING_STATES,
            "power": by_func.get("power"),
            "clean_time_min": by_func.get("clean_time"),
            "clean_area_m2": by_func.get("clean_area"),
            "fault": by_func.get("fault") or None,
            "water": by_func.get("water"),
            "voice": by_func.get("voice"),
            "volume": by_func.get("volume"),
            "consumables": {
                part: by_func[part] for part in CONSUMABLES if part in by_func
            } or None,
        }
        out = {k: v for k, v in out.items() if v is not None}
        # every DP with its name, handy for the unmapped ones
        out["all_dps"] = {
            f"{dp} ({(self.mapping.get(dp) or {}).get('code', '?')})": v
            for dp, v in dps.items()
        }
        return out

    def start(self) -> dict:
        if "power" in self.dp_for:
            try:
                self._set_func("power", True)
                time.sleep(0.5)
            except RobotError:
                pass
        if "start" in self.dp_for:
            return self._set_func("start", True)
        modes = self._enum_values("mode")
        for m in ("smart", "smart_clean", "auto"):
            if m in modes:
                return self._set_func("mode", m)
        raise RobotError("No start command found for this robot.")

    def pause(self) -> dict:
        if "pause" in self.dp_for:
            return self._set_func("pause", True)
        if "start" in self.dp_for:
            return self._set_func("start", False)
        raise RobotError("No pause command found for this robot.")

    def dock(self) -> dict:
        if "dock" in self.dp_for:
            return self._set_func("dock", True)
        modes = self._enum_values("mode")
        for m in ("chargego", "goto_charge", "charge"):
            if m in modes:
                return self._set_func("mode", m)
        raise RobotError("No dock command found for this robot.")

    def locate(self) -> dict:
        return self._set_func("locate", True)

    def _set_enum(self, func: str, value: str) -> dict:
        allowed = self._enum_values(func)
        if allowed and value not in allowed:
            raise RobotError(f"'{value}' is not valid for {func}. Allowed: {allowed}")
        return self._set_func(func, value)

    def set_suction(self, level: str) -> dict:
        return self._set_enum("suction", level)

    def set_mode(self, mode: str) -> dict:
        return self._set_enum("mode", mode)

    def move(self, direction: str) -> dict:
        return self._set_enum("direction", direction)

    def set_water(self, level: str) -> dict:
        rng = self._int_range("water")
        if rng:  # some robots use a number instead of low/middle/high
            n = int(level)
            if not (rng[0] <= n <= rng[1]):
                raise RobotError(f"Water level must be between {rng[0]} and {rng[1]}")
            return self._set_func("water", n)
        return self._set_enum("water", level)

    def set_voice(self, on: bool) -> dict:
        return self._set_func("voice", bool(on))

    def _int_range(self, func: str) -> tuple[int, int] | None:
        dp = self.dp_for.get(func)
        vals = (self.mapping.get(dp) or {}).get("values") if dp else None
        if isinstance(vals, dict) and "min" in vals and "max" in vals:
            return int(vals["min"]), int(vals["max"])
        return None

    def set_volume(self, level: int) -> dict:
        rng = self._int_range("volume")
        if rng and not (rng[0] <= int(level) <= rng[1]):
            raise RobotError(f"Volume must be between {rng[0]} and {rng[1]}")
        return self._set_func("volume", int(level))

    def reset_consumable(self, part: str) -> dict:
        if part not in CONSUMABLES:
            raise RobotError(f"Unknown part '{part}'. Allowed: {CONSUMABLES}")
        return self._set_func(f"reset_{part}", True)

    # ------------------------------------------------------------------ rooms
    def rooms(self) -> list[dict]:
        data = _load_json(self.base_dir / "rooms.json") or {}
        out = []
        for app_name, r in (data.get("rooms") or {}).items():
            out.append({"app_name": app_name, "id": r.get("id"), "name": r.get("name", app_name),
                        "aliases": r.get("aliases", [])})
        return out

    def _resolve_room(self, name: str) -> dict:
        q = name.strip().lower()
        rooms = self.rooms()
        for r in rooms:  # exact match first
            if q in [r["app_name"].lower(), str(r["id"]), r["name"].lower(), *[a.lower() for a in r["aliases"]]]:
                return r
        hits = [r for r in rooms if q in r["name"].lower() or any(q in a.lower() for a in r["aliases"])]
        if len(hits) == 1:
            return hits[0]
        known = ", ".join(f"{r['name']} ({r['app_name']})" for r in rooms)
        if hits:
            raise RobotError(f"'{name}' is ambiguous: could be {', '.join(h['name'] for h in hits)}.")
        raise RobotError(f"Room '{name}' not found. Known rooms: {known}")

    def clean_rooms(self, names: list[str], times: int = 1) -> dict:
        if not names:
            raise RobotError("Give at least one room.")
        times = int(times)
        if not 1 <= times <= 3:
            raise RobotError("Passes must be between 1 and 3.")
        rooms, ids = [], []
        for n in names:
            r = self._resolve_room(n)
            if r["id"] not in ids:
                rooms.append(r)
                ids.append(int(r["id"]))
        frame = _frame(0x14, [times, len(ids), *ids])
        res = self.set_dp(ROOM_CMD_DP, base64.b64encode(frame).decode())
        return {"ok": True, "rooms": [r["name"] for r in rooms], "passes": times,
                "command": frame.hex(" "), "response": res.get("response")}

    def options(self) -> dict:
        rng = self._int_range("volume")
        return {
            "suction": self._enum_values("suction"),
            "modes": self._enum_values("mode"),
            "directions": self._enum_values("direction"),
            "water": self._enum_values("water"),
            "voice": "voice" in self.dp_for,
            "volume": {"min": rng[0], "max": rng[1]} if rng else None,
            "resettable": [
                p for p in CONSUMABLES if f"reset_{p}" in self.dp_for
            ],
            "functions": sorted(self.dp_for),
        }
