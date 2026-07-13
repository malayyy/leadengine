from pydantic import BaseModel
from typing import List, Optional


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
