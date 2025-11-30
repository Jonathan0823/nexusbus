# Stage 1: Builder
# Used to compile dependencies and prepare the virtual environment
FROM python:3.10-alpine AS builder

WORKDIR /app

# Set environment variables to avoid interactive prompts during build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies for Alpine
# gcc, musl-dev, linux-headers for compiling Python packages
# postgresql-dev for asyncpg
# g++ for C++ extensions (pandas, numpy)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    postgresql-dev \
    g++ \
    libffi-dev \
    openssl-dev

# Create a virtual environment
RUN python -m venv /opt/venv
# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --compile -r requirements.txt && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete && \
    find /opt/venv -type f -name "*.pyo" -delete && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.so" -exec strip {} \; 2>/dev/null || true


# Stage 2: Final Runtime
# A clean, small image containing only what's needed to run the app
FROM python:3.10-alpine AS final

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime libraries
# libpq is needed for postgres communication
# libstdc++ and libgcc needed for C++ extensions (numpy, pandas)
RUN apk add --no-cache \
    libpq \
    libstdc++ \
    libgcc

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Create a non-root user for security
# It is best practice not to run applications as root
RUN addgroup -S appgroup && adduser -S -G appgroup appuser

# Change ownership of the application directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Start the application
# We do not auto-migrate here. The database will be initialized (empty tables) by main.py logic.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
