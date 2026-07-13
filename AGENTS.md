# Lead Engine — Complete Project Context

## CRITICAL SYSTEM RULES

### AWS Connection
- **SSH Command**: `ssh -i ~/.ssh/leadengine-ec2-key.pem -o StrictHostKeyChecking=no ec2-user@34.198.122.194`
- **Key Location**: `~/.ssh/leadengine-ec2-key.pem` (DO NOT glob or search elsewhere)
- **Local AWS Config**: `~/.aws/credentials` corrupted (keys set to "re"). User must provide real creds.

### No Loops
- **STRICTLY FORBIDDEN**: `for`, `while`, list/dict comprehensions in Python
- **Use instead**: `map`, `filter`, `reduce`, recursion, lambda

### Docker
- Docker is NOT running locally. All `psql`, `docker exec`, `docker compose` commands execute via SSH on EC2.

---

## Project Overview

Lead Engine is an enterprise B2B lead generation pipeline with 4 phases:
1. **Phase 1** — Google Maps scraping by industry + zipcode
2. **Phase 2** — LinkedIn profile discovery for target titles (blocked by IP blacklisting)
3. **Phase 3** — Email generation (7 patterns per contact)
4. **Phase 4** — Email verification via MillionVerifier

---

## Infrastructure

### EC2 Instance
- **Type**: t3.medium (2 vCPU, 4GB RAM, 4GB swap)
- **IP**: `34.198.122.194` (Elastic IP)
- **App Dir**: `/home/ec2-user/leadengine/`
- **Docker Compose**: `docker-compose.enterprise.yml`
- **Deploy Command**: `docker compose -f docker-compose.enterprise.yml up -d --build --force-recreate`

### 13 Docker Containers
| Container | Service | Purpose |
|-----------|---------|---------|
| `leadgen_postgres` | postgres:16 | Database |
| `leadgen_redis` | redis:7 | Queue + cache (2GB maxmemory) |
| `leadgen_api` | FastAPI | API server (4 uvicorn workers) |
| `leadgen_worker_1` | celery | Phase 1 scrape (concurrency 2, queue: `scrape`) |
| `leadgen_worker_2` | celery | Phase 2 enrich (concurrency 2, queue: `enrich`) |
| `leadgen_worker_3` | celery | Phase 3-4 email (concurrency 10, queue: `email`) |
| `leadgen_beat` | celery | Beat scheduler |
| `leadgen_flower` | flower | Worker monitoring at `flower.chopstickintegrations.com` |
| `leadgen_traefik` | traefik:v3.1 | Reverse proxy + Let's Encrypt TLS |
| `leadgen_prometheus` | prometheus | Metrics (30d retention) |
| `leadgen_grafana` | grafana | Dashboards at `monitor.chopstickintegrations.com` |
| `leadgen_searxng` | searxng | Meta-search (BROKEN — all engines CAPTCHA blocked) |
| `leadgen_frontend` | React/nginx | Dashboard at `app.chopstickintegrations.com` |

### Domain
- **API**: `api.chopstickintegrations.com`
- **App**: `app.chopstickintegrations.com`
- **Flower**: `flower.chopstickintegrations.com`
- **Grafana**: `monitor.chopstickintegrations.com`

---

## LinkedIn Cookie (`li_at`)

- **Env Var**: `LINKEDIN_LI_AT_COOKIE` in `/home/ec2-user/leadengine/.env`
- **Length**: 152 chars
- **Lifespan**: ~200-400 searches or days-weeks before expiry
- **Passed**: Only to `api` service in docker-compose; workers get it as task arg
- **Refresh**: Must copy from browser devtools (Application → Cookies → li_at)
- **Force Recreate**: `--force-recreate` needed for new .env (not `docker compose restart`)
- **Cookie Format Fix**: Must be array: `[{"name": "li_at", "value": cookie, "domain": ".linkedin.com"}]` (Scrapling validates `array | null`)

---

## Pipeline Details

### Phase 1 — Google Maps Scrape (`phase_1_gmaps_scrape`)
- Iterates zipcodes, searches Google Maps for industry keywords via Playwright
- Infinite scroll feed extraction
- Deduplicates by company name
- Saves to `RawCompanyRecord` table
- Dispatches Phase 2 batches after completion

### Phase 2 — LinkedIn Enrichment (`phase_2_enrichment_batch`)
- For each company, searches target titles (e.g., "SITE MANAGER", "OPERATIONS MANAGER")
- **With cookie**: Playwright searches LinkedIn directly, scrapes profile experience for strict company match
- **Without cookie** (X-Ray mode): DuckDuckGo/Bing search via AWS Lambda proxy
- Parses profiles from search result HTML
- Saves to `EnrichedLead` table

### Phase 3 — Email Generation
- Generates 7 patterns: `fname.lname`, `finitial.lname`, `fname`, `lname`, `finitialname`, `fname-lname`, `fname_lname` @ domain
- Falls back to website scraping (`/team`, `/about`, `/contact`)
- Caches results in `EmailCache`

### Phase 4 — MillionVerifier Verification
- API Key: `MILLION_VERIFIER_API_KEY` in .env
- Verifies all pattern-generated emails
- Results: `valid`, `invalid`, `catch_all`, `unknown`

