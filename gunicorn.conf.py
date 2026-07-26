import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", str(max(2, multiprocessing.cpu_count()))))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 30
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
