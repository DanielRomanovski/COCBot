# Loguru sink that forwards every DEBUG+ log record to a Discord webhook.
# Lines are batched every 0.8 s to stay within Discord's rate limit.
#
# Usage:
#   import console_sink
#   console_sink.setup("notice_board")   # string shown as the webhook username
from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request

from loguru import logger

# Webhook URL for the #console channel
WEBHOOK_URL = (
    "https://discord.com/api/webhooks/1477923684365635730/"
    "BYi0pohQl4yFwuGNEwZ9ZL_62UOQVzvYDL1WJevjqGDHwSk8Svbo60Wpx83J7beW8MMq"
)

# Loguru format — identical to what you see in the terminal
_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
    "{name}:{function}:{line} - {message}"
)

# Accumulate lines for this many seconds before flushing
_FLUSH_INTERVAL = 0.8

# Discord hard cap per message (2000) minus code-fence overhead (8)
_MAX_CONTENT = 1990

_q: queue.Queue[str] = queue.Queue()
_started = False
_lock = threading.Lock()


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _post(content: str, username: str) -> None:
    """POST *content* to the webhook, retrying once on 429."""
    payload = json.dumps({"content": content, "username": username}).encode()
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(2):
        try:
            urllib.request.urlopen(req, timeout=8)
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(2)       # back off once on rate-limit
            else:
                return
        except Exception:
            return


# ── Worker thread ─────────────────────────────────────────────────────────────

def _flush(buffer: list[str], username: str) -> list[str]:
    """
    Pack as many buffered lines as fit into one Discord code-block message.
    Returns any lines that didn't fit (to stay at the front of the next batch).
    """
    block_lines: list[str] = []
    block_len = 0
    remaining: list[str] = []

    for line in buffer:
        # +1 for the newline separator
        if block_len + len(line) + 1 <= _MAX_CONTENT - 8:  # 8 = len("```\n\n```")
            block_lines.append(line)
            block_len += len(line) + 1
        else:
            remaining.append(line)

    if block_lines:
        _post("```\n" + "\n".join(block_lines) + "\n```", username)

    return remaining


def _worker(username: str) -> None:
    buffer: list[str] = []
    last_flush = time.monotonic()

    while True:
        try:
            item = _q.get(timeout=_FLUSH_INTERVAL)
            buffer.append(item)
        except queue.Empty:
            pass

        if buffer and (time.monotonic() - last_flush >= _FLUSH_INTERVAL):
            buffer = _flush(buffer, username)
            last_flush = time.monotonic()


# ── Public API ────────────────────────────────────────────────────────────────

def setup(script_name: str = "cocbot") -> None:
    """
    Register a loguru sink that forwards all DEBUG+ records to Discord.
    Safe to call multiple times — only installs once per process.
    """
    global _started
    with _lock:
        if _started:
            return
        _started = True

    username = f"cocbot/{script_name}"
    t = threading.Thread(target=_worker, args=(username,), daemon=True)
    t.start()

    def _sink(message: object) -> None:
        # str(message) produces the fully-formatted log line using _LOG_FORMAT
        line = str(message).rstrip("\n")
        # Truncate individual lines that are absurdly long
        if len(line) > _MAX_CONTENT - 8:
            line = line[: _MAX_CONTENT - 11] + "..."
        _q.put(line)

    logger.add(_sink, level="DEBUG", format=_LOG_FORMAT, colorize=False)
    logger.info("[console_sink] Discord logging active ({})", script_name)
