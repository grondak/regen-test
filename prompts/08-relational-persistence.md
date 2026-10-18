# Stage 8: Introduce relational persistence

Design a minimal relational TinyWMS schema derived from the existing JSON contracts. This stage introduces
only the inventory table; orders and order lines belong to Stage 11. Use `bin_location` as the canonical
column name so SQL and inventory JSON use the same vocabulary. Provide SQL schema creation and seed scripts
that transform/load the existing sample JSON data.

Add one small, commented `src/db_adapter.py` plus `data/init_db.py` supporting an explicit
`TINYWMS_DB=sqlite|postgres` selection and `TINYWMS_SQLITE_PATH`. PostgreSQL remains the default. The
SQLite adapter may translate TinyWMS's visible `%s` placeholders to `?` and remove ` FOR UPDATE`, but must
say clearly that it is a narrow teaching adapter, not a general SQL translator. Enable SQLite foreign keys.
The initializer must create the schema and load seed data for either backend, with the PostgreSQL driver
imported lazily so the safe local tests require only the standard library. Do not modify Lambda to use it yet.
Document and test this exact local invocation from the stage root (module form keeps `src/` importable):
`TINYWMS_DB=sqlite TINYWMS_SQLITE_PATH=data/tinywms.db python3 -m data.init_db`.

Add `tests/test_relational_persistence.py` with behavior-specific names such as
`test_schema_uses_bin_location`, `test_seed_matches_inventory_schema`, and
`test_sqlite_initializer_loads_inventory`. Execute or inspect the real artifacts with meaningful
assertions. Do not emit `test_placeholder...`, `pass`, or `assert True` safety-net tests.

Document explicitly how JSON structures map to relational columns. Explain that SQLite makes the relational
lesson runnable locally but does not demonstrate a database server process/port or row locking; use PostgreSQL
for those instructor demonstrations. Preserve the inherited `tests/test_web_app.js` Node safety check.

Update `docs/architecture.md` "Component Assembly Map" to add relational persistence components and map their dependencies to existing JSON contracts and application paths.

Update stage README with purpose, schema/file map, setup/run/test commands, exercises, cleanup notes,
continuity note, and a "Component assembly update" section. Placeholder README output is not acceptable.
