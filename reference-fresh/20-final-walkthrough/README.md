# TinyWMS lesson: 19-git-history

## Stage purpose
This lesson turns the repository history into part of the teaching material. Students can compare milestones, check out earlier points in the semester, and see how TinyWMS grew from JSON files into a cloud-deployed order-processing system.

## Files in this lesson
- `README.md` - lesson guide for the git-history stage and milestone checkout exercises
- `docs/architecture.md` - updated assembly map plus a component-evolution timeline derived from the map
- `docs/data-contracts.md` - inherited contract guide for inventory, order, queue, event, and worker shapes
- `docs/end-to-end.md` - final walkthrough document carried forward for comparison with earlier milestones
- `deploy/aws/README.md` - consolidated AWS deployment guide kept available for cloud-related milestones
- `deploy/api-gateway/README.md` - API Gateway deployment guide kept available for earlier cloud milestones
- `deploy/lambda/README.md` - Lambda deployment guide kept available for earlier cloud milestones
- `deploy/rds/README.md` - RDS deployment guide kept available for earlier cloud milestones
- `deploy/sqs/README.md` - SQS deployment guide kept available for earlier cloud milestones
- `deploy/events/README.md` - EventBridge deployment guide kept available for earlier cloud milestones
- `deploy/ec2/README.md` - EC2 deployment guide kept available for the Linux hosting milestone
- `infra/template.yaml` - consolidated AWS stack used by the later cloud milestone history
- `infra/api-gateway.yaml` - earlier API Gateway stack kept for milestone comparisons
- `infra/lambda.yaml` - earlier Lambda stack kept for milestone comparisons
- `infra/rds.yaml` - earlier RDS stack kept for milestone comparisons
- `infra/sqs.yaml` - earlier SQS stack kept for milestone comparisons
- `infra/events.yaml` - earlier EventBridge stack kept for milestone comparisons
- `src/lambda_inventory.py` - order and inventory handler used by the later milestones
- `src/http_server.py` - local HTTP server used by earlier milestones
- `src/pick_ticket_worker.py` - durable pick-ticket worker used by later milestones
- `src/sqs_consumer.py` - shared SQS receive/delete helper reused by worker lessons
- `src/Dockerfile` - container runtime for the worker milestone
- `src/web/index.html` - browser inventory/order page used by the browser milestone
- `src/web/app.js` - browser client logic used by the browser milestone
- `src/web/style.css` - browser styling used by the browser milestone
- `data/inventory.json` - canonical inventory JSON contract shared by the course
- `data/inventory.schema.json` - inventory JSON schema used by the early lessons
- `data/orders.schema.json` - order JSON schema used by the order lessons
- `data/pick-work.json` - sample pick-work command contract
- `data/schema.sql` - relational schema artifact used by the database lessons
- `data/seed.sql` - seed script derived from the inventory JSON contract
- `tests/test_lambda_inventory.py` - order/inventory contract tests
- `tests/test_http_order_flow.py` - local HTTP order flow proof
- `tests/test_sqs_consumer.py` - queue consumer contract tests
- `tests/test_pick_ticket_worker.py` - durable worker tests
- `tests/test_callback_integration.py` - local end-to-end callback proof
- `tests/test_container_worker.py` - container runtime tests for the worker
- `tests/test_deployment_wiring.py` - deployment wiring checks for the consolidated AWS stack
- `tests/test_event_consumers.py` - independent EventBridge consumer tests
- `tests/test_concurrency.py` - order concurrency hardening tests
- `tests/test_browser_assets.py` - browser asset contract tests
- `tests/test_api_gateway_files.py` - API Gateway deployment file checks
- `tests/test_rds_files.py` - RDS deployment file checks
- `tests/test_ec2_deployment_files.py` - EC2 deployment file checks
- `tests/test_sql_export.py` - SQL export and relational schema checks
- `tests/test_linux_visible.py` - Linux-observability checks
- `tests/test_inventory_cli.py` - inventory CLI checks
- `tests/test_aws_deployment_files.py` - consolidated AWS deployment checks

## Run the lesson
From this folder:
```bash
python3 -m unittest discover -s tests -v
```

To inspect the milestone map and history notes:
```bash
sed -n '1,260p' docs/architecture.md
```

To compare this stage with an earlier milestone once you have tagged the repository:
```bash
git tag --list
git log --oneline --decorate --graph --all --max-count=40
```

To check out an earlier milestone that students are studying:
```bash
git checkout <milestone-tag>
```

## Run tests
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --test tests/test_web_app.js
```

## Student exercises
1. Submit a lightweight tag for one milestone, such as `stage-11-orders`, then inspect it with `git show --stat stage-11-orders` to see which files existed at that point in the semester.
2. Observe an earlier milestone tag, then optionally run the tests with `PYTHONPATH=src python3 -m unittest discover -s tests -v` and `node --test tests/test_web_app.js`, and compare the architecture and deployment guides with the current stage.
## Continuity note
- Inherited contract: the inventory JSON, order JSON, pick-work command, OrderPlaced event, and pick-ticket output contracts remain valid and unchanged.
- Boundary changed in this stage: Git history becomes a visible teaching boundary, so milestones and checkouts are now part of the lesson itself.

## Component assembly update
- Added: `README.md` history-map guidance and the component-evolution timeline in `docs/architecture.md` for the git-history lesson.
- Reused unchanged: `src/lambda_inventory.py`, `src/http_server.py`, `src/pick_ticket_worker.py`, `src/sqs_consumer.py`, `src/Dockerfile`, `src/web/index.html`, `src/web/app.js`, `src/web/style.css`, `docs/data-contracts.md`, `docs/end-to-end.md`, and the deployment guides under `deploy/`.
- Replaced/evolved: no application component is replaced; this stage reuses the current system and documents how earlier milestones can be viewed through tags and checkouts.

## Cleanup
If you create teaching tags for class, remove them when finished:
```bash
git tag -d stage-11-orders stage-13-sqs stage-18-aws-deployment
```
No external resources are created in this stage.
