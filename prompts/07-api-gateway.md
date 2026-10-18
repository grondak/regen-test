# Stage 7: Put HTTP in front of Lambda

Add API Gateway configuration so `GET /inventory` invokes the Lambda implementation. The existing browser must be configurable to use either the Pi/EC2 endpoint or API Gateway endpoint without changing its inventory model. Preserve identical JSON response semantics.

Add deployment automation appropriate for students and document the request path.

Required deployment artifacts for this stage:
- `infra/api-gateway.yaml` (or equivalent CloudFormation template) defining API Gateway resources/methods and Lambda invoke permission.
- `deploy/api-gateway/README.md` containing exact deploy, output-resolution, verify (`GET /inventory`), and destroy commands.
- the template must include a deployable API stage and output(s) that let students resolve the API base URL via CLI.

Do not hardcode fake API endpoints in runnable verification commands. Retrieve API base URL values from deployment outputs (or equivalent CLI query commands) and then call `GET /inventory` using that resolved value.

Update `docs/architecture.md` "Component Assembly Map" to add API Gateway as the HTTP front-door component for the Lambda path while preserving prior Pi/EC2 and browser component relationships.

Add `tests/test_web_app.js` using Node's built-in `node:test` support and no npm dependencies. It must
exercise or inspect the plain JavaScript browser contract without requiring a browser or network. Document
`node --test tests/test_web_app.js` as an optional repository safety check; student exercises should verify
behavior through the browser or `curl` first.

The stage README must provide student-usable purpose, file map, deploy/run/test/curl commands, cleanup
steps, a continuity note, and a "Component assembly update" section. Do not emit placeholder README text.
