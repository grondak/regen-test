# TinyWMS SQS deployment notes

From the stage root:

## Deploy
```bash
aws cloudformation deploy \
  --stack-name tinywms-sqs \
  --template-file infra/sqs.yaml
```

## Resolve outputs
```bash
QUEUE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-sqs \
  --query 'Stacks[0].Outputs[?OutputKey==`QueueUrl`].OutputValue | [0]' \
  --output text)"

QUEUE_ARN="$(aws cloudformation describe-stacks \
  --stack-name tinywms-sqs \
  --query 'Stacks[0].Outputs[?OutputKey==`QueueArn`].OutputValue | [0]' \
  --output text)"

echo "$QUEUE_URL"
echo "$QUEUE_ARN"
```

## Verify contracts
```bash
QUEUE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-sqs \
  --query 'Stacks[0].Outputs[?OutputKey==`QueueUrl`].OutputValue | [0]' \
  --output text)"

python3 - <<'PY'
from src.sqs_consumer import consume_messages
print('queue ready; no local polling loop yet')
PY
```

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-sqs
```
