import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("minecraft-telegram-bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "")
TELEGRAM_API_BASE = os.getenv(
    "TELEGRAM_API_BASE",
    "https://api.telegram.org",
)
BOT_LISTEN_HOST = os.getenv("BOT_LISTEN_HOST", "0.0.0.0")
BOT_LISTEN_PORT = int(os.getenv("BOT_LISTEN_PORT", "8080"))

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
if not TELEGRAM_CHAT_ID:
    raise RuntimeError("TELEGRAM_CHAT_ID is required")
if not WEBHOOK_SHARED_SECRET:
    raise RuntimeError("WEBHOOK_SHARED_SECRET is required")


class MinecraftEvent(BaseModel):
    player: str = Field(min_length=1, max_length=32)
    event: str
    timestamp: str | None = None
    source_line: str | None = None


app = FastAPI(title="minecraft-telegram-bridge", version="1.0.0")


async def send_telegram_message(text: str) -> dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def format_event_message(event: MinecraftEvent) -> str:
    escaped_player = event.player.replace("<", "&lt;").replace(">", "&gt;")
    if event.event == "join":
        return f"<b>{escaped_player}</b> joined the Minecraft server"
    if event.event == "leave":
        return f"<b>{escaped_player}</b> left the Minecraft server"
    return f"<b>{escaped_player}</b> event: {event.event}"


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/minecraft/events")
async def receive_event(
    event: MinecraftEvent,
    x_bridge_secret: str = Header(default="", alias="X-Bridge-Secret"),
) -> dict[str, str]:
    if x_bridge_secret != WEBHOOK_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if event.event not in {"join", "leave"}:
        raise HTTPException(status_code=400, detail="Unsupported event")

    message = format_event_message(event)
    logger.info(
        "Sending telegram message for player=%s event=%s",
        event.player,
        event.event,
    )
    await send_telegram_message(message)
    return {"status": "sent"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=BOT_LISTEN_HOST, port=BOT_LISTEN_PORT)
