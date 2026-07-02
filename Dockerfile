FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to optimize Docker layer caching
COPY lead_generation_app/backend/requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers and their system dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy microservice source code
COPY . .

# Expose API port
EXPOSE 8000