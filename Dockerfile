# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# Next.js 16/15+ requires sharp sometimes but for export it's often not needed
RUN npm run build

# Stage 2: Build the backend and combine
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

# Copy project files
COPY . .

# Copy the built frontend from Stage 1
# We expect the 'out' directory from Next.js export
COPY --from=frontend-builder /app/frontend/out /app/frontend/out

# Set environment variables
ENV PORT=9090
ENV MONGO_URI=mongodb://localhost:27017
ENV DB_NAME=kahi

# Run the backend server
# The backend will serve the static files from /app/frontend/out
CMD uvicorn backend.src.app:app --host 0.0.0.0 --port $PORT
