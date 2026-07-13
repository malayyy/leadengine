import io
import csv
from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import EnrichedLead, RawCompanyRecord
from ..auth import get_current_user

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.get("")
def get_all_leads(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).order_by(EnrichedLead.id.desc()).offset(skip).limit(limit).all()
    return list(map(lambda lr: {"id": lr[0].id, "first_name": lr[0].first_name, "last_name": lr[0].last_name, "title": lr[0].title, "email": lr[0].guessed_email, "email_status": lr[0].email_verification_status, "linkedin_url": lr[0].linkedin_url, "company_name": lr[1].company_name, "industry": lr[1].industry, "city": lr[1].city, "state": lr[1].state, "job_id": lr[1].job_id}, leads))


@router.get("/export")
def export_leads_csv(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    leads = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["First Name", "Last Name", "Title", "Email", "Email Status", "LinkedIn", "Company", "Industry", "City", "State"])
    list(map(lambda lr: writer.writerow([lr[0].first_name, lr[0].last_name, lr[0].title, lr[0].guessed_email, lr[0].email_verification_status, lr[0].linkedin_url, lr[1].company_name, lr[1].industry, lr[1].city, lr[1].state]), leads))
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=leads_export.csv"})


@router.get("/search")
def search_leads(title: Optional[str] = None, industry: Optional[str] = None, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    query = db.query(EnrichedLead, RawCompanyRecord).join(RawCompanyRecord, EnrichedLead.raw_record_id == RawCompanyRecord.id)
    if title:
        query = query.filter(EnrichedLead.title.ilike(f"%{title}%"))
    if industry:
        query = query.filter(RawCompanyRecord.industry.ilike(f"%{industry}%"))
    leads = query.all()
    return list(map(lambda lr: {"id": lr[0].id, "first_name": lr[0].first_name, "last_name": lr[0].last_name, "title": lr[0].title, "email": lr[0].guessed_email, "email_status": lr[0].email_verification_status, "linkedin_url": lr[0].linkedin_url, "company_name": lr[1].company_name, "industry": lr[1].industry}, leads))


@router.get("/{lead_id}/organization")
def get_lead_organization(lead_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    lead = db.query(EnrichedLead).filter(EnrichedLead.id == lead_id).first()
    if not lead:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Lead not found")
    return db.query(RawCompanyRecord).filter(RawCompanyRecord.id == lead.raw_record_id).first()
