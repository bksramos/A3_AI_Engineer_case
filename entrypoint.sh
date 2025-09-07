#!/bin/sh
set -e

echo "Starting Incident Parser API..."

# Check if Ollama is accessible
echo "Checking Ollama connectivity..."
OLLAMA_URL=${OLLAMA_URL:-"http://172.29.80.1:11434"}

# Simple connectivity test
if command -v curl >/dev/null 2>&1; then
    if curl -s --connect-timeout 5 "$OLLAMA_URL/api/tags" >/dev/null; then
        echo "✅ Ollama is accessible at $OLLAMA_URL"
    else
        echo "⚠️ Warning: Ollama not accessible at $OLLAMA_URL"
        echo "   Make sure Ollama is running and accessible"
        echo "   The API will still start but parsing may fail"
    fi
else
    echo "ℹ️ curl not found, skipping Ollama connectivity test"
fi

# Set default port if not specified
PORT=${PORT:-8080}

echo "Starting FastAPI server on port $PORT..."

# Start the FastAPI application
exec uvicorn main:app --host 0.0.0.0 --port "$PORT" --log-level info