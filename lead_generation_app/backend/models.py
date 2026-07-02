from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    industry = Column(String, index=True)
    state = Column(String, index=True)
    target_titles = Column(JSON, default=list)
    zipcodes = Column(JSON, default=list)
    total_contacts = Column(Integer, default=0)
    status = Column(String, default="active") # active, paused, completed, failed
    cost_spent = Column(Float, default=0.0)
    proxy_list = Column(JSON, nullable=True) # Optional list of proxies
    contacts_per_company = Column(Integer, nullable=True) # Max valid emails per company
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    jobs = relationship("Job", back_populates="campaign")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    celery_task_id = Column(String, index=True, nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    status = Column(String, default="pending") # pending, in_progress, completed, failed
    log_messages = Column(JSON, default=list)
    error_message = Column(Text, nullable=True)
    skip_email_verify = Column(Integer, default=0)
    mv_credits_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign", back_populates="jobs")
    raw_records = relationship("RawCompanyRecord", back_populates="job")

class RawCompanyRecord(Base):
    __tablename__ = "raw_company_records"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    
    # Scraped Data
    company_name = Column(String, index=True)
    website = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, index=True)
    zip_code = Column(String, index=True)
    industry = Column(String, index=True)
    
    # Rich Data
    rating = Column(Float, nullable=True)
    gmaps_url = Column(String, nullable=True)
    source = Column(String, default="google_maps")
    
    # Status
    status = Column(String, default="pending_enrichment") # pending_enrichment, enriched, enrichment_failed
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    job = relationship("Job", back_populates="raw_records")
    enriched_leads = relationship("EnrichedLead", back_populates="raw_record")

class EnrichedLead(Base):
    __tablename__ = "enriched_leads"

    id = Column(Integer, primary_key=True, index=True)
    raw_record_id = Column(Integer, ForeignKey("raw_company_records.id"))
    
    # Enrichment Data
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    title = Column(String, index=True, nullable=True)
    linkedin_url = Column(String, nullable=True)
    guessed_email = Column(String, nullable=True)
    
    # Enrichment Meta
    email_verification_status = Column(String, default="pending") # pending, valid, invalid, catch_all
    email_confidence_score = Column(Float, nullable=True)
    linkedin_profile_pic_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    raw_record = relationship("RawCompanyRecord", back_populates="enriched_leads")

class EmailCache(Base):
    __tablename__ = "email_cache"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    status = Column(String) # valid, invalid, catch_all, unknown
    source = Column(String, default="millionverifier")
    last_verified_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
