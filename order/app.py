"""
Order Server - Bazar.com
========================

Handles purchases.

Endpoints
---------
POST /purchase/<item_id>   buy one copy of a book

Purchase flow
-------------
1. Ask the catalog server for the book (GET /info/<id>) to check it is in stock.
2. If it is, ask the catalog to decrement the stock by one
   (PUT /update/<id> {"quantity_delta": -1}).
3. Print "bought book <title>".
The purchase fails if the book is unknown or out of stock.
"""

import logging
import os

import requests
from flask import Flask, jsonify

# Where the catalog server lives. In docker-compose this is the service name.
CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:5001")
TIMEOUT = 5  # seconds for calls to the catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ORDER] %(message)s")
log = logging.getLogger("order")

app = Flask(__name__)


@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase(item_id):
    # Step 1: query the catalog to make sure the book exists and is in stock.
    try:
        r = requests.get(f"{CATALOG_URL}/info/{item_id}", timeout=TIMEOUT)
    except requests.RequestException as e:
        log.error("catalog unreachable: %s", e)
        return jsonify({"error": "catalog server unavailable"}), 503
    if r.status_code == 404:
        log.info("purchase item=%d failed: no such item", item_id)
        return jsonify({"error": f"item {item_id} not found"}), 404
    book = r.json()
    if book["quantity"] <= 0:
        log.info("purchase item=%d failed: out of stock", item_id)
        return jsonify({"error": "out of stock", "title": book["title"]}), 409

    # Step 2: decrement the stock. The catalog refuses with 409 if another
    # request bought the last copy in the meantime.
    try:
        r = requests.put(f"{CATALOG_URL}/update/{item_id}",
                         json={"quantity_delta": -1}, timeout=TIMEOUT)
    except requests.RequestException as e:
        log.error("catalog unreachable: %s", e)
        return jsonify({"error": "catalog server unavailable"}), 503
    if r.status_code == 409:
        log.info("purchase item=%d failed: out of stock", item_id)
        return jsonify({"error": "out of stock", "title": book["title"]}), 409
    if not r.ok:
        return jsonify({"error": "catalog update failed"}), 502

    log.info("bought book %s", book["title"])
    return jsonify({"message": f"bought book {book['title']}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    log.info("Order server listening on port %d (catalog at %s)", port, CATALOG_URL)
    app.run(host="0.0.0.0", port=port, threaded=True)
