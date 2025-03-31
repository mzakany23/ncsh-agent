import multiprocessing

# Server socket
bind = "0.0.0.0:8050"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'eventlet'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'soccer-analytics'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Header size limits
limit_request_line = 8190
limit_request_fields = 32768
limit_request_field_size = 32768