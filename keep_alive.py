# keep_alive.py
import os
import time
import logging
import urllib.request
from threading import Thread

from flask import Flask

app = Flask(__name__)

# Hide the noisy per-request logs from the ping traffic
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/")
def home():
    return "Bot is running on Render!", 200


@app.route("/health")
def health():
    return "OK", 200


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


def self_ping(interval=240):
    """Ping our own public URL every 4 minutes (Render sets RENDER_EXTERNAL_URL)."""
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://aisanamusic.onrender.com") or os.environ.get("APP_URL") #change live url
    if not url:
        print("[keep_alive] RENDER_EXTERNAL_URL/APP_URL not set, self-ping disabled.")
        return

    url = url.rstrip("/") + "/health"
    time.sleep(60)  # let the web server start first
    while True:
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                print(f"[keep_alive] self-ping {r.status}")
        except Exception as e:
            print(f"[keep_alive] self-ping failed: {e}")
        time.sleep(interval)


def keep_alive():
    Thread(target=run, daemon=True).start()
    Thread(target=self_ping, daemon=True).start()
