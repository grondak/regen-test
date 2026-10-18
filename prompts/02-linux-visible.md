# Stage 2: Make Linux visible

Extend TinyWMS with simple command-line programs designed to demonstrate Linux concepts. Programs must make stdin, stdout, stderr, exit codes, files, environment variables and long-running processes visible rather than hiding them.

Include exercises suitable for `grep`, pipes, redirection, `ps`, `kill`, and `tail -f`. Do not introduce HTTP yet. Update README with commands students can execute on a Raspberry Pi.

Update `docs/architecture.md` "Component Assembly Map" to show which Stage 1 components are reused unchanged and which Linux-observability components are newly added. Make the dependencies between JSON files, CLI tools, and Linux process behavior explicit.

The stage README must be lesson-specific (not placeholder output) and include purpose, key file map,
run/test commands, exercises, cleanup notes, a continuity note, and a "Component assembly update" section.
