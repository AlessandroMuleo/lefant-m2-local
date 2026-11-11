"""Check the connection and show how the robot exposes its functions.

    python discover.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lefant import LefantRobot, RobotError

try:
    r = LefantRobot()
except RobotError as e:
    sys.exit(f"ERROR: {e}")

print("== Functions found ==")
print(json.dumps(r.capabilities(), indent=2, ensure_ascii=False))
print("\n== Current state ==")
try:
    print(json.dumps(r.status(), indent=2, ensure_ascii=False))
    print("\nOK, the robot answers on the LAN.")
except RobotError as e:
    sys.exit(f"\nERROR: {e}")
