# Session 11 — Functions as a service: Lambda

**Stage:** `06-lambda` · **Repo support:** Yes (handler runs locally; deploying it is AWS-side) · **Run from:** `06-lambda/`

**Concept (20 min):** function invocation, handler, event, return value, execution environment, ephemeral compute, the serverless responsibility boundary.
**Demo (20 min):** Lambda returns the same inventory JSON students previously served from the Pi and EC2.

## Run sheet

**Step 1: call the handler like Lambda does, locally.** A Lambda is just a function that takes an `event` and returns a dict.
```bash
PYTHONPATH=. python3 -c "import json; from src.lambda_inventory import handler; print(json.dumps(handler({'queryStringParameters': {'demo': 'local-json'}}, None), indent=2))"
```
Output: `statusCode: 200`, `headers`, and a `body` that is the inventory as a JSON **string**. Compare with the body `curl` showed in session 6; it is the same data in an envelope.

**Step 2: read the handler** (`src/lambda_inventory.py`, short): event in, dict out, no server loop, no port, no listening.

**Step 3: deploy and invoke for real (needs an AWS account; not run for this plan).** Stage 6 ships `infra/lambda.yaml` and `deploy/lambda/README.md`. Its deploy command:
```bash
aws cloudformation deploy --stack-name tinywms-lambda --template-file infra/lambda.yaml \
  --capabilities CAPABILITY_IAM --parameter-overrides DatabaseEndpoint=... DatabasePassword=...
aws lambda invoke --function-name "$FUNCTION_NAME" --payload '{}' /tmp/out.json && cat /tmp/out.json
aws cloudformation delete-stack --stack-name tinywms-lambda
```
**Check this before class.** Reading the template, I expect the live demo to fail as written:
- The function's code is a short inline script that opens `data/inventory.json`, but only the script is uploaded, so that file does not exist inside Lambda. Expect a `FileNotFoundError`, not the inventory.
- The deploy command asks for database parameters (endpoint, password) that stage 6 does not use.
- The function name defaults to `tinywms-lambda-inventory`, but the API Gateway notes in session 12 expect `tinywms-inventory-lesson`.

The reliable path is the one in stage 20: `20-final-walkthrough/deploy/aws/README.md` packages the real `src/lambda_inventory.py` and deploys it. Use it, or make the inline function return a literal list so the stage-6 demo works on its own.

## Talking points
- "Serverless" still has servers; the responsibility boundary moved. AWS patches the OS, scales, restarts. You supply a function and its permissions.
- Ephemeral: each invocation may land on a fresh environment. Nothing you write to local disk is durable. That is why state moves to a database in sessions 13–16.
- No port, no process you start. Compare the Pi/EC2 server (a process you run) with Lambda (code AWS runs when called).
- The role: the function needs an IAM role (session 10) to be allowed to do anything.

## Caveats
- At stage 6 the handler returns the inventory file packaged with the code (`demo=local-json`). Later stages replace that with a database query.
