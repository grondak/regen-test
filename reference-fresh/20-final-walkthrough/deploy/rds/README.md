# TinyWMS RDS deployment notes

From the stage root:

## Deploy
```bash
aws cloudformation deploy \
  --stack-name tinywms-rds \
  --template-file infra/rds.yaml \
  --parameter-overrides \
    DatabaseName='tinywms' \
    DatabaseUsername='tinywms' \
    DatabasePassword='REPLACE_WITH_A_REAL_PASSWORD' \
    VpcSecurityGroupIds='sg-REPLACE_ME' \
    DbSubnetIds='subnet-REPLACE_ME_A,subnet-REPLACE_ME_B'
```

## Resolve outputs
```bash
DB_ENDPOINT_ADDRESS="$(aws cloudformation describe-stacks \
  --stack-name tinywms-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`DbEndpointAddress`].OutputValue | [0]' \
  --output text)"

DB_ENDPOINT_PORT="$(aws cloudformation describe-stacks \
  --stack-name tinywms-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`DbEndpointPort`].OutputValue | [0]' \
  --output text)"

echo "$DB_ENDPOINT_ADDRESS"
echo "$DB_ENDPOINT_PORT"
```

## Verify
```bash
DB_ENDPOINT_ADDRESS="$(aws cloudformation describe-stacks \
  --stack-name tinywms-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`DbEndpointAddress`].OutputValue | [0]' \
  --output text)"

DB_ENDPOINT_PORT="$(aws cloudformation describe-stacks \
  --stack-name tinywms-rds \
  --query 'Stacks[0].Outputs[?OutputKey==`DbEndpointPort`].OutputValue | [0]' \
  --output text)"

psql "host=${DB_ENDPOINT_ADDRESS} port=${DB_ENDPOINT_PORT} dbname=tinywms user=tinywms sslmode=require" -c '\dt'
```

## Destroy
```bash
aws cloudformation delete-stack --stack-name tinywms-rds
```
