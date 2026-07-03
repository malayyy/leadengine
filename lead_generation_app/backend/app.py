import os
import json
import asyncio
import time
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime
import redis.asyncio as aioredis
from dotenv import load_dotenv
import io
import csv
from mcp.server.sse import SseServerTransport
from functools import reduce
from collections import defaultdict

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from .database import engine, get_db
from .models import Campaign, Job, RawCompanyRecord, EnrichedLead
from .tasks import phase_1_gmaps_scrape
from .millionverifier import get_remaining_credits
from .mcp_server import server as mcp_server_instance
from .websocket_manager import ws_manager
from .proxy_rotator import ProxyRotator
from .rate_limiter import DomainRateLimiter
from .metrics import metrics_endpoint, jobs_total, records_total, leads_total, emails_verified, active_jobs, scrape_rate, mv_credits_gauge
from .logger import get_logger, mask_sensitive
from .auth import create_access_token, verify_token, get_current_user

log = get_logger("api")
request_log = get_logger("http")

app = FastAPI(title="Lead Generation Pipeline API", version="4.0.0")
rate_limiter = DomainRateLimiter()
proxy_rotator = ProxyRotator.from_env()

MCP_API_KEY = os.environ.get("MCP_API_KEY", "leadengine-secret-key")
sse = SseServerTransport("/messages")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    request_log.info("%s %s | status=%d duration=%.3fs | client=%s",
                     request.method, request.url.path, response.status_code, elapsed,
                     request.client.host if request.client else "unknown",
                     extra={"extra_fields": {
                         "method": request.method, "path": request.url.path,
                         "status": response.status_code, "duration_ms": round(elapsed * 1000, 2),
                         "client_ip": request.client.host if request.client else None,
                     }})
    return response


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    if request.url.path in ["/sse", "/messages"]:
        if request.method == "OPTIONS":
            return await call_next(request)
        auth_header = request.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {MCP_API_KEY}":
            return Response(content="Unauthorized. Missing or invalid Authorization Bearer token.", status_code=401)
    return await call_next(request)


@app.on_event("startup")
async def startup():
    rr = aioredis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    try:
        info = await rr.info()
        queue_len = info.get("db0", {}).get("keys", 0) if isinstance(info, dict) else 0
        scrape_rate.set(queue_len)
    except Exception:
        pass
    await rr.close()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "lead-engine", "version": "4.0.0", "proxies": proxy_rotator.count()}


@app.get("/metrics")
def metrics():
    return metrics_endpoint()


@app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server_instance.run(read_stream, write_stream, mcp_server_instance.create_initialization_options())


@app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


# WebSocket endpoint for real-time job events
@app.websocket("/api/v1/ws/jobs/{job_id}")
async def websocket_job_events(websocket: WebSocket, job_id: int):
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        verify_token(token)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    await ws_manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(job_id, websocket)


class PipelineRequest(BaseModel):
    campaign_name: str
    industry: str
    titles: List[str]
    zipcodes: List[str]
    state: str
    total_contacts: int = 100
    contacts_per_company: int = -1
    proxy: Optional[str] = None
    linkedin_cookie: Optional[str] = None
    priority: int = 0
    skip_email_verify: bool = False


class BatchPipelineRequest(BaseModel):
    jobs: List[PipelineRequest]


class LoginRequest(BaseModel):
    password: str


@app.post("/api/v1/jobs/pipeline")
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


@app.post("/api/v1/jobs/batch")
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


@app.get("/api/v1/jobs/{job_id}/stream")
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


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    raw_count = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).count()
    return {
        "job_id": job.id, "status": job.status, "error_message": job.error_message,
        "created_at": job.created_at, "completed_at": job.completed_at, "raw_records_found": raw_count,
    }


@app.get("/api/v1/jobs/{job_id}/records")
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


@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    admin_password = os.environ.get("ADMIN_PASSWORD", "leadengine123")
    if req.password == admin_password:
        token = create_access_token({"sub": "admin"})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid password")


