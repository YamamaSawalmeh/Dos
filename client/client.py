"""
Command-line client for Bazar.com
=================================

Runs on the host machine and talks to the front-end server over HTTP REST.

Usage
-----
    python client/client.py search "distributed systems"
    python client/client.py info 2
    python client/client.py purchase 2

The front-end address can be changed with --frontend or the FRONTEND_URL
environment variable.
"""

import argparse
import os
import sys
from urllib.parse import quote

import requests

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5000")


def call(method, url, **kwargs):
    """Send a request and return (status_code, json_body)."""
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


def do_purchase(item_id):
    print(f"\n> purchase({item_id})")
    status, body = call("POST", f"{FRONTEND_URL}/purchase/{item_id}")
    if status == 200:
        print(f"  {body['message']}")
    else:
        msg = f"purchase failed: {body.get('error')}"
        if body.get("title"):
            msg += f" ({body['title']})"
        print(f"  {msg}")


def main():
    global FRONTEND_URL
    p = argparse.ArgumentParser(description="Bazar.com command-line client")
    p.add_argument("--frontend", default=FRONTEND_URL)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("search").add_argument("topic")
    sub.add_parser("info").add_argument("item_id", type=int)
    sub.add_parser("purchase").add_argument("item_id", type=int)
    args = p.parse_args()

    FRONTEND_URL = args.frontend

    if args.cmd == "search":
        do_search(args.topic)
    elif args.cmd == "info":
        do_info(args.item_id)
    elif args.cmd == "purchase":
        do_purchase(args.item_id)


if __name__ == "__main__":
    sys.exit(main())
