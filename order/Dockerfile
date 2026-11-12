# Order service image (Linux container). Build context is the repo root.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY order/ .
ENV PYTHONUNBUFFERED=1 PORT=5002 DATA_DIR=/app/data
EXPOSE 5002
CMD ["python", "app.py"]
