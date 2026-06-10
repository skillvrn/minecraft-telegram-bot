#!/usr/bin/env python3
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("minecraft-log-forwarder")

TARGET_URL = os.getenv("FORWARDER_TARGET_URL", "").strip()
SHARED_SECRET = os.getenv("FORWARDER_SHARED_SECRET", "").strip()
CONTAINER_NAME = os.getenv("MC_DOCKER_CONTAINER", "minecraft").strip()
RECONNECT_DELAY_SEC = int(os.getenv("RECONNECT_DELAY_SEC", "3"))
DEDUPE_WINDOW_SEC = int(os.getenv("DEDUPE_WINDOW_SEC", "5"))

if not TARGET_URL:
    raise RuntimeError("FORWARDER_TARGET_URL is required")
if not SHARED_SECRET:
    raise RuntimeError("FORWARDER_SHARED_SECRET is required")

JOIN_PATTERNS = [
    re.compile(r": (?P<player>[A-Za-z0-9_]{1,16}) joined the game\\b"),
    re.compile(r": (?P<player>[A-Za-z0-9_]{1,16})\\[/[^\\]]+\\] logged in\\b"),
]

LEAVE_PATTERNS = [
    re.compile(r": (?P<player>[A-Za-z0-9_]{1,16}) left the game\\b"),
    re.compile(r": (?P<player>[A-Za-z0-9_]{1,16}) lost connection\\b"),
]

last_sent: dict[tuple[str, str], float] = {}


def parse_event(line: str) -> tuple[str, str] | None:
    for pattern in JOIN_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("player"), "join"

    for pattern in LEAVE_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("player"), "leave"

    return None


def should_skip_duplicate(player: str, event: str) -> bool:
    key = (player, event)
    now = time.time()
    previous = last_sent.get(key)
    if previous is not None and now - previous < DEDUPE_WINDOW_SEC:
        return True
    last_sent[key] = now
    return False


def post_event(player: str, event: str, source_line: str) -> None:
    payload = {
        "player": player,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_line": source_line.strip(),
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        TARGET_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Bridge-Secret": SHARED_SECRET,
        },
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 400:
            raise RuntimeError(f"Unexpected status code: {response.status}")


def run_stream() -> None:
    cmd = ["docker", "logs", "-f", "--tail", "0", CONTAINER_NAME]
    logger.info("Starting log stream: %s", " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue

            parsed = parse_event(line)
            if not parsed:
                continue

            player, event = parsed
            if should_skip_duplicate(player, event):
                continue

            try:
                post_event(player, event, line)
                logger.info(
                    "Forwarded event player=%s event=%s",
                    player,
                    event,
                )
            except (urllib.error.URLError, RuntimeError) as exc:
                logger.exception("Failed to forward event: %s", exc)
    finally:
        process.kill()


if __name__ == "__main__":
    while True:
        try:
            run_stream()
        except FileNotFoundError:
            logger.error(
                "'docker' command is not available. Install Docker CLI."
            )
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Forwarder crashed: %s", exc)

        logger.info("Restarting stream in %s seconds", RECONNECT_DELAY_SEC)
        time.sleep(RECONNECT_DELAY_SEC)
