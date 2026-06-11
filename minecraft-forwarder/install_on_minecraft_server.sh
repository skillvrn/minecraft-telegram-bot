#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root: sudo bash install_on_minecraft_server.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /opt/minecraft-log-forwarder
mkdir -p /etc/minecraft-log-forwarder

install -m 755 "$SCRIPT_DIR/forwarder.py" /opt/minecraft-log-forwarder/forwarder.py

if [[ ! -f /etc/minecraft-log-forwarder/forwarder.env ]]; then
  install -m 600 "$SCRIPT_DIR/forwarder.env.example" /etc/minecraft-log-forwarder/forwarder.env
  echo "Created /etc/minecraft-log-forwarder/forwarder.env from example"
  echo "Edit this file before starting service"
fi

install -m 644 "$SCRIPT_DIR/minecraft-log-forwarder.service" /etc/systemd/system/minecraft-log-forwarder.service

systemctl daemon-reload
systemctl enable minecraft-log-forwarder.service

echo "Installed. Edit /etc/minecraft-log-forwarder/forwarder.env, then run:"
echo "  sudo systemctl restart minecraft-log-forwarder.service"
echo "  sudo systemctl status minecraft-log-forwarder.service"
