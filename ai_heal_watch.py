"""
Claude Code watcher for auto-bot AI self-healing.

Run this in Claude Code terminal while auto-bot is running:
  python ai_heal_watch.py

When auto-bot fails to find an image, it writes to ai_heal/:
  - screen.png  : current screenshot
  - request.json: what element was being looked for

This script detects the request, exits, and Claude Code then:
  1. Reads ai_heal/screen.png natively (no API key needed)
  2. Locates the element visually
  3. Writes ai_heal/response.json with coordinates

auto-bot picks up the response and continues automatically.
"""

import json
import sys
import time
from pathlib import Path

AI_HEAL_DIR = Path("ai_heal")
REQUEST = AI_HEAL_DIR / "request.json"
RESPONSE = AI_HEAL_DIR / "response.json"

timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 120

print(f"Watching ai_heal/ for requests (timeout: {timeout}s)...")

deadline = time.time() + timeout
while time.time() < deadline:
    if REQUEST.exists():
        try:
            req = json.loads(REQUEST.read_text(encoding="utf-8"))
            print(f"\n=== AI HEAL REQUEST ===")
            print(f"Template: {req['template_path']}")
            print(f"Screen saved: ai_heal/screen.png")
            print(f"\nPlease read ai_heal/screen.png and find the element.")
            print(f"Then write ai_heal/response.json:")
            print(f'  Found:    {{"x": <int>, "y": <int>}}')
            print(f'  NotFound: {{"fallback": true}}')
            sys.exit(0)
        except Exception as e:
            print(f"Error reading request: {e}")
    time.sleep(1)

print("timeout — no heal request received")
sys.exit(1)
