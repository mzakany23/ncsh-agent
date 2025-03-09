FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including Nginx and Apache utils for htpasswd
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nginx \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/*

# Create directory for memory persistence
RUN mkdir -p /app/memory

# Install dependencies directly
RUN pip install --no-cache-dir streamlit anthropic pandas llama-index duckdb matplotlib rich pytest numpy

# Copy the application code first - more specific files will override if needed
COPY . /app/

# Create Nginx configuration with basic auth
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    \
    # Main Streamlit app \
    location / { \
        auth_basic "NC Soccer Hudson - Match Analysis Agent"; \
        auth_basic_user_file /etc/nginx/.htpasswd; \
        proxy_pass http://localhost:8501; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_cache_bypass $http_upgrade; \
    } \
}' > /etc/nginx/conf.d/streamlit.conf

# Create a default htpasswd file
RUN htpasswd -bc /etc/nginx/.htpasswd ncsoccer password

# Create a simple entrypoint script
RUN echo '#!/bin/bash \n\
echo "Starting NC Soccer Hudson - Match Analysis Agent" \n\
\n\
# Set auth credentials if provided via environment variables \n\
if [ -n "$BASIC_AUTH_USERNAME" ] && [ -n "$BASIC_AUTH_PASSWORD" ]; then \n\
    echo "Setting up authentication for user: $BASIC_AUTH_USERNAME" \n\
    htpasswd -bc /etc/nginx/.htpasswd "$BASIC_AUTH_USERNAME" "$BASIC_AUTH_PASSWORD" \n\
fi \n\
\n\
# Start Nginx \n\
echo "Starting Nginx..." \n\
service nginx start \n\
\n\
# Start Streamlit \n\
echo "Starting Streamlit application..." \n\
cd /app \n\
streamlit run /app/ui/app.py --server.port=8501 --server.address=0.0.0.0 \n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose ports
EXPOSE 80 8501

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MEMORY_PATH=/app/memory
ENV PYTHONPATH=/app

# Use the embedded entrypoint script
CMD ["/app/entrypoint.sh"]

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1
