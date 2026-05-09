# =============================================================
# Hi-Tech Waste Management — Backend Dockerfile
# Python 3.11-slim + WeasyPrint system dependencies
# =============================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# -------------------------------------------------------------
# System dependencies
# WeasyPrint requires: libcairo2, pango, gdk-pixbuf, libffi
# PDF/image support: libpq-dev for psycopg2, fonts
# -------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint core dependencies
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libffi8 \
    shared-mime-info \
    # Font packages
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # GObject introspection (required by WeasyPrint)
    libgirepository1.0-dev \
    gir1.2-pango-1.0 \
    gir1.2-gdkpixbuf-2.0 \
    # Build tools
    gcc \
    g++ \
    build-essential \
    pkg-config \
    # PostgreSQL client libraries
    libpq-dev \
    # Networking & utilities
    curl \
    wget \
    ca-certificates \
    # OCR & PDF rendering (pytesseract + pdf2image)
    tesseract-ocr \
    poppler-utils \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Update font cache
RUN fc-cache -fv

# -------------------------------------------------------------
# Builder stage — install Python dependencies
# -------------------------------------------------------------
FROM base AS builder

WORKDIR /build

# Copy only requirements first for better layer caching
COPY requirements.txt .

# Install all Python dependencies into a virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# -------------------------------------------------------------
# Final runtime stage
# -------------------------------------------------------------
FROM base AS runtime

# Copy the virtualenv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Create necessary runtime directories
RUN mkdir -p \
    /app/generated_reports \
    /app/templates/certificates \
    /app/templates/emails \
    /app/logs \
    /app/media \
    && chmod -R 755 /app/generated_reports \
    && chmod -R 755 /app/templates

# Create a non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser && \
    chown -R appuser:appgroup /app

# Copy application source code
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Default command — can be overridden by docker-compose for celery workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--loop", "uvloop", "--http", "httptools"]
