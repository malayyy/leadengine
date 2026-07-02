import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from functools import wraps

jobs_total = Counter("leadengine_jobs_total", "Total jobs created", ["status"])
records_total = Counter("leadengine_records_total", "Total records scraped", ["source"])
leads_total = Counter("leadengine_leads_total", "Total leads enriched")
emails_verified = Counter("leadengine_emails_verified", "Total emails verified", ["status"])
scrape_duration = Histogram("leadengine_scrape_duration_seconds", "Scrape duration per phase", ["phase"], buckets=[1, 5, 10, 30, 60, 120, 300])
active_jobs = Gauge("leadengine_active_jobs", "Currently active jobs")
scrape_rate = Gauge("leadengine_scrape_rate", "Current scrape rate (leads/sec)")
mv_credits_gauge = Gauge("leadengine_mv_credits", "MillionVerifier remaining credits")
queue_depth = Gauge("leadengine_queue_depth", "Celery queue depth")


def track_scrape_duration(phase: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.time() - start
                scrape_duration.labels(phase=phase).observe(elapsed)
        return wrapper
    return decorator


def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
