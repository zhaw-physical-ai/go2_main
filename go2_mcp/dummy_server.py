"""Dummy MCP server for testing without a robot or bridge.

Same tool interface as server.py, but maintains state in memory and writes
it to a JSON file for the companion dummy_simulator.py to visualize.

Usage:
    python go2_mcp/dummy_server.py
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import sys
import time

import cv2
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger("go2_mcp_dummy")

STATE_FILE = os.getenv("GO2_DUMMY_STATE_FILE", "/tmp/go2_dummy_state.json")

mcp = FastMCP("go2-robot-dummy")

# ── Robot state ──────────────────────────────────────────────────

ACTIONS = [
    "stand_up", "stand_down", "balance_stand", "recovery_stand",
    "sit", "hello", "stretch", "dance1", "dance2", "heart",
    "front_flip", "front_jump", "back_flip", "left_flip",
    "hand_stand", "damp", "stop_move",
]

_state = {
    "x": 0.0,
    "y": 0.0,
    "heading": 0.0,  # radians, 0 = facing up/north
    "stance": "standing",
    "speed_level": 1,
    "obstacle_avoidance": True,
    "light_on": False,
    "last_action": None,
    "vx": 0.0,
    "vy": 0.0,
    "vyaw": 0.0,
    "log": [],
}

LOG_MAX = 20


def _log(msg: str) -> None:
    _state["log"].append(msg)
    if len(_state["log"]) > LOG_MAX:
        _state["log"] = _state["log"][-LOG_MAX:]


def _save() -> None:
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(_state, f, indent=2)
    except Exception as exc:
        log.warning("Failed to write state file: %s", exc)


# ── Tools ────────────────────────────────────────────────────────


@mcp.tool()
def get_status() -> str:
    """Get the current status of the Go2 robot.

    Returns obstacle avoidance state, speed level, and light state.
    """
    _log("status checked")
    _save()
    data = {
        "obstacle_avoidance": _state["obstacle_avoidance"],
        "speed_level": _state["speed_level"],
        "light_on": _state["light_on"],
    }
    return f"OK: ok\n{json.dumps(data, indent=2)}"


@mcp.tool()
def list_actions() -> str:
    """List all available robot actions (e.g. stand_up, sit, dance1, hello)."""
    _log("listed actions")
    _save()
    data = {"actions": ACTIONS}
    return f"OK: actions\n{json.dumps(data, indent=2)}"


@mcp.tool()
def execute_action(name: str) -> str:
    """Execute a named action on the robot.

    Args:
        name: Action name (e.g. stand_up, stand_down, sit, hello, stretch,
              dance1, dance2, heart, front_flip, front_jump, back_flip,
              left_flip, hand_stand, balance_stand, recovery_stand, damp, stop_move)
    """
    if name not in ACTIONS:
        _log(f"unknown action: {name}")
        _save()
        return f"ERROR: unknown action: {name}"

    _state["last_action"] = name
    if name == "stand_up":
        _state["stance"] = "standing"
    elif name in ("stand_down", "sit"):
        _state["stance"] = name.replace("_", " ")
        _state["vx"] = _state["vy"] = _state["vyaw"] = 0.0
    elif name == "damp":
        _state["stance"] = "damped"
        _state["vx"] = _state["vy"] = _state["vyaw"] = 0.0
    elif name == "balance_stand":
        _state["stance"] = "balance standing"
    elif name == "recovery_stand":
        _state["stance"] = "standing"

    _log(f"{name} executed")
    _save()
    return f"OK: {name} executed\n{json.dumps({'code': 0}, indent=2)}"


@mcp.tool()
def move(vx: float, vy: float = 0.0, vyaw: float = 0.0) -> str:
    """Move the robot with the given velocity.

    The robot must be standing first. Velocities are in m/s (linear) and rad/s (rotation).
    The movement continues at the given velocity until a stop command or new move command.
    The bridge has a 250ms safety timeout — if no new command arrives, the robot stops automatically.

    Args:
        vx: Forward/backward velocity (-1.0 to 1.0). Positive = forward.
        vy: Left/right velocity (-1.0 to 1.0). Positive = left.
        vyaw: Rotation velocity (-1.0 to 1.0). Positive = counter-clockwise.
    """
    _state["vx"] = max(-1.0, min(1.0, vx))
    _state["vy"] = max(-1.0, min(1.0, vy))
    _state["vyaw"] = max(-1.0, min(1.0, vyaw))

    # Simulate one step of movement
    step = 0.5 * _state["speed_level"]
    h = _state["heading"]
    _state["x"] += step * (_state["vx"] * math.sin(h) + _state["vy"] * math.cos(h))
    _state["y"] += step * (_state["vx"] * math.cos(h) - _state["vy"] * math.sin(h))
    _state["heading"] += _state["vyaw"] * 0.3

    _log(f"move vx={vx:.2f} vy={vy:.2f} vyaw={vyaw:.2f}")
    _save()
    return "OK: velocity updated"


@mcp.tool()
def stop() -> str:
    """Immediately stop all robot movement. Use this as an emergency stop or to halt motion."""
    _state["vx"] = _state["vy"] = _state["vyaw"] = 0.0
    _log("stopped")
    _save()
    return "OK: stopped"


@mcp.tool()
def set_obstacle_avoidance(enabled: bool) -> str:
    """Enable or disable the robot's obstacle avoidance system.

    When enabled, the robot uses its sensors to avoid collisions during movement.
    Enabled by default at bridge startup.

    Args:
        enabled: True to enable, False to disable.
    """
    _state["obstacle_avoidance"] = enabled
    state = "enabled" if enabled else "disabled"
    _log(f"obstacle avoidance {state}")
    _save()
    return f"OK: obstacle avoidance {state}"


@mcp.tool()
def set_speed_level(level: int) -> str:
    """Set the robot's movement speed level.

    Args:
        level: Speed level from 1 (slow) to 3 (fast).
    """
    _state["speed_level"] = max(1, min(3, level))
    _log(f"speed level set to {_state['speed_level']}")
    _save()
    return f"OK: speed level set to {_state['speed_level']}"


@mcp.tool()
def set_light(on: bool) -> str:
    """Turn the robot's head light on or off.

    Args:
        on: True to turn on (max brightness), False to turn off.
    """
    _state["light_on"] = on
    state = "on" if on else "off"
    _log(f"light {state}")
    _save()
    return f"OK: light {state}\n{json.dumps({'code': 0}, indent=2)}"


@mcp.tool()
def get_camera_frame() -> CallToolResult:
    """Capture a single camera frame from the robot and return it as a JPEG image.

    The bridge must be running with camera publishing enabled.
    """
    cap = cv2.VideoCapture(0)
    try:
        ret, frame = cap.read()
        if not ret:
            _log("camera frame failed")
            _save()
            return CallToolResult(
                content=[TextContent(type="text", text="ERROR: Failed to capture from webcam")]
            )

        _, jpeg = cv2.imencode(".jpg", frame)
        jpeg_bytes = jpeg.tobytes()
        b64 = base64.b64encode(jpeg_bytes).decode("utf-8")

        _log("camera frame captured")
        _save()
        return CallToolResult(
            content=[
                TextContent(type="text", text=f"Camera frame captured ({len(jpeg_bytes)} bytes)"),
                ImageContent(type="image", data=b64, mimeType="image/jpeg"),
            ]
        )
    finally:
        cap.release()


if __name__ == "__main__":
    # Write initial state so simulator can start
    _save()
    log.info("Dummy MCP server starting (state file: %s)", STATE_FILE)
    mcp.run(transport="stdio")
