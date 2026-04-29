# ---------------------------------------------------------------
# Stage 1: Builder — install dependencies
# ---------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------
# Stage 2: Runtime — lean production image
# ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="PM Automation Agent" \
      org.opencontainers.image.description="Multi-source AI-driven project management system" \
      org.opencontainers.image.vendor="Datawebify" \
      org.opencontainers.image.version="1.0.0"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Copy Supabase schema for reference (not executed at runtime)
COPY supabase/ ./supabase/

# Create non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Start the server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]