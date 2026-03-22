FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir uvicorn

# Copy backend source only
COPY backend/ ./backend/
COPY pyproject.toml ./

# Set environment variables
ENV PORT=9090
ENV MONGO_URI=mongodb://localhost:27017
ENV DB_NAME=kahi

CMD uvicorn backend.src.app:app --host 0.0.0.0 --port $PORT
