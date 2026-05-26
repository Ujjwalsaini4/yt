# --- Stage 1: Build React Frontend ---
FROM node:22-alpine AS builder
WORKDIR /app/frontend

# Install package dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copy source and build static app
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Run Python Backend & Serve App ---
FROM python:3.10-slim
WORKDIR /app

# Install system utilities and Linux FFmpeg binary
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend python code
COPY backend/ ./backend/

# Copy React production build from Stage 1 builder
COPY --from=builder /app/frontend/dist ./frontend/dist

# Expose port (informative, Railway uses dynamic $PORT environment variable)
EXPOSE 8000

# Set environment production flag
ENV ENV=production

# Run FastAPI backend with Uvicorn
CMD ["python", "backend/main.py"]
