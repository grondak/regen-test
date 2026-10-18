# Stage 1: Define the JSON backbone

Define TinyWMS's initial JSON contracts. Create realistic sample warehouse inventory containing products with SKU, description, bin location, quantity and unit information. Create JSON Schema documents where useful. Put examples under `data/`. Document each field in `docs/data-contracts.md`. Keep the model intentionally small enough for beginning students to understand immediately.

Add a Python script that reads inventory JSON, validates basic required fields without introducing a large validation framework, lists inventory, finds a SKU, and emits valid JSON.

Rationalize this stage as the first concrete component set. Update `docs/architecture.md` "Component Assembly Map" to list the JSON contract and CLI components, their boundaries, and that later stages must build on these contracts rather than silently replacing them.

Update this stage README as a teaching guide with: purpose, file map, run/test commands, student
exercises, cleanup notes (if any), a contract-continuity note, and a "Component assembly update" section. Do not leave placeholder README text.
