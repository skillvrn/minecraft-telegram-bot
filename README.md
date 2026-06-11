# minecraft-telegram-bot

Bridge for Minecraft join/leave notifications when Minecraft host cannot access Telegram directly.

## Architecture

1. Minecraft host in RU:
	- Reads Minecraft container logs.
	- Detects player join/leave events.
	- Sends events to external webhook over HTTPS.
2. External host (outside RU):
	- Runs this bot service.
	- Accepts webhook events.
	- Sends messages to Telegram group.

## Event format

Bot accepts POST requests to `/minecraft/events` with JSON:

```json
{
  "player": "Notch",
  "event": "join",
  "timestamp": "2026-06-10T10:00:00Z",
  "source_line": "[10:00:00 INFO]: Notch joined the game"
}
```

Required header:

`X-Bridge-Secret: <WEBHOOK_SHARED_SECRET>`

## Environment variables (bot)

- `TELEGRAM_BOT_TOKEN` - token from BotFather.
- `TELEGRAM_CHAT_ID` - target group/chat id.
- `WEBHOOK_SHARED_SECRET` - shared secret with forwarder.
- `BOT_LISTEN_PORT` - internal port (default `8080`).
- `BOT_LISTEN_HOST` - bind host (default `0.0.0.0`).
- `TELEGRAM_API_BASE` - optional Telegram API base.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export WEBHOOK_SHARED_SECRET=...
python bot.py
```

Health check:

```bash
curl http://127.0.0.1:8080/healthz
```

## Deploying bot with GitHub Actions

Workflow file: `.github/workflows/ci-cd.yaml`.

Set repository variables:

- `DOCKER_REPO`
- `DEPLOY_SSH_HOST` (external host, e.g. `hastapronto.xyz`)
- `DEPLOY_SSH_PORT` (e.g. `22875`)
- `DEPLOY_SSH_USERNAME` (e.g. `sk`)
- `TELEGRAM_CHAT_ID`
- `BOT_LISTEN_PORT` (public bot port on external host, e.g. `18080`)

Set repository secrets:

- `DOCKER_USERNAME`
- `DOCKER_PASSWORD`
- `DEPLOY_SSH_PRIVATE_KEY`
- `TELEGRAM_BOT_TOKEN`
- `WEBHOOK_SHARED_SECRET`

The workflow builds and pushes image, renders `docker-compose.yaml` from template, copies it to `/srv/minecraft-telegram-bot`, and runs `docker compose up -d` on the external server.

## Minecraft host setup (RU server)

Directory: `minecraft-forwarder/` contains a lightweight forwarder service.

### 1. Copy files to Minecraft host

```bash
scp -r minecraft-forwarder user@1.2.3.4:/home/user/
```

### 2. Install service

```bash
ssh user@1.2.3.4
cd ~/minecraft-forwarder
sudo bash install_on_minecraft_server.sh
```

### 3. Configure forwarder

Edit `/etc/minecraft-log-forwarder/forwarder.env`:

- `FORWARDER_TARGET_URL` -> `http://<external-host-or-ip>:<BOT_LISTEN_PORT>/minecraft/events`
- `FORWARDER_SHARED_SECRET` -> same as `WEBHOOK_SHARED_SECRET`
- `MC_DOCKER_CONTAINER` -> exact Minecraft container name in `/srv/minecraft` stack

### 4. Start and verify

```bash
sudo systemctl restart minecraft-log-forwarder.service
sudo systemctl status minecraft-log-forwarder.service
sudo journalctl -u minecraft-log-forwarder.service -f
```

## Verifying end-to-end

1. Start bot on external host.
2. Ensure port is reachable from Minecraft host.
3. Join Minecraft server with test account.
4. Confirm message appears in Telegram group.
5. Disconnect and confirm leave message.

## Notes

- Forwarder supports common vanilla/Paper join/leave log patterns.
- Duplicate events are deduplicated in a short time window.
- If Docker container name differs from `minecraft`, set `MC_DOCKER_CONTAINER` accordingly.
