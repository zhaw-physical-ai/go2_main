# Go2 ZMQ Bridge, CLI Client, Web App & MCP Server

A reusable interface layer for the Unitree Go2 quadruped robot. A ZeroMQ bridge process sits between the Unitree SDK and any number of clients, providing a clean JSON protocol for actions, movement, and camera streaming.

## Architecture

```
┌─────────────┐   ZMQ REQ/REP    ┌──────────────────┐   Unitree SDK2   ┌──────────┐
│  CLI Client  │ ──────────────► │                  │ ───────────────► │          │
└─────────────┘   (port 5555)    │   go2_bridge     │                  │  Go2     │
                                 │                  │ ◄─────────────── │  Robot   │
┌─────────────┐   HTTP/WS        │  ┌─────────────┐ │                  │          │
│  Web App     │ ──────────────► │  │ cmd_handler  │ │                  └──────────┘
│  (FastAPI)   │ ◄── ZMQ SUB ── │  │ move_loop    │ │
└─────────────┘   (port 5556)    │  │ camera_pub   │ │
                                 │  └─────────────┘ │
┌─────────────┐   ZMQ REQ/REP   │                  │
│  MCP Server  │ ──────────────► │                  │
│  (stdio)     │ ◄── ZMQ SUB ── │                  │
└─────────────┘                  └──────────────────┘
```

**go2_bridge** runs three threads:

| Thread | Purpose | Rate |
|--------|---------|------|
| **command_handler** | ZMQ REQ/REP on port 5555 — dispatches action, move, stop, config commands | On demand |
| **movement_loop** | Relays last commanded velocity to the robot via SDK | 20 Hz |
| **camera_publisher** | Grabs JPEG frames from VideoClient, publishes on ZMQ PUB port 5556 | 10 FPS |

### Movement Safety

The movement loop continuously sends the last commanded velocity at 20 Hz. If no new `move` command arrives within **250 ms**, velocity automatically resets to zero. This gives smooth continuous motion from a joystick or keyboard while guaranteeing a quick stop if the client disconnects or crashes.

### Obstacle Avoidance

Enabled by default. Uses `ObstaclesAvoidClient` for all movement, routing through the robot's built-in obstacle detection. Can be toggled at runtime via the `obstacle_avoidance` command. Falls back to `SportClient.Move()` when disabled.

## Quick Start

### Prerequisites

- Python 3.11+ with the Unitree SDK2 Python package installed
- Network connection to the Go2 robot
- ZeroMQ, FastAPI, and uvicorn

### Install Dependencies

```bash
source go2_py311/bin/activate
pip install -r requirements_bridge.txt
```

### 1. Start the Bridge

```bash
GO2_NETWORK_INTERFACE=eno1 python -m go2_bridge
```

You should see:
```
Go2 Bridge running — CMD port 5555, PUB port 5556
```

### 2. CLI Client

```bash
# Check bridge status
python go2_client/cli_client.py status

# List available actions
python go2_client/cli_client.py list_actions

# Make the robot stand up
python go2_client/cli_client.py action stand_up

# Move forward at 0.3 m/s
python go2_client/cli_client.py move 0.3 0.0 0.0

# Emergency stop
python go2_client/cli_client.py stop

# Save a camera frame
python go2_client/cli_client.py camera_frame

# Toggle obstacle avoidance
python go2_client/cli_client.py obstacle_avoidance 0   # off
python go2_client/cli_client.py obstacle_avoidance 1   # on

# Set speed level (1-3)
python go2_client/cli_client.py speed_level 2
```

### 3. Web App

```bash
python -m go2_webapp
```

Open **http://localhost:8080** in a browser. The UI provides:

- **Live camera feed** via WebSocket
- **WASD + Q/E keyboard controls** for movement and rotation
- **On-screen directional buttons** (touch-friendly)
- **Action buttons** for all registered actions (stand up, sit, dance, flip, etc.)
- **Obstacle avoidance toggle**
- **Speed level selector** (1-3)
- **STOP button** (also spacebar)

### 4. MCP Server (for Claude Code / Claude Desktop)

The MCP server exposes robot control as tools that an LLM can call. It connects to the bridge as a ZMQ client, just like the CLI and web app.

```bash
# Run directly (stdio transport)
python -m go2_mcp

# Test with MCP inspector
mcp dev go2_mcp/server.py
```

**Available MCP tools:**

