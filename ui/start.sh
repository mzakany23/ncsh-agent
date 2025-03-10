#!/bin/bash
# Startup script for Nginx and Streamlit with Basic Auth

echo "Starting NC Soccer Hudson - Match Analysis Agent with Nginx Basic Auth"

# Debug: List files to verify mount points and file structure
echo "Listing directories for debugging:"
echo "Main directory:"
ls -la /app
echo "UI directory:"
ls -la /app/ui
echo "Nginx directory:"
ls -la /etc/nginx/conf.d/

# Check if environment variables are set
if [ -z "$BASIC_AUTH_USERNAME" ]; then
    echo "BASIC_AUTH_USERNAME not set, using default: ncsoccer"
    BASIC_AUTH_USERNAME="ncsoccer"
fi

if [ -z "$BASIC_AUTH_PASSWORD" ]; then
    echo "BASIC_AUTH_PASSWORD not set, using default password"
    BASIC_AUTH_PASSWORD="password"
fi

# Create htpasswd file
echo "Creating htpasswd file for user: $BASIC_AUTH_USERNAME"
htpasswd -bc /etc/nginx/.htpasswd "$BASIC_AUTH_USERNAME" "$BASIC_AUTH_PASSWORD"

# Start Nginx
echo "Starting Nginx..."
service nginx start

# Start Streamlit
echo "Starting Streamlit application..."
cd /app
streamlit run /app/ui/app.py --server.port=8501 --server.address=0.0.0.0