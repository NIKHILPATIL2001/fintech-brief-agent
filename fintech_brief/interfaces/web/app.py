"""
Local web UI — run the pipeline without memorizing CLI flags.

Binds to 127.0.0.1 only. Not intended for production exposure.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

ROOT = Path(__file__).resolve().parents[3]
_WEB_ROOT = Path(__file__).resolve().parent

_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "mode": None,
    "started_at": None,
    "last": None,
}


def _run_subprocess(mode: str) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    cmd = [sys.executable, "-m", "fintech_brief", "--mock" if mode == "mock" else "--now"]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=900,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Run exceeded 15 minute timeout.",
            "duration_sec": int(time.perf_counter() - t0),
        }
    except OSError as e:
        return {"ok": False, "error": str(e), "duration_sec": int(time.perf_counter() - t0)}

    duration = int(time.perf_counter() - t0)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "duration_sec": duration,
        "stderr": proc.stderr or "",
        "stdout": proc.stdout or "",
    }


def _background_run(mode: str) -> None:
    try:
        result = _run_subprocess(mode)
        with _lock:
            _state["last"] = {**result, "mode": mode, "finished_at": time.time()}
    finally:
        with _lock:
            _state["running"] = False
            _state["mode"] = None
            _state["started_at"] = None


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_WEB_ROOT / "templates"),
        static_folder=str(_WEB_ROOT / "static"),
    )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        with _lock:
            last = dict(_state["last"]) if _state["last"] else None
            return jsonify(
                {
                    "running": _state["running"],
                    "mode": _state["mode"],
                    "started_at": _state["started_at"],
                    "last": last,
                }
            )

    @app.post("/api/run")
    def run():
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "mock")
        if mode not in ("mock", "now"):
            return jsonify({"ok": False, "error": "mode must be mock or now."}), 400
        if mode == "now" and not data.get("confirm"):
            return jsonify(
                {
                    "ok": False,
                    "error": 'Sending email requires confirm: true in the JSON body.',
                }
            ), 400

        with _lock:
            if _state["running"]:
                return jsonify({"ok": False, "error": "A run is already in progress."}), 409
            _state["running"] = True
            _state["mode"] = mode
            _state["started_at"] = time.time()

        thread = threading.Thread(target=_background_run, args=(mode,), daemon=True)
        thread.start()
        return jsonify({"ok": True, "accepted": True, "mode": mode})

    @app.get("/api/last/brief.html")
    def last_brief():
        with _lock:
            last = _state.get("last")
            if not last or last.get("mode") != "mock":
                return ("No mock output yet. Run Preview brief first.", 404)
            html_out = last.get("stdout") or ""
            if not html_out.strip():
                return ("No HTML captured.", 404)
        buf = BytesIO(html_out.encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype="text/html",
            as_attachment=True,
            download_name="fintech_brief_preview.html",
        )

    @app.get("/api/learn/summary")
    def learn_summary():
        from fintech_brief.core.preferences import LearnedPreferences

        lp = LearnedPreferences()
        return jsonify({"ok": True, **lp.summary()})

    @app.post("/api/learn")
    def learn():
        from fintech_brief.core.preferences import LearnedPreferences

        data = request.get_json(silent=True) or {}
        action = data.get("action")
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"ok": False, "error": "title is required"}), 400
        if action not in ("penalize", "boost"):
            return jsonify({"ok": False, "error": "action must be penalize or boost"}), 400

        lp = LearnedPreferences()
        if action == "penalize":
            tokens = lp.learn_penalize(title)
        else:
            tokens = lp.learn_boost(title)
        return jsonify({"ok": True, "tokens_added": tokens, **lp.summary()})

    return app


def run_dev_server(host: str = "127.0.0.1", port: int | None = None) -> None:
    load_dotenv(ROOT / ".env")
    p = port or int(os.environ.get("FB_WEB_PORT", "5050"))
    app = create_app()
    print(f"\n  FinTech Brief console → http://{host}:{p}\n")
    app.run(host=host, port=p, debug=False, use_reloader=False, threaded=True)
