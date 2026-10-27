"""POST finished run summaries to the Scoreboard Pi (LAN only).

Does not talk to saintcon.org. Only submits when a run finishes and
summary.json is written; failed posts are queued for retry (no full
results/ tree scan on startup).
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from baton_relay.config import ScoreboardConfig

log = logging.getLogger(__name__)

SUBMITTED_MARKER = "scoreboard_submitted"
PENDING_QUEUE = "scoreboard_pending.jsonl"
DEFAULT_RETRY_INTERVAL_S = 30.0


def bearer_token_from_base_url(base_url: str) -> str:
    """API key is the Pi IP — same as the host in base_url."""
    host = urlparse(base_url).hostname
    if not host:
        raise ValueError(f"scoreboard base_url has no host: {base_url!r}")
    return host


def runs_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/v1/runs"


def _utc_submitted_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pending_queue_path(root_dir: Path) -> Path:
    return Path(root_dir) / "data" / PENDING_QUEUE


def is_submitted(run_dir: Path) -> bool:
    return (Path(run_dir) / SUBMITTED_MARKER).is_file()


def mark_submitted(run_dir: Path) -> None:
    path = Path(run_dir) / SUBMITTED_MARKER
    path.write_text("", encoding="utf-8")


def build_payload(
    cfg: ScoreboardConfig,
    summary: dict[str, Any],
    *,
    submitted_at: str | None = None,
) -> dict[str, Any]:
    return {
        "machine_id": cfg.machine_id,
        "submitted_at": submitted_at or _utc_submitted_at(),
        "summary": summary,
    }


def post_run(cfg: ScoreboardConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """POST once. Raises URLError/HTTPError/OSError on failure."""
    token = bearer_token_from_base_url(cfg.base_url)
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    req = Request(
        runs_url(cfg.base_url),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=cfg.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            if resp.status and resp.status >= 400:
                raise URLError(f"scoreboard HTTP {resp.status}: {raw[:200]}")
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise URLError(f"scoreboard HTTP {exc.code}: {detail or exc.reason}") from exc
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def enqueue_pending(root_dir: Path, *, run_dir: Path, payload: dict[str, Any]) -> None:
    path = pending_queue_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"run_dir": str(Path(run_dir)), "payload": payload}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        fh.flush()


def _read_queue(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(rec, dict)
                    and isinstance(rec.get("run_dir"), str)
                    and isinstance(rec.get("payload"), dict)
                ):
                    out.append(rec)
    except OSError:
        return out
    return out


def _write_queue(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass
        return
    text = "".join(
        json.dumps(rec, ensure_ascii=False, default=str) + "\n" for rec in records
    )
    path.write_text(text, encoding="utf-8")


def submit_summary(
    cfg: ScoreboardConfig,
    *,
    root_dir: Path,
    summary_path: Path,
    enqueue_on_failure: bool = True,
) -> bool:
    """POST the written summary.json. Returns True on success. Never raises."""
    if not cfg.enabled:
        return False
    summary_path = Path(summary_path)
    run_dir = summary_path.parent
    if is_submitted(run_dir):
        return True
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("scoreboard: cannot read %s: %s", summary_path, exc)
        return False
    if not isinstance(summary, dict):
        log.warning("scoreboard: %s is not a JSON object", summary_path)
        return False
    payload = build_payload(cfg, summary)
    try:
        post_run(cfg, payload)
        mark_submitted(run_dir)
        log.info("scoreboard: submitted %s", summary_path)
        return True
    except Exception as exc:
        log.warning("scoreboard: POST failed for %s: %s", summary_path, exc)
        if enqueue_on_failure:
            try:
                enqueue_pending(root_dir, run_dir=run_dir, payload=payload)
            except OSError as qexc:
                log.warning("scoreboard: could not enqueue pending: %s", qexc)
        return False


def retry_pending(cfg: ScoreboardConfig, *, root_dir: Path) -> int:
    """Retry only the pending queue (not a full results/ scan). Returns successes."""
    if not cfg.enabled:
        return 0
    path = pending_queue_path(root_dir)
    records = _read_queue(path)
    if not records:
        return 0
    remaining: list[dict[str, Any]] = []
    succeeded = 0
    seen_dirs: set[str] = set()
    for rec in records:
        run_key = rec["run_dir"]
        run_dir = Path(run_key)
        payload = rec["payload"]
        if run_key in seen_dirs:
            continue
        seen_dirs.add(run_key)
        if is_submitted(run_dir):
            succeeded += 1
            continue
        try:
            post_run(cfg, payload)
            mark_submitted(run_dir)
            succeeded += 1
            log.info("scoreboard: retry succeeded for %s", run_dir)
        except Exception as exc:
            log.warning("scoreboard: retry failed for %s: %s", run_dir, exc)
            remaining.append(rec)
    try:
        _write_queue(path, remaining)
    except OSError as exc:
        log.warning("scoreboard: could not rewrite pending queue: %s", exc)
    return succeeded


class ScoreboardUploader:
    """Non-blocking submit + periodic retry of the pending queue only."""

    def __init__(
        self,
        cfg: ScoreboardConfig,
        root_dir: Path,
        *,
        retry_interval_s: float = DEFAULT_RETRY_INTERVAL_S,
    ) -> None:
        self._cfg = cfg
        self._root = Path(root_dir)
        self._retry_interval = max(5.0, float(retry_interval_s))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return self._cfg.enabled

    def update_config(self, cfg: ScoreboardConfig) -> None:
        with self._lock:
            was_enabled = self._cfg.enabled
            self._cfg = cfg
        if cfg.enabled and not was_enabled:
            self.start()
        elif not cfg.enabled and was_enabled:
            self.stop()

    def start(self) -> None:
        if not self._cfg.enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="scoreboard-retry", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def submit_async(self, summary_path: Path) -> None:
        if not self._cfg.enabled:
            return
        threading.Thread(
            target=self._submit_once,
            args=(Path(summary_path),),
            name="scoreboard-post",
            daemon=True,
        ).start()

    def _submit_once(self, summary_path: Path) -> None:
        with self._lock:
            cfg = self._cfg
            root = self._root
        submit_summary(cfg, root_dir=root, summary_path=summary_path)

    def _loop(self) -> None:
        # Drain any leftovers from prior sessions first (queue file only).
        while True:
            with self._lock:
                cfg = self._cfg
                root = self._root
            if cfg.enabled:
                try:
                    retry_pending(cfg, root_dir=root)
                except Exception as exc:
                    log.warning("scoreboard: retry loop error: %s", exc)
            if self._stop.wait(self._retry_interval):
                break
