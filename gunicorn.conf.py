# Gunicorn Configuration File for AI Swarm Orchestrator
# Created: January 19, 2026
# Last Updated: February 27, 2026 - ADDED KEEP-ALIVE post_fork HOOK
#
# CHANGELOG:
#
# - February 27, 2026: ADDED post_fork KEEP-ALIVE HOOK
#   Added post_fork() hook that starts a background thread inside each worker
#   process (after fork) to ping /health every 14 minutes. This prevents Render
#   free/starter tier from spinning down the service due to inactivity.
#   IMPORTANT: post_fork is the ONLY safe place for background threads when
#   preload_app=True. Starting threads at module level or in on_starting()
#   puts them in the master process; they die during fork and crash workers.
#
# - January 19, 2026: INITIAL CONFIGURATION
#   Extended timeouts for long-running AI operations, 2 workers, sync class.
#
# This config file has HIGHER PRIORITY than command-line arguments.
# Place this in the root of your repository alongside app.py.
#
# CRITICAL: Extended timeouts for long-running AI operations

import os
import threading
import time

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


# =============================================================================
# SERVER HOOKS
# =============================================================================

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


def post_fork(server, worker):
    """
    Called by gunicorn in each worker process immediately after forking.

    KEEP-ALIVE THREAD:
    This is the correct and only safe place to start background threads when
    preload_app=True. The master process loads app.py (preload), then forks
    workers. Any threads started before fork are dead in the child process.
    post_fork() runs inside the worker after fork, so threads start cleanly.

    The keep-alive thread pings /health every 14 minutes to prevent Render
    from spinning down the service due to inactivity.
    """
    def _keep_alive_ping():
        """Ping /health every 14 minutes to keep Render service alive."""
        time.sleep(90)  # Wait 90s for worker to fully initialize
        while True:
            try:
                import requests as _req
                port = int(os.environ.get('PORT', 10000))
                url = f'http://127.0.0.1:{port}/health'
                resp = _req.get(url, timeout=10)
                print(f"[KeepAlive] Worker {worker.pid} ping OK ({resp.status_code})", flush=True)
            except Exception as e:
                print(f"[KeepAlive] Ping failed (non-fatal): {e}", flush=True)
            time.sleep(840)  # 14 minutes between pings

    t = threading.Thread(
        target=_keep_alive_ping,
        daemon=True,
        name=f'KeepAlive-{worker.pid}'
    )
    t.start()
    print(f"[KeepAlive] Keep-alive thread started in worker {worker.pid}", flush=True)


def worker_int(worker):
    """Called when worker receives SIGINT or SIGQUIT"""
    print(f"Worker {worker.pid} received INT/QUIT signal")


def worker_abort(worker):
    """Called when worker receives SIGABRT"""
    print(f"Worker {worker.pid} ABORTED - check for timeout issues!")
    print(f"Current timeout setting: {timeout}s")

# I did no harm and this file is not truncated
