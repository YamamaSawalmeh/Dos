"""
Catalog Server - Bazar.com
==========================

Keeps the book catalog (stock, price and topic of every book) in a CSV file
and exposes it over HTTP REST.

The data is persisted on disk in data/catalog.csv. On first start the file is
created from seed_catalog.csv.
"""

import csv
import logging
import os
import shutil

from flask import Flask

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.csv")
SEED_FILE = os.path.join(BASE_DIR, "seed_catalog.csv")
FIELDS = ["id", "title", "topic", "quantity", "price"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CATALOG] %(message)s")
log = logging.getLogger("catalog")

app = Flask(__name__)


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
    """Read the CSV file and return {id: book_dict}."""
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
    """Write the catalog back to disk.

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


if __name__ == "__main__":
    init_storage()
    port = int(os.environ.get("PORT", 5001))
    log.info("Catalog server listening on port %d", port)
    # threaded=True: each request runs in its own thread (concurrent requests)
    app.run(host="0.0.0.0", port=port, threaded=True)
