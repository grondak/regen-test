# Session 28 — Student demonstrations (part 2) and synthesis

**Format:** continue demonstrations; reserve the final ~20 minutes for synthesis. The final architecture walkthrough belongs to the students first, the instructor second. **Repo support:** `20-final-walkthrough/docs/end-to-end.md` and `docs/architecture.md` are the instructor's answer key.

## 10 bullets to work from
1. Finish the remaining demos with the same checklist (session 27), with a hard stop 20 minutes before the end.
2. Synthesis step 1 (students): put the Session 1 architecture picture on one side of the board and ask the class to draw today's system on the other, from memory, one component per volunteer.
3. Synthesis step 2 (students): for each box, who is responsible (AWS or us)? For each arrow, what representation crosses it?
4. Synthesis step 3 (students): replay the journey of one order: browser → API → function → database transaction → queue and event → worker → ticket file. They narrate, you only prompt.
5. Instructor pass: now compare their picture with `docs/end-to-end.md` and `docs/architecture.md` and add what was missed. Likely misses: the event side (subscribers), the idempotency state file, the IAM role, the security group.
6. Ask for the three failures that mattered most, using the table from session 20 ("down / slow / who finds out / data lost"). Highlight the one the code does not handle (commit succeeds, queue send fails).
7. Name what was deliberately left out and what would come next: authentication on the API, secrets management, retries and dead-letter queues, an outbox, monitoring and alarms, infrastructure review, real load.
8. Revisit the arc: Pi → Linux → network → cloud → data → distributed system. Each boundary moved one question: where does the code run, where is its data.
9. Collect feedback: what would students teach differently, which session needed more time, which demo broke.
10. Final housekeeping: confirm every AWS resource is deleted, remove access keys created for the course, and point students to the repo for review.
