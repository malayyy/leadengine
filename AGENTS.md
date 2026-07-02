# Lead Engine - Project Context

## Infrastructure
- **EC2**: t3.medium (2 vCPU, 4GB RAM, 4GB swap), Elastic IP `34.198.122.194`
- **13 Docker containers**: PostgreSQL, Redis, SearXNG, Traefik, API, 3 Celery workers, Beat, Flower, Prometheus, Grafana, Frontend
- **Domain**: `api.chopstickintegrations.com`
- **SSH Key**: `leadengine-ec2-key.pem`
- **App Dir on EC2**: `/home/ec2-user/leadengine/`
- **Docker Compose**: `docker-compose.enterprise.yml`
- **Commands**: `docker compose -f docker-compose.enterprise.yml up -d --build --force-recreate`

## LinkedIn Cookie
- **`LINKEDIN_LI_AT_COOKIE`** in `/home/ec2-user/leadengine/.env` on EC2
- Length: 152 chars
- Passed only to `api` service in docker-compose (workers get it as task arg)
- `--force-recreate` needed to pick up new .env values (not `docker compose restart`)
- Cookie expires periodically, needs refresh from browser devtools

## Cookie Format Fix (Critical)
- **File**: `lead_generation_app/backend/linkedin.py` lines 301 and 354
- **Bug**: Was sending `cookies = {"li_at": cookie}` (object) to Scrapling's `DynamicFetcher.fetch()`
- **Fix**: Changed to `cookies = [{"name": "li_at", "value": cookie, "domain": ".linkedin.com"}]` (array)
- Scrapling validates cookies as `array | null`, rejects objects

## Job History
| Job ID | Client | Scraped | Enriched | Status |
|--------|--------|---------|----------|--------|
| 1-6 | AstraCleaningServices | Yes | ~1300 | Complete (no LinkedIn cookie) |
| 7 | AstraCleaningServices | Yes | 3 (stale) | Scrape done, enrichment was X-Ray only |
| 8 | AstraCleaningServices | 10,069 | ~500 (no LinkedIn) | Cancelled |
| 9 | AdvancedCleaning WI | 0 | 0 | Cancelled |
| 10 | BHSSolutionsLLC TN | - | - | Cancelled |
| 11 | AppellStripingNorthJersey NJ | - | - | Cancelled |
| 12 | AdvancedCleaning WI | - | - | Cancelled (old cookie format) |
| 13 | BHSSolutionsLLC TN | - | - | Cancelled (old cookie format) |
| 14 | AppellStripingNorthJersey NJ | - | - | Cancelled (old cookie format) |
| 15 | **AdvancedCleaning WI** | Scraping | 0 | **Active** - first with cookie + fix |
| 16 | **BHSSolutionsLLC TN** | Scraping | 0 | **Active** - first with cookie + fix |
| 17 | **AppellStripingNorthJersey NJ** | Scraping | 0 | **Active** - first with cookie + fix |

## Key Settings
- `skip_email_verify: true` on all jobs (no MillionVerifier credits)
- `enrichment_method: "LinkedIn cookie"` (not X-Ray)
- Batch pipeline via `/api/v1/jobs/pipeline` endpoint
- 4 scrape worker forks, separate enrich queue

## SearXNG
- Broken - all engines blocked by CAPTCHAs
- No longer needed since LinkedIn cookie provides direct search

## GitHub
- **Repo**: `https://github.com/malayyy/leadengine`
- **Branch**: `main`
- **Commit**: `3e21170` - 173 files, source + ICP spreadsheets only
- **Excluded from git**: `.env`, `logs/`, `__pycache__/`, `*.db`, `celerybeat-schedule`

## Checking Status (for AI assistants)
1. `docker ps` on EC2 - are all 13 containers running?
2. `docker compose -f docker-compose.enterprise.yml logs --tail=50 api` - API health
3. Flower dashboard at `http://34.198.122.194:5555` - worker status
4. `curl http://localhost:8000/api/v1/jobs/{id}` - job status
5. `docker exec leadengine-db psql -U leadengine -c "SELECT job_id, COUNT(*) FROM leads WHERE enriched=true GROUP BY job_id;"` - enriched count
6. `redis-cli LLEN scrape` / `redis-cli LLEN enrich` - queue sizes
