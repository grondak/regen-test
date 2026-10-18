# Stage 4: Add the browser

Add a deliberately simple static warehouse inventory page using plain HTML, CSS and browser JavaScript. Use `fetch()` to retrieve `GET /inventory` and render SKU, description, bin and quantity as a table. Avoid frontend frameworks and build tools.

The browser must consume the same JSON contract already used by the CLI and HTTP application. Make failures visible and understandable to students.

Update `docs/architecture.md` "Component Assembly Map" to add the browser component, its `GET /inventory` dependency, and the unchanged contracts it reuses from prior stages.

Update the stage README to be student-usable with purpose, file map, run/test commands, exercises,
cleanup notes, continuity note, and a "Component assembly update" section. Placeholder README text is not acceptable.
