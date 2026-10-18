# Stage 10: Make Lambda read RDS

Modify the Lambda `GET /inventory` path so inventory comes from RDS instead of embedded/static JSON. Convert database rows into exactly the established inventory JSON contract so the existing web page requires no data-model changes.

The handler must contain a real, visible PostgreSQL connection/query path (for example a small `psycopg` dependency), while tests may inject or mock the connection so the local suite requires no live database. Falling back to `data/inventory.json` is allowed only as an explicitly named local demonstration path; it must not be the deployed RDS path.

Reuse `src/db_adapter.py` and make the backend switch explicit: `TINYWMS_DB=postgres` remains the default
for Lambda/RDS, while `TINYWMS_DB=sqlite` uses `TINYWMS_SQLITE_PATH` for a runnable local path. Keep
`open_connection` readable and use lazy optional imports. Query the canonical SQL column `bin_location`.
SQLite cannot prove row locks, and the documentation must not imply otherwise.

This is an implementation evolution, not a documentation-only lesson. The stage delta must replace
`src/lambda_inventory.py` and `tests/test_lambda_inventory.py`. The handler must visibly import a PostgreSQL
driver, obtain connection settings from the environment, execute a `SELECT` against the inventory table,
and map the returned rows to the existing inventory JSON fields, including the canonical `bin_location`
field (do not silently rename it to `bin`). The test must inject a fake or mocked
database connection and prove that the response values came from those database rows. Adapt the matching
parts of the final reference implementation, but do not introduce orders, SQS, or EventBridge early.

Keep persistence, mapping and HTTP concerns understandable and separated without introducing enterprise architecture patterns.

Any deploy/verify workflow in this stage must reuse real outputs from prior deployment artifacts (Lambda/API/RDS) rather than introducing new hardcoded example endpoints or identifiers.

Required cloud-artifact continuity for this stage:
- keep runnable AWS deployment artifacts present and coherent for this combined path (`infra/` templates and deployment READMEs for Lambda/API/RDS introduced earlier);
- if this stage changes the Lambda↔RDS wiring, update the relevant CloudFormation template(s) and deployment instructions in the same stage so students can actually redeploy and verify;
- include at least one explicit verify command that uses output-resolved values and proves `GET /inventory` still works end-to-end.

Update `docs/architecture.md` "Component Assembly Map" so students can see that the Lambda component is reused but its data-source dependency changes from static JSON to RDS.

Update stage README with purpose, key files, deploy/run/test commands, exercises, cleanup notes, and
continuity note, plus a "Component assembly update" section. Placeholder README output is not acceptable.
