"""gunicorn settings for production (docker-compose.prod.yml): uvicorn workers behind nginx.

Workers share Prometheus metrics through PROMETHEUS_MULTIPROC_DIR, which must be empty when
the server starts. Keep WEB_CONCURRENCY x (DB_POOL_SIZE + DB_MAX_OVERFLOW) below the Postgres
max_connections (100 by default), together with the worker and the bot.
"""

import os
import shutil
from pathlib import Path

from prometheus_client import multiprocess

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "uvicorn_worker.UvicornWorker"
timeout = 60
graceful_timeout = 20
forwarded_allow_ips = "*"  # only nginx can reach the container
accesslog = None  # the app writes its own access log with the request id


def on_starting(server):
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if path:
        shutil.rmtree(path, ignore_errors=True)
        Path(path).mkdir(parents=True, exist_ok=True)


def child_exit(server, worker):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.mark_process_dead(worker.pid)
