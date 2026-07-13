import datetime
from functools import reduce
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Campaign, Job, RawCompanyRecord, EnrichedLead
from ..auth import get_current_user
from ..millionverifier import get_remaining_credits
from ..metrics import mv_credits_gauge

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    total_jobs = db.query(Job).count()
    total_records = db.query(RawCompanyRecord).count()
    total_enriched = db.query(EnrichedLead).count()
    total_emails = db.query(EnrichedLead).filter(
        EnrichedLead.email_verification_status.in_(['valid', 'catch_all'])
    ).count()
    return {"total_jobs": total_jobs, "total_records": total_records, "total_enriched": total_enriched, "total_valid_emails": total_emails}


@router.get("/realtime-metrics")
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


@router.get("/credits")
async def get_mv_credits(_: dict = Depends(get_current_user)):
    credits = await get_remaining_credits()
    mv_credits_gauge.set(credits or 0)
    return {"credits": credits}
