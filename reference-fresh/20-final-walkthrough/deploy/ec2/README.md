# TinyWMS EC2 deployment notes

From the stage root:

## Connect
```bash
ssh ec2-user@YOUR_EC2_PUBLIC_IP
```

## Configure
```bash
cp deploy/ec2/environment.example deploy/ec2/environment
set -a
. deploy/ec2/environment
set +a
```

## Run
```bash
bash deploy/ec2/run_inventory_server.sh
```

## Verify
```bash
curl -i "http://127.0.0.1:${TINYWMS_PORT:-8000}/inventory"
```

## Stop and clean up
```bash
pkill -f src/http_server.py
rm -f deploy/ec2/environment
```
