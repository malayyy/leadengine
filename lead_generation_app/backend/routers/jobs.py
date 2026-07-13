import os
import json
import asyncio
import io
import csv
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import redis.asyncio as aioredis
from ..database import get_db
from ..models import Job, RawCompanyRecord, EnrichedLead, Campaign
from ..schemas.job import PipelineRequest, BatchPipelineRequest
from ..tasks import phase_1_gmaps_scrape
from ..auth import get_current_user
from ..proxy_rotator import ProxyRotator
from ..metrics import jobs_total, active_jobs
from ..logger import get_logger

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
log = get_logger("api")
proxy_rotator = ProxyRotator.from_env()


async def _sse_poll(pubsub, request, channel, r, depth=5000):
    if depth <= 0 or await request.is_disconnected():
        await pubsub.unsubscribe(channel)
        await r.close()
        return
    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    if message:
        data = message['data'].decode('utf-8')
        yield f"data: {data}\n\n"
        try:
            parsed = json.loads(data)
            if parsed.get("type") == "status" and parsed.get("status") in ["completed", "failed"]:
                await pubsub.unsubscribe(channel)
                await r.close()
                return
        except Exception:
            pass
    else:
        yield ": keepalive\n\n"
    async for item in _sse_poll(pubsub, request, channel, r, depth - 1):
        yield item


@router.post("/pipeline")
def start_lead_pipeline(req: PipelineRequest, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.name == req.campaign_name).first()
    if not campaign:
        campaign = Campaign(
            name=req.campaign_name,
            industry=req.industry,
            state=req.state,
            target_titles=req.titles,
            zipcodes=req.zipcodes,
            total_contacts=req.total_contacts,
            contacts_per_company=req.contacts_per_company,
            proxy_list=[req.proxy] if req.proxy else []
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    else:
        campaign.total_contacts = req.total_contacts
        db.commit()

    job = Job(
        campaign_id=campaign.id,
        status="pending",
        skip_email_verify=1 if req.skip_email_verify else 0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    final_cookie = req.linkedin_cookie or os.getenv("LINKEDIN_LI_AT_COOKIE")
    assigned_proxy = req.proxy or proxy_rotator.assign_session()
    task = phase_1_gmaps_scrape.delay(
        job_id=job.id,
        industry=req.industry,
        zipcodes=req.zipcodes,
        state=req.state,
        target_titles=req.titles,
        contacts_per_company=req.contacts_per_company,
        proxy=assigned_proxy,
        linkedin_cookie=final_cookie,
    )

    job.celery_task_id = task.id
    db.commit()
    jobs_total.labels(status="created").inc()
    active_jobs.inc()

    return {
        "message": "Lead generation pipeline started",
        "job_id": job.id,
        "celery_task_id": task.id,
        "proxy_assigned": bool(assigned_proxy),
    }


@router.post("/batch")
def batch_lead_pipelines(req: BatchPipelineRequest, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    results = []
    for j in req.jobs:
        campaign = db.query(Campaign).filter(Campaign.name == j.campaign_name).first()
        if not campaign:
            campaign = Campaign(
                name=j.campaign_name, industry=j.industry, state=j.state,
                target_titles=j.titles, zipcodes=j.zipcodes,
                total_contacts=j.total_contacts, contacts_per_company=j.contacts_per_company,
                proxy_list=[j.proxy] if j.proxy else []
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
        else:
            campaign.total_contacts = j.total_contacts
            db.commit()

        job = Job(
            campaign_id=campaign.id,
            status="pending",
            skip_email_verify=1 if j.skip_email_verify else 0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        final_cookie = j.linkedin_cookie or os.getenv("LINKEDIN_LI_AT_COOKIE")
        assigned_proxy = j.proxy or proxy_rotator.get_next()
        task = phase_1_gmaps_scrape.apply_async(
            kwargs=dict(
                job_id=job.id, industry=j.industry, zipcodes=j.zipcodes,
                state=j.state, target_titles=j.titles,
                contacts_per_company=j.contacts_per_company,
                proxy=assigned_proxy, linkedin_cookie=final_cookie,
            ),
            priority=j.priority,
        )
        job.celery_task_id = task.id
        db.commit()
        results.append({"job_id": job.id, "celery_task_id": task.id, "campaign": j.campaign_name})
        jobs_total.labels(status="created").inc()
        active_jobs.inc()

    return {"message": f"Queued {len(results)} jobs", "jobs": results}


@router.get("")
def get_jobs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    jobs = db.query(Job).order_by(Job.id.desc()).offset(skip).limit(limit).all()

    def serialize_job(j):
        c = db.query(Campaign).filter(Campaign.id == j.campaign_id).first()
        rec_count = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == j.id).count()
        return {
            "id": j.id, "status": j.status, "created_at": j.created_at,
            "campaign_name": c.name if c else "Unknown", "industry": c.industry if c else "",
            "state": c.state if c else "", "mv_credits_used": j.mv_credits_used,
            "records_extracted": rec_count,
        }
    return list(map(serialize_job, jobs))


@router.get("/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    raw_count = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).count()
    return {
        "job_id": job.id, "status": job.status, "error_message": job.error_message,
        "created_at": job.created_at, "completed_at": job.completed_at, "raw_records_found": raw_count,
    }


@router.get("/{job_id}/stream")
async def stream_job_events(job_id: int, request: Request, _: dict = Depends(get_current_user)):
    async def event_generator():
        redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url)
        pubsub = r.pubsub()
        channel = f"job_{job_id}_events"
        await pubsub.subscribe(channel)
        async for item in _sse_poll(pubsub, request, channel, r):
            yield item

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{job_id}/records")
def get_job_records(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    records = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()

    def enrich_record(r):
        enriched = db.query(EnrichedLead).filter(EnrichedLead.raw_record_id == r.id).all()
        return {
            "company_name": r.company_name, "website": r.website, "phone": r.phone,
            "address": r.address, "city": r.city, "state": r.state, "zip_code": r.zip_code,
            "industry": r.industry, "rating": r.rating, "gmaps_url": r.gmaps_url, "status": r.status,
            "enriched_leads": list(map(lambda e: {
                "first_name": e.first_name, "last_name": e.last_name, "title": e.title,
                "linkedin_url": e.linkedin_url, "email": e.guessed_email,
                "email_verification_status": e.email_verification_status,
                "email_confidence_score": e.email_confidence_score,
                "linkedin_profile_pic_url": e.linkedin_profile_pic_url, "location": e.location,
            }, enriched)),
        }
    return {"job_id": job.id, "records": list(map(enrich_record, records))}


@router.get("/{job_id}/details")
def get_job_details(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    records = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()
    leads = db.query(EnrichedLead).join(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()
    records_data = list(map(lambda r: {"id": r.id, "company_name": r.company_name, "website": r.website, "phone": r.phone, "address": r.address, "city": r.city, "state": r.state}, records))
    leads_data = list(map(lambda l: {"id": l.id, "first_name": l.first_name, "last_name": l.last_name, "title": l.title, "email": l.guessed_email, "email_status": l.email_verification_status, "linkedin_url": l.linkedin_url, "company_name": next((rc.company_name for rc in records if rc.id == l.raw_record_id), "Unknown"),}, leads))
    return {"job_id": job.id, "status": job.status, "records": records_data, "leads": leads_data}


@router.get("/{job_id}/export")
def export_job_leads_csv(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).filter(RawCompanyRecord.job_id == job_id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["First Name", "Last Name", "Title", "Email", "Email Status", "LinkedIn", "Company", "Address", "City", "State"])
    list(map(lambda lr: writer.writerow([lr[0].first_name, lr[0].last_name, lr[0].title, lr[0].guessed_email, lr[0].email_verification_status, lr[0].linkedin_url, lr[1].company_name, lr[1].address, lr[1].city, lr[1].state]), leads))
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=job_{job_id}_export.csv"})


@router.get("/{job_id}/companies")
def get_job_companies(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()


@router.get("/{job_id}/leads")
def get_job_specific_leads(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).filter(RawCompanyRecord.job_id == job_id).all()
    return list(map(lambda lr: {"id": lr[0].id, "first_name": lr[0].first_name, "last_name": lr[0].last_name, "title": lr[0].title, "email": lr[0].guessed_email, "email_status": lr[0].email_verification_status, "linkedin_url": lr[0].linkedin_url, "company_name": lr[1].company_name}, leads))


@router.post("/{job_id}/pause")
def pause_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job and job.status == 'in_progress':
        job.status = 'paused'
        db.commit()
    return {"status": job.status if job else "not found"}


@router.post("/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job and job.status == 'paused':
        job.status = 'in_progress'
        db.commit()
    return {"status": job.status if job else "not found"}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job and job.status in ['in_progress', 'paused', 'pending']:
        job.status = 'cancelled'
        db.commit()
        active_jobs.dec()
    return {"status": job.status if job else "not found"}


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    raw_records = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()
    list(map(lambda rec: db.query(EnrichedLead).filter(EnrichedLead.raw_record_id == rec.id).delete(), raw_records))
    db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).delete()
    db.delete(job)
    db.commit()
    return {"message": f"Job {job_id} and all associated data deleted"}
