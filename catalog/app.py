"""
Catalog Server - Bazar.com
==========================

Keeps the book catalog (stock, price and topic of every book) in a CSV file
and exposes it over HTTP REST.

Endpoints
---------
GET  /search/<topic>        query-by-subject -> [{"id", "title"}, ...]
GET  /info/<item_id>        query-by-item    -> {"id", "title", "topic", "quantity", "price"}
PUT  /update/<item_id>      update price and/or stock. JSON body, any of:
                              {"price": 45}             set a new price
                              {"quantity": 20}          set stock to an exact value
                              {"quantity_delta": -1}    add/remove stock (restock or sale)
GET  /catalog               the whole catalog (handy for debugging)

The data is persisted on disk in data/catalog.csv. On first start the file is
created from seed_catalog.csv.
"""

import csv
import logging
import os
import shutil
import threading

from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.csv")
SEED_FILE = os.path.join(BASE_DIR, "seed_catalog.csv")
FIELDS = ["id", "title", "topic", "quantity", "price"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CATALOG] %(message)s")
log = logging.getLogger("catalog")

app = Flask(__name__)

# Flask serves every request in its own thread, so all reads and writes of the
# CSV file go through this lock. This keeps "check stock then decrement" atomic
# and prevents two concurrent purchases from selling the same last copy.
lock = threading.Lock()


# --------------------------------------------------------------------------- #
# CSV storage helpers
# --------------------------------------------------------------------------- #
def init_storage():
    """Create the data file from the seed file if it does not exist yet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CATALOG_FILE):
        shutil.copy(SEED_FILE, CATALOG_FILE)
        log.info("Created %s from seed file", CATALOG_FILE)


def load_catalog():
    """Read the CSV file and return {id: book_dict}. Caller must hold the lock."""
    books = {}
    with open(CATALOG_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            books[int(row["id"])] = {
                "id": int(row["id"]),
                "title": row["title"],
                "topic": row["topic"],
                "quantity": int(row["quantity"]),
                "price": float(row["price"]),
            }
    return books


def save_catalog(books):
    """Write the catalog back to disk. Caller must hold the lock.

    We write to a temp file first and then rename it, so a crash in the middle
    of a write never leaves a half-written catalog behind.
    """
    tmp = CATALOG_FILE + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for book_id in sorted(books):
            writer.writerow(books[book_id])
    os.replace(tmp, CATALOG_FILE)


# --------------------------------------------------------------------------- #
# REST endpoints
# --------------------------------------------------------------------------- #
@app.route("/search/<path:topic>", methods=["GET"])
def search(topic):
    """Query-by-subject: return id and title of every book in the topic."""
    with lock:
        books = load_catalog()
    result = [
        {"id": b["id"], "title": b["title"]}
        for b in books.values()
        if b["topic"].lower() == topic.strip().lower()
    ]
    log.info("search topic=%r -> %d result(s)", topic, len(result))
    return jsonify(result)


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    """Query-by-item: return all details of one book."""
    with lock:
        book = load_catalog().get(item_id)
    if book is None:
        log.info("info item=%d -> not found", item_id)
        return jsonify({"error": f"item {item_id} not found"}), 404
    log.info("info item=%d -> quantity=%d price=%s", item_id, book["quantity"], book["price"])
    return jsonify(book)


@app.route("/update/<int:item_id>", methods=["PUT"])
def update(item_id):
    """Update the price and/or stock of a book.

    A negative quantity_delta that would make stock go below zero is rejected
    with 409 Conflict. The order server relies on this to fail a purchase when
    the book sold out between its stock check and its update.
    """
    body = request.get_json(silent=True) or {}
    with lock:
        books = load_catalog()
        book = books.get(item_id)
        if book is None:
            return jsonify({"error": f"item {item_id} not found"}), 404

        if "price" in body:
            book["price"] = float(body["price"])
        if "quantity" in body:
            book["quantity"] = int(body["quantity"])
        if "quantity_delta" in body:
            new_qty = book["quantity"] + int(body["quantity_delta"])
            if new_qty < 0:
                log.info("update item=%d rejected: out of stock", item_id)
                return jsonify({"error": "out of stock", "quantity": book["quantity"]}), 409
            book["quantity"] = new_qty

        save_catalog(books)
    log.info("update item=%d %s -> quantity=%d price=%s",
             item_id, body, book["quantity"], book["price"])
    return jsonify(book)


@app.route("/catalog", methods=["GET"])
def whole_catalog():
    """Return the full catalog (for debugging / the client 'list' command)."""
    with lock:
        books = load_catalog()
    return jsonify(list(books.values()))


if __name__ == "__main__":
    init_storage()
    port = int(os.environ.get("PORT", 5001))
    log.info("Catalog server listening on port %d", port)
    # threaded=True: each request runs in its own thread (concurrent requests)
    app.run(host="0.0.0.0", port=port, threaded=True)
