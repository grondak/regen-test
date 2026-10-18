# Stage 6: Add Lambda without removing the old path

Add an AWS Lambda implementation of `GET inventory` that initially returns the same inventory JSON without a database. Preserve the Pi/EC2 implementation. The purpose is to compare execution models, not replace history.

Lambda input/output should be explicit and readable. Add deployment support and architecture documentation. Do not add RDS yet.

Deployment commands must be runnable and must not rely on fabricated values. If an invoke or verify command needs a function name or ARN, derive it from deployment outputs or an explicit variable set by a prior command.

Required deployment artifacts for this stage:
- `infra/lambda.yaml` (or equivalent CloudFormation template) defining the Lambda function and its IAM role/policies.
- `deploy/lambda/README.md` containing exact deploy, invoke/verify, and destroy commands.
- deploy/invoke commands must resolve and reuse real output values (for example function name/ARN) rather than hardcoded placeholders.

Update `docs/architecture.md` "Component Assembly Map" to show Lambda as an additional compute component in parallel with Pi/EC2, not a replacement. Record shared contracts and any new deployment components.

Update the stage README as a lesson guide with purpose, file map, deploy/run/test commands, exercises,
cleanup notes, continuity note, and a "Component assembly update" section. Placeholder README text is not acceptable.
