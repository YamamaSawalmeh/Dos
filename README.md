# 📚 Bazar.com – Multi-tier Online Book Store

A distributed online bookstore built from three **Python/Flask microservices** that communicate over HTTP REST – Lab 1 of the **Distributed & Operating Systems** course.

| Service | Port | Responsibility |
|---------|------|----------------|
| `frontend/` | 5000 | Public REST API – forwards search/info requests to the catalog |
| `catalog/`  | 5001 | Book catalog: search by topic, item info, stock and price (seeded from `seed_catalog.csv`) |
| `order/`    | 5002 | Purchases – checks stock with the catalog and logs orders |

## API

```
GET  :5000/search/<topic>      # books on a topic (front-end → catalog)
GET  :5000/info/<item_id>      # title, price and stock of one book
POST :5002/purchase/<item_id>  # buy one copy (order service → catalog)
```

## Run

```bash
pip install -r requirements.txt
python catalog/app.py    # port 5001
python order/app.py      # port 5002
python frontend/app.py   # port 5000
```

Then open <http://127.0.0.1:5000/search/distributed%20systems>.

## Tech stack

Python · Flask · REST · Microservices
