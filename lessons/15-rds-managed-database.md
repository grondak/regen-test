# Session 15 — Managed services and RDS

**Stage:** `09-rds` · **Repo support:** Yes for reading and deploying; the AWS steps were not run for this plan · **Run from:** `09-rds/`

**Concept (20 min):** what AWS takes over in a managed service; endpoint, credentials, networking, backups, availability.
**Demo (20 min):** provision a prepared small RDS setup; connect with the same SQL client; load the same schema.

## Run sheet

**Step 1: compare self-managed with managed.** Put session 14's list of things *you* did (install, start, patch, back up, open the port, restart if it dies) beside what the RDS template asks for. Read `infra/rds.yaml` and `deploy/rds/README.md`: engine/version, instance class, storage, `DatabaseName`, username/password, security groups, subnet group. Note what you no longer do: OS patching, installing, backups scheduling, host failure handling.

**Step 2: provision** (commands from `deploy/rds/README.md`; replace the placeholders):
```bash
aws cloudformation deploy --stack-name tinywms-rds --template-file infra/rds.yaml \
  --parameter-overrides DatabaseName=tinywms DatabaseUsername=tinywms DatabasePassword=... \
  VpcSecurityGroupIds=sg-... DbSubnetIds=subnet-...,subnet-...
```
RDS takes several minutes; start it before the class begins, or provision it in the break and use the time for step 1.
Get the endpoint and port from the stack outputs (`DbEndpointAddress`, `DbEndpointPort`, see the README's "Resolve outputs").

**Step 3: connect with the same client and load the same schema.** From the EC2 instance (it must be able to reach the database: same VPC, and the database's security group must allow 5432 from it; this is session 8 again):
```bash
psql -h <endpoint> -U tinywms -d tinywms -f data/schema.sql
psql -h <endpoint> -U tinywms -d tinywms -f data/seed.sql
psql -h <endpoint> -U tinywms -d tinywms -c 'SELECT * FROM inventory'
```
Teaching beat: this is exactly the session-14 commands with a different host name.

**Step 4: tear down** (`aws cloudformation delete-stack --stack-name tinywms-rds`). RDS bills by the hour.

## Talking points
- A managed service is a shared responsibility. AWS: hardware, OS, patching, engine installation, backups, failover. You: schema, credentials, who may connect, queries, cost.
- The application sees an endpoint (host and port) and credentials; it cannot see or touch the server. You cannot SSH into it.
- Networking decides everything: if the database is reachable only inside the VPC, your laptop cannot connect; this is a feature.

## Caveats
- The database password is a deploy-time parameter and later ends up in a Lambda environment variable (see session 10).
- The stage guides assume a VPC, subnets and a security group already exist (`sg-REPLACE_ME`); the repo does not create them.
