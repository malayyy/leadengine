import asyncio
import os
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("lead-engine")

PUBLIC_DOMAIN = os.environ.get("PUBLIC_API_DOMAIN", "")
if PUBLIC_DOMAIN:
    API_BASE = f"https://{PUBLIC_DOMAIN}/api/v1"
else:
    API_BASE = "http://localhost:8000/api/v1"

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_system_metrics",
            description="Fetches current Lead Engine metrics, including total jobs, extracted companies, enriched leads, verified emails, and live MillionVerifier API credits.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="launch_lead_generation_job",
            description="Launches a highly concurrent data extraction and enrichment pipeline using Google Maps, LinkedIn, and MillionVerifier.",
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_name": {
                        "type": "string",
                        "description": "A descriptive name for the campaign."
                    },
                    "industry": {
                        "type": "string",
                        "description": "Target industry for the campaign"
                    },
                    "titles": {
                        "type": "string",
                        "description": "Comma separated target titles (e.g., 'CEO, Founder, Owner')."
                    },
                    "state": {
                        "type": "string",
                        "description": "2-letter US State abbreviation (e.g., 'CA', 'TX')."
                    },
                    "zipcodes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific zipcodes to scrape. If empty, the engine will attempt to find default ones, but providing them is recommended."
                    },
                    "total_contacts": {
                        "type": "integer",
                        "description": "Overall target limit for total contacts to generate across this entire campaign."
                    },
                    "contacts_per_company": {
                        "type": "integer",
                        "description": "Maximum number of contacts to extract per company found."
                    }
                },
                "required": ["campaign_name", "industry", "titles", "state", "zipcodes"]
            }
        ),
        Tool(
            name="check_job_status",
            description="Checks the current status of a specific job by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "integer",
                        "description": "The ID of the job to check."
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="get_job_details",
            description="Retrieves the full unified table of raw records and enriched leads for a specific job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "integer",
                        "description": "The ID of the job."
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="pause_lead_job",
            description="Pauses an active lead generation job. The background workers will enter sleep mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "integer",
                        "description": "The ID of the job to pause."
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="resume_lead_job",
            description="Resumes a paused lead generation job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "integer",
                        "description": "The ID of the job to resume."
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="cancel_lead_job",
            description="Securely cancels an active or paused lead generation job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "integer",
                        "description": "The ID of the job to cancel."
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="search_universal_database",
            description="Retrieves a list of the most recent enriched leads from the universal database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of leads to return (max 100)."
                    }
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        if name == "get_system_metrics":
            try:
                metrics_resp = await client.get(f"{API_BASE}/dashboard/metrics")
                credits_resp = await client.get(f"{API_BASE}/dashboard/credits")
                
                metrics = metrics_resp.json()
                credits = credits_resp.json().get("credits", 0)
                
                return [TextContent(type="text", text=f"System Metrics:\n- Total Jobs: {metrics.get('total_jobs')}\n- Companies Extracted: {metrics.get('total_records')}\n- Enriched Leads: {metrics.get('total_enriched')}\n- Verified Emails: {metrics.get('total_valid_emails')}\n- Live MV Credits Available: {credits}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error fetching metrics: {str(e)}")]
                
        elif name == "launch_lead_generation_job":
            try:
                payload = {
                    "campaign_name": arguments["campaign_name"],
                    "industry": arguments["industry"],
                    "titles": list(filter(None, map(lambda t: t.strip(), arguments["titles"].split(",")))),
                    "zipcodes": arguments["zipcodes"],
                    "state": arguments["state"],
                    "total_contacts": arguments.get("total_contacts", 0),
                    "contacts_per_company": arguments.get("contacts_per_company", -1),
                    "proxy": arguments.get("proxy")
                }
                resp = await client.post(f"{API_BASE}/jobs/pipeline", json=payload)
                data = resp.json()
                return [TextContent(type="text", text=f"Job successfully launched! Job ID: {data.get('job_id')}\nMessage: {data.get('message')}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error launching job: {str(e)}")]
                
        elif name == "check_job_status":
            try:
                resp = await client.get(f"{API_BASE}/jobs/{arguments['job_id']}")
                if resp.status_code == 404:
                    return [TextContent(type="text", text="Job not found.")]
                data = resp.json()
                return [TextContent(type="text", text=f"Job #{data['job_id']} Status:\nState: {data['status']}\nCompanies Found: {data['raw_records_found']}\nCreated: {data['created_at']}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error checking job: {str(e)}")]

        elif name == "get_job_details":
            try:
                resp = await client.get(f"{API_BASE}/jobs/{arguments['job_id']}/details")
                if resp.status_code == 404:
                    return [TextContent(type="text", text="Job not found.")]
                data = resp.json()
                
                records_count = len(data.get("records", []))
                leads_count = len(data.get("leads", []))
                lines = [f"Job #{data['job_id']} ({data['status']}) - {records_count} Records, {leads_count} Leads found."]
                lines.extend(list(map(
                    lambda l: f"- {l['first_name']} {l['last_name']} ({l['title']}) at {l['company_name']}. Email: {l['email']} [{l['email_status']}]",
                    data.get("leads", []),
                )))
                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error getting job details: {str(e)}")]

        elif name == "pause_lead_job":
            try:
                resp = await client.post(f"{API_BASE}/jobs/{arguments['job_id']}/pause")
                return [TextContent(type="text", text=f"Job paused. Current status: {resp.json().get('status')}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == "resume_lead_job":
            try:
                resp = await client.post(f"{API_BASE}/jobs/{arguments['job_id']}/resume")
                return [TextContent(type="text", text=f"Job resumed. Current status: {resp.json().get('status')}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == "cancel_lead_job":
            try:
                resp = await client.post(f"{API_BASE}/jobs/{arguments['job_id']}/cancel")
                return [TextContent(type="text", text=f"Job cancelled. Current status: {resp.json().get('status')}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == "search_universal_database":
            try:
                limit = arguments.get("limit", 10)
                resp = await client.get(f"{API_BASE}/leads?limit={limit}")
                leads = resp.json()
                lines = list(map(
                    lambda lead: f"- {lead['first_name']} {lead['last_name']} ({lead['title']}) at {lead['company_name']}. Email: {lead['email'] or 'Not Found'} [{lead['email_status']}]",
                    leads,
                ))
                if not lines:
                    return [TextContent(type="text", text="No leads found in the database.")]
                return [TextContent(type="text", text="Recent Leads:\n" + "\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error fetching leads: {str(e)}")]
        
        else:
            raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
