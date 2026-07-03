import asyncio
import datetime
import json
import os
import re
import time
from functools import reduce

import redis
import tldextract
from typing import Optional, List

from .celery_app import celery_app
from .database import SessionLocal
from .models import Job, RawCompanyRecord, EnrichedLead, Campaign, EmailCache
from .google_maps import GoogleMapsScraper
from .linkedin import LinkedInScraper
from . import millionverifier
from .millionverifier import verify_email_millionverifier
from .website_scraper import scrape_general_emails
from .rate_limiter import DomainRateLimiter
from .proxy_rotator import ProxyRotator
from .metrics import records_total, leads_total, emails_verified, scrape_rate, active_jobs
from .logger import PhaseLogger, get_logger, mask_sensitive

log = get_logger("tasks")

BATCH_SIZE = 50
redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(redis_url)
rate_limiter = DomainRateLimiter()
proxy_rotator = ProxyRotator.from_env()


def publish_event(job_id, event_type, data):
    channel = f"job_{job_id}_events"
    message = json.dumps({"type": event_type, **data})
    redis_client.publish(channel, message)


def update_job_status(job_id, status, error_message=None):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = status
            if error_message:
                job.error_message = error_message
            if status in ("completed", "failed", "cancelled"):
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
    finally:
        db.close()


def log_to_job(job_id, message):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            logs = list(job.log_messages or [])
            logs.append({"log": "message", "text": message, "ts": datetime.datetime.utcnow().isoformat()})
            job.log_messages = logs
            db.commit()
    finally:
        db.close()


async def _areduce(func, items, initial):
    if not items:
        return initial
    return await _areduce(func, items[1:], await func(initial, items[0]))


