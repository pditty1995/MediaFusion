# Guide app (DaddyLive guide module)

This directory contains `daddylive_guide.py`, a small FastAPI guide app. Run it from this directory so Python imports the module directly; running it as `api.daddylive_guide:app` from the repository root imports `api/__init__.py` and can trigger MediaFusion's unrelated database and worker configuration.

## Requirements

- macOS with Python 3.12+ and [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed.
- Project dependencies installed (from the repository root, run `uv sync` if needed).
- For access from other devices, the Mac and client must be on the same LAN, and macOS Firewall must allow the connection.

## Run in the foreground

From the repository root:

```bash
cd api
uv run uvicorn daddylive_guide:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/> on the Mac. Stop the foreground server with **Control-C**.

## Run in the background on the Mac LAN

The launcher binds only to the private IPv4 address you provide, not to `0.0.0.0`. It checks that the address is private and currently assigned to an interface on this Mac. Find the address (Wi-Fi is often `en0`; Ethernet may use a different interface):

```bash
ipconfig getifaddr en0
```

Then, from the repository root, launch it with that address:

```bash
bash api/start_daddylive_guide.sh start 10.28.1.220
```

Replace `10.28.1.220` with the actual private LAN IP reported for your Mac. To use a different port, supply it as the optional third argument:

```bash
bash api/start_daddylive_guide.sh start 10.28.1.220 8001
```

The script prints the URL and writes its log to `~/Library/Logs/MediaFusion/daddylive-guide.log`. From another device on the same network, open `http://<Mac-LAN-IP>:8000/` (or the selected port). The API endpoint is `/api/pluto/channels`.

Manage the background server from the repository root:

```bash
bash api/start_daddylive_guide.sh status
bash api/start_daddylive_guide.sh stop
```

The launcher does not configure automatic startup after reboot. The guide has no authentication or HTTPS; keep it on a trusted LAN and do not forward its port to the public Internet.

## Troubleshooting

- If the launcher rejects an address, verify it is the Mac's current private IPv4 address, not `127.0.0.1`, a gateway address, or another device's address. `ifconfig` lists addresses on the Mac's interfaces.
- If it starts but other devices cannot connect, check that they are on the same network, the Mac's IP has not changed, and macOS Firewall permits incoming connections to Python/Terminal on the selected port.
- Inspect the server log with `tail -f ~/Library/Logs/MediaFusion/daddylive-guide.log`.
- This is separate from the main MediaFusion server and does not require the main app's `.env` database settings when launched from this directory.
