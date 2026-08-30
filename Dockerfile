FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git nodejs npm sqlite3 libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g markdown-link-check

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/src

CMD ["python", "src/main.py"]
