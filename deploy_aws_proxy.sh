#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# deploy_aws_proxy.sh
#
# Deploys an API Gateway + Lambda proxy for dynamic IP rotation via AWS CLI.
# Outputs AWS_PROXY_URL and AWS_PROXY_API_KEY at the end.
#
# Usage:  ./deploy_aws_proxy.sh
###############################################################################

# ── 1. Collect inputs ──────────────────────────────────────────────────────
read -rp "AWS Account ID (12 digits): " AWS_ACCOUNT_ID
[[ "$AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]] || {
  echo "ERROR: Account ID must be exactly 12 digits."
  exit 1
}

read -rp "AWS Region (default: us-east-1): " AWS_REGION
AWS_REGION="${AWS_REGION:-us-east-1}"

# Verify AWS CLI works
aws sts get-caller-identity &>/dev/null || {
  echo "ERROR: AWS CLI not configured. Run 'aws configure' first."
  exit 1
}

echo ""
echo "  Account: $AWS_ACCOUNT_ID"
echo "  Region:  $AWS_REGION"
echo ""

# ── 2. Build deployment zip (Lambda code + httpx) ─────────────────────────
LAMBDA_FN="leadengine-proxy"
ROLE_NAME="leadengine-proxy-role"
TMPDIR=$(mktemp -d)
ZIPFILE="/tmp/proxy-lambda-$$.zip"
trap 'rm -rf "$TMPDIR" "$ZIPFILE"' EXIT

cat > "$TMPDIR/lambda_function.py" << 'PYEOF'
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
PYEOF

echo "==> Installing httpx into deployment package..."
pip install httpx -q -t "$TMPDIR" --no-input 2>/dev/null

echo "==> Creating deployment zip..."
cd "$TMPDIR" && zip -r "$ZIPFILE" . > /dev/null
cd /tmp

# ── 3. IAM execution role ─────────────────────────────────────────────────
IAM_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
  echo "==> IAM role '$ROLE_NAME' already exists, reusing."
else
  echo "==> Creating IAM role '$ROLE_NAME'..."
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }' > /dev/null

  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" > /dev/null

  echo "==> Waiting 10s for IAM propagation..."
  sleep 10
fi

# ── 4. Lambda function ────────────────────────────────────────────────────
if aws lambda get-function --function-name "$LAMBDA_FN" &>/dev/null; then
  echo "==> Lambda '$LAMBDA_FN' exists, updating code..."
  aws lambda update-function-code \
    --function-name "$LAMBDA_FN" \
    --zip-file "fileb://$ZIPFILE" > /dev/null
else
  echo "==> Creating Lambda function '$LAMBDA_FN'..."
  aws lambda create-function \
    --function-name "$LAMBDA_FN" \
    --runtime python3.12 \
    --handler lambda_function.lambda_handler \
    --role "$IAM_ROLE_ARN" \
    --zip-file "fileb://$ZIPFILE" \
    --timeout 30 \
    --memory-size 512 \
    --region "$AWS_REGION" > /dev/null
fi

FUNCTION_ARN=$(aws lambda get-function --function-name "$LAMBDA_FN" --query Configuration.FunctionArn --output text)
echo "       Lambda ARN: $FUNCTION_ARN"

# ── 5. API Gateway ────────────────────────────────────────────────────────
API_NAME="LeadEngineProxy"

EXISTING_API_ID=$(aws apigateway get-rest-apis --query "items[?name=='$API_NAME'].id" --output text --region "$AWS_REGION")
if [[ -n "$EXISTING_API_ID" ]]; then
  API_ID="$EXISTING_API_ID"
  echo "==> API '$API_NAME' ($API_ID) exists, reusing."
else
  echo "==> Creating REST API '$API_NAME'..."
  API_ID=$(aws apigateway create-rest-api \
    --name "$API_NAME" \
    --region "$AWS_REGION" \
    --query id --output text)
  echo "       API ID: $API_ID"
fi

ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id "$API_ID" \
  --region "$AWS_REGION" \
  --query 'items[0].id' --output text)

# Check if /proxy resource exists
PROXY_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id "$API_ID" \
  --region "$AWS_REGION" \
  --query "items[?pathPart=='proxy'].id" --output text)

if [[ -z "$PROXY_RESOURCE_ID" || "$PROXY_RESOURCE_ID" == "None" ]]; then
  echo "==> Creating /proxy resource..."
  PROXY_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id "$API_ID" \
    --parent-id "$ROOT_ID" \
    --path-part proxy \
    --region "$AWS_REGION" \
    --query id --output text)
fi
echo "       /proxy resource ID: $PROXY_RESOURCE_ID"

# ANY method with Lambda proxy integration
METHOD_EXISTS=$(aws apigateway get-method \
  --rest-api-id "$API_ID" \
  --resource-id "$PROXY_RESOURCE_ID" \
  --http-method ANY \
  --region "$AWS_REGION" \
  --query httpMethod --output text 2>/dev/null || echo "")

