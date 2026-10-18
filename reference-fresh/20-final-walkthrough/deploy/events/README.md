# TinyWMS event deployment notes

From the stage root:

## Deploy
```bash
aws cloudformation deploy \
  --stack-name tinywms-events \
  --template-file infra/events.yaml \
  --parameter-overrides EventBusName=tinywms-order-events
```

## Resolve outputs
```bash
EVENT_BUS_NAME="$(aws cloudformation describe-stacks \
  --stack-name tinywms-events \
  --query 'Stacks[0].Outputs[?OutputKey==`EventBusName`].OutputValue | [0]' \
  --output text)"

EVENT_CONSUMER_A_QUEUE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-events \
  --query 'Stacks[0].Outputs[?OutputKey==`EventConsumerAQueueUrl`].OutputValue | [0]' \
  --output text)"

EVENT_CONSUMER_B_QUEUE_URL="$(aws cloudformation describe-stacks \
  --stack-name tinywms-events \
  --query 'Stacks[0].Outputs[?OutputKey==`EventConsumerBQueueUrl`].OutputValue | [0]' \
  --output text)"

echo "$EVENT_BUS_NAME"
echo "$EVENT_CONSUMER_A_QUEUE_URL"
echo "$EVENT_CONSUMER_B_QUEUE_URL"
```

## Verify contracts
```bash
python3 src/event_consumer_a.py "$EVENT_CONSUMER_A_QUEUE_URL"
python3 src/event_consumer_b.py "$EVENT_CONSUMER_B_QUEUE_URL"
```

The consumers are independent so students can inspect each queue with the AWS CLI or their own small Python wrapper.

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-events
```
