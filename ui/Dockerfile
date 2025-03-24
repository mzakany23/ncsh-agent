FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including Nginx and Apache utils for htpasswd
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nginx \
    apache2-utils \
    python3-pip \
    unzip \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip

# Create directory for memory persistence
RUN mkdir -p /app/memory

# Create directory for data
RUN mkdir -p /app/analysis/data /app/ui/data

# Install dependencies directly
RUN pip install --no-cache-dir streamlit anthropic pandas llama-index duckdb matplotlib rich pytest numpy uv

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
# Sync data from S3 using Makefile \n\
echo "Attempting to refresh data from S3..." \n\
# First try with explicit credentials if provided \n\
if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then \n\
    echo "Using provided AWS credentials" \n\
elif curl -s -m 1 http://169.254.169.254/latest/meta-data/iam/security-credentials/ > /dev/null ; then \n\
    echo "Using EC2 instance profile for AWS credentials" \n\
else \n\
    echo "No AWS credentials available. Sync may fail if AWS credentials are required." \n\
fi \n\
\n\
# Run the data refresh command \n\
cd /app && make refresh-data || echo "Failed to refresh data from S3" \n\
\n\
# Ensure data.parquet exists in both locations for compatibility \n\
if [ -f "/app/analysis/data/data.parquet" ]; then \n\
    echo "Data refreshed and copying to UI data directory..." \n\
    cp /app/analysis/data/data.parquet /app/ui/data/data.parquet \n\
    echo "Data copied to UI data directory" \n\
    \n\
    # Also copy any additional datasets found \n\
    echo "Copying additional datasets to UI data directory..." \n\
    find /app/analysis/data -name "*.parquet" ! -name "data.parquet" -exec cp {} /app/ui/data/ \\; \n\
    echo "Listing all available datasets:" \n\
    find /app/ui/data -name "*.parquet" | sort \n\
else \n\
    echo "ERROR: No data.parquet file found after refresh. Please check S3 path and credentials." \n\
    exit 1 \n\
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
