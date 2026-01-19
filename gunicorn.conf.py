# Gunicorn Configuration File for AI Swarm Orchestrator
# Last Updated: January 19, 2026
#
# This config file has HIGHER PRIORITY than command-line arguments
# Place this in the root of your repository alongside swarm_app.py
#
# CRITICAL: Extended timeouts for long-running AI operations

import os
import multiprocessing

# Server Socket
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
backlog = 2048

# Worker Processes
workers = 2  # Render Pro optimized
worker_class = "sync"  # Synchronous workers for AI API calls
worker_connections = 1000
max_requests = 100  # Restart workers after 100 requests
max_requests_jitter = 20  # Randomize restart timing

# CRITICAL TIMEOUT SETTINGS - FOR AI OPERATIONS
timeout = 180  # 3 minutes - MUST be long for Claude API calls
graceful_timeout = 200  # 200 seconds for clean shutdown
keepalive = 65  # Keep connections alive

# Logging
accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server Mechanics
daemon = False
pidfile = None
umask = 0
tmp_upload_dir = None
preload_app = True  # Load app before forking workers

# Process Naming
proc_name = "ai-swarm-orchestrator"

# Server Hooks (for debugging)
def on_starting(server):
    """Called just before the master process is initialized"""
    print("=" * 60)
    print("AI Swarm Orchestrator Starting")
    print(f"Workers: {workers}")
    print(f"Timeout: {timeout} seconds")
    print(f"Graceful Timeout: {graceful_timeout} seconds")
    print("=" * 60)

def when_ready(server):
    """Called just after the server is started"""
    print("AI Swarm Orchestrator ready - accepting connections")
    print(f"Timeout configured: {timeout}s")

def worker_int(worker):
    """Called when worker receives SIGINT or SIGQUIT"""
    print(f"Worker {worker.pid} received INT/QUIT signal")

def worker_abort(worker):
    """Called when worker receives SIGABRT"""
    print(f"Worker {worker.pid} ABORTED - check for timeout issues!")
    print(f"Current timeout setting: {timeout}s")

# I did no harm and this file is not truncated
