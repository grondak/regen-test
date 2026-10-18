# Stage 3: Turn the Pi into a server

Add the smallest reasonable Python HTTP application that exposes `GET /inventory` and returns the existing inventory JSON. Keep the application deliberately transparent so students can understand process, listening port, request, response, status code, headers and JSON body. It must run on Raspberry Pi Linux and EC2 Linux.

Configuration such as port should come from environment variables. Include `curl` examples. Do not add a database or AWS SDK.

Update `docs/architecture.md` "Component Assembly Map" to show the new HTTP server component and its dependency on the existing inventory JSON contract. Explicitly record which earlier CLI/Linux components remain valid and unchanged.

The stage README must teach exactly how to run and test this stage and must include purpose, file map,
commands, exercises, cleanup notes, a continuity note, and a "Component assembly update" section; do not emit placeholder README text.
