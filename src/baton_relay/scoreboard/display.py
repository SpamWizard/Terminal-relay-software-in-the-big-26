"""Local projector page. It reads results and does not push."""

from __future__ import annotations

import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from baton_relay.config import AppConfig, ConfigError, load_config
from baton_relay.scoreboard.model import build_board

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Terminal Relay</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #050816;
    --fg: #e8f1ff;
    --muted: #8aa0b8;
    --line: rgba(125, 211, 252, 0.16);
    --accent: #7dd3fc;
    --gold: #f5d76e;
    --silver: #d5dde6;
    --bronze: #e0a36a;
    --live: #5ee0a0;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; }
  body {
    background:
      radial-gradient(1200px 500px at 10% -10%, rgba(125, 211, 252, 0.16), transparent 55%),
      radial-gradient(900px 420px at 110% 0%, rgba(199, 125, 255, 0.12), transparent 50%),
      var(--bg);
    color: var(--fg);
    font-family: "Segoe UI", "Avenir Next", "Trebuchet MS", sans-serif;
  }
  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2.2rem 2.4rem 3rem;
    min-height: 100%;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1.5rem;
    padding-bottom: 1.2rem;
    border-bottom: 1px solid var(--line);
  }
  .kicker {
    margin: 0 0 0.35rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--accent);
    font-size: 0.82rem;
  }
  h1 {
    margin: 0;
    font-size: clamp(1.8rem, 3vw, 2.8rem);
    font-weight: 650;
    letter-spacing: -0.03em;
  }
  .status-wrap { text-align: right; }
  .status {
    display: inline-block;
    margin: 0;
    padding: 0.35rem 0.8rem;
    border: 1px solid var(--accent);
    border-radius: 999px;
    color: var(--accent);
    letter-spacing: 0.16em;
    font-size: 0.85rem;
  }
  .status[data-status="final"] { color: var(--gold); border-color: var(--gold); }
  .status[data-status="ended"] { color: var(--muted); border-color: var(--muted); }
  .status[data-status="upcoming"] { color: #c4b5fd; border-color: #c4b5fd; }
  .frozen {
    margin: 0 0 0.45rem;
    color: var(--gold);
    letter-spacing: 0.18em;
    font-size: 0.78rem;
  }
  .updated { margin: 0.45rem 0 0; color: var(--muted); font-size: 0.95rem; }
  #list { margin-top: 0.4rem; }
  .row {
    display: grid;
    grid-template-columns: 4.5rem 1fr auto;
    gap: 0.8rem 1.2rem;
    align-items: center;
    padding: 0.85rem 0.2rem;
    border-bottom: 1px solid var(--line);
  }
  .rank {
    font-size: clamp(1.8rem, 3vw, 2.6rem);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
  }
  .place-1 .rank { color: var(--gold); }
  .place-2 .rank { color: var(--silver); }
  .place-3 .rank { color: var(--bronze); }
  .name {
    font-size: clamp(1.55rem, 3vw, 2.5rem);
    font-weight: 650;
    letter-spacing: -0.03em;
    line-height: 1.1;
  }
  .detail, .roster {
    margin-top: 0.2rem;
    color: var(--muted);
    font-size: clamp(0.95rem, 1.5vw, 1.15rem);
  }
  .row.live .detail { color: var(--live); }
  .score {
    font-size: clamp(2rem, 4vw, 3.3rem);
    font-weight: 720;
    font-variant-numeric: tabular-nums;
    color: var(--accent);
    letter-spacing: -0.04em;
  }
  .empty {
    margin: 3rem 0;
    color: var(--muted);
    font-size: 1.6rem;
  }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <p class="kicker">Terminal Relay</p>
      <h1 id="message">Scoreboard</h1>
    </div>
    <div class="status-wrap">
      <p id="frozen" class="frozen" hidden>FROZEN</p>
      <p id="status" class="status" data-status="live">LIVE</p>
      <p id="updated" class="updated"></p>
    </div>
  </header>
  <div id="list"></div>
</main>
<script>
const INITIAL = /*BOARD*/null;

function render(board) {
  const status = String(board.status || "live");
  const pill = document.getElementById("status");
  pill.textContent = status.toUpperCase();
  pill.dataset.status = status;
  document.getElementById("message").textContent = board.message || "Scoreboard";
  document.getElementById("frozen").hidden = !board.frozen;
  const stamp = String(board.updated_at || "").replace("T", " ").replace("Z", " UTC");
  document.getElementById("updated").textContent = stamp ? ("as of " + stamp) : "";
  const list = document.getElementById("list");
  list.replaceChildren();
  const entries = Array.isArray(board.entries) ? board.entries : [];
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Waiting for the first team.";
    list.appendChild(empty);
    return;
  }
  for (const entry of entries) {
    const row = document.createElement("article");
    row.className = "row";
    const rankNo = Number(entry.rank);
    if (rankNo >= 1 && rankNo <= 3) row.classList.add("place-" + rankNo);
    const detail = entry.detail == null ? "" : String(entry.detail);
    if (detail.startsWith("live")) row.classList.add("live");
    const rank = document.createElement("div");
    rank.className = "rank";
    rank.textContent = String(entry.rank ?? "");
    const mid = document.createElement("div");
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = entry.name == null ? "" : String(entry.name);
    mid.appendChild(name);
    if (detail) {
      const line = document.createElement("div");
      line.className = "detail";
      line.textContent = detail;
      mid.appendChild(line);
    }
    if (entry.team) {
      const roster = document.createElement("div");
      roster.className = "roster";
      roster.textContent = String(entry.team);
      mid.appendChild(roster);
    }
    const score = document.createElement("div");
    score.className = "score";
    score.textContent = (typeof entry.score === "number") ? String(entry.score) : "";
    row.append(rank, mid, score);
    list.appendChild(row);
  }
}

