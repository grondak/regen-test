# Stage 9: Move the database to RDS

Add an Amazon RDS deployment option for the existing relational database. Do not change the logical schema merely because it moved to RDS. Provide student-readable configuration and deployment instructions. Secrets must not be committed.

Preserve the explicit SQLite/PostgreSQL adapter and initializer from Stage 08. RDS uses the PostgreSQL
branch; the local SQLite branch remains a compatible, inspectable classroom path rather than being deleted.

RDS instructions must be concrete and runnable without fabricated endpoints. If commands need host/port values, include explicit steps to resolve them from deployment outputs or CLI queries before running `psql`.

Required deployment artifacts for this stage:
- `infra/rds.yaml` (or equivalent CloudFormation template) defining RDS resources and required networking/parameter inputs for the lesson scope.
- `deploy/rds/README.md` containing exact deploy, output-resolution (endpoint/port), verify, and destroy commands.
- output values used by verify commands must come from template outputs or explicit CLI queries in this stage docs.

Update architecture documentation to compare self-managed Linux DB and managed RDS and identify which operational responsibilities moved to AWS.

Update `docs/architecture.md` "Component Assembly Map" to mark relational components as reused while infrastructure/operations components shift to managed RDS. Keep contract and dependency continuity explicit.

The stage README must be an operator/student guide with purpose, key files, deploy/verify/test commands,
cleanup/destruction steps, continuity note, and a "Component assembly update" section. No placeholder README text.
