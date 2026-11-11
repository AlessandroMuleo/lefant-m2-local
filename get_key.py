"""Download device id, local key and DP map from the Tuya cloud project.

Uses the credentials the tinytuya wizard saved in tinytuya.json, writes
devices.json, then scans the LAN for the robot's IP and protocol version.
Never prints keys or secrets.
"""
import json
import sys

import tinytuya


def portal_message(payload):
    """Keep only code and message from a portal answer."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return payload
    if isinstance(payload, dict):
        return {k: v for k, v in payload.items() if k in ("code", "msg", "success")}
    return payload


try:
    cloud = tinytuya.Cloud()
except Exception as e:  # noqa: BLE001
    sys.exit(f"ERROR: can't reach the Tuya cloud: {e}")

err = getattr(cloud, "error", None)
if err:
    info = err if isinstance(err, dict) else {"Error": str(err)}
    print("Cloud error:", info.get("Error"), info.get("Err"))
    print("Portal says:", portal_message(info.get("Payload")))
    cfg = json.load(open("tinytuya.json"))
    print("Saved region:", cfg.get("apiRegion"),
          "| Access ID length:", len(str(cfg.get("apiKey", ""))),
          "| Secret length:", len(str(cfg.get("apiSecret", ""))))
    sys.exit(1)

devs = cloud.getdevices(verbose=False, include_map=True)
if isinstance(devs, dict) and (devs.get("Error") or devs.get("Err")):
    sys.exit(f"Cloud error: {devs.get('Error')} {devs.get('Err', '')} | portal: {portal_message(devs.get('Payload'))}")
if not devs:
    sys.exit("No devices in the Tuya project.")

print(f"Devices found: {len(devs)}")

# DP map, if the device list didn't include it
for d in devs:
    if not d.get("mapping"):
        try:
            m = cloud.getmapping(d.get("product_id"), d.get("id"))
            if m:
                d["mapping"] = m
        except Exception:  # noqa: BLE001
            pass

# IP and protocol version from the local network
try:
    print("Looking for the robot on the LAN (about 20 seconds)...")
    found = tinytuya.deviceScan(False, 8, color=False)
    by_id = {v.get("gwId"): v for v in found.values()}
    for d in devs:
        info = by_id.get(d.get("id"))
        if info:
            d["ip"] = info.get("ip", "")
            d["version"] = info.get("version", "")
except Exception as e:  # noqa: BLE001
    print("LAN scan failed:", e)

with open("devices.json", "w", encoding="utf-8") as f:
    json.dump(devs, f, indent=4, ensure_ascii=False)

for d in devs:
    print(
        "-", d.get("name"),
        "| category:", d.get("category"),
        "| key:", "yes" if d.get("key") else "no",
        "| mapped DPs:", len(d.get("mapping") or {}),
        "| IP:", d.get("ip") or "not found",
        "| protocol:", d.get("version") or "?",
    )
print("Wrote devices.json")
