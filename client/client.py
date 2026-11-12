"""
Command-line client for Bazar.com
=================================

Runs on the host machine and talks to the front-end server over HTTP REST.

Usage
-----
    python client/client.py search "distributed systems"
    python client/client.py info 2
    python client/client.py purchase 2
    python client/client.py restock 2 10        # new stock arrives (catalog update)
    python client/client.py price 2 55          # change a price (catalog update)
    python client/client.py orders              # show the order log
    python client/client.py demo                # run a full scripted scenario
    python client/client.py concurrent 2 8      # 8 parallel purchases of item 2

Server addresses can be changed with --frontend / --catalog / --order or the
FRONTEND_URL / CATALOG_URL / ORDER_URL environment variables.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5000")
CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:5001")
ORDER_URL = os.environ.get("ORDER_URL", "http://localhost:5002")
LINE = "-" * 60


# --------------------------------------------------------------------------- #
# Calls to the servers. Each returns (status_code, json_body).
# --------------------------------------------------------------------------- #
def call(method, url, **kwargs):
    try:
        r = requests.request(method, url, timeout=10, **kwargs)
        return r.status_code, r.json()
    except requests.RequestException as e:
        return None, {"error": f"cannot reach {url}: {e}"}


def do_search(topic):
    print(f"\n> search({topic!r})")
    status, body = call("GET", f"{FRONTEND_URL}/search/{quote(topic)}")
    if status != 200:
        print(f"  ERROR: {body.get('error')}")
        return
    if not body:
        print("  No books found for this topic.")
        return
    print(f"  {'ID':<4} TITLE")
    for book in body:
        print(f"  {book['id']:<4} {book['title']}")


def do_info(item_id):
    print(f"\n> info({item_id})")
    status, body = call("GET", f"{FRONTEND_URL}/info/{item_id}")
    if status != 200:
        print(f"  ERROR: {body.get('error')}")
        return
    print(f"  Title    : {body['title']}")
    print(f"  Topic    : {body['topic']}")
    print(f"  In stock : {body['quantity']}")
    print(f"  Price    : ${body['price']:.2f}")


def do_purchase(item_id, quiet=False):
    status, body = call("POST", f"{FRONTEND_URL}/purchase/{item_id}")
    if status == 200:
        msg = body["message"]
    else:
        msg = f"purchase failed: {body.get('error')}"
        if body.get("title"):
            msg += f" ({body['title']})"
    if not quiet:
        print(f"\n> purchase({item_id})")
        print(f"  {msg}")
    return status, msg


def do_restock(item_id, amount):
    print(f"\n> restock({item_id}, +{amount})")
    status, body = call("PUT", f"{CATALOG_URL}/update/{item_id}",
                        json={"quantity_delta": amount})
    if status != 200:
        print(f"  ERROR: {body.get('error')}")
        return
    print(f"  {body['title']} now has {body['quantity']} in stock")


def do_price(item_id, price):
    print(f"\n> set price({item_id}, {price})")
    status, body = call("PUT", f"{CATALOG_URL}/update/{item_id}", json={"price": price})
    if status != 200:
        print(f"  ERROR: {body.get('error')}")
        return
    print(f"  {body['title']} now costs ${body['price']:.2f}")


def do_orders():
    print("\n> orders")
    status, body = call("GET", f"{ORDER_URL}/orders")
    if status != 200:
        print(f"  ERROR: {body.get('error')}")
        return
    if not body:
        print("  No orders yet.")
        return
    print(f"  {'#':<4} {'ITEM':<5} {'PRICE':<8} TITLE")
    for o in body:
        print(f"  {o['order_id']:<4} {o['item_id']:<5} ${float(o['price']):<7.2f} {o['title']}")


def do_concurrent(item_id, n):
    """Fire n purchases at the same time to show the server handles concurrency
    and never sells more copies than it has."""
    print(f"\n> {n} concurrent purchase({item_id}) requests")
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(lambda _: do_purchase(item_id, quiet=True), range(n)))
    for i, (_, msg) in enumerate(results, 1):
        print(f"  [{i}] {msg}")
    ok = sum(1 for s, _ in results if s == 200)
    print(f"  {ok} succeeded, {n - ok} failed")


def do_demo():
    """A scripted scenario that exercises every operation, including failures."""
    print(LINE + "\nBazar.com demo\n" + LINE)
    do_search("distributed systems")
    do_search("undergraduate school")
    do_search("cooking")                 # topic with no books
    do_info(1)
    do_info(2)
    do_info(99)                          # unknown item
    do_purchase(1)
    do_purchase(3)
    do_info(1)                           # stock went down by one
    do_price(4, 30)
    do_info(4)
    # Sell out book 2, then try once more
    status, body = call("GET", f"{FRONTEND_URL}/info/2")
    stock = body.get("quantity", 0) if status == 200 else 0
    for _ in range(stock):
        do_purchase(2)
    do_purchase(2)                       # should fail: out of stock
    do_restock(2, 3)                     # new stock arrives
    do_purchase(2)                       # works again
    do_concurrent(2, 5)                  # only 2 copies left -> 2 succeed, 3 fail
    do_orders()
    print("\n" + LINE)


def main():
    global FRONTEND_URL, CATALOG_URL, ORDER_URL
    p = argparse.ArgumentParser(description="Bazar.com command-line client")
    p.add_argument("--frontend", default=FRONTEND_URL)
    p.add_argument("--catalog", default=CATALOG_URL)
    p.add_argument("--order", default=ORDER_URL)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("search").add_argument("topic")
    sub.add_parser("info").add_argument("item_id", type=int)
    sub.add_parser("purchase").add_argument("item_id", type=int)
    r = sub.add_parser("restock")
    r.add_argument("item_id", type=int)
    r.add_argument("amount", type=int)
    pr = sub.add_parser("price")
    pr.add_argument("item_id", type=int)
    pr.add_argument("price", type=float)
    sub.add_parser("orders")
    sub.add_parser("demo")
    c = sub.add_parser("concurrent")
    c.add_argument("item_id", type=int)
    c.add_argument("n", type=int)
    args = p.parse_args()

    FRONTEND_URL, CATALOG_URL, ORDER_URL = args.frontend, args.catalog, args.order

    if args.cmd == "search":
        do_search(args.topic)
    elif args.cmd == "info":
        do_info(args.item_id)
    elif args.cmd == "purchase":
        do_purchase(args.item_id)
    elif args.cmd == "restock":
        do_restock(args.item_id, args.amount)
    elif args.cmd == "price":
        do_price(args.item_id, args.price)
    elif args.cmd == "orders":
        do_orders()
    elif args.cmd == "demo":
        do_demo()
    elif args.cmd == "concurrent":
        do_concurrent(args.item_id, args.n)


if __name__ == "__main__":
    sys.exit(main())
