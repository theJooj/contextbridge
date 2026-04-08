# ContextBridge

**Mac → OpenClaw Context Streaming**

ContextBridge captures screen context from your Mac and streams it to OpenClaw for enhanced AI conversations with full activity awareness.

## Features

- Real-time screen reading via macOS Accessibility APIs
- Privacy-first filtering (ignores passwords, sensitive fields)
- Direct OpenClaw integration
- Local processing (no cloud dependencies)
- Lightweight Python daemon

## Status

**Started:** 2026-04-08
**Target:** Working prototype by end of week

## Architecture

```
[Mac Screen] → [PyScreenReader] → [ContextBridge] → [HTTP/JSON] → [OpenClaw Linux]
```

## Installation

```bash
# Install dependencies
pip3 install atomacos requests

# Clone and setup
git clone https://github.com/theJooj/contextbridge.git
cd contextbridge

# Setup and grant permissions
python3 contextbridge.py --setup

# Test screen reading
python3 contextbridge.py --test

# Start daemon
python3 contextbridge.py --start
```

## Configuration

- OpenClaw endpoint configuration
- App filtering rules
- Polling intervals
- Privacy controls

---

*Alternative to Little Bird AI ($17-20/month) with direct OpenClaw integration.*