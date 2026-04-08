# ContextBridge

**Mac → OpenClaw Context Streaming**

ContextBridge captures screen context from your Mac and streams it to OpenClaw for enhanced AI conversations with full activity awareness.

## Features

- Real-time screen reading via macOS Accessibility APIs
- Privacy-first filtering (ignores passwords, sensitive fields)
- Direct OpenClaw integration via MCP server
- Local processing and storage
- Lightweight Python daemon

## Status

**Started:** 2026-04-08
**Status:** Working - captures Mac screen context and provides to OpenClaw

## Architecture

```
[Mac Screen] → [AppleScript + atomacos] → [ContextBridge] → [MCP Server] → [OpenClaw Linux]
```

## Installation

**On Mac:**
```bash
# Install dependencies
pip3 install atomacos requests flask

# Clone and setup
git clone https://github.com/theJooj/contextbridge.git
cd contextbridge

# Test screen reading
python3 contextbridge.py --test

# Start context capture daemon
python3 contextbridge.py --start
```

**MCP Server (runs on Mac):**
```bash
# Start MCP server (in separate terminal)
python3 mcp_server.py --port 8790
```

**OpenClaw Integration:**
Add to your OpenClaw `openclaw.json` under `mcpServers`:
```json
"contextbridge": {
  "url": "http://192.168.4.100:8790/mcp",
  "headers": {
    "X-ContextBridge-Secret": "yf28M-0xmlonP-zautzykrH9_wnEXLVGIGkqiOyStYM"
  }
}
```

## Usage

Once running, OpenClaw can access your screen context via MCP tools:
- `get_recent_context` - Recent screen activity 
- `search_context` - Search by text content
- `get_app_summary` - App usage summary
- `get_current_context` - Most recent context

## Components

- **`contextbridge.py`** - Mac screen capture daemon
- **`mcp_server.py`** - MCP server for OpenClaw integration 
- **`config.json`** - Configuration (polling, filtering, endpoints)

---

*Open source alternative to Little Bird AI ($17-20/month) with direct OpenClaw integration.*