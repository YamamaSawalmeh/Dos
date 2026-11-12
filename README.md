# Bazar.com: A Multi-tier Online Book Store

Lab 1 of Distributed and Operating Systems (Fall 2026).

The store has three Python/Flask microservices that talk to each other over HTTP REST:

| Service   | Port | Folder      |
|-----------|------|-------------|
| front-end | 5000 | `frontend/` |
| catalog   | 5001 | `catalog/`  |
| order     | 5002 | `order/`    |

A command-line client is in `client/`. The design document and sample outputs are in `docs/`.

## Requirements
- Docker with Docker Compose
- Python 3.10+ with `pip install -r requirements.txt` (for the client)

## Run with Docker (recommended)

```bash
docker compose up -d --build
docker compose ps            # all three containers should be "Up"
```

Then use the client from the host:

```bash
python client/client.py search "distributed systems"
python client/client.py info 2
python client/client.py purchase 2
python client/client.py restock 2 5        # new stock arrives
python client/client.py price 2 55         # change a price
python client/client.py orders             # list all orders
python client/client.py concurrent 2 10    # 10 purchases at the same time
python client/client.py demo               # full scenario, every operation
```

You can also open the REST API in a browser, for example
<http://127.0.0.1:5000/search/distributed%20systems> or <http://127.0.0.1:5000/info/2>.

To watch the log messages of the services:

```bash
docker compose logs -f
```

To stop the services, and reset the stock and order log with `-v`:

```bash
docker compose down -v
```

## Run without Docker

```bash
pip install -r requirements.txt
python run_local.py
```

This starts the three services, runs the client demo against them, stops them
and prints each service's log.

## Running on different machines
Each service reads the addresses of the others from environment variables:

| Variable | Used by | Default |
|----------|---------|---------|
| `CATALOG_URL` | order, front-end, client | `http://127.0.0.1:5001` |
| `ORDER_URL` | front-end, client | `http://127.0.0.1:5002` |
| `FRONTEND_URL` | client | `http://127.0.0.1:5000` |

For example, if the catalog runs on `10.0.0.5`, start the order server with
`CATALOG_URL=http://10.0.0.5:5001 python order/app.py`.

## Repository layout
```
catalog/    catalog service + seed_catalog.csv
order/      order service
frontend/   front-end service
client/     command-line client
docs/       design document, client output, server logs
docker-compose.yml
```
