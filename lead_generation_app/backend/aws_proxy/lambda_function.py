import json
import httpx
from functools import reduce

RESPONSE_HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
ALLOWED_HEADERS = {"content-type", "cache-control", "pragma", "expires", "location", "set-cookie"}


def error_response(code, message):
    return {"statusCode": code, "body": json.dumps({"error": message}), "headers": RESPONSE_HEADERS}


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except (TypeError, json.JSONDecodeError):
        return error_response(400, "Invalid JSON body")

    url = body.get("url")
    if not url:
        return error_response(400, "url is required")

    method = body.get("method", "GET").upper()
    headers = body.get("headers", {})
    data = body.get("data")
    timeout = body.get("timeout", 30)

    try:
        resp = httpx.request(method, url, headers=headers, content=data, timeout=timeout, follow_redirects=True)
        safe_headers = dict(filter(
            lambda item: item[0].lower() in ALLOWED_HEADERS,
            resp.headers.items()
        ))
        return {
            "statusCode": resp.status_code,
            "headers": safe_headers,
            "body": resp.text,
            "isBase64Encoded": False,
        }
    except httpx.TimeoutException:
        return error_response(504, "Target timed out")
    except Exception as e:
        return error_response(502, f"Request failed: {str(e)}")