async function refresh() {
  try {
    const res = await fetch("/board.json", { cache: "no-store" });
    if (!res.ok) return;
    render(await res.json());
  } catch (err) {
    /* keep the last board on screen */
  }
}

render(INITIAL);
setInterval(refresh, 4000);
</script>
</body>
</html>
"""


def page_html(payload: dict) -> str:
    blob = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return _PAGE.replace("/*BOARD*/null", f"/*BOARD*/{blob}", 1)


def make_server(
    config: AppConfig,
    host: str,
    port: int,
    *,
    reload: bool = True,
) -> ThreadingHTTPServer:
    holder = {"config": config}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            current = _current_config(holder, config, reload)
            path = urllib.parse.urlsplit(self.path).path
            if path == "/board.json":
                body = json.dumps(build_board(current), ensure_ascii=False).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
                return
            if path in ("/", "/index.html"):
                body = page_html(build_board(current)).encode("utf-8")
                self._send(200, "text/html; charset=utf-8", body)
                return
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            self.send_error(404)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve_board(config: AppConfig, host: str = "127.0.0.1", port: int = 8765) -> int:
    if port < 1 or port > 65535:
        print("Scoreboard display: port must be 1–65535", file=sys.stderr)
        return 1
    try:
        httpd = make_server(config, host, port)
    except OSError as exc:
        print(f"Scoreboard display: {exc}", file=sys.stderr)
        return 1
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    bound = httpd.server_address[1]
    print(f"Scoreboard display: http://{shown}:{bound}", flush=True)
    print("This page only reads results. It does not push to SaintCon.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nScoreboard display stopped.", flush=True)
    finally:
        httpd.server_close()
    return 0


def _current_config(holder: dict, original: AppConfig, reload: bool) -> AppConfig:
    if not reload:
        return holder["config"]
    try:
        return load_config(original.config_path)
    except (ConfigError, OSError):
        return holder["config"]
