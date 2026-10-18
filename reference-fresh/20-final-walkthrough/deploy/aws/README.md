# TinyWMS AWS deployment notes

This lesson deploys the real `src/lambda_inventory.py` Lambda package, not an inline stub.

From the repository root:

## 1) Install the Lambda dependency
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt -t deploy/aws/build/lambda
```

## 2) Package and upload the Lambda code
You can use the helper script below, or do the same steps manually.

### Option A: helper script
```bash
chmod +x deploy/aws/package_lambda.sh
./deploy/aws/package_lambda.sh tinywms-lambda-bucket tinywms-cloud-inventory
```

### Option B: manual zip + upload
```bash
rm -rf deploy/aws/build
mkdir -p deploy/aws/build/lambda
python3 -m pip install -r requirements.txt -t deploy/aws/build/lambda
cp src/lambda_inventory.py deploy/aws/build/lambda/
cp src/db_adapter.py deploy/aws/build/lambda/
(cd deploy/aws/build/lambda && zip -r ../lambda_inventory.zip .)
aws s3 cp deploy/aws/build/lambda_inventory.zip s3://tinywms-lambda-bucket/tinywms-cloud-inventory/lambda_inventory.zip
```

## Deploy
Use the packaged artifact path with CloudFormation:
```bash
aws cloudformation deploy \
  --stack-name tinywms-cloud \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    DatabasePassword="$TINYWMS_DB_PASSWORD" \
    VpcSecurityGroupIds=sg-REPLACE_ME \
    DbSubnetIds=subnet-REPLACE_ME_A,subnet-REPLACE_ME_B \
    LambdaCodeS3Bucket=tinywms-lambda-bucket \
    LambdaCodeS3Key=tinywms-cloud-inventory/lambda_inventory.zip
```

If you prefer SAM-style packaging, the equivalent flow is the same idea: upload the zip first, then deploy the template with the S3 bucket/key parameters.

Cost note: this stack creates one `db.t3.micro` RDS PostgreSQL instance (billed hourly until the stack is deleted)
plus three SQS queues, an EventBridge bus with two rules, a Lambda and an API Gateway. Export the password first
(`export TINYWMS_DB_PASSWORD=...`); it is never stored in the repository. The stack deletes the database with
`aws cloudformation delete-stack --stack-name tinywms-cloud`.

## Resolve outputs
```bash
API_BASE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-cloud \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue | [0]' \
  --output text)"
FUNCTION_NAME="$(aws cloudformation describe-stacks \
  --stack-name tinywms-cloud \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue | [0]' \
  --output text)"
QUEUE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-cloud \
  --query 'Stacks[0].Outputs[?OutputKey==`QueueUrl`].OutputValue | [0]' \
  --output text)"
```

## Verify contracts
```bash
curl -i "$API_BASE_URL/inventory"

curl -i -X POST "$API_BASE_URL/orders" \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORD-1001","lines":[{"sku":"SKU-001","quantity":1}]}'
```

The POST request should return a successful order response once the deployed Lambda can reach its database and downstream services.

## 6) Verify the worker path
```bash
python3 src/pick_ticket_worker.py data/pick-work.json pick-tickets.txt
```

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-cloud
```
