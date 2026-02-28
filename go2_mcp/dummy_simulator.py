#!/usr/bin/env python3
"""ASCII simulator that visualizes the dummy MCP server state.

Watches the state JSON file written by dummy_server.py and renders
a live terminal view of the robot's position and status.

Usage:
    python go2_mcp/dummy_simulator.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

STATE_FILE = os.getenv("GO2_DUMMY_STATE_FILE", "/tmp/go2_dummy_state.json")

GRID_W = 41  # odd so center is exact
GRID_H = 21
CENTER_X = GRID_W // 2
CENTER_Y = GRID_H // 2

# Heading (radians) to arrow character — 0 = north/up
ARROWS = [
    (0.0, "^"),
    (math.pi / 4, "/"),
    (math.pi / 2, ">"),
    (3 * math.pi / 4, "\\"),
    (math.pi, "v"),
    (-3 * math.pi / 4, "/"),
    (-math.pi / 2, "<"),
    (-math.pi / 4, "\\"),
]


def heading_arrow(heading: float) -> str:
    # Normalize to [-pi, pi]
    h = heading % (2 * math.pi)
    if h > math.pi:
        h -= 2 * math.pi
    best = min(ARROWS, key=lambda a: abs(a[0] - h))
    return best[1]


def render(state: dict) -> str:
    lines: list[str] = []

    # Title
    lines.append("\033[1m  Go2 Dummy Simulator\033[0m")
    lines.append("")

    # Build grid
    grid = [["." for _ in range(GRID_W)] for _ in range(GRID_H)]

    # Robot position — map world coords to grid (1 unit = 2 cells)
    rx = CENTER_X + int(round(state.get("x", 0.0) * 2))
    ry = CENTER_Y - int(round(state.get("y", 0.0) * 2))  # y-up in world, y-down on screen
    arrow = heading_arrow(state.get("heading", 0.0))

    if 0 <= rx < GRID_W and 0 <= ry < GRID_H:
        grid[ry][rx] = f"\033[1;32m{arrow}\033[0m"  # bright green

    # Draw grid with border
    border_h = "+" + "-" * GRID_W + "+"
    lines.append(border_h)
    for row in grid:
        lines.append("|" + "".join(row) + "|")
    lines.append(border_h)

    # Status panel
    lines.append("")
    stance = state.get("stance", "unknown")
    light = "ON" if state.get("light_on") else "off"
    oa = "ON" if state.get("obstacle_avoidance") else "off"
    speed = state.get("speed_level", 1)
    vx = state.get("vx", 0.0)
    vy = state.get("vy", 0.0)
    vyaw = state.get("vyaw", 0.0)
    x = state.get("x", 0.0)
    y = state.get("y", 0.0)
    heading_deg = math.degrees(state.get("heading", 0.0)) % 360
    last = state.get("last_action") or "-"

    lines.append(f"  Stance: {stance:<20s}  Light: {light}")
    lines.append(f"  Speed:  {speed}                      Obstacle avoid: {oa}")
    lines.append(f"  Pos:    ({x:+.1f}, {y:+.1f})  Heading: {heading_deg:.0f}deg")
    lines.append(f"  Vel:    vx={vx:+.2f}  vy={vy:+.2f}  vyaw={vyaw:+.2f}")
    lines.append(f"  Action: {last}")

    # Command log
    log = state.get("log", [])
    lines.append("")
    lines.append("  \033[1mRecent commands:\033[0m")
    for entry in log[-8:]:
        lines.append(f"    > {entry}")

    return "\n".join(lines)


def main() -> None:
    print(f"Watching {STATE_FILE} (Ctrl+C to quit)")
    print("Waiting for dummy_server.py to write state...\n")

    last_mtime = 0.0
    last_output = ""

    try:
        while True:
            try:
                mtime = os.path.getmtime(STATE_FILE)
            except FileNotFoundError:
                time.sleep(0.2)
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    with open(STATE_FILE) as f:
                        state = json.load(f)
                except (json.JSONDecodeError, IOError):
                    time.sleep(0.1)
                    continue

                output = render(state)
                if output != last_output:
                    last_output = output
                    # Clear screen and move cursor to top
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.write(output + "\n")
                    sys.stdout.flush()

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