async def _wait_for_resume(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
    finally:
        db.close()
    if job and job.status == "paused":
        await asyncio.sleep(5)
        return await _wait_for_resume(job_id)
    return job


def _check_cancelled(job):
    return bool(job and job.status == "cancelled")


def _make_address_parts(lead, zipcode):
    address = lead.get("address", "") or ""
    matches = re.findall(r'\b\d{5}(?:-\d{4})?\b', address)
    real_zip = matches[-1] if matches else zipcode
    address_clean = address.lower().replace("united states", "").replace("usa", "").strip()
    parts = list(filter(None, map(str.strip, address_clean.split(","))))
    real_city = parts[-2].title() if len(parts) >= 2 else ""
    return address, real_zip, real_city


def _make_raw_record(lead, job_id, real_zip, real_city, state, industry, address):
    return RawCompanyRecord(
        job_id=job_id,
        company_name=lead.get("name"),
        website=lead.get("website"),
        phone=lead.get("phone"),
        rating=lead.get("rating"),
        address=address,
        city=real_city,
        state=state,
        zip_code=real_zip,
        industry=industry,
        gmaps_url=lead.get("url"),
        source="google_maps",
        status="pending_enrichment",
    )


def _batch_save_and_dispatch(records, job_id, query, records_saved_base, target_titles, proxy, linkedin_cookie):
    if not records:
        return 0
    db = SessionLocal()
    saved_ids = []
    record_data = []
    try:
        for record in records:
            db.add(record)
        db.flush()
        for record in records:
            saved_ids.append(record.id)
            record_data.append({
                "id": record.id,
                "company_name": record.company_name,
                "website": record.website,
                "phone": record.phone,
                "address": record.address,
                "city": record.city,
                "state": record.state,
                "zip_code": record.zip_code,
                "industry": record.industry,
            })
        db.commit()
    finally:
        db.close()

    for i, data in enumerate(record_data):
        records_total.labels(source="google_maps").inc()
        publish_event(job_id, "raw_record_found", {
            "searched": query, "found records": records_saved_base + i + 1,
            "record": data,
        })

    for i in range(0, len(saved_ids), BATCH_SIZE):
        batch = saved_ids[i:i + BATCH_SIZE]
        phase_2_enrichment_batch.delay(
            job_id=job_id, raw_record_ids=batch, target_titles=target_titles,
            proxy=proxy, linkedin_cookie=linkedin_cookie,
        )
    return len(records)


async def async_phase_1_scrape(job_id, industry, zipcodes, state, target_titles, contacts_per_company, proxy, linkedin_cookie):
    proxies = [proxy] if proxy else (proxy_rotator.proxies if proxy_rotator.count() > 0 else None)
    scraper = GoogleMapsScraper(headless=True, proxy=proxy_rotator.get_next() if not proxy else proxy)
    db = SessionLocal()
    campaign_name = "Unknown"
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first() if job else None
        campaign_name = campaign.name if campaign else "Unknown"
        total_cap = campaign.total_contacts if campaign else 0

        pl = PhaseLogger(campaign_name, job_id)
        pl.log_scrape("Phase 1 started | industry=%s state=%s zips=%d titles=%d cap=%d",
                      industry, state, len(zipcodes), len(target_titles), total_cap,
                      extra_fields={"phase": "scrape", "industry": industry, "state": state,
                                    "zipcodes_count": len(zipcodes), "titles_count": len(target_titles),
                                    "total_cap": total_cap})

        def progress_callback(log_msg):
            publish_event(job_id, "log_msg", {"message": log_msg})
            log_to_job(job_id, log_msg)

        initial_state = {
            "scraper": scraper, "job_id": job_id, "industry": industry,
            "state": state, "target_titles": target_titles,
            "contacts_per_company": contacts_per_company, "proxy": proxy,
            "linkedin_cookie": linkedin_cookie, "total_cap": total_cap,
            "records_saved": 0, "progress_callback": progress_callback,
            "campaign_name": campaign_name,
        }

        final_state = await _areduce(lambda state, z: _process_zipcode(state, z), zipcodes, initial_state)

        pl.log_scrape("Phase 1 completed | records_saved=%d", final_state["records_saved"],
                      extra_fields={"records_saved": final_state["records_saved"]})
    finally:
        db.close()

    return final_state["records_saved"]


async def _process_zipcode(state, zipcode):
    start_time = time.monotonic()
    pl = PhaseLogger(state.get("campaign_name", "Unknown"), state["job_id"])
    job = _check_job_state(state["job_id"])
    if _check_cancelled(job):
        publish_event(state["job_id"], "status", {"status": "cancelled", "message": "Job cancelled. Stopping Phase 1."})
        return {**state, "records_saved": state["records_saved"]}

    if state["total_cap"] > 0 and state["records_saved"] >= state["total_cap"]:
        publish_event(state["job_id"], "log_msg", {"message": "Record cap reached. Stopping Phase 1."})
        pl.log_scrape("Cap reached at %d records, stopping", state["records_saved"])
        return {**state, "records_saved": state["records_saved"]}

    industry_keywords = [kw.strip() for kw in state['industry'].split(',') if kw.strip()]
    if not industry_keywords:
        industry_keywords = [state['industry']]

    all_candidates = []

    for keyword in industry_keywords:
        if state["total_cap"] > 0 and state["records_saved"] + len(all_candidates) >= state["total_cap"]:
            break

        await rate_limiter.wait_for_domain("google.com")

        query = f"{keyword} in {zipcode}, {state['state']}"
        pl.log_scrape("Searching zip=%s | industry=%s | query=%s", zipcode, keyword, query,
                      extra_fields={"zipcode": zipcode, "industry": keyword, "query": query})

        publish_event(state["job_id"], "log_msg", {
            "message": f"searched {query}"
        })

        leads = await state["scraper"].scrape_all(query, max_leads=200, progress_callback=state["progress_callback"])
        pl.log_scrape("Zip=%s | industry=%s | found %d raw leads", zipcode, keyword, len(leads),
                      extra_fields={"zipcode": zipcode, "industry": keyword, "raw_leads": len(leads)})

        for lead in leads:
            if state["total_cap"] > 0 and state["records_saved"] + len(all_candidates) >= state["total_cap"]:
                pl.log_scrape("Cap reached mid-zipcode %s at %d candidates", zipcode, len(all_candidates))
                break
            name = lead.get("name")
            if not name:
                continue
            address, real_zip, real_city = _make_address_parts(lead, zipcode)
            record = _make_raw_record(lead, state["job_id"], real_zip, real_city, state["state"], state["industry"], address)
            all_candidates.append(record)

    if not all_candidates:
        elapsed = time.monotonic() - start_time
        scrape_rate.set(0)
        pl.log_scrape("Zip=%s | 0 new candidates after dedup | took %.2fs", zipcode, elapsed)
        return {**state, "records_saved": state["records_saved"]}

    db = SessionLocal()
    try:
        existing_names = set()
        names_to_check = list(filter(None, [r.company_name for r in all_candidates]))
        if names_to_check:
            existing = db.query(RawCompanyRecord.company_name).filter(
                RawCompanyRecord.company_name.in_(names_to_check),
            ).all()
            existing_names = set(r[0] for r in existing)
            pl.log_scrape("Zip=%s | %d candidates, %d existing in DB",
                          zipcode, len(all_candidates), len(existing_names))
    finally:
        db.close()

    new_records = [r for r in all_candidates if r.company_name not in existing_names]
    pl.log_scrape("Zip=%s | %d new records after dedup", zipcode, len(new_records),
                  extra_fields={"zipcode": zipcode, "new_records": len(new_records), "duplicates_skipped": len(all_candidates) - len(new_records)})

    saved_count = _batch_save_and_dispatch(
        new_records, state["job_id"], "",
        state["records_saved"], state["target_titles"],
        state["proxy"], state["linkedin_cookie"],
    )

    elapsed = time.monotonic() - start_time
    zip_rate = saved_count / elapsed if elapsed > 0 else 0
    scrape_rate.set(zip_rate)
    pl.log_scrape("Zip=%s | saved=%d rate=%.2f/s took=%.2fs", zipcode, saved_count, zip_rate, elapsed)

    return {**state, "records_saved": state["records_saved"] + saved_count}


def _check_job_state(job_id):
    db = SessionLocal()
    try:
        return db.query(Job).filter(Job.id == job_id).first()
    finally:
        db.close()


@celery_app.task(name="phase_1_gmaps_scrape", bind=True)
def phase_1_gmaps_scrape(self, job_id, industry, zipcodes, state, target_titles, contacts_per_company, proxy, linkedin_cookie):
    task_id = self.request.id
    log.info("Phase 1 task starting | job_id=%s task_id=%s industry=%s state=%s zips=%d",
             job_id, task_id, industry, state, len(zipcodes))
    update_job_status(job_id, "in_progress")
    publish_event(job_id, "status", {"status": "in_progress"})

    try:
        records_saved = asyncio.run(async_phase_1_scrape(
            job_id=job_id, industry=industry, zipcodes=zipcodes,
            state=state, target_titles=target_titles,
            contacts_per_company=contacts_per_company,
            proxy=proxy, linkedin_cookie=linkedin_cookie,
        ))
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status not in ("cancelled", "failed"):
                update_job_status(job_id, "completed")
                publish_event(job_id, "status", {"status": "completed"})
                active_jobs.dec()
                log.info("Phase 1 completed | job_id=%d records_saved=%d", job_id, records_saved)
        finally:
            db.close()
        return {"status": "success", "raw_records_saved": records_saved}
    except Exception as e:
        log.error("Phase 1 failed | job_id=%d error=%s", job_id, str(e), exc_info=True)
        update_job_status(job_id, "failed", error_message=str(e))
        publish_event(job_id, "status", {"status": "failed", "message": str(e)})
        active_jobs.dec()
        raise


async def async_phase_2_enrich(job_id, raw_record_id, target_titles, proxy, linkedin_cookie):
    db = SessionLocal()
    scraper = LinkedInScraper(proxy=proxy_rotator.get_next() if not proxy else proxy)

    def progress_callback(log_msg):
        publish_event(job_id, "enrichment_log", {"message": log_msg})
        log_to_job(job_id, log_msg)

    try:
        record = db.query(RawCompanyRecord).filter(RawCompanyRecord.id == raw_record_id).first()
        if not record:
            log.warning("Phase 2 | record %d not found, skipping", raw_record_id)
            return

        job = db.query(Job).filter(Job.id == job_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first() if job else None
        campaign_name = campaign.name if campaign else "Unknown"
        pl = PhaseLogger(campaign_name, job_id)

        clean_company = re.sub(r'\b(llc|inc|corp|ltd|co\.?)\b', '', record.company_name, flags=re.IGNORECASE).strip()

        pl.log_enrich("Enriching record=%d | company=%s titles=%d", raw_record_id, clean_company, len(target_titles),
                      extra_fields={"record_id": raw_record_id, "company": clean_company, "titles_count": len(target_titles)})

        skip_email = job.skip_email_verify if job else 0
        initial_state = {
            "scraper": scraper, "job_id": job_id, "raw_record_id": raw_record_id,
            "clean_company": clean_company, "state": record.state,
            "linkedin_cookie": linkedin_cookie, "leads_found": 0,
            "seen_urls": set(), "progress_callback": progress_callback,
            "db": db, "campaign_name": campaign_name,
            "skip_email_verify": skip_email,
        }

        final_state = await _areduce(
            lambda state, title: _process_title(state, title),
            target_titles,
            initial_state,
        )

        record.status = "enriched" if final_state["leads_found"] > 0 else "enrichment_failed"
        if final_state["leads_found"] > 0:
            leads_total.inc(final_state["leads_found"])
        db.commit()

        pl.log_enrich("Record=%d | company=%s | leads_found=%d status=%s",
                      raw_record_id, clean_company, final_state["leads_found"], record.status,
                      extra_fields={"record_id": raw_record_id, "company": clean_company,
                                    "leads_found": final_state["leads_found"], "status": record.status})
    finally:
        db.close()


@celery_app.task(name="phase_2_enrichment", bind=True)
def phase_2_enrichment(self, job_id, raw_record_id, target_titles, proxy, linkedin_cookie):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status == "cancelled":
            return {"status": "cancelled"}
    finally:
        db.close()

    log.info("Phase 2 enrichment | job_id=%d record=%d titles=%d", job_id, raw_record_id, len(target_titles))
    try:
        asyncio.run(async_phase_2_enrich(
            job_id=job_id, raw_record_id=raw_record_id,
            target_titles=target_titles, proxy=proxy,
            linkedin_cookie=linkedin_cookie,
        ))
    except Exception as e:
        log.error("Phase 2 enrichment failed | job_id=%d record=%d error=%s", job_id, raw_record_id, str(e), exc_info=True)
        publish_event(job_id, "error", {"message": f"Phase 2 Enrichment failed for record {raw_record_id}: {e}"})
        raise


@celery_app.task(name="phase_2_enrichment_batch", bind=True)
def phase_2_enrichment_batch(self, job_id, raw_record_ids, target_titles, proxy, linkedin_cookie):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status == "cancelled":
            return {"status": "cancelled", "job_id": job_id}
    finally:
        db.close()

    batch_start = time.monotonic()
    log.info("Phase 2 batch | job_id=%d records=%d batch_size=%d", job_id, len(raw_record_ids), len(raw_record_ids))
    succeeded = 0
    failed = 0
    for rid in raw_record_ids:
        try:
            asyncio.run(async_phase_2_enrich(
                job_id=job_id, raw_record_id=rid,
                target_titles=target_titles, proxy=proxy,
                linkedin_cookie=linkedin_cookie,
            ))
            succeeded += 1
        except Exception as e:
            failed += 1
            log.error("Phase 2 enrichment failed | job_id=%d record=%d error=%s", job_id, rid, str(e), exc_info=True)
            publish_event(job_id, "error", {"message": f"Phase 2 Enrichment failed for record {rid}: {e}"})

    elapsed = time.monotonic() - batch_start
    log.info("Phase 2 batch completed | job_id=%d succeeded=%d failed=%d took=%.2fs",
             job_id, succeeded, failed, elapsed)
    return {"status": "completed", "records_processed": len(raw_record_ids),
            "succeeded": succeeded, "failed": failed, "job_id": job_id}

async def _process_title(state, title):
    job = _check_job_state(state["job_id"])
    if _check_cancelled(job):
        publish_event(state["job_id"], "enrichment_log", {"message": "Job cancelled. Stopping Phase 2."})
        return {**state}
    job = await _wait_for_resume(state["job_id"])

    pl = PhaseLogger(state.get("campaign_name", "Unknown"), state["job_id"])
    rate_limit_domain = "linkedin.com" if state["linkedin_cookie"] else "google.com"
    await rate_limiter.wait_for_domain(rate_limit_domain)

    method = "LinkedIn cookie" if state["linkedin_cookie"] else "X-Ray"
    publish_event(state["job_id"], "enrichment_log", {
        "message": f"Searching for: {title} at {state['clean_company']} (method: {method})"
    })

    pl.log_enrich("Searching title=%s company=%s method=%s", title, state["clean_company"], method,
                  extra_fields={"title": title, "company": state["clean_company"], "method": method})

    search_start = time.monotonic()
    results = await state["scraper"].scrape(
        query=title,
        location=f"{state['clean_company']} {state['state']}",
        search_type="people",
        li_at_cookie=state["linkedin_cookie"],
        max_leads=20,
        progress_callback=state["progress_callback"],
    )
    search_elapsed = time.monotonic() - search_start
    pl.log_enrich("Title=%s | found %d results in %.2fs", title, len(results), search_elapsed,
                  extra_fields={"title": title, "results_count": len(results), "search_duration_ms": round(search_elapsed * 1000, 2)})

    async def process_result(res, acc):
        profile_url = res.get("url", "")
        if not profile_url or profile_url in acc["seen_urls"]:
            return acc
        return await _process_linkedin_result(res, profile_url, title, acc)

    return await _areduce(process_result, results, state)


async def _process_linkedin_result(res, profile_url, title, state):
    db = SessionLocal()
    pl = PhaseLogger(state.get("campaign_name", "Unknown"), state["job_id"])
    try:
        is_match = True
        exact_title = None

        if state["linkedin_cookie"] and profile_url:
            exp_start = time.monotonic()
            exp_data = await state["scraper"]._scrape_profile_experience(
                profile_url, state["linkedin_cookie"], state["progress_callback"],
            )
            exp_elapsed = time.monotonic() - exp_start
            if exp_data:
                current_company = exp_data.get("company", "").lower()
                target_lower = state["clean_company"].lower()
                if target_lower not in current_company and current_company not in target_lower:
                    is_match = False
                    pl.log_enrich("STRICT REJECT url=%s | current_company=%s target=%s",
                                  profile_url, current_company, state["clean_company"],
                                  extra_fields={"profile_url": profile_url, "current_company": current_company,
                                                "target_company": state["clean_company"], "match": False})
                    publish_event(state["job_id"], "enrichment_log", {
                        "message": f"STRICT REJECT {profile_url}: Current company is '{current_company}'"
                    })
                else:
                    exact_title = exp_data.get("title")
                    pl.log_enrich("MATCH url=%s | title=%s company=%s (profile scrape took %.2fs)",
                                  profile_url, exact_title, current_company, exp_elapsed,
                                  extra_fields={"profile_url": profile_url, "exact_title": exact_title,
                                                "company": current_company, "match": True})
                    publish_event(state["job_id"], "enrichment_log", {
                        "message": f"Extracted perfect title: {exact_title} at {current_company}"
                    })

        if not is_match:
            return state

        name = res.get("name", "Unknown")
        parts = re.split(r'[-|]', name)
        fname = parts[0].strip() if parts else name
        lname = " ".join(parts[1:]).strip() if len(parts) > 1 else ""

        clean_url = profile_url.split("?")[0].rstrip("/")

        existing = db.query(EnrichedLead).filter(EnrichedLead.linkedin_url == clean_url).first()
        if existing:
            pl.log_enrich("DUPLICATE url=%s already exists in DB", clean_url)
            publish_event(state["job_id"], "enrichment_log", {
                "message": f"Global duplicate found: {clean_url} already exists"
            })
            return state

        enriched = EnrichedLead(
            raw_record_id=state["raw_record_id"],
            first_name=fname,
            last_name=lname,
            title=exact_title or title,
            linkedin_url=clean_url,
            location=res.get("location", state["state"]),
            email_verification_status="pending",
        )
        db.add(enriched)
        db.commit()
        db.refresh(enriched)

        pl.log_enrich("SAVED lead id=%d | name=%s %s | title=%s | url=%s",
                      enriched.id, fname, lname, enriched.title, clean_url,
                      extra_fields={"lead_id": enriched.id, "first_name": fname, "last_name": lname,
                                    "title": enriched.title, "linkedin_url": clean_url})

        publish_event(state["job_id"], "enriched_lead_found", {
            "record_id": state["raw_record_id"],
            "lead": {"id": enriched.id, "first_name": enriched.first_name, "last_name": enriched.last_name,
                     "title": enriched.title, "linkedin_url": enriched.linkedin_url},
        })

        job_skip_email = state.get("skip_email_verify", 0)
        if not job_skip_email:
            phase_3_email_verification.delay(job_id=state["job_id"], raw_record_id=state["raw_record_id"])

        seen_urls = set(state["seen_urls"])
        seen_urls.add(profile_url)
        return {**state, "leads_found": state["leads_found"] + 1, "seen_urls": seen_urls}
    finally:
        db.close()


async def check_or_verify_email(db, email, job_id):
    cached = db.query(EmailCache).filter(EmailCache.email == email).first()
    if cached:
        return cached.status

    job = db.query(Job).filter(Job.id == job_id).first()
    status = await verify_email_millionverifier(email)

    if job and status in ("valid", "catch_all"):
        job.mv_credits_used = (job.mv_credits_used or 0) + 1
        db.commit()

    new_cache = EmailCache(email=email, status=status, source="millionverifier")
    db.add(new_cache)
    try:
        db.commit()
    except Exception:
        db.rollback()

    emails_verified.labels(status=status).inc()
    return status


async def async_phase_3_email_verification(job_id, raw_record_id):
    db = SessionLocal()
    try:
        record = db.query(RawCompanyRecord).filter(RawCompanyRecord.id == raw_record_id).first()
        if not record or not record.website:
            log.debug("Phase 3 | record %d has no website, skipping email verification", raw_record_id)
            return

        job = db.query(Job).filter(Job.id == job_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first() if job else None
        campaign_name = campaign.name if campaign else "Unknown"
        pl = PhaseLogger(campaign_name, job_id)

        website = record.website
        ext = tldextract.extract(website)
        domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain

        leads = db.query(EnrichedLead).filter(EnrichedLead.raw_record_id == raw_record_id).all()

        pl.log_email("Verifying %d leads for company=%s domain=%s", len(leads), record.company_name, domain,
                     extra_fields={"record_id": raw_record_id, "company": record.company_name,
                                   "domain": domain, "leads_count": len(leads)})

        initial_state = {"db": db, "job_id": job_id, "domain": domain, "website": website, "pl": pl}
        reduce(lambda state, lead: _verify_lead_email(state, lead), leads, initial_state)

        pl.log_email("Completed verification for company=%s domain=%s", record.company_name, domain)
    finally:
        db.close()


def _verify_lead_email(state, lead):
    db = state["db"]
    job_id = state["job_id"]
    domain = state["domain"]
    website = state["website"]
    pl = state.get("pl")

    fname = (lead.first_name or "").lower().strip()
    lname = (lead.last_name or "").lower().strip()

    if not fname or not domain:
        if pl:
            pl.log_email("Skipping lead id=%d | no name or domain (fname=%s domain=%s)", lead.id, fname, domain)
        return state

    patterns = list(filter(None, [
        f"{fname}.{lname}@{domain}",
        f"{fname[0]}{lname}@{domain}",
        f"{fname}@{domain}",
        f"{fname}{lname[0]}@{domain}" if lname else None,
        f"{fname[0]}.{lname}@{domain}",
    ]))

    if pl:
        pl.log_email("Verifying lead id=%d | name=%s %s | %d patterns to try",
                     lead.id, fname, lname, len(patterns),
                     extra_fields={"lead_id": lead.id, "first_name": fname, "last_name": lname,
                                   "patterns": patterns, "domain": domain})

    def verify_pattern(pattern, acc):
        if acc.get("found"):
            return acc
        if pl:
            pl.log_email("Trying pattern=%s for lead=%s %s", pattern, fname, lname)
        asyncio.run(_verify_single(lead, pattern, job_id, db))
        if lead.email_verification_status == "valid":
            if pl:
                pl.log_email("FOUND valid email=%s for lead=%s %s", pattern, fname, lname,
                             extra_fields={"lead_id": lead.id, "email": pattern, "status": "valid"})
            return {**acc, "found": True}
        return acc

    result = reduce(lambda acc, p: verify_pattern(p, acc), patterns, {"found": False})

    if not result["found"]:
        if pl:
            pl.log_email("Patterns exhausted for lead=%s %s, trying website scrape on %s", fname, lname, website)
        general_emails = asyncio.run(scrape_general_emails(website))
        if pl:
            pl.log_email("Website scrape found %d general emails on %s", len(general_emails), website)
        general_matches = list(filter(
            lambda g: asyncio.run(_try_general_email(lead, g, job_id, db)),
            general_emails,
        ))
        if general_matches:
            if pl:
                pl.log_email("Matched %d general emails for lead=%s %s", len(general_matches), fname, lname)
            return state

    if not lead.guessed_email:
        lead.email_verification_status = "not_found"
        db.commit()
        if pl:
            pl.log_email("No email found for lead=%s %s, marked not_found", fname, lname)

    return state


async def _verify_single(lead, email_pattern, job_id, db):
    publish_event(job_id, "verification_log", {
        "message": f"Checking email for {lead.first_name}: {email_pattern}"
    })
    status = await check_or_verify_email(db, email_pattern, job_id)
    lead.email_verification_status = status
    if status == "valid":
        lead.guessed_email = email_pattern
        db.commit()
        publish_event(job_id, "email_found", {"type": "personalized", "email": email_pattern, "status": status})
    elif status == "catch_all":
        if not lead.guessed_email:
            lead.guessed_email = email_pattern
        db.commit()


async def _try_general_email(lead, g_email, job_id, db):
    status = await check_or_verify_email(db, g_email, job_id)
    if status in ("valid", "catch_all"):
        lead.guessed_email = g_email
        lead.email_verification_status = status
        db.commit()
        publish_event(job_id, "email_found", {"type": "general", "email": g_email, "status": status})
        return True
    return False


@celery_app.task(name="phase_3_email_verification", bind=True)
def phase_3_email_verification(self, job_id, raw_record_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status == "cancelled":
            return {"status": "cancelled"}
    finally:
        db.close()

    log.info("Phase 3 email verification | job_id=%d record=%d", job_id, raw_record_id)
    try:
        asyncio.run(async_phase_3_email_verification(job_id=job_id, raw_record_id=raw_record_id))
    except Exception as e:
        log.error("Phase 3 verification failed | job_id=%d record=%d error=%s", job_id, raw_record_id, str(e), exc_info=True)
        publish_event(job_id, "error", {"message": f"Phase 3 Verification failed for record {raw_record_id}: {e}"})
        raise