| Tool | Description |
|------|-------------|
| `get_status` | Get robot status (obstacle avoidance, speed, light) |
| `list_actions` | List all available actions |
| `execute_action` | Run a named action (stand_up, dance1, etc.) |
| `move` | Move with velocity (vx, vy, vyaw) |
| `stop` | Emergency stop |
| `set_obstacle_avoidance` | Toggle obstacle avoidance on/off |
| `set_speed_level` | Set speed 1-3 |
| `set_light` | Turn head light on/off |
| `get_camera_frame` | Capture and return a JPEG frame |

**Claude Desktop configuration** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "go2": {
      "command": "/path/to/go2/go2_py311/bin/python",
      "args": ["/path/to/go2/go2_mcp/server.py"]
    }
  }
}
```

**Claude Code configuration** (`.claude/settings.json` or project settings):
```json
{
  "mcpServers": {
    "go2": {
      "command": "/path/to/go2/go2_py311/bin/python",
      "args": ["-m", "go2_mcp"],
      "cwd": "/path/to/go2"
    }
  }
}
```

## ZMQ Protocol

### Commands (REQ/REP — port 5555)

All messages are JSON. Request format:

```json
{"cmd": "<command>", "params": {<optional params>}}
```

Response format:

```json
{"ok": true, "msg": "description", "data": null}
```

| Command | Params | Description |
|---------|--------|-------------|
| `action` | `{"name": "stand_up"}` | Execute a named action |
| `move` | `{"vx": 0.3, "vy": 0.0, "vyaw": 0.0}` | Set movement velocity |
| `stop` | — | Zero velocity immediately |
| `obstacle_avoidance` | `{"enabled": true}` | Toggle obstacle avoidance |
| `speed_level` | `{"level": 2}` | Set speed (1-3) |
| `light` | `{"on": true}` | Turn head light on/off |
| `list_actions` | — | Get list of available actions |
| `status` | — | Get current bridge status |

### Streams (PUB/SUB — port 5556)

| Topic | Payload | Rate |
|-------|---------|------|
| `camera` | Raw JPEG bytes | ~10 FPS |

Subscribe with topic filter `b"camera"`. Frames arrive as two-part multipart messages: `[topic, jpeg_data]`.

## Available Actions

| Action | Robot Behavior |
|--------|---------------|
| `stand_up` | Stand up from sitting/lying |
| `stand_down` | Lie down |
| `balance_stand` | Enter balance stand mode |
| `recovery_stand` | Recovery stand (from fallen) |
| `sit` | Sit down |
| `hello` | Wave hello |
| `stretch` | Stretching motion |
| `dance1` | Dance routine 1 |
| `dance2` | Dance routine 2 |
| `heart` | Heart gesture |
| `front_flip` | Front flip |
| `front_jump` | Front jump |
| `back_flip` | Back flip |
| `left_flip` | Left flip |
| `hand_stand` | Handstand |
| `damp` | Emergency soft stop (all motors) |
| `stop_move` | Stop current movement |

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GO2_NETWORK_INTERFACE` | `eno1` | DDS network interface for SDK |
| `GO2_ZMQ_CMD_PORT` | `5555` | REQ/REP command port |
| `GO2_ZMQ_PUB_PORT` | `5556` | PUB/SUB stream port |
| `GO2_MOVE_HZ` | `20` | Movement loop rate |
| `GO2_MOVE_TIMEOUT_MS` | `250` | Movement command timeout |
| `GO2_CAMERA_FPS` | `10` | Camera publish rate |
| `GO2_OBSTACLE_AVOIDANCE` | `1` | Enable obstacle avoidance at startup |
| `GO2_BRIDGE_HOST` | `localhost` | Bridge host (for clients) |
| `GO2_WEBAPP_HOST` | `0.0.0.0` | Web app bind address |
| `GO2_WEBAPP_PORT` | `8080` | Web app port |

## Writing Custom Clients

The bridge speaks plain JSON over ZeroMQ, so you can write clients in any language with a ZMQ binding:

```python
import zmq

ctx = zmq.Context()
sock = ctx.socket(zmq.REQ)
sock.connect("tcp://localhost:5555")

# Send a command
sock.send_json({"cmd": "action", "params": {"name": "hello"}})
response = sock.recv_json()
print(response)  # {"ok": true, "msg": "hello executed", "data": {"code": 0}}

# Subscribe to camera
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://localhost:5556")
sub.subscribe(b"camera")
topic, jpeg_data = sub.recv_multipart()
with open("frame.jpg", "wb") as f:
    f.write(jpeg_data)
```

## Shutdown

Press `Ctrl+C` to stop the bridge. It will:
1. Zero all velocity commands
2. Call `UseRemoteCommandFromApi(False)` to restore normal robot control
3. Clean up ZMQ sockets
