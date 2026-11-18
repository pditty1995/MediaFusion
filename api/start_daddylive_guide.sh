#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PID_FILE="$HOME/.mediafusion-daddylive-guide.pid"
LOG_DIR="$HOME/Library/Logs/MediaFusion"
LOG_FILE="$LOG_DIR/daddylive-guide.log"
DEFAULT_PORT=8000

usage() {
  cat <<'EOF'
Usage:
  start_daddylive_guide.sh start <this-Mac-private-LAN-IPv4> [port]
  start_daddylive_guide.sh status
  start_daddylive_guide.sh stop

The start command only binds to a private IPv4 address currently assigned to
this Mac. It does not listen on all network interfaces.
EOF
}

validate_lan_ip() {
  local candidate="$1"

  # Confirm this is a private IPv4 address assigned to one of this Mac's interfaces.
  if ! python3 - "$candidate" <<'PY'
import ipaddress
import re
import subprocess
import sys

candidate = sys.argv[1]
try:
    address = ipaddress.ip_address(candidate)
except ValueError:
    sys.exit("Error: provide a valid IPv4 address.")

if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local:
    sys.exit("Error: address must be a private LAN IPv4 address (not loopback or link-local).")

try:
    output = subprocess.check_output(["ifconfig"], text=True, stderr=subprocess.DEVNULL)
except (OSError, subprocess.CalledProcessError):
    sys.exit("Error: could not read this Mac's network interfaces using ifconfig.")

assigned = set(re.findall(r"^\s*inet\s+(\d+\.\d+\.\d+\.\d+)\b", output, re.MULTILINE))
if candidate not in assigned:
    sys.exit("Error: that private address is not currently assigned to this Mac.")
PY
  then
    return 1
  fi
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

case "${1:-}" in
  start)
    if [[ $# -lt 2 || $# -gt 3 ]]; then
      usage >&2
      exit 2
    fi

    LAN_IP="$2"
    PORT="${3:-$DEFAULT_PORT}"
    validate_lan_ip "$LAN_IP"

    if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
      echo "Error: port must be a number from 1 to 65535." >&2
      exit 2
    fi

    if is_running; then
      echo "Guide is already running (PID $(cat "$PID_FILE")). Stop it first or use another port." >&2
      exit 1
    fi
    rm -f "$PID_FILE"

    mkdir -p "$LOG_DIR"
    cd "$SCRIPT_DIR"
    nohup uv run uvicorn daddylive_guide:app --host "$LAN_IP" --port "$PORT" >>"$LOG_FILE" 2>&1 </dev/null &
    SERVER_PID=$!
    printf '%s\n' "$SERVER_PID" > "$PID_FILE"

    sleep 2
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "Server failed to start. Check $LOG_FILE" >&2
      exit 1
    fi

    echo "Guide started (PID $SERVER_PID) at http://$LAN_IP:$PORT/"
    echo "Log: $LOG_FILE"
    ;;

  status)
    if is_running; then
      echo "Guide is running (PID $(cat "$PID_FILE"))."
      echo "Log: $LOG_FILE"
    else
      rm -f "$PID_FILE"
      echo "Guide is not running."
      exit 1
    fi
    ;;

  stop)
    if ! is_running; then
      rm -f "$PID_FILE"
      echo "Guide is not running."
      exit 1
    fi

    SERVER_PID="$(cat "$PID_FILE")"
    kill "$SERVER_PID"
    for _ in {1..10}; do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "Guide stopped."
        exit 0
      fi
      sleep 1
    done

    echo "Server did not stop after SIGTERM; PID $SERVER_PID is still running." >&2
    exit 1
    ;;

  *)
    usage >&2
    exit 2
    ;;
esac
