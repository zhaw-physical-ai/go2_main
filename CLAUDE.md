# Go2 Robot Control Project

## Project Overview

This project provides a reusable interface layer for the Unitree Go2 quadruped robot. A ZeroMQ bridge process (`go2_bridge`) sits between the Unitree SDK and any number of clients, exposing a clean JSON protocol for actions, movement, and camera streaming. Three client applications are included: a CLI tool, a web app, and an MCP server.

## Directory Layout

```
go2/
├── go2_bridge/          # ZMQ bridge process (python -m go2_bridge)
│   ├── config.py        # Env-var configuration
│   ├── protocol.py      # Action registry + JSON message helpers
│   ├── robot.py         # SDK wrapper (SportClient, ObstaclesAvoidClient, VideoClient)
│   ├── movement_loop.py # 20 Hz heartbeat thread with 250ms timeout safety
│   ├── camera_publisher.py  # Camera JPEG → ZMQ PUB thread
│   ├── command_handler.py   # ZMQ REQ/REP command dispatcher
│   └── __main__.py      # Entry point, wires components, graceful shutdown
├── go2_client/
│   └── cli_client.py    # CLI demo (send commands, save camera frames)
├── go2_webapp/          # FastAPI web app (python -m go2_webapp)
│   ├── __main__.py      # HTTP/WS server, proxies to bridge via ZMQ
│   └── static/          # Single-page UI (HTML + vanilla JS + CSS)
├── go2_mcp/             # MCP server (python -m go2_mcp)
│   ├── server.py        # FastMCP tools → ZMQ bridge client
│   └── __main__.py      # Entry point (stdio transport)
├── unitree_sdk2_python/  # Unitree SDK2 Python (clone, not committed)
├── go2_py311/           # Python 3.11 venv (not committed)
├── requirements_bridge.txt
└── CLAUDE.md
```

## Running

```bash
# Activate venv
source go2_py311/bin/activate

# Start the bridge (must be on same network as robot)
GO2_NETWORK_INTERFACE=eno1 python -m go2_bridge

# In another terminal — CLI
python go2_client/cli_client.py status
python go2_client/cli_client.py action stand_up
python go2_client/cli_client.py move 0.3 0.0 0.0

# In another terminal — Web app
python -m go2_webapp
# Open http://localhost:8080

# MCP server (for Claude Code / Claude Desktop)
python -m go2_mcp
```

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

## Configuration

All config is via environment variables (defaults in `go2_bridge/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GO2_NETWORK_INTERFACE` | `eno1` | DDS network interface |
| `GO2_ZMQ_CMD_PORT` | `5555` | REQ/REP command port |
| `GO2_ZMQ_PUB_PORT` | `5556` | PUB/SUB stream port |
| `GO2_MOVE_HZ` | `20` | Movement loop frequency |
| `GO2_MOVE_TIMEOUT_MS` | `250` | Movement timeout (auto-stop) |
| `GO2_CAMERA_FPS` | `10` | Camera publish rate |
| `GO2_OBSTACLE_AVOIDANCE` | `1` | Enable obstacle avoidance at startup |
| `GO2_BRIDGE_HOST` | `localhost` | Bridge host (for clients) |
| `GO2_WEBAPP_HOST` | `0.0.0.0` | Web app bind address |
| `GO2_WEBAPP_PORT` | `8080` | Web app HTTP port |

## ZMQ Protocol

Commands go over REQ/REP (port 5555). Streams go over PUB/SUB (port 5556).

**Command examples:**
```json
{"cmd": "action", "params": {"name": "stand_up"}}
{"cmd": "move", "params": {"vx": 0.3, "vy": 0.0, "vyaw": 0.0}}
{"cmd": "stop"}
{"cmd": "status"}
{"cmd": "list_actions"}
```

**PUB topics:** `camera` (JPEG bytes), `state` (JSON).

## Key SDK References

- `unitree_sdk2_python/unitree_sdk2py/go2/sport/sport_client.py` — Action methods (StandUp, Move, etc.)
- `unitree_sdk2_python/unitree_sdk2py/go2/obstacles_avoid/obstacles_avoid_client.py` — Obstacle avoidance Move, SwitchSet, UseRemoteCommandFromApi
- `unitree_sdk2_python/unitree_sdk2py/go2/video/video_client.py` — GetImageSample (returns code + list of ints, must convert to bytes)
- `unitree_sdk2_python/example/obstacles_avoid/obstacles_avoid_move.py` — Reference init pattern

## Important SDK Notes

- `SportClient.Move()` and `ObstaclesAvoidClient.Move()` use `_CallNoReply` (fire-and-forget, safe at 20 Hz)
- All other sport actions use `_Call()` (blocking RPC)
- `VideoClient.GetImageSample()` returns `(code, list_of_ints)` — convert with `bytes(data)`
- Obstacle avoidance init must poll `SwitchGet()` + re-send `SwitchSet(True)` until confirmed (SDK example pattern)
- `UseRemoteCommandFromApi(True)` needs ~500ms before first move command takes effect
- Always call `UseRemoteCommandFromApi(False)` on shutdown

## Architecture Conventions

- Bridge components are started as daemon threads (movement_loop, camera_publisher, command_handler)
- Movement safety: 20 Hz heartbeat relays last velocity; 250ms timeout zeros velocity automatically
- Graceful shutdown via SIGINT/SIGTERM: zeros velocity, disables remote API control, terminates ZMQ context
- Web app uses async ZMQ (`zmq.asyncio`) for non-blocking bridge communication
- Camera frames are relayed: SDK → ZMQ PUB → WebSocket → browser `<img>` tag via blob URLs
- MCP server is a thin ZMQ bridge client (stdio transport); all clients (CLI, web, MCP) can run simultaneously
- MCP `get_camera_frame` subscribes to PUB topic and returns a single frame as base64 JPEG
