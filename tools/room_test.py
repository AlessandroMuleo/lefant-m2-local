"""Send a room clean (Tuya 0x14) and print what the robot reports for 60 seconds.

    python tools/room_test.py 9 1     # room id 9, one pass

Run it from the repo root. Start with the robot on the dock: if it's
already going somewhere it may keep doing that.
"""
import base64
import json
import sys
import time

import tinytuya

ROOM = int(sys.argv[1]) if len(sys.argv) > 1 else 8
PASSES = int(sys.argv[2]) if len(sys.argv) > 2 else 1


def frame(cmd, data):
    body = bytes([cmd]) + bytes(data)
    return bytes([0xAA]) + len(body).to_bytes(2, "big") + body + bytes([sum(body) & 0xFF])


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


d = json.load(open("devices.json", encoding="utf-8"))[0]
dev = tinytuya.Device(d["id"], d["ip"], d["key"], version=float(d.get("version") or 3.3))
dev.set_socketTimeout(5)

f = frame(0x14, [PASSES, 1, ROOM])
log("command:", f.hex(" "))
before = (dev.status() or {}).get("dps", {})
log("before: status", before.get("5"), "| mode", before.get("4"))
r = dev.set_value(15, base64.b64encode(f).decode())
log("sent ->", (r or {}).get("dps", r))

end = time.time() + 60
last = {}
while time.time() < end:
    try:
        for k, v in ((dev.status() or {}).get("dps") or {}).items():
            if last.get(k) != v:
                if isinstance(v, str) and len(v) > 6:
                    try:
                        v = base64.b64decode(v).hex(" ")
                    except ValueError:
                        pass
                log("DP", k, "=", v)
                last[k] = v
    except Exception as e:  # noqa: BLE001
        log("error:", e)
    time.sleep(2)
log("done")