---

## AWS Lambda Proxy Architecture (Current)

### Why
EC2 datacenter IPs blocked by DuckDuckGo (202), Bing (CAPTCHA), Google (429). Free proxies from proxyscrape also blocked.

### How It Works
```
Celery Worker ──POST──► API Gateway ──► Lambda (no VPC)
  { url, method, headers }              │
                                         └──► httpx.request(target)
                                              │
                                         HTML ◄──┘
```
- Lambda without VPC = random AWS IP each invocation
- No NAT Gateway needed → free
- Each concurrent invocation gets different IP

### Cost
- ~$3-5 per 500K requests (free tier covers 1M requests/month)
- Lambda compute + API Gateway only

### Files
- `lead_generation_app/backend/aws_proxy/lambda_function.py` — Lambda handler
- `deploy_aws_proxy.sh` — Deployment script (asks for Account ID + Region)

### Deployment
```bash
./deploy_aws_proxy.sh
# Outputs AWS_PROXY_URL and AWS_PROXY_API_KEY
# Add to EC2 .env, then docker compose up -d --build --force-recreate
```

---

## Message Queues (Redis)

| Queue | Pending | Consumer | Concurrency |
|-------|---------|----------|-------------|
| `scrape` | ~6 | worker_1 | 2 |
| `enrich` | ~1,895 | worker_2 | 2 |
| `email` | 0 | worker_3 | 10 |

---

## Database (PostgreSQL)

### Tables
- `campaigns` — Campaign configs, target titles, zipcodes
- `jobs` — Job lifecycle, status tracking
- `raw_company_records` — 53,684 scraped companies (48,705 unique)
- `enriched_leads` — 760 enriched contacts (from cookie before expiry)
- `email_cache` — Cached verification results

### Key Queries
```sql
-- Check enrich progress
SELECT job_id, COUNT(*) FROM enriched_leads GROUP BY job_id;
-- Check raw records
SELECT COUNT(DISTINCT company_name) FROM raw_company_records;
-- Queue sizes via Docker
docker exec leadgen_redis redis-cli LLEN enrich
```

---

## MCP Integration

Server: `lead_generation_app/backend/mcp_server.py` (8 tools)
Transport: `mcp_http_server.py` (SSE at `/sse`, POST at `/messages`)
Auth: API key in `x-api-key` header

### Available Tools
1. `get_system_metrics` — Dashboard + MV credits
2. `launch_lead_generation_job` — New pipeline
3. `check_job_status` — By job ID
4. `get_job_details` — Full records + leads
5. `pause_lead_job` / `resume_lead_job` / `cancel_lead_job`
6. `search_universal_database` — Recent enriched leads

---

## Job History

| Job ID | Client | Raw | Enriched | Status |
|--------|--------|-----|----------|--------|
| 1-6 | AstraCleaningServices | Yes | ~1,300 | Complete (no cookie) |
| 7 | AstraCleaningServices | Yes | 3 (stale) | Scraped, X-Ray only |
| 8 | AstraCleaningServices | 10,069 | ~500 | Cancelled |
| 9 | AdvancedCleaning WI | 0 | 0 | Cancelled |
| 10 | BHSSolutionsLLC TN | - | - | Cancelled |
| 11 | AppellStripingNorthJersey NJ | - | - | Cancelled |
| 12-14 | Various | - | - | Cancelled (old cookie format) |
| 15 | AdvancedCleaning WI | Scraping | 0 | Active |
| 16 | BHSSolutionsLLC TN | Scraping | 0 | Active |
| 17 | AppellStripingNorthJersey NJ | Scraping | 0 | Active |

---

## Configuration

### Key Settings
- `skip_email_verify: true` on all jobs (no MV credits)
- `enrichment_method: "LinkedIn cookie"` (not X-Ray)
- Batch pipeline via `/api/v1/jobs/pipeline`

### Environment Variables (.env)
Stored on EC2 at `/home/ec2-user/leadengine/.env` (gitignored).
Key vars: `DATABASE_URL`, `CELERY_BROKER_URL`, `ADMIN_PASSWORD`, `JWT_SECRET_KEY`,
`LINKEDIN_LI_AT_COOKIE`, `MILLION_VERIFIER_API_KEY`, `AWS_PROXY_URL`, `AWS_PROXY_API_KEY`

---

## GitHub
- **Repo**: `https://github.com/malayyy/leadengine`
- **Branch**: `main`
- **Excluded**: `.env`, `logs/`, `__pycache__/`, `*.db`, `celerybeat-schedule`, `node_modules/`

---

## Email Status (Travis @ Prospectr)
- Sent `raw_company_records.csv` (53,684 records)
- Waiting on AWS compute access to resume Phase 2
- Draft saved at `email_to_travis.md`

---

## Deployment Scripts
- `deploy_aws_proxy.sh` — Creates Lambda + API Gateway for IP rotation
- `requeue_top5.py` — Re-queues enrichment for top 5 campaigns
- `requeue_enrichment.py` — Re-queues all pending records
- `submit_all_jobs.py` — Batch job submission
- `prepare_ab_test.py` — ICP spreadsheet → payloads
