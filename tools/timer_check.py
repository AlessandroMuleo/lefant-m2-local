"""Why didn't the scheduled clean start? Prints time zone, saved timers and the
last 7 days of state changes from the Tuya cloud logs.

Run it from the repo root:  python tools/timer_check.py
Some endpoints need extra cloud services on the free plan, those just print an error.
"""
import base64, json, time
import tinytuya

d = json.load(open("devices.json", encoding="utf-8"))[0]
did = d["id"]
c = tinytuya.Cloud()

def req(url, **kw):
    r = c.cloudrequest(url, **kw)
    if isinstance(r, dict) and r.get("success"):
        return r.get("result")
    print(url, "->", {k: r.get(k) for k in ("code", "msg")} if isinstance(r, dict) else r)
    return None

def hx(v):
    try:
        return base64.b64decode(v).hex(" ")
    except Exception:  # noqa: BLE001
        return v

info = req(f"/v1.0/devices/{did}")
if info:
    print("== Device ==")
    for k in ("time_zone", "online", "active_time", "update_time", "ip"):
        v = info.get(k)
        if k in ("active_time", "update_time") and v:
            v = time.strftime("%d/%m %H:%M", time.localtime(v))
        if k == "ip":
            v = "yes" if v else "no"
        print(k, ":", v)

st = req(f"/v1.0/devices/{did}/status")
if st:
    print("\n== Current values ==")
    for x in st:
        if x["code"] in ("device_timer", "time_taask", "disturb_set", "appointment_clean", "break_clean",
                         "status", "mode", "electricity_left", "fault"):
            v = x["value"]
            print(x["code"], ":", hx(v) if isinstance(v, str) and len(v) > 8 else v)

# cloud timers, the ones the app creates through the cloud
for url in (f"/v1.0/devices/{did}/timers", f"/v2.0/cloud/timer/device/{did}"):
    t = req(url)
    if t:
        print("\n== Cloud timers", url, "==")
        print(json.dumps(t, ensure_ascii=False)[:1500])

print("\n== Last 7 days ==")
end = int(time.time() * 1000)
start = end - 7 * 24 * 3600 * 1000
rows, last_row = [], None
while True:
    q = {"type": "7", "start_time": start, "end_time": end, "size": 100}
    if last_row:
        q["start_row_key"] = last_row
    res = req(f"/v1.0/devices/{did}/logs", action="GET", query=q)
    if not res:
        break
    rows += res.get("logs", [])
    if not res.get("has_next") or len(rows) > 2000:
        break
    last_row = res.get("next_row_key")
for x in sorted(rows, key=lambda y: y["event_time"]):
    t = time.strftime("%a %d/%m %H:%M:%S", time.localtime(x["event_time"] / 1000))
    v = x.get("value")
    print(t, x["code"], hx(v) if isinstance(v, str) and len(v) > 8 else v)
print("rows:", len(rows))
for kind, name in (("1", "online"), ("2", "offline")):
    res = req(f"/v1.0/devices/{did}/logs", action="GET", query={"type": kind, "start_time": start, "end_time": end, "size": 100})
    if res:
        for x in sorted(res.get("logs", []), key=lambda y: y["event_time"]):
            print(time.strftime("%a %d/%m %H:%M", time.localtime(x["event_time"] / 1000)), name)
