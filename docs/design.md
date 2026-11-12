# Bazar.com: Design Document

Distributed and Operating Systems, Lab 1 (Fall 2026)

## 1. Overview

Bazar.com is a small online book store built as a two-tier system of microservices.
It sells four books in two topics (*distributed systems* and *undergraduate school*).

The system has three independent services. Each is a small Python/Flask web
application running in its own Docker container:

| Service   | Port | Responsibility |
|-----------|------|----------------|
| front-end | 5000 | The only service clients use. It validates requests and forwards them to the back end. |
| catalog   | 5001 | Owns the catalog: stock, price and topic of every book. Supports *query* and *update*. |
| order     | 5002 | Handles purchases and keeps a persistent log of all orders. |

```
            search / info / purchase   (HTTP REST, JSON)
 client  ───────────────────────────────▶  front-end :5000
                                          │            │
                         search, info     │            │  purchase
                                          ▼            ▼
                                     catalog :5001 ◀─── order :5002
                                                query (GET /info)
                                                update (PUT /update)
```

All communication is HTTP REST with JSON bodies. No component imports another
component's code. They only know each other's URLs, which are passed in as
environment variables (`CATALOG_URL`, `ORDER_URL`). Because of this, the three
services can run on three different machines just by changing those URLs.

## 2. REST interface

### Front-end (what clients call)
| Method | URL | Result |
|--------|-----|--------|
| GET  | `/search/<topic>`  | `[{"id": 1, "title": "..."}, ...]` |
| GET  | `/info/<item_id>`  | `{"id", "title", "topic", "quantity", "price"}` |
| POST | `/purchase/<item_id>` | `{"message": "bought book <title>", "order": {...}}` |

### Catalog
| Method | URL | Result |
|--------|-----|--------|
| GET | `/search/<topic>` | query-by-subject |
| GET | `/info/<item_id>` | query-by-item |
| PUT | `/update/<item_id>` | body `{"price": x}`, `{"quantity": n}` or `{"quantity_delta": d}` |
| GET | `/catalog` | the whole catalog (debugging) |

### Order
| Method | URL | Result |
|--------|-----|--------|
| POST | `/purchase/<item_id>` | buys one copy |
| GET  | `/orders` | all orders received |

Errors use standard HTTP status codes with a JSON body `{"error": "..."}`:
`404` unknown item, `409` out of stock, `503` a back-end service is unreachable.

## 3. How it works

**search / info.** The front-end forwards the request to the catalog, which
reads `catalog.csv` and returns the matching books. The front-end passes the
JSON reply and the status code back to the client unchanged.

**purchase.** The front-end forwards the request to the order server, which:

1. queries the catalog (`GET /info/<id>`). If the book does not exist it returns
   404, and if the stock is 0 it returns 409 *out of stock*;
2. asks the catalog to decrement the stock (`PUT /update/<id>` with
   `{"quantity_delta": -1}`);
3. appends the order to `orders.csv` and logs `bought book <title>`.

**restock / price change.** New stock arrives through the catalog's update
operation (`{"quantity_delta": +n}`). The client exposes this as the `restock`
and `price` commands.

### Concurrency
Flask runs every request in its own thread (`threaded=True`), so concurrent
requests are served in parallel without any low-level threading code.

The catalog is the only service that changes stock, so it keeps one
`threading.Lock` around every read-modify-write of `catalog.csv`. Checking
stock and decrementing it therefore happen as one atomic step. A
`quantity_delta` that would push stock below zero is refused with `409`.

This matters because the order server's step 1 (check) and step 2 (decrement)
are two separate requests. Two clients can both see "1 in stock" in step 1. The
catalog serialises their step 2 and only the first succeeds, so the second
purchase fails cleanly instead of selling a book that does not exist. The
`concurrent` client command shows this: with 2 copies left, 5 parallel
purchases give exactly 2 successes and 3 failures (see `docs/client_output.txt`).

### Persistence
- `catalog/data/catalog.csv` is created from `seed_catalog.csv` on first start
  and rewritten on every update. It is written to a temporary file first and then
  renamed, so a crash never leaves a half-written file.
- `order/data/orders.csv` is an append-only log.

In Docker both `data/` folders are named volumes, so the data survives
container restarts (`docker compose down -v` resets it).

## 4. Design decisions and trade-offs

- **Python + Flask.** This is a micro-framework with REST and multithreading
  built in. It keeps every service under ~150 lines, which is the point of
  microservices.
- **CSV instead of SQLite.** With four books a CSV file is enough, easy to read
  by hand, and has no extra dependencies. The cost is that every update
  rewrites the whole file and we must do our own locking. SQLite would give us
  transactions for free.
- **Arguments in the URL** (`/info/2`) instead of a JSON body. This matches the
  lab appendix, works from a browser, and makes the logs easy to read.
- **POST for purchase.** A purchase creates a new order and is not idempotent
  (calling it twice buys two books), so POST fits better than PUT. Catalog
  updates use PUT because they change an existing resource.
- **Order server checks, catalog enforces.** The stock check in the order
  server gives a clear error early, but the real guarantee is the catalog's
  atomic update. This keeps all stock logic in one place, the owner of the data.
- **Front-end is stateless.** It only forwards requests, so it could be
  replicated behind a load balancer without any change.
- **Flask development server.** It is simple and enough for a lab. A real
  deployment would use a production WSGI server such as gunicorn.

## 5. Known limitations

- **Single catalog instance.** The lock lives in the catalog's memory, so it
  only protects one catalog process. Running two catalog replicas against one
  file would break the stock guarantee.
- **No distributed transaction.** If the order server crashes after the catalog
  decremented stock but before the order is written, one copy is "lost" (stock
  goes down but there is no order). Likewise, if the catalog's reply is lost on
  the network, the order server reports a failure even though stock was taken.
- **Order ids** are computed from the number of lines in `orders.csv`. This is
  correct only while a single order server writes the file.
- **No authentication.** Anyone who can reach port 5001 can change prices or
  stock.
- **No caching.** Every `search` and `info` goes to the catalog and reads the
  file from disk.

## 6. Possible improvements

- **SQLite with transactions** instead of CSV plus a lock. This gives atomic
  updates that also work across several processes.
- **Caching in the front-end** for `search`/`info`, invalidated by the catalog on
  every update. This reduces load on the catalog.
- **Replication.** Run several catalog and order replicas behind the front-end
  and keep them consistent (for example, a primary-backup protocol for writes).
- **Reliable purchases.** Give each purchase a unique request id so retries are
  idempotent, and record a "pending" order before decrementing stock so that a
  crash can be recovered from.
- **Automatic restocking.** Add a background job in the catalog that adds stock
  periodically.
- **Health checks** in `docker-compose.yml`, so the front-end only starts once
  the back end is ready.

## 7. How to run

See `README.md` for the full instructions. In short:

```bash
docker compose up -d --build        # start the three containers
python client/client.py demo        # run the full scenario
docker compose logs -f              # watch the services' log messages
docker compose down -v              # stop and reset the data
```

Outputs from a real run are in `docs/client_output.txt` (client side) and
`docs/server_logs.txt` (service side).
