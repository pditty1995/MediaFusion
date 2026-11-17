"""Standalone browser guide for the public Pluto TV US M3U playlist.

Run from the repository root with:
    uv run uvicorn pluto_guide:app --host 127.0.0.1 --port 8000

This intentionally lives outside the ``api`` package: importing ``api.*`` first
runs MediaFusion's worker setup and requires its full database configuration.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

PLAYLIST_URL = (
    "https://raw.githubusercontent.com/OwnerPlugins/pluto-tv-m3u/"
    "refs/heads/main/pluto-live-US.m3u"
)

app = FastAPI(title="Pluto TV Guide", docs_url=None, redoc_url=None)


def _attribute(attributes: str, name: str) -> str:
    match = re.search(rf'(?:^|\s){re.escape(name)}="([^"]*)"', attributes)
    return match.group(1).strip() if match else ""


def parse_m3u(text: str) -> list[dict[str, str]]:
    """Parse channel entries from an extended M3U playlist."""
    channels: list[dict[str, str]] = []
    pending_attributes: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            comma = line.find(",")
            pending_attributes = line[8:comma] if comma >= 0 else line[8:]
            continue
        if line.startswith("#") or pending_attributes is None:
            continue

        comma = line.find(",")
        stream_url = line[:comma].strip() if comma >= 0 else line
        display_name = line[comma + 1 :].strip() if comma >= 0 else ""
        parsed = urlparse(stream_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            channels.append(
                {
                    "name": display_name or _attribute(pending_attributes, "tvg-name") or "Unnamed channel",
                    "tvg_id": _attribute(pending_attributes, "tvg-id"),
                    "logo": _attribute(pending_attributes, "tvg-logo"),
                    "group": _attribute(pending_attributes, "group-title") or "Pluto TV",
                    "stream_url": stream_url,
                }
            )
        pending_attributes = None

    return channels


@app.get("/api/pluto/channels")
async def get_channels(
    query: str | None = Query(None, description="Filter channel names"),
    group: str | None = Query(None, description="Filter by category"),
):
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(PLAYLIST_URL)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(502, "Could not fetch the public Pluto TV playlist") from error

    channels = parse_m3u(response.text)
    if not channels:
        raise HTTPException(502, "The Pluto TV playlist did not contain any channel entries")

    if query:
        search = query.strip().casefold()
        channels = [item for item in channels if search in item["name"].casefold()]
    if group:
        category = group.strip().casefold()
        channels = [item for item in channels if item["group"].casefold() == category]
    return JSONResponse({"count": len(channels), "channels": channels})


PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pluto TV Guide</title>
  <style>
    :root{color-scheme:dark;--bg:#090b10;--panel:#151821;--line:#292d38;--text:#f5f7fb;--muted:#9da5b4;--accent:#ffb000}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif}
    header{position:sticky;top:0;z-index:2;background:#090b10f5;border-bottom:1px solid var(--line);padding:18px 24px}
    .top{display:flex;align-items:center;justify-content:space-between;gap:18px;max-width:1500px;margin:auto}h1{margin:0;font-size:24px}
    .controls{display:flex;gap:10px;width:min(680px,70%)}input,select{height:42px;border:1px solid var(--line);border-radius:8px;background:#11141b;color:var(--text);padding:0 12px}
    input{flex:1;min-width:180px}select{max-width:220px}main{max-width:1500px;margin:auto;padding:24px}.status{color:var(--muted);margin:0 0 16px}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}.channel{display:flex;align-items:center;gap:12px;min-height:92px;padding:12px;background:var(--panel);border:1px solid var(--line);border-radius:10px;color:inherit;text-decoration:none}
    .channel:hover{border-color:var(--accent);transform:translateY(-2px)}.logo{width:68px;height:68px;flex:none;object-fit:contain;background:#fff;border-radius:8px;padding:5px}
    .fallback{display:grid;place-items:center;color:#111;font-size:20px;font-weight:800}.name{font-weight:700;line-height:1.25}.group{color:var(--muted);font-size:12px;margin-top:7px}
    .error{color:#ff9b9b;border:1px solid #643838;background:#261414;border-radius:8px;padding:14px}
    @media(max-width:700px){header{padding:14px}.top{align-items:stretch;flex-direction:column}.controls{width:100%}h1{font-size:20px}main{padding:14px}}
  </style>
</head>
<body>
  <header><div class="top"><h1>Pluto TV Guide</h1><div class="controls">
    <input id="search" type="search" placeholder="Search channels" aria-label="Search channels">
    <select id="group" aria-label="Category"><option value="">All categories</option></select>
  </div></div></header>
  <main><p class="status" id="status">Loading public channels…</p><div class="grid" id="grid"></div></main>
<script>
const grid=document.getElementById('grid'),status=document.getElementById('status');
const search=document.getElementById('search'),group=document.getElementById('group');
let channels=[];
function esc(value){return String(value).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}
function render(){
  const needle=search.value.trim().toLowerCase(),category=group.value;
  const visible=channels.filter(c=>(!needle||c.name.toLowerCase().includes(needle))&&(!category||c.group===category));
  status.textContent=`${visible.length} channel${visible.length===1?'':'s'} available`;
  grid.innerHTML=visible.map(c=>{
    const initial=esc(c.name.charAt(0).toUpperCase()||'P');
    const logo=c.logo?`<img class="logo" src="${esc(c.logo)}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'"><div class="logo fallback" style="display:none">${initial}</div>`:`<div class="logo fallback">${initial}</div>`;
    return `<a class="channel" href="${esc(c.stream_url)}" target="_blank" rel="noopener noreferrer">${logo}<div><div class="name">${esc(c.name)}</div><div class="group">${esc(c.group)}</div></div></a>`;
  }).join('');
}
async function init(){try{
  const response=await fetch('/api/pluto/channels');if(!response.ok)throw new Error('Could not load the Pluto channel list');
  channels=(await response.json()).channels;
  const categories=[...new Set(channels.map(c=>c.group).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  group.innerHTML='<option value="">All categories</option>'+categories.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');render();
}catch(error){status.innerHTML=`<span class="error">${esc(error.message)}</span>`;}}
search.addEventListener('input',render);group.addEventListener('change',render);init();
</script>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
@app.get("/pluto-guide", response_class=HTMLResponse)
async def pluto_guide() -> HTMLResponse:
    return HTMLResponse(PAGE)
'''