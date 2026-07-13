import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Campaign
from ..auth import get_current_user
from ..proxy_rotator import ProxyRotator
from ..websocket_manager import ws_manager

router = APIRouter(tags=["misc"])
proxy_rotator = ProxyRotator.from_env()


@router.get("/health")
def health():
    return {"status": "healthy", "service": "lead-engine", "version": "4.0.0", "proxies": proxy_rotator.count()}


@router.get("/api/v1/campaigns")
def get_campaigns(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


@router.get("/api/v1/locations/zipcodes")
def get_zipcodes_by_state(state: str = Query(...), limit: int = 500, _: dict = Depends(get_current_user)):
    from uszipcode import SearchEngine
    search = SearchEngine()
    res = search.by_state(state.upper(), returns=limit)
    zip_list = list(map(lambda r: {"zipcode": r.zipcode, "city": r.major_city}, res))
    return {"state": state.upper(), "zipcodes": zip_list}


@router.get("/api/v1/system/info")
def system_info(_: dict = Depends(get_current_user)):
    return {
        "version": "4.0.0",
        "database": os.environ.get("DATABASE_URL", "sqlite").split("://")[0],
        "proxies_configured": proxy_rotator.count(),
        "websocket_connections": ws_manager.total_connections,
        "celery_broker": os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    }
