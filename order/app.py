"""
Order Server - Bazar.com
========================

Handles purchases and keeps a persistent log of every order in a CSV file.

Endpoints
---------
POST /purchase/<item_id>   buy one copy of a book
GET  /orders               list every order received so far

Purchase flow
-------------
1. Ask the catalog server for the book (GET /info/<id>) to check it is in stock.
2. If it is, ask the catalog to decrement the stock by one
   (PUT /update/<id> {"quantity_delta": -1}).
3. Append the order to data/orders.csv and print "bought book <title>".
The purchase fails if the book is unknown or out of stock.
"""

import csv
import logging
import os
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
ORDERS_FILE = os.path.join(DATA_DIR, "orders.csv")
FIELDS = ["order_id", "item_id", "title", "price", "timestamp"]

# Where the catalog server lives. In docker-compose this is the service name.
CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:5001")
TIMEOUT = 5  # seconds for calls to the catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ORDER] %(message)s")
log = logging.getLogger("order")

app = Flask(__name__)
lock = threading.Lock()  # protects the orders file and the order counter


# --------------------------------------------------------------------------- #
# CSV storage helpers
# --------------------------------------------------------------------------- #
def init_storage():
    """Create the orders file with a header row if it does not exist yet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def read_orders():
    with open(ORDERS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_order(item_id, title, price):
    """Append one order to the log and return it. Order ids keep increasing."""
    with lock:
        order = {
            "order_id": len(read_orders()) + 1,
            "item_id": item_id,
            "title": title,
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with open(ORDERS_FILE, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerow(order)
    return order


# --------------------------------------------------------------------------- #
# REST endpoints
# --------------------------------------------------------------------------- #
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

    # Step 2: decrement the stock. The catalog does this atomically and refuses
    # with 409 if another request bought the last copy in the meantime.
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

    # Step 3: record the order persistently.
    order = append_order(item_id, book["title"], book["price"])
    log.info("bought book %s", book["title"])
    return jsonify({"message": f"bought book {book['title']}", "order": order})


@app.route("/orders", methods=["GET"])
def orders():
    with lock:
        return jsonify(read_orders())


if __name__ == "__main__":
    init_storage()
    port = int(os.environ.get("PORT", 5002))
    log.info("Order server listening on port %d (catalog at %s)", port, CATALOG_URL)
    app.run(host="0.0.0.0", port=port, threaded=True)
