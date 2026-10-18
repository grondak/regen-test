# Stage 16: Engineer the callback

Prepare TinyWMS so an instructor can run `tail -f pick-tickets.txt`, submit an order from the browser, and watch the corresponding pick ticket appear.

Add an instructor demo script/document that traces the complete path: browser → HTTP → API Gateway → Lambda → RDS transaction → SQS/event → Python worker → Linux file. Do not hide intermediate representations. At each boundary, identify the JSON being transmitted.

Add an executable local integration proof using the real HTTP application and worker logic with fake
database, SQS, and EventBridge clients at AWS boundaries. The proof must load inventory, submit an order,
observe the changed quantity, invoke the real `lambda_inventory` order publisher with injected fake
database/SQS/EventBridge clients, consume its emitted pick-work command, and observe the corresponding line
in `pick-tickets.txt`. Preserve the request, response, command, event, and ticket representations in test
output or fixtures. Do not construct a pick-work command literal inside the integration test. A
narrative-only walkthrough does not satisfy this stage.

The integration test must use an actual local HTTP request to the test server, redirect all mutable
inventory/ticket/idempotency paths into a temporary directory, and invoke the real worker consumption
function. It must not call `_read_inventory` directly as a substitute for HTTP and must never modify a
checked-in data file.

The local HTTP server returns an HTTP status plus its direct JSON body. Assert that status separately;
do not expect the local JSON body to contain Lambda proxy keys such as `statusCode` and `body`.

The browser and worker runbooks must invoke the same paths and commands exercised by the tests.

Cloud-demo integrity requirement:
- the demo runbook must only use runnable commands backed by existing deployment artifacts and output-resolved identifiers (API base URL, queue/event identifiers, function names, DB endpoint as needed);
- if any cloud path command changes in this stage, update the corresponding CloudFormation/deploy README artifacts in the same stage.

Update `docs/architecture.md` "Component Assembly Map" to include an explicit end-to-end dependency chain that references all participating components built so far.

Update stage README with purpose, demo artifacts map, exact demo runbook commands, verification steps,
cleanup notes, continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