@app.get("/api/v1/dashboard/metrics")
def get_metrics(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    total_jobs = db.query(Job).count()
    total_records = db.query(RawCompanyRecord).count()
    total_enriched = db.query(EnrichedLead).count()
    total_emails = db.query(EnrichedLead).filter(
        EnrichedLead.email_verification_status.in_(['valid', 'catch_all'])
    ).count()
    return {"total_jobs": total_jobs, "total_records": total_records, "total_enriched": total_enriched, "total_valid_emails": total_emails}


@app.get("/api/v1/dashboard/realtime-metrics")
def get_realtime_metrics(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    zips = db.query(RawCompanyRecord.zip_code, func.count(RawCompanyRecord.id)).group_by(RawCompanyRecord.zip_code).order_by(func.count(RawCompanyRecord.id).desc()).limit(10).all()
    zip_data = list(map(lambda z: {"zipcode": z[0] or "Unknown", "count": z[1]}, zips))
    campaign_records = db.query(Campaign.name, RawCompanyRecord.industry, func.count(RawCompanyRecord.id)).join(Job, Job.campaign_id == Campaign.id).join(RawCompanyRecord, RawCompanyRecord.job_id == Job.id).group_by(Campaign.name, RawCompanyRecord.industry).all()
    campaign_data = reduce(lambda acc, cr: {**acc, cr[0]: acc.get(cr[0], []) + [{"name": cr[1] or "Unknown", "value": cr[2]}]}, campaign_records, {})
    formatted_campaigns = list(map(lambda item: {"campaign": item[0], "industries": item[1]}, campaign_data.items()))
    twenty_four_hours_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    recent_records = db.query(RawCompanyRecord.created_at).filter(RawCompanyRecord.created_at >= twenty_four_hours_ago).all()
    velocity_map = reduce(lambda acc, r: {**acc, r[0].strftime('%Y-%m-%d %H:00'): acc.get(r[0].strftime('%Y-%m-%d %H:00'), 0) + 1} if r[0] else acc, recent_records, {})
    sorted_hours = sorted(velocity_map.keys())
    velocity_data = list(map(lambda h: {"time": h, "count": velocity_map[h]}, sorted_hours))
    return {"zipcodes": zip_data, "campaigns": formatted_campaigns, "velocity": velocity_data}


@app.get("/api/v1/dashboard/credits")
async def get_mv_credits(_: dict = Depends(get_current_user)):
    credits = await get_remaining_credits()
    mv_credits_gauge.set(credits or 0)
    return {"credits": credits}


@app.get("/api/v1/locations/zipcodes")
def get_zipcodes_by_state(state: str, limit: int = 500, _: dict = Depends(get_current_user)):
    from uszipcode import SearchEngine
    search = SearchEngine()
    res = search.by_state(state.upper(), returns=limit)
    zip_list = list(map(lambda r: {"zipcode": r.zipcode, "city": r.major_city}, res))
    return {"state": state.upper(), "zipcodes": zip_list}


@app.get("/api/v1/campaigns")
def get_campaigns(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


@app.get("/api/v1/jobs")
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


@app.post("/api/v1/jobs/{job_id}/pause")
def pause_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job and job.status == 'in_progress':
        job.status = 'paused'
        db.commit()
    return {"status": job.status if job else "not found"}


@app.post("/api/v1/jobs/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job and job.status == 'paused':
        job.status = 'in_progress'
        db.commit()
    return {"status": job.status if job else "not found"}


@app.post("/api/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job and job.status in ['in_progress', 'paused', 'pending']:
        job.status = 'cancelled'
        db.commit()
        active_jobs.dec()
    return {"status": job.status if job else "not found"}


@app.get("/api/v1/jobs/{job_id}/export")
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


@app.get("/api/v1/jobs/{job_id}/details")
def get_job_details(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    records = db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()
    leads = db.query(EnrichedLead).join(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()
    records_data = list(map(lambda r: {"id": r.id, "company_name": r.company_name, "website": r.website, "phone": r.phone, "address": r.address, "city": r.city, "state": r.state}, records))
    leads_data = list(map(lambda l: {"id": l.id, "first_name": l.first_name, "last_name": l.last_name, "title": l.title, "email": l.guessed_email, "email_status": l.email_verification_status, "linkedin_url": l.linkedin_url, "company_name": next((rc.company_name for rc in records if rc.id == l.raw_record_id), "Unknown"),}, leads))
    return {"job_id": job.id, "status": job.status, "records": records_data, "leads": leads_data}


@app.get("/api/v1/leads")
def get_all_leads(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).order_by(EnrichedLead.id.desc()).offset(skip).limit(limit).all()
    return list(map(lambda lr: {"id": lr[0].id, "first_name": lr[0].first_name, "last_name": lr[0].last_name, "title": lr[0].title, "email": lr[0].guessed_email, "email_status": lr[0].email_verification_status, "linkedin_url": lr[0].linkedin_url, "company_name": lr[1].company_name, "industry": lr[1].industry, "city": lr[1].city, "state": lr[1].state, "job_id": lr[1].job_id}, leads))


@app.get("/api/v1/leads/export")
def export_leads_csv(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["First Name", "Last Name", "Title", "Email", "Email Status", "LinkedIn", "Company", "Industry", "City", "State"])
    list(map(lambda lr: writer.writerow([lr[0].first_name, lr[0].last_name, lr[0].title, lr[0].guessed_email, lr[0].email_verification_status, lr[0].linkedin_url, lr[1].company_name, lr[1].industry, lr[1].city, lr[1].state]), leads))
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=leads_export.csv"})


@app.get("/api/v1/jobs/{job_id}/companies")
def get_job_companies(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(RawCompanyRecord).filter(RawCompanyRecord.job_id == job_id).all()


@app.get("/api/v1/jobs/{job_id}/leads")
def get_job_specific_leads(job_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).filter(RawCompanyRecord.job_id == job_id).all()
    return list(map(lambda lr: {"id": lr[0].id, "first_name": lr[0].first_name, "last_name": lr[0].last_name, "title": lr[0].title, "email": lr[0].guessed_email, "email_status": lr[0].email_verification_status, "linkedin_url": lr[0].linkedin_url, "company_name": lr[1].company_name}, leads))


@app.delete("/api/v1/jobs/{job_id}")
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


@app.get("/api/v1/companies")
def get_all_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(RawCompanyRecord).order_by(RawCompanyRecord.id.desc()).offset(skip).limit(limit).all()


@app.get("/api/v1/companies/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    company = db.query(RawCompanyRecord).filter(RawCompanyRecord.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.get("/api/v1/companies/{company_id}/leads")
def get_company_leads(company_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(EnrichedLead).filter(EnrichedLead.raw_record_id == company_id).all()


@app.get("/api/v1/leads/{lead_id}/organization")
def get_lead_organization(lead_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    lead = db.query(EnrichedLead).filter(EnrichedLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return db.query(RawCompanyRecord).filter(RawCompanyRecord.id == lead.raw_record_id).first()


@app.get("/api/v1/leads/search")
def search_leads(title: Optional[str] = None, industry: Optional[str] = None, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    query = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id)
    if title:
        query = query.filter(EnrichedLead.title.ilike(f"%{title}%"))
    if industry:
        query = query.filter(RawCompanyRecord.industry.ilike(f"%{industry}%"))
    leads = query.all()
    return list(map(lambda lr: {"id": lr[0].id, "first_name": lr[0].first_name, "last_name": lr[0].last_name, "title": lr[0].title, "email": lr[0].guessed_email, "email_status": lr[0].email_verification_status, "linkedin_url": lr[0].linkedin_url, "company_name": lr[1].company_name, "industry": lr[1].industry}, leads))


@app.get("/api/v1/system/info")
def system_info(_: dict = Depends(get_current_user)):
    return {
        "version": "4.0.0",
        "database": os.environ.get("DATABASE_URL", "sqlite").split("://")[0],
        "proxies_configured": proxy_rotator.count(),
        "websocket_connections": ws_manager.total_connections,
        "celery_broker": os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    }


frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def root_fallback():
        return {"message": "Lead Generation Pipeline API is running. Frontend dist folder not found."}


if __name__ == "__main__":
    import uvicorn
    print("Starting Lead Generation Studio API v4.0 on http://localhost:8000")
    uvicorn.run("lead_generation_app.backend.app:app", host="0.0.0.0", port=8000, reload=True)
