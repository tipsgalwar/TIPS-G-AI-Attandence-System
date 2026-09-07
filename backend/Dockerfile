# TIPS-G ALWAR Student Attendance System - Backend Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Kolkata

# Install system dependencies required for PostgreSQL, system utilities, and timezone data
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

# Copy application source code and configuration files
COPY src/ ./src/
COPY config/ ./config/

COPY run.py .

# Create storage and log directories
RUN mkdir -p storage/reports storage/students storage/documents logs

# Expose FastAPI backend port
EXPOSE 8000

# Run FastAPI backend directly using uvicorn for optimal performance and health checks
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]

