# Installation & Environment Setup

Step-by-step guide to reproduce the full Go2 control environment from scratch.

## Prerequisites

- **Python 3.11** (the Unitree SDK requires 3.11; 3.12+ may not work with cyclonedds)
- **Git**
- A network connection to the Unitree Go2 robot (Ethernet or Wi-Fi)

## 1. Clone This Repo

```bash
git clone <this-repo-url> go2
cd go2
```

## 2. Create Python 3.11 Virtual Environment

```bash
python3.11 -m venv go2_py311
source go2_py311/bin/activate
```

## 3. (Optional) Clone CycloneDDS C Library

Only needed if you want to build CycloneDDS from source for custom DDS configuration. 

```bash
cd ~
git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x 
cd cyclonedds && mkdir build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../install
cmake --build . --target install
```

## 4. Install the Unitree SDK

The SDK is not on PyPI — clone it and install in editable mode:

```bash
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd ~/unitree_sdk2_python
export CYCLONEDDS_HOME="/global/path/to/your/cyclonedss/install"
pip3 install -e .
```

This pulls in `cyclonedds`, `numpy`, `opencv-python`, and other SDK dependencies automatically.

## 5. Install Bridge & Web App Dependencies

```bash
pip install -r requirements_bridge.txt
```

This adds: `pyzmq`, `fastapi`, `uvicorn`.

## 6. (Optional) Install MCP Server Dependencies

Only needed if you want to use the MCP server with Claude Code / Claude Desktop:

```bash
pip install "mcp[cli]"
```

## 7. Verify Installation

```bash
source go2_py311/bin/activate

# Check SDK is importable
python -c "from unitree_sdk2py.go2.sport.sport_client import SportClient; print('SDK OK')"

# Check bridge dependencies
python -c "import zmq, fastapi, uvicorn; print('Bridge deps OK')"
```

## 8. Network Setup

The Go2 robot communicates via DDS over a local network. You need to know which network interface connects to the robot:

```bash
# List interfaces
ip link show        # Linux
ifconfig            # macOS

# Common values:
#   eno1, eth0      — wired Ethernet
#   wlan0, en0      — Wi-Fi
```

Set up a manual IP: 192.168.123.100

Set the interface when starting the bridge:

```bash
GO2_NETWORK_INTERFACE=eno1 python -m go2_bridge
```

## Running

### Start the Bridge

```bash
source go2_py311/bin/activate
GO2_NETWORK_INTERFACE=eno1 python -m go2_bridge
```

### Start the Web App (separate terminal)

```bash
source go2_py311/bin/activate
python -m go2_webapp
# Open http://localhost:8080
```

### CLI Client (separate terminal)

```bash
source go2_py311/bin/activate
python go2_client/cli_client.py status
python go2_client/cli_client.py action stand_up
```

See [README.md](README.md) for full usage details.

## Installed Package Versions (Reference)

These are the versions known to work together:

```
unitree_sdk2py    1.0.1
cyclonedds        0.10.2
numpy             2.4.2
opencv-python     4.13.0.92
pyzmq             27.1.0
fastapi           0.132.0
uvicorn           0.41.0
```

## Troubleshooting

**"No module named unitree_sdk2py"**
Make sure you installed the SDK in editable mode (`pip install -e unitree_sdk2_python/`) and are using the correct venv.

**Bridge starts but robot doesn't respond**
Check `GO2_NETWORK_INTERFACE` matches the interface connected to the robot's network. The robot and your machine must be on the same subnet.

**Camera frames not arriving**
The VideoClient sometimes needs a few seconds after init. If frames never arrive, verify the robot's camera is enabled and the SDK `GetImageSample()` works standalone.

**Movement commands ignored**
The robot must be standing (`stand_up` action) before it will accept move commands. Also verify obstacle avoidance initialized correctly — you should hear a voice confirmation from the robot.
