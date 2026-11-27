#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$SCRIPT_DIR/lfhai-wifi.env}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Create $ENV_FILE from lfhai-wifi.env.example" >&2
    exit 1
fi
chmod 600 "$ENV_FILE"
set -a
source "$ENV_FILE"
set +a

: "${WIFI_SSID:?WIFI_SSID is required}"
: "${WIFI_PASSWORD:?WIFI_PASSWORD is required}"

if ! command -v nmcli >/dev/null 2>&1; then
    echo "nmcli is required to join Wi-Fi" >&2
    exit 1
fi

IFACE="${WIFI_IFACE:-wlan0}"
nmcli radio wifi on
ACTIVE=" $(nmcli -t -f NAME con show --active | tr '\n' ' ') "
if [[ "$ACTIVE" == *" $WIFI_SSID "* ]]; then
    echo "Already connected to $WIFI_SSID"
else
    nmcli dev wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD" name "$WIFI_SSID" ifname "$IFACE"
fi
