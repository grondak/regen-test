# TinyWMS Lambda deployment notes

From the stage root:

## Deploy
```bash
aws cloudformation deploy \
  --stack-name tinywms-lambda \
  --template-file infra/lambda.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    DatabaseEndpoint='REPLACE_WITH_RDS_ENDPOINT' \
    DatabasePort='5432' \
    DatabaseName='tinywms' \
    DatabaseUser='tinywms' \
    DatabasePassword='REPLACE_WITH_A_REAL_PASSWORD'
```

## Resolve outputs
```bash
FUNCTION_NAME="$(aws cloudformation describe-stacks \
  --stack-name tinywms-lambda \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue | [0]' \
  --output text)"

FUNCTION_ARN="$(aws cloudformation describe-stacks \
  --stack-name tinywms-lambda \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionArn`].OutputValue | [0]' \
  --output text)"

echo "$FUNCTION_NAME"
echo "$FUNCTION_ARN"
```

## Verify
```bash
FUNCTION_NAME="$(aws cloudformation describe-stacks \
  --stack-name tinywms-lambda \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue | [0]' \
  --output text)"

aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' \
  /tmp/tinywms-lambda-response.json

cat /tmp/tinywms-lambda-response.json
```

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-lambda
```
