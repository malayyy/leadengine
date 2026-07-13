"""
Re-queue enrichment tasks for all pending records WITHOUT LinkedIn cookie.
This forces X-Ray fallback since the LinkedIn cookie is expired.
Run this on EC2 after clearing the stale enrich queue.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["CELERY_CONFIG_MODULE"] = "lead_generation_app.backend.celery_app"

from lead_generation_app.backend.tasks import phase_2_enrichment_batch
from lead_generation_app.backend.database import SessionLocal
from lead_generation_app.backend.models import RawCompanyRecord, Job, Campaign

BATCH_SIZE = 25

db = SessionLocal()
try:
    pending = (
        db.query(RawCompanyRecord)
        .filter(RawCompanyRecord.status == "pending_enrichment")
        .all()
    )
    print(f"Found {len(pending)} pending records")

    by_job = {}
    for r in pending:
        by_job.setdefault(r.job_id, []).append(r.id)

    for job_id, record_ids in sorted(by_job.items()):
        job = db.query(Job).filter(Job.id == job_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first() if job else None
        target_titles = campaign.target_titles if campaign and campaign.target_titles else []

        print(f"Job {job_id} ({campaign.name if campaign else '?'}): {len(record_ids)} records, {len(target_titles)} titles")

        for i in range(0, len(record_ids), BATCH_SIZE):
            batch = record_ids[i:i + BATCH_SIZE]
            phase_2_enrichment_batch.delay(
                job_id=job_id,
                raw_record_ids=batch,
                target_titles=target_titles,
                proxy=None,
                linkedin_cookie=None,
            )

        print(f"  -> Queued {(len(record_ids) + BATCH_SIZE - 1) // BATCH_SIZE} batch tasks")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
