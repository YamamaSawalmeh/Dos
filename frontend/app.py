"""
Front-end Server - Bazar.com
============================

The only service clients talk to. It does light processing (input checks,
logging) and forwards each request to the right back-end service.

Endpoints
---------
GET  /search/<topic>       -> catalog  GET /search/<topic>
GET  /info/<item_id>       -> catalog  GET /info/<item_id>
"""

import logging
import os

import requests
from flask import Flask, jsonify

CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:5001")
TIMEOUT = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s [FRONTEND] %(message)s")
log = logging.getLogger("frontend")

app = Flask(__name__)


def forward(method, url):
    """Send the request to a back-end service and relay its JSON reply and status."""
    try:
        r = requests.request(method, url, timeout=TIMEOUT)
    except requests.RequestException as e:
        log.error("%s %s failed: %s", method, url, e)
        return jsonify({"error": "back-end service unavailable"}), 503
    log.info("%s %s -> %d", method, url, r.status_code)
    return jsonify(r.json()), r.status_code


@app.route("/search/<path:topic>", methods=["GET"])
def search(topic):
    log.info("search(%r)", topic)
    return forward("GET", f"{CATALOG_URL}/search/{topic}")


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    log.info("info(%d)", item_id)
    return forward("GET", f"{CATALOG_URL}/info/{item_id}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log.info("Front-end listening on port %d (catalog=%s)", port, CATALOG_URL)
    app.run(host="0.0.0.0", port=port, threaded=True)
