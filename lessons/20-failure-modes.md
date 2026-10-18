# Session 20 — Network boundaries, partial failure and coupling

**Repo support:** Partly. No failure-injection material exists, but the pieces from sessions 6–19 are what you break, and `lessons/support/` can reproduce several failures offline.

**Concept (20 min):** network boundaries, latency, partial failure, timeout, retry, coupling, state. Keep theory attached to TinyWMS.
**Demo (20 min):** draw their actual system and kill or break components one at a time.

## 10 bullets to work from
1. Draw the real system on the whiteboard together, left to right: browser → API Gateway → Lambda → RDS, then Lambda → SQS → worker → ticket file, and Lambda → EventBridge → subscribers. Mark every arrow that crosses a network. Use `20-final-walkthrough/docs/end-to-end.md` as the answer key.
2. A local function call fails together with its caller. A network call can fail on its own: refused, timed out, or succeeded but the reply was lost. The caller cannot tell the last two apart.
3. Latency adds up: each hop costs time, and the user waits for the slowest synchronous chain. Which hops does the browser wait for? (Everything up to the database commit.) Which does it not? (Queue, worker, subscribers.)
4. Break 1: stop the server (session 6) while the page is open. Show the page's error text from session 9. Failing loudly beats failing silently.
5. Break 2: take away the database. Locally, point `TINYWMS_SQLITE_PATH` at a nonexistent directory and run the session-19 script to see the failure surface; in AWS, stop the instance or change the security group (session 8). What does the user see?
6. Break 3, the partial failure to dwell on: the order commits, then the SQS send fails (remove `sqs:SendMessage` from the Lambda role, or call `place_order` with a client whose `send_message` raises). The order exists, stock is reduced, no pick request was sent. Which component knows? Which should? Discuss retry, a dead-letter queue, and an outbox table as ideas, not as things the repo already has.
7. Break 4: kill the worker (session 25). Orders keep succeeding, messages wait in the queue, and nothing is lost. The queue buys decoupling in time. Restart the worker and watch it drain.
8. Timeouts and retries: a retry is only safe if the operation is idempotent. Submit the same order twice (session 18 accepts it twice) and see why that matters; this sets up session 23.
9. Coupling: what does the order function need to know about the worker? Almost nothing, just the queue. What does it know about the event subscribers? Nothing at all. Contrast with the synchronous path, where it needs the database to be up.
10. Close with a table students fill in: for each component, "what if it is down", "what if it is slow", "who finds out", "is any data lost?". Keep it; they use it again in the final synthesis session.
