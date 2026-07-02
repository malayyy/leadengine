FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first to optimize layers caching
COPY backend/requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers and their system dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy lead generation app files
COPY . .

# Expose FastAPI server port
EXPOSE 8000

# Define default command (overridden by docker-compose)
CMD ["python", "-m", "uvicorn", "lead_generation_app.backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
