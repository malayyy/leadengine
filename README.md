# Lead Engine v4

Enterprise lead generation pipeline — scrapes, enriches, and verifies B2B contacts at scale.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Lead Engine Pipeline                         │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 1          Phase 2           Phase 3          Phase 4        │
│  Google Maps ──►  LinkedIn ──►  Email Gen ──►  MillionVerifier      │
│  Scraper          Profile          (7 patterns)    Verification      │
│                   Discovery                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Pipeline Phases

| Phase | Component | Description |
|-------|-----------|-------------|
| 1 | `google_maps.py` | Scrapes business listings by industry + zipcode (Playwright automation) |
| 2 | `linkedin.py` | Finds LinkedIn profiles for target titles at each company |
| 3 | `tasks.py` (phase 3) | Generates 7 email patterns + website scraping fallback |
| 4 | `millionverifier.py` | Verifies all emails, keeps only valid ones |

### LinkedIn Discovery (Phase 2) — Two Modes

1. **Cookie Mode** (`li_at`) — Playwright with LinkedIn session cookie. Direct profile search + experience validation. ~200-400 searches per cookie before rate-limiting.

2. **X-Ray Mode** (no cookie) — DuckDuckGo / Bing search via AWS Lambda proxy. Each request egresses from a fresh IP via API Gateway → Lambda invocation. Fallback to direct HTTP if proxy fails.

### Email Generation

Per decision-maker, generates 7 patterns:
- `fname.lname@domain`
- `finitial.lname@domain`
- `fname@domain`
- `lname@domain`
- `finitialname@domain`
- `fname-lname@domain`
- `fname_lname@domain`

Verified via MillionVerifier, cached in `email_cache`.

## Infrastructure

```
EC2 t3.medium (34.198.122.194)
├── 13 Docker containers
│   ├── postgres:16         ── Database
│   ├── redis:7             ── Queue + cache
│   ├── api                 ── FastAPI (4 uvicorn workers)
│   ├── celery_worker_scrape ── Phase 1 (concurrency 2)
│   ├── celery_worker_enrich ── Phase 2 (concurrency 2)
│   ├── celery_worker_email  ── Phase 3-4 (concurrency 10)
│   ├── celery_beat         ── Scheduler
│   ├── flower              ── Worker monitoring
│   ├── traefik             ── Reverse proxy + TLS
│   ├── prometheus          ── Metrics
│   ├── grafana             ── Dashboards
│   ├── searxng             ── Search (deprecated)
│   └── frontend            ── React dashboard
└── 4GB swap
```

### AWS Lambda Proxy (IP Rotation)

```
Scraper ──POST──► API Gateway ──► Lambda (new IP each invocation)
  { url, method, headers }           │
                                     └──► httpx.request(target)
                                          │
                                     HTML response ◄──┘
```

- **No VPC** — uses AWS shared IP pool (no NAT Gateway cost)
- ~$3-5 per 500K requests (free tier covers first 1M)
- Deployed via `deploy_aws_proxy.sh`

## Queues

| Queue | Consumer | Concurrency | Max tasks/child |
|-------|----------|-------------|-----------------|
| `scrape` | worker_1 | 2 | 5 |
| `enrich` | worker_2 | 2 | 5 |
| `email` | worker_3 | 10 | 50 |

## API Endpoints

### Core
- `POST /api/v1/jobs/pipeline` — Create campaign + dispatch Phase 1
- `POST /api/v1/jobs/batch` — Batch pipeline creation
- `GET /api/v1/jobs` — List all jobs
- `GET /api/v1/jobs/{id}` — Job status
- `GET /api/v1/jobs/{id}/stream` — SSE event stream
- `GET /api/v1/jobs/{id}/export` — CSV export
- `POST /api/v1/jobs/{id}/pause|resume|cancel` — Lifecycle

### Data
- `GET /api/v1/leads` — All enriched leads
- `GET /api/v1/companies` — All companies
- `GET /api/v1/dashboard/metrics` — Aggregated stats

### System
- `GET /health` — Health check
- `GET /api/v1/system/info` — Version, broker, queue depths
- `GET /sse` — MCP SSE endpoint

### MCP (Model Context Protocol)
8 tools for AI-agent orchestration:
- `get_system_metrics`, `launch_lead_generation_job`, `check_job_status`
- `get_job_details`, `pause_lead_job`, `resume_lead_job`
- `cancel_lead_job`, `search_universal_database`

## Setup

### Prerequisites
- Python 3.12+
- Docker (for EC2 deployment)
- AWS CLI (for Lambda proxy)

### Local Dev
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r lead_generation_app/backend/requirements.txt
playwright install chromium
python lead_generation_app/backend/app.py
```

### EC2 Deploy
```bash
docker compose -f docker-compose.enterprise.yml up -d --build --force-recreate
```

### Lambda Proxy Deploy
```bash
./deploy_aws_proxy.sh
# Prompts for AWS Account ID + Region
# Outputs AWS_PROXY_URL and AWS_PROXY_API_KEY
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `CELERY_BROKER_URL` | Yes | Redis URL |
| `ADMIN_PASSWORD` | Yes | API auth password |
| `JWT_SECRET_KEY` | Yes | Token signing key |
| `LINKEDIN_LI_AT_COOKIE` | No | LinkedIn session cookie |
| `MILLION_VERIFIER_API_KEY` | No | Email verification credits |
| `AWS_PROXY_URL` | No | Lambda proxy URL |
| `AWS_PROXY_API_KEY` | No | Lambda proxy API key |
| `MCP_API_KEY` | No | MCP server auth |

## Database Schema

5 tables: `campaigns`, `jobs`, `raw_company_records`, `enriched_leads`, `email_cache`

## License

Proprietary — Prospectr Marketing
