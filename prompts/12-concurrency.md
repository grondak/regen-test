# Stage 12: Make concurrency visible

Review the order implementation specifically for concurrent attempts to order the same remaining inventory. Create a simple reproducible demonstration of the naive race condition, then implement the smallest understandable database transaction strategy that prevents overselling.

Document the before/after behavior for students. Avoid sophisticated abstractions that conceal the SQL or transaction boundary.

Add `src/concurrency_demo.py` as the student-facing demonstration entry point. From the stage root,
`python3 src/concurrency_demo.py` must launch two visibly overlapping order attempts, print each outcome,
and print the final inventory result. Keep database configuration visible through the existing environment
variables, import optional PostgreSQL support lazily, and explain that the command needs the instructor's
PostgreSQL setup for the real row-lock demonstration. It is a demo command, not a test runner.

The fixed path must show either row locking (`SELECT ... FOR UPDATE`) or an atomic conditional decrement (`UPDATE ... WHERE quantity >= ...`) inside the transaction. The test must launch genuinely overlapping attempts using threads/processes plus a barrier or equivalent synchronization, then assert that committed quantity never exceeds available inventory. A sequential insufficient-stock test is useful but does not prove concurrency safety.

Preserve the Stage 11 order API unless the implementation and every importing test are evolved together.
Before emitting `tests/test_concurrency.py`, verify that every name it imports is actually defined by
`src/lambda_inventory.py`; do not assume final-reference dataclasses or helper APIs exist in this predecessor.
This stage still must not publish SQS messages or EventBridge events, which belong to Stages 13 and 14.

Keep the real SQLite order tests as transaction/rollback proofs, but state plainly that SQLite cannot
demonstrate PostgreSQL `SELECT ... FOR UPDATE` row-lock behavior. The instructor's real concurrency
demonstration requires PostgreSQL; do not claim that serialized SQLite writes prove the same lesson.

Update `docs/architecture.md` "Component Assembly Map" to show that this stage hardens existing order/database components rather than introducing a new top-level subsystem.

Update stage README with purpose, reproducible race demo commands, fix-validation commands/tests,
student exercises, cleanup notes, continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
Both exercises must change a stock/delay/transaction value, run `python3 src/concurrency_demo.py`, and ask
students to observe or compare printed outcomes. Tests may appear only afterward as an explicitly optional check.
