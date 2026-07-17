# ===================================================
# Dockerfile for FastAPI Backend
# ===================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk and ensure output is unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-root system user for security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

# Copy dependency definition
COPY backend/requirements.txt .

# Install dependencies without cache write-back
RUN pip install --no-cache-dir --upgrade -r requirements.txt psycopg2-binary==2.9.9

# Copy backend application source files
COPY backend/ .

# Ensure permissions belong to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose FastAPI default port
EXPOSE 8000

# Run uvicorn server in production mode
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
