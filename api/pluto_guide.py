"""MediaFusion Pluto TV browser guide.

This module exposes a small public playlist/EPG page and API endpoints.
It is intentionally independent of the rest of MediaFusion's databases.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

PLUTO_M3U_URL = (
    "https://raw.githubusercontent.com/OwnerPlugins/pluto-tv-m3u/"
    "refs/heads/main/pluto-live-US.m3u"
)

app = FastAPI(title="Pluto TV Public Guide", docs_url=None, redoc_url=None)


def _attribute(attrs: str, name: str) -> str:
    match = re.search(rf'(?:^|\s){re.escape(name)}="([^"]*)"', attrs)
    return match.group(1).strip() if match else ""


def parse_m3u(content: str) -> list[dict]:
    channels: list[dict] = []
    pending_attrs: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            comma = line.find(",")
            pending_attrs = line[8:comma] if comma >= 0 else ""
            continue

        if line.startswith("#") or pending_attrs is None:
            continue

        name = ""
        comma = line.find(",")
        if comma >= 0:
            name = line[comma + 1:].strip()

        if not name:
            name = _attribute(pending_attrs, "tvg-name")

        stream_url = line if comma < 0 else line[:comma].strip()

        if stream_url:
            parsed = urlparse(stream_url)
            if parsed.scheme not in {"http", "https"}:
                pending_attrs = None
                continue

            channels.append(
                {
                    "name": name or parsed.path.rsplit("/", 1)[-1] or "Unnamed channel",
                    "tvg_id": _attribute(pending_attrs, "tvg-id"),
                    "logo": _attribute(pending_attrs, "tvg-logo"),
                    "group": _attribute(pending_attrs, "group-title") or "Pluto TV",
                    "stream_url": stream_url,
                }
            )
        pending_attrs = None

    return channels


async def load_channels() -> list[dict]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(PLUTO_M3U_URL)

    if response.status_code >= 400:
        raise HTTPException(502, "Unable to load the public Pluto TV playlist")

    channels = parse_m3u(response.text)
    if not channels:
        raise HTTPException(502, "The public Pluto TV playlist contained no channels")
    return channels


@app.get("/api/pluto/channels")
async def pluto_channels(
    query: str | None = Query(None, description="Channel name filter"),
    group: str | None = Query(None, description="Category filter"),
):
    channels = await load_channels()

    if query:
        needle = query.strip().lower()
        channels = [channel for channel in channels if needle in channel["name"].lower()]

    if group:
        channels = [channel for channel in channels if channel["group"].lower() == group.lower()]

    return JSONResponse({"count": len(channels), "channels": channels})


@app.get("/pluto-guide", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def pluto_guide():
    return HTMLResponse(CSS + JS)


CSS = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pluto TV Program Guide</title>
  <style>
    :root { color-scheme: dark; --bg:#090b10; --panel:#151821; --line:#292d38; --text:#f5f7fb; --muted:#9da5b4; --accent:#ffb000; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter,system-ui,-apple-system,sans-serif; }
    header { position:sticky; top:0; z-index:10; background:rgba(9,11,16,.96); border-bottom:1px solid var(--line); padding:18px 24px; backdrop-filter:blur(12px); }
    .top { display:flex; align-items:center; justify-content:space-between; gap:18px; max-width:1500px; margin:auto; }
    h1 { margin:0; font-size:24px; }
    .controls { display:flex; gap:10px; width:min(680px,70%); }
    input, select { height:42px; border:1px solid var(--line); border-radius:8px; background:#11141b; color:var(--text); padding:0 12px; }
    input { flex:1; min-width:180px; } select { max-width:220px; }
    main { max-width:1500px; margin:auto; padding:24px; }
    .status { color:var(--muted); margin:0 0 16px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:14px; }
    .channel { display:flex; align-items:center; gap:12px; min-height:92px; padding:12px; background:var(--panel); border:1px solid var(--line); border-radius:10px; color:inherit; text-decoration:none; transition:.15s ease; }
    .channel:hover { border-color:var(--accent); transform:translateY(-2px); }
    .logo { width:68px; height:68px; flex:none; object-fit:contain; background:#fff; border-radius:8px; padding:5px; }
    .logo-fallback { display:grid; place-items:center; font-size:20px; font-weight:800; color:#111; }
    .name { font-weight:700; line-height:1.25; }
    .group { color:var(--muted); font-size:12px; margin-top:7px; }
    .error { color:#ff9b9b; border:1px solid #643838; background:#261414; border-radius:8px; padding:14px; }
    @media (max-width:700px) { header { padding:14px; } .top { align-items:stretch; flex-direction:column; } .controls { width:100%; } h1 { font-size:20px; } main { padding:14px; } }
  </style>
</head>
<body>
  <header>
    <div class="top">
      <h1>Pluto TV Guide</h1>
      <div class="controls">
        <input id="search" type="search" placeholder="Search channels" aria-label="Search channels">
        <select id="group" aria-label="Category"><option value="">All categories</option></select>
      </div>
    </div>
  </header>
  <main>
    <p class="status" id="status">Loading public channels…</p>
    <div class="grid" id="grid"></div>
  </main>
  <script src="/static/pluto-guide.js"></script>
</body>
</html>'''

JS = r'''const grid = document.getElementById('grid');
const status = document.getElementById('status');
const search = document.getElementById('search');
const group = document.getElementById('group');
let channels = [];

function esc(value) {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function render() {
  const needle = search.value.trim().toLowerCase();
  const category = group.value;
  const filtered = channels.filter(channel =>
    (!needle || channel.name.toLowerCase().includes(needle)) &&
    (!category || channel.group === category)
  );

  status.textContent = `${filtered.length} channel${filtered.length === 1 ? '' : 's'} available`;
  grid.innerHTML = filtered.map(channel => {
    const letter = esc(channel.name.charAt(0).toUpperCase() || 'P');
    const logo = channel.logo
      ? `<img class="logo" src="${esc(channel.logo)}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'"><div class="logo logo-fallback" style="display:none">${letter}</div>`
      : `<div class="logo logo-fallback">${letter}</div>`;
    return `<a class="channel" href="${esc(channel.stream_url)}" target="_blank" rel="noopener noreferrer">${logo}<div><div class="name">${esc(channel.name)}</div><div class="group">${esc(channel.group)}</div></div></a>`;
  }).join('');
}

async function init() {
  try {
    const response = await fetch('/api/pluto/channels');
    if (!response.ok) throw new Error('Could not load the channel list');
    const data = await response.json();
    channels = data.channels;

    const categories = [...new Set(channels.map(channel => channel.group).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    group.innerHTML = '<option value="">All categories</option>' + categories.map(category => `<option value="${esc(category)}">${esc(category)}</option>`).join('');
    render();
  } catch (error) {
    status.innerHTML = `<span class="error">${esc(error.message)}</span>`;
  }
}

search.addEventListener('input', render);
group.addEventListener('change', render);
init();'''


# The route exists mainly for compatibility with static-only deployments.
from fastapi.staticfiles import StaticFiles

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
(static_dir / "pluto-guide.js").write_text(JS, encoding="utf-8")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
