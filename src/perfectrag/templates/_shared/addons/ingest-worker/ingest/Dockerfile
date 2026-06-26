FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Crawl4AI needs playwright browsers
RUN playwright install --with-deps chromium || true
COPY . .
CMD ["python", "runner.py"]
