FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Установка необходимых системных пакетов, Chromium и chromedriver
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    ca-certificates \
    libnss3 \
    libgconf-2-4 \
    libx11-6 \
    xvfb \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3.13", "main.py"]
