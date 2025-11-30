# Stage 1: Builder
# Used to compile dependencies and prepare the virtual environment
FROM python:3.10.11-slim as builder

WORKDIR /app

# Set environment variables to avoid interactive prompts during build
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
# gcc and libpq-dev are required to build python packages like asyncpg
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python -m venv /opt/venv
# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Final Runtime
# A clean, small image containing only what's needed to run the app
FROM python:3.10.11-slim as builder

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime libraries
# libpq5 is needed for postgres communication, but we don't need the full dev headers
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Create a non-root user for security
# It is best practice not to run applications as root
RUN addgroup --system appgroup && adduser --system --group appuser

# Change ownership of the application directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Start the application
# We do not auto-migrate here. The database will be initialized (empty tables) by main.py logic.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