if [[ -z "$METHOD_EXISTS" ]]; then
  echo "==> Creating ANY method with Lambda proxy integration..."
  aws apigateway put-method \
    --rest-api-id "$API_ID" \
    --resource-id "$PROXY_RESOURCE_ID" \
    --http-method ANY \
    --authorization-type NONE \
    --api-key-required \
    --region "$AWS_REGION" > /dev/null

  aws apigateway put-integration \
    --rest-api-id "$API_ID" \
    --resource-id "$PROXY_RESOURCE_ID" \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${FUNCTION_ARN}/invocations" \
    --region "$AWS_REGION" > /dev/null

  aws apigateway put-method-response \
    --rest-api-id "$API_ID" \
    --resource-id "$PROXY_RESOURCE_ID" \
    --http-method ANY \
    --status-code 200 \
    --region "$AWS_REGION" > /dev/null

  aws apigateway put-integration-response \
    --rest-api-id "$API_ID" \
    --resource-id "$PROXY_RESOURCE_ID" \
    --http-method ANY \
    --status-code 200 \
    --region "$AWS_REGION" > /dev/null
fi

# ── 6. Lambda permission for API Gateway ──────────────────────────────────
SRC_ARN="arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*/*/proxy"
if ! aws lambda get-policy --function-name "$LAMBDA_FN" --query "Policy" --output text 2>/dev/null | grep -q "$API_ID"; then
  echo "==> Adding Lambda invoke permission for API Gateway..."
  aws lambda add-permission \
    --function-name "$LAMBDA_FN" \
    --source-arn "$SRC_ARN" \
    --principal apigateway.amazonaws.com \
    --statement-id "api-gateway-${API_ID}" \
    --action lambda:InvokeFunction \
    --region "$AWS_REGION" > /dev/null
fi

# ── 7. Deploy to prod ─────────────────────────────────────────────────────
echo "==> Deploying API to 'prod' stage..."
DEPLOY_ID=$(aws apigateway create-deployment \
  --rest-api-id "$API_ID" \
  --stage-name prod \
  --region "$AWS_REGION" \
  --query id --output text)

# ── 8. API Key + Usage Plan ──────────────────────────────────────────────
API_KEY_NAME="leadengine-proxy-key"

EXISTING_KEY_ID=$(aws apigateway get-api-keys \
  --name-query "$API_KEY_NAME" \
  --include-values \
  --region "$AWS_REGION" \
  --query 'items[0].id' --output text)

if [[ -n "$EXISTING_KEY_ID" && "$EXISTING_KEY_ID" != "None" ]]; then
  API_KEY_ID="$EXISTING_KEY_ID"
  API_KEY_VALUE=$(aws apigateway get-api-key \
    --api-key "$API_KEY_ID" \
    --include-value \
    --region "$AWS_REGION" \
    --query value --output text)
  echo "==> API key '$API_KEY_NAME' ($API_KEY_ID) exists, reusing."
else
  echo "==> Creating API key '$API_KEY_NAME'..."
  API_KEY_ID=$(aws apigateway create-api-key \
    --name "$API_KEY_NAME" \
    --enabled \
    --region "$AWS_REGION" \
    --query id --output text)
  API_KEY_VALUE=$(aws apigateway get-api-key \
    --api-key "$API_KEY_ID" \
    --include-value \
    --region "$AWS_REGION" \
    --query value --output text)
fi

# Usage Plan
PLAN_NAME="leadengine-proxy-plan"
EXISTING_PLAN_ID=$(aws apigateway get-usage-plans \
  --query "items[?name=='$PLAN_NAME'].id" --output text --region "$AWS_REGION")

if [[ -n "$EXISTING_PLAN_ID" && "$EXISTING_PLAN_ID" != "None" ]]; then
  PLAN_ID="$EXISTING_PLAN_ID"
  echo "==> Usage plan '$PLAN_NAME' ($PLAN_ID) exists, reusing."
else
  echo "==> Creating usage plan '$PLAN_NAME'..."
  PLAN_ID=$(aws apigateway create-usage-plan \
    --name "$PLAN_NAME" \
    --api-stages "[{\"apiId\": \"$API_ID\", \"stage\": \"prod\"}]" \
    --throttle burstLimit=20,rateLimit=10 \
    --region "$AWS_REGION" \
    --query id --output text)
fi

# Associate key with plan (idempotent)
EXISTING_PLAN_KEY=$(aws apigateway get-usage-plan-keys \
  --usage-plan-id "$PLAN_ID" \
  --region "$AWS_REGION" \
  --query "items[?id=='$API_KEY_ID'].id" --output text 2>/dev/null || echo "")

if [[ -z "$EXISTING_PLAN_KEY" || "$EXISTING_PLAN_KEY" == "None" ]]; then
  echo "==> Associating API key with usage plan..."
  aws apigateway create-usage-plan-key \
    --usage-plan-id "$PLAN_ID" \
    --key-type API_KEY \
    --key-id "$API_KEY_ID" \
    --region "$AWS_REGION" > /dev/null
fi

# ── 9. Output ─────────────────────────────────────────────────────────────
echo ""
echo "======================================================================"
echo "  DEPLOYMENT COMPLETE"
echo "======================================================================"
echo ""
echo "  AWS_PROXY_URL=https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/proxy"
echo "  AWS_PROXY_API_KEY=${API_KEY_VALUE}"
echo ""
echo "  Add these to your EC2 .env file, then restart workers:"
echo ""
echo "    echo \"AWS_PROXY_URL=https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/proxy\" >> /home/ec2-user/leadengine/.env"
echo "    echo \"AWS_PROXY_API_KEY=${API_KEY_VALUE}\" >> /home/ec2-user/leadengine/.env"
echo "    docker compose -f docker-compose.enterprise.yml restart celery_worker_enrich celery_worker_scrape celery_worker_email"
echo ""
echo "======================================================================"
