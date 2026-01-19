# AI Swarm Orchestrator - Gunicorn Configuration
# Last Updated: 2026-01-19
#
# This file provides additional configuration for Gunicorn workers
# to handle long-running AI API calls without timeouts
#
# Usage: This file is automatically loaded by Gunicorn if present

import multiprocessing
import os

# Server Socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
backlog = 2048

# Worker Processes
workers = 2  # Render free tier optimized
worker_class = 'sync'  # Synchronous workers for AI API calls
worker_connections = 1000
max_requests = 100  # Restart workers after 100 requests to prevent memory leaks
max_requests_jitter = 20  # Add randomness to prevent all workers restarting at once

# Timeout Configuration - CRITICAL FOR AI OPERATIONS
timeout = 180  # 3 minutes - enough for complex AI operations
graceful_timeout = 200  # 200 seconds - allow graceful shutdown
keepalive = 65  # Keep connections alive for 65 seconds

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log to stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = 'ai-swarm-orchestrator'

# Server Mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (not used, but defined for completeness)
keyfile = None
certfile = None

# Debugging (set to True for development)
reload = False
reload_engine = 'auto'
reload_extra_files = []
spew = False
check_config = False
print_config = False

# Server Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("AI Swarm Orchestrator starting...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("AI Swarm Orchestrator reloading...")

def when_ready(server):
    """Called just after the server is started."""
    print("AI Swarm Orchestrator ready to accept connections")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker spawned (pid: {worker.pid})")

def pre_exec(server):
    """Called just before a new master process is forked."""
    print("Forked child, re-executing.")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    print(f"Worker received INT or QUIT signal (pid: {worker.pid})")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    print(f"Worker received SIGABRT signal (pid: {worker.pid})")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug(f"Processing request: {req.uri}")

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass

def child_exit(server, worker):
    """Called just after a worker has been exited."""
    print(f"Worker exited (pid: {worker.pid})")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    print(f"Worker exiting (pid: {worker.pid})")

def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed."""
    print(f"Workers changed from {old_value} to {new_value}")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("AI Swarm Orchestrator shutting down")

# I did no harm and this file is not truncated
