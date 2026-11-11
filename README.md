# lefant-m2-local

Local control for my Lefant M2 robot vacuum. It's a Tuya device, so it can be driven over the LAN with [tinytuya](https://github.com/jasonacox/tinytuya) once you have its local key. I use it from Claude Desktop through an MCP server, and from a small web page on my phone.

Status: works on my M2, used every day. I haven't tried other robots. Tuya robots with a laser map probably speak the same protocol, but that's a guess.

The cloud is only needed once, to get the local key. After that the commands go straight to the robot on the Wi-Fi. The robot itself still talks to the Tuya cloud, this doesn't change that.

## What it does

- state, battery, cleaning time and area, errors
- start, pause, dock, find robot (it beeps)
- suction, water, manual drive
- clean only some rooms, with a number of passes ("clean the kitchen twice")

## Room cleaning

This was the part the app didn't expose locally. The app sends the selected rooms through the cloud, so I couldn't just watch it. What helped was the Tuya protocol for laser robots: command `0x14` sets a room clean, and it goes on DP 15 (`command_trans`).

The frame is `AA`, a 2-byte length, then the command, the number of passes, how many rooms, the room ids, and a checksum (sum of the bytes from the command on, last byte only). Room 9 with one pass:

```
aa 00 04 14 01 01 09 1f
```

The room ids show up in DP 150 (`personalized_cleaning`). On my robot they go from 5 to 11, one per room in the app. I checked two of them by sending the command with the robot on the dock and watching where it went. The others follow the same order. More than one pass is built the same way but I haven't checked that the robot really goes over twice.

## Layout

```
lefant/robot.py      talks to the robot, finds DPs by their Tuya code
mcp_server.py        tools for Claude Desktop (stdio)
web_app.py           web page, optional PIN for the LAN
static/index.html    the page itself
get_key.py           local key, IP and DP map from the Tuya cloud
discover.py          checks the connection and prints what was found
add_to_claude.py     adds the server to the Claude Desktop config
tools/               watch DPs, test a room, check the schedule
windows/             .bat files for the steps below
```

`devices.json`, `tinytuya.json`, `config.json` and `rooms.json` hold the keys and the room names of your home. They are in `.gitignore`, the repo only has the `.example` files.

## Setup

You need Python 3.10+, the robot paired with the Smart Life app, and a free cloud project on platform.tuya.com. With the Lefant app I found no way to get the key.

1. Create the cloud project (Central Europe data center for me) and link your Smart Life account under Devices, Link App Account.
2. `windows/setup.bat` installs the requirements and runs the tinytuya wizard, which asks for the project's Access ID and Secret.
3. `windows/get-key.bat` writes `devices.json` and checks that the robot answers.
4. Copy `rooms.example.json` to `rooms.json` and put your room names in it.
5. `windows/add-to-claude.bat`, then quit and reopen Claude Desktop.

Web page on the PC only: `windows/web.bat`, then http://127.0.0.1:8765

From the phone: put a `web_pin` of at least 6 characters in `config.json` and run `windows/web-lan.bat`. It prints the address to open.

On Linux it's the same scripts without the .bat files.

## Things that went wrong

- Error 911 "sign invalid": the Access Secret in `tinytuya.json` was wrong. Copy it again from the portal, don't type it.
- Error 28841002 "subscription has expired": the free IoT Core trial lasts a month. It can be extended from the portal (Extend Trial Period), mine was approved within a few hours.
- "permission deny" on every cloud call: when the trial expired the robot got unlinked from the project. After the extension I had to press Refresh under Link App Account, and since the robot was gone I paired it again.
- Error 904 on the LAN: the local key changes every time the robot is paired with an app. Run `get-key.bat` again.
- Pairing again also wipes the cleaning schedule saved in the robot.

## Security

The web page uses plain http. With `--lan` it asks for the PIN, and after 5 wrong tries from the same address (or 20 overall) it stops answering for 15 minutes. That's fine on a home network, I wouldn't put it on the internet.

The MCP server has no tool to write raw DPs. I had one while testing and removed it before publishing: some DPs wipe the map (13) or reboot the robot (121), and a prompt injection in something Claude reads shouldn't be able to reach those.

`reset_consumable` only runs with `confirm=true`, so Claude has to ask first.

## Not done

- map and live position, they come through the cloud (MQTT) and not the local protocol
- checking more than one pass and the other room ids on the robot
- running the schedule from a Raspberry Pi instead of the robot's own timer

## License

MIT, see [LICENSE](LICENSE).
