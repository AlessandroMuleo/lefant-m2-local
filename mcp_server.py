"""MCP server so Claude (Desktop or Code) can drive the robot over the LAN.

Claude Desktop starts it on its own, see add_to_claude.py.
Manual run for testing: python mcp_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # mcp >= 2.0
from mcp.types import ToolAnnotations

from lefant import LefantRobot, RobotError

server = MCPServer(
    name="lefant-robot",
    instructions=(
        "Controls the user's Lefant robot vacuum on their home network. "
        "Call get_status before acting if the current state matters. "
        "Use list_options to see valid suction levels, modes and directions, "
        "and list_rooms for the room names."
    ),
)

_robot: LefantRobot | None = None


def robot() -> LefantRobot:
    global _robot
    if _robot is None:
        _robot = LefantRobot()
    return _robot


def _run(fn, *args) -> dict:
    try:
        return fn(*args)
    except RobotError as e:
        return {"ok": False, "error": str(e)}


READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
ACT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)


@server.tool(annotations=READ)
def get_status() -> dict:
    """Current state of the robot: state, battery %, suction, mode, cleaning time/area, errors, plus all raw DPs."""
    return _run(lambda: robot().status())


@server.tool(annotations=READ)
def list_options() -> dict:
    """Valid values for suction levels, cleaning modes and manual directions, and which functions this robot supports."""
    return _run(lambda: robot().options())


@server.tool(annotations=READ)
def list_capabilities() -> dict:
    """Detailed DP map (data point number, Tuya code, type, allowed values). Useful for debugging."""
    return _run(lambda: robot().capabilities())


@server.tool(annotations=ACT)
def start_cleaning() -> dict:
    """Start an automatic cleaning run."""
    return _run(lambda: robot().start())


@server.tool(annotations=ACT)
def pause_cleaning() -> dict:
    """Pause / stop the current cleaning run (the robot stays where it is)."""
    return _run(lambda: robot().pause())


@server.tool(annotations=ACT)
def return_to_dock() -> dict:
    """Send the robot back to its charging base."""
    return _run(lambda: robot().dock())


@server.tool(annotations=ACT)
def locate_robot() -> dict:
    """Make the robot beep so it can be found."""
    return _run(lambda: robot().locate())


@server.tool(annotations=ACT)
def set_suction(level: str) -> dict:
    """Set suction power. `level` must be one of the values from list_options (e.g. gentle/normal/strong)."""
    return _run(lambda: robot().set_suction(level))


@server.tool(annotations=ACT)
def set_mode(mode: str) -> dict:
    """Set cleaning mode (e.g. smart, wall_follow, spiral, chargego). Use list_options for valid values."""
    return _run(lambda: robot().set_mode(mode))


@server.tool(annotations=ACT)
def move(direction: str) -> dict:
    """Manual drive: forward, backward, turn_left, turn_right or stop (valid values from list_options)."""
    return _run(lambda: robot().move(direction))


@server.tool(annotations=ACT)
def set_water(level: str) -> dict:
    """Set mopping water flow (e.g. low/middle/high, or a number on some models). Valid values from list_options."""
    return _run(lambda: robot().set_water(level))


@server.tool(annotations=ACT)
def set_voice(on: bool) -> dict:
    """Turn the robot's voice prompts on (true) or off (false)."""
    return _run(lambda: robot().set_voice(on))


@server.tool(annotations=ACT)
def set_volume(level: int) -> dict:
    """Set voice volume. Allowed range from list_options."""
    return _run(lambda: robot().set_volume(level))


@server.tool(annotations=READ)
def list_rooms() -> dict:
    """Rooms the robot knows, with the user's own names and aliases (from rooms.json)."""
    return _run(lambda: {"rooms": robot().rooms()})


@server.tool(annotations=ACT)
def clean_rooms(rooms: list[str], times: int = 1) -> dict:
    """Clean only the given rooms. `rooms` are names as the user says them ('kitchen', 'bedroom', 'Room4'...);
    `times` is the number of passes (1-3), done by the robot in one run. Call list_rooms if a name is unclear."""
    return _run(lambda: robot().clean_rooms(rooms, times))


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
def reset_consumable(part: str, confirm: bool = False) -> dict:
    """Reset the wear counter of a consumable after replacing it. part: edge_brush, roll_brush or filter.
    Irreversible: only call with confirm=true after the user explicitly says they replaced that part."""
    if not confirm:
        return {
            "ok": False,
            "error": "Not reset. Ask the user to confirm, then call again with confirm=true.",
        }
    return _run(lambda: robot().reset_consumable(part))


if __name__ == "__main__":
    server.run("stdio")
