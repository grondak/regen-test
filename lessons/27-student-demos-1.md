# Session 27 — Student system demonstrations (part 1)

**Format:** 5-minute opening on expectations; the rest is students demonstrating. **Repo support:** No new material. Students present their own deployments, and the earlier sessions' run sheets are the reference.

## 10 bullets to work from
1. Opening (5 min, you talk): what a good demo looks like, the time limit per student or team (suggest 8–10 minutes including questions), and the order. Post the checklist below.
2. Demo checklist, one line each: start from a cold terminal; show the inventory page; place an order from the browser; show inventory change; show the queue message or the pick ticket; stop one component and show the failure.
3. Students narrate with the four course questions: where is the code running, where is its data, how did the data get there, what representation crosses each boundary?
4. Ask each presenter to name one thing that broke while building it and how they found it. Reward the debugging path (process → port → local curl → firewall → logs), not a flawless run.
5. Prepare a fallback so a demo is never lost: the offline scripts in `lessons/support/` (`order_demo.py`, `worker_demo.py`, `events_demo.py`) show the order → queue → event → ticket path without AWS.
6. Keep the audience active: after each demo, one other student asks a question from the checklist in session 20 ("what if this component is down?").
7. Time-keeping: a visible timer; interrupt politely at the limit; demos that run over lose the Q&A, not the next presenter's slot.
8. Keep a shared list of recurring problems you see (permissions, security groups, wrong region, stale environment variables, forgotten terminations) for the synthesis.
9. Cost safety: remind everyone that anything still running (EC2, RDS, API stacks) must be torn down after their demo. Name the exact commands (`aws cloudformation delete-stack`, terminate instance).
10. End the session with the order of presenters for part 2 and what each person should have ready.
