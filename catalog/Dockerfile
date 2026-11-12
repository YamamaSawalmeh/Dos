# Catalog service image (Linux container). Build context is the repo root.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY catalog/ .
ENV PYTHONUNBUFFERED=1 PORT=5001 DATA_DIR=/app/data
EXPOSE 5001
CMD ["python", "app.py"]
