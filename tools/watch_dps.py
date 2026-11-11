"""Print every DP change for 10 minutes.

I used it to see what changes when the app starts a room clean.
Run it from the repo root:  python tools/watch_dps.py
"""
import json
import time

import tinytuya

devs = json.load(open("devices.json", encoding="utf-8"))
d = next(x for x in devs if x.get("ip"))
names = {str(k): v.get("code") for k, v in (d.get("mapping") or {}).items()}


def connect():
    dev = tinytuya.Device(d["id"], d["ip"], d["key"], version=float(d.get("version") or 3.3))
    dev.set_socketPersistent(True)
    dev.set_socketTimeout(4)
    return dev


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


dev = connect()
last = {}
end = time.time() + 600
log("watching, use the app now")
while time.time() < end:
    try:
        st = dev.status()
        dps = (st or {}).get("dps") or {}
        for k, v in dps.items():
            if last.get(k) != v:
                log(f"DP {k} ({names.get(k, '?')}) = {v!r}")
                last[k] = v
        if not dps and st:
            # 904 here usually means the local key changed (robot paired again)
            log(f"error {st.get('Err')}, reconnecting")
            try:
                dev.close()
            except Exception:  # noqa: BLE001
                pass
            dev = connect()
            time.sleep(2)
    except Exception as e:  # noqa: BLE001
        log(f"error: {e}")
    time.sleep(1)
log("done")
