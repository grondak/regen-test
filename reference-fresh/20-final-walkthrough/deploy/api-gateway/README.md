# TinyWMS API Gateway deployment notes

From the repository root:

## Deploy
```bash
aws cloudformation deploy \
  --stack-name tinywms-api-gateway \
  --template-file infra/api-gateway.yaml \
  --parameter-overrides LambdaFunctionName=tinywms-inventory-lesson
```

## Resolve outputs
```bash
API_BASE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-api-gateway \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue | [0]' \
  --output text)"

API_ID="$(aws cloudformation describe-stacks \
  --stack-name tinywms-api-gateway \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiId`].OutputValue | [0]' \
  --output text)"

echo "$API_BASE_URL"
echo "$API_ID"
```

## Verify contracts
```bash
API_BASE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-api-gateway \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue | [0]' \
  --output text)"

curl -i "$API_BASE_URL/inventory"
```

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-api-gateway
```
