FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nginx \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/*

# Create directory for data
RUN mkdir -p /app/analysis/data

# Install dependencies directly with pip instead of uv
RUN pip install --no-cache-dir dash>=2.11.1 plotly pandas duckdb numpy dash-bootstrap-components gunicorn

# Copy the application code
COPY ui-analytics /app/ui-analytics
COPY analysis /app/analysis

# Create Nginx configuration with basic auth
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    \
    # Main Dash app \
    location / { \
        auth_basic "NC Soccer Analytics Dashboard"; \
        auth_basic_user_file /etc/nginx/.htpasswd; \
        proxy_pass http://localhost:8050; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_cache_bypass $http_upgrade; \
    } \
}' > /etc/nginx/conf.d/dash.conf

# Create a default htpasswd file
RUN htpasswd -bc /etc/nginx/.htpasswd ncsoccer password

# Create entrypoint script
RUN echo '#!/bin/bash \n\
echo "Starting NC Soccer Analytics Dashboard" \n\
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
# Start Dash app \n\
echo "Starting Dash application..." \n\
cd /app/ui-analytics \n\
gunicorn --workers 2 --bind 0.0.0.0:8050 app:server \n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose ports
EXPOSE 80 8050

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the entrypoint script
CMD ["/app/entrypoint.sh"]

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8050/ || exit 1