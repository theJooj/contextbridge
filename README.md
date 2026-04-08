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
pip install PyScreenReader requests
python contextbridge.py --setup
# Grant accessibility permissions in System Preferences
python contextbridge.py --start
```

## Configuration

- OpenClaw endpoint configuration
- App filtering rules
- Polling intervals
- Privacy controls

---

*Alternative to Little Bird AI ($17-20/month) with direct OpenClaw integration.*