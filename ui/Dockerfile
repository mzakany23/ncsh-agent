FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create directory for memory persistence
RUN mkdir -p /app/memory

# Install dependencies directly
RUN pip install --no-cache-dir streamlit anthropic pandas llama-index duckdb matplotlib rich pytest numpy

# Copy the entire codebase to /app
COPY .. /app/

# Expose Streamlit port
EXPOSE 8501

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MEMORY_PATH=/app/memory
ENV PYTHONPATH=/app

# Start Streamlit
ENTRYPOINT ["streamlit", "run", "/app/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1
