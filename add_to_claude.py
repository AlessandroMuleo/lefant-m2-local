"""Add the 'lefant' MCP server to the Claude Desktop config.
Backs the file up first and leaves the other servers alone."""
import json, os, shutil, sys
from pathlib import Path

here = Path(__file__).resolve().parent
cands = [Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"]
local = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"
if local.exists():
    cands += list(local.glob("Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"))
cfg_path = next((c for c in cands if c.exists()), cands[0])
cfg_path.parent.mkdir(parents=True, exist_ok=True)

cfg = {}
if cfg_path.exists():
    shutil.copy2(cfg_path, cfg_path.with_suffix(".json.bak"))
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8") or "{}")
    except Exception as e:
        sys.exit(f"Can't read the config file ({e}), leaving it alone.")

cfg.setdefault("mcpServers", {})["lefant"] = {
    "command": sys.executable,
    "args": [str(here / "mcp_server.py")],
}
cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("Done, updated:", cfg_path)
print("Quit Claude Desktop completely (also from the tray icon) and open it again.")
