"""Re-queue enrichment for top 5 campaigns only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["CELERY_CONFIG_MODULE"] = "lead_generation_app.backend.celery_app"

from lead_generation_app.backend.tasks import phase_2_enrichment_batch
from lead_generation_app.backend.database import SessionLocal
from lead_generation_app.backend.models import RawCompanyRecord, Job, Campaign

BATCH_SIZE = 25
db = SessionLocal()

try:
    pending = db.query(RawCompanyRecord).filter(RawCompanyRecord.status == "pending_enrichment").all()
    print(f"Total pending: {len(pending)}")

    by_job = {}
    for r in pending:
        by_job.setdefault(r.job_id, []).append(r.id)

    # Get top 5 campaigns
    from collections import Counter
    job_to_campaign = {}
    campaign_counts = Counter()
    for job_id in by_job:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job_to_campaign[job_id] = job.campaign_id
            campaign_counts[job.campaign_id] += len(by_job[job_id])

    top5 = [cid for cid, _ in campaign_counts.most_common(5)]
    print(f"Top 5 campaign IDs: {top5}")

    total_queued = 0
    for job_id, record_ids in sorted(by_job.items()):
        if job_to_campaign.get(job_id) not in top5:
            continue
        job = db.query(Job).filter(Job.id == job_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first() if job else None
        target_titles = campaign.target_titles if campaign and campaign.target_titles else []
        camp_name = campaign.name if campaign else "?"
        print(f"Job {job_id} ({camp_name}): {len(record_ids)} records")
        for i in range(0, len(record_ids), BATCH_SIZE):
            batch = record_ids[i:i + BATCH_SIZE]
            phase_2_enrichment_batch.delay(
                job_id=job_id, raw_record_ids=batch,
                target_titles=target_titles, proxy=None, linkedin_cookie=None,
            )
            total_queued += len(batch)
    print(f"Queued {total_queued} records for enrichment")
finally:
    db.close()
