FROM python:3.12-slim

USER root

# Install system dependencies
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      curl \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /src

# Install Python dependencies first (for better caching)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r ./requirements.txt

# Copy application files with correct folder structure
COPY tools/                 ./tools/
COPY stark/                 ./stark/
COPY main.py               ./main.py
COPY entrypoint.sh         ./entrypoint.sh

# Set execute permissions
RUN chmod +x ./entrypoint.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /src
USER appuser

# Expose API port
EXPOSE 8080

# Use the entrypoint script
ENTRYPOINT ["/src/entrypoint.sh"]