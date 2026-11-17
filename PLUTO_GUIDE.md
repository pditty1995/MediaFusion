# Pluto TV browser guide

The guide is an optional, standalone FastAPI app that reads the public Pluto TV US M3U playlist. It does not initialize MediaFusion's task worker or require MediaFusion's database `.env` settings.

From the repository root, install the project dependencies if needed and run:

```bash
uv sync
uv run uvicorn pluto_guide:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000/> or <http://127.0.0.1:8000/pluto-guide>. Search and category filters are available; selecting a channel opens its playlist URL in a new tab.

To stop the server, press **Control-C** in Terminal.

This is separate from the main MediaFusion server (`api.main:app`), which requires the full configuration and database setup described in `deployment/README.md`.
