# Session 12 — Turning a function into an HTTP API

**Stage:** `07-api-gateway` · **Repo support:** Yes for reading and deploying; the AWS steps were not run for this lesson plan · **Run from:** `07-api-gateway/`

**Concept (20 min):** route, method, request, integration, response.
**Demo (20 min):** connect a GET route to Lambda; call it with `curl`; then point the existing page at it.

## Run sheet

**Step 1: read the wiring before deploying.** `infra/api-gateway.yaml` is the whole story in about 50 lines:
- `RestApi` → `Resource` with `PathPart: inventory` → `Method` GET with an `AWS_PROXY` integration whose URI is the Lambda ARN → a Lambda `Permission` allowing API Gateway to invoke the function.
- Map each piece to the vocabulary: route = resource + method, integration = what the route calls, proxy = pass the whole HTTP request to Lambda as the `event` and expect `statusCode`/`headers`/`body` back (the shape you printed in session 11).

**Step 2: deploy and call it** (the Lambda from session 11 must exist, and its name must match: the notes use `tinywms-inventory-lesson`, but stage 6 creates `tinywms-lambda-inventory` unless you override it; commands from `deploy/api-gateway/README.md`):
```bash
aws cloudformation deploy --stack-name tinywms-api-gateway \
  --template-file infra/api-gateway.yaml \
  --parameter-overrides LambdaFunctionName=tinywms-inventory-lesson
API_BASE_URL="$(aws cloudformation describe-stacks --stack-name tinywms-api-gateway \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue | [0]' --output text)"
curl -i "$API_BASE_URL/inventory"
```
Compare this response's headers with the Pi's from session 6.

**Step 3: point the existing page at it.** `src/web/app.js` reads `window.TINYWMS_API_BASE_URL`. The simplest route is a local test page or a quick edit to `index.html` that sets it before `app.js` loads:
```html
<script>window.TINYWMS_API_BASE_URL = 'https://<api-id>.execute-api.<region>.amazonaws.com/<stage>';</script>
```
Serve the page locally (`python3 src/http_server.py`) and open it. Because the page is now on a different origin from the API, the browser enforces CORS; if the table fails to load, open DevTools → Console. Nothing in the repo adds the CORS headers, so this is where you teach (or work around) it.

**Step 4: tear down** (`deploy/api-gateway/README.md` → Destroy).

## Talking points
- The browser, `curl` and the page all call a URL; they do not know or care whether Python on a Pi or Lambda answers. That is the payoff of keeping the contract stable.
- A route has a method and a path; unknown routes get a gateway-generated 403/404, not your code.
- Unauthenticated (`AuthorizationType: NONE`): anyone with the URL can call it. Callback to session 10.
