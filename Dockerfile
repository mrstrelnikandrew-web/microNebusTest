# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures stdout/stderr are sent straight to terminal
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed by asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Default command — overridden by docker-compose for each service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
