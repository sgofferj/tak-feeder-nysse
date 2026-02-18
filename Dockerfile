# Stage 1: Build
FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

# Install the package and its dependencies
RUN pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy the installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the source code again to the final image if needed (though it's already installed in site-packages)
# For simplicity, we just copy everything needed for runtime
COPY src/ ./src/
COPY pyproject.toml ./

ENTRYPOINT ["python", "-m", "tak_feeder_nysse"]
