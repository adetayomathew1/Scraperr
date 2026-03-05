#!/usr/bin/env python3
"""
tools/server.py
────────────────────────────────────────────────────────────────
SCRAPERRR — Flask Development Server
Layer 3: Navigation — routes data from scraper → dashboard.

Endpoints:
  GET  /              → serves index.html
  GET  /api/articles  → returns .tmp/articles.json payload
  POST /api/refresh   → triggers forced scrape run
  GET  /api/health    → health check
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from dotenv import load_dotenv
try:
    from supabase import create_client
    SUPABASE_OK = True
except ImportError:
    SUPABASE_OK = False

# ── Setup ──────────────────────────────────────────────────────
load_dotenv()
ROOT_DIR  = Path(__file__).parent.parent
TMP_DIR   = ROOT_DIR / ".tmp"
OUT_FILE  = TMP_DIR / "articles.json"

app = Flask(
    __name__,
    static_folder=str(ROOT_DIR / "static"),
    template_folder=str(ROOT_DIR)
)
CORS(app)   # Allow dashboard JS to call API

# ── Root — serve dashboard ─────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(ROOT_DIR), "index.html")

# ── Static files ───────────────────────────────────────────────
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(ROOT_DIR / "static"), filename)

# ── API: Articles ──────────────────────────────────────────────
@app.route("/api/articles")
def get_articles():
    """Return cached articles payload from .tmp/articles.json"""
    if not OUT_FILE.exists():
        return jsonify({
            "articles":     [],
            "last_fetched": None,
            "total_count":  0,
            "sources_hit":  [],
            "message":      "No data yet. POST /api/refresh to scrape."
        }), 200

    try:
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── API: Force Refresh ─────────────────────────────────────────
@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Trigger a forced scrape run (bypasses 24h gate)."""
    try:
        scraper_path = Path(__file__).parent / "scraper.py"
        result = subprocess.run(
            [sys.executable, str(scraper_path), "--force"],
            capture_output=True,
            timeout=120,
            cwd=str(ROOT_DIR),
            # Force UTF-8 so Windows emoji in logs never causes exit-code 1
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        )

        # Do NOT trust returncode — emoji chars in stderr cause code 1 on Windows
        # Instead, verify the output file was actually written/updated
        if not OUT_FILE.exists():
            stderr_txt = (result.stderr or b"").decode("utf-8", errors="replace")[:300]
            return jsonify({
                "success": False,
                "error":   f"Scraper ran but produced no output. stderr: {stderr_txt}"
            }), 500

        with open(OUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return jsonify({
            "success":      True,
            "total_count":  data.get("total_count", 0),
            "sources_hit":  data.get("sources_hit", []),
            "last_fetched": data.get("last_fetched"),
            "casualties":   data.get("casualties", {})
        }), 200

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Scraper timed out (120s)"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── API: Casualty History ──────────────────────────────────────────────
@app.route("/api/history")
def get_casualty_history():
    """Return last 7 days of casualty snapshots from Supabase."""
    if not SUPABASE_OK:
        return jsonify({"error": "supabase package not installed"}), 500
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_ANON_KEY")
    if not sb_url or not sb_key:
        return jsonify({"error": "Supabase env vars not configured"}), 500
    try:
        sb = create_client(sb_url, sb_key)
        result = sb.table("casualty_snapshots") \
            .select("*") \
            .order("recorded_at", desc=True) \
            .limit(500) \
            .execute()
        return jsonify({"data": result.data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── API: Health ────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({
        "status":    "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_file": str(OUT_FILE),
        "data_exists": OUT_FILE.exists()
    }), 200

# ── Run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════╗
║   SCRAPERRR — War Intelligence Server   ║
╠══════════════════════════════════════════╣
║  Dashboard  →  http://localhost:{port}      ║
║  Articles   →  http://localhost:{port}/api/articles ║
║  Refresh    →  POST /api/refresh        ║
╚══════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=True)
