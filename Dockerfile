# ============================================
# AI OS - Docker Container Configuration
# ============================================

# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Set environment variable for port
ENV PORT=8000

# Run application with shell to support environment variable expansion
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
