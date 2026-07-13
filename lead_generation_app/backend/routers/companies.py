from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import EnrichedLead, RawCompanyRecord
from ..auth import get_current_user

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("")
def get_all_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(RawCompanyRecord).order_by(RawCompanyRecord.id.desc()).offset(skip).limit(limit).all()


@router.get("/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    company = db.query(RawCompanyRecord).filter(RawCompanyRecord.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/{company_id}/leads")
def get_company_leads(company_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(EnrichedLead).filter(EnrichedLead.raw_record_id == company_id).all()
