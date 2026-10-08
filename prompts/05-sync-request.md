# Stage: Synchronous request

Create a tiny Python HTTP service that responds synchronously to a request.

Requirements:
- Use the standard library `http.server` module.
- Expose a `GET /health` route that responds with JSON.
- The response should include a status message.
- Include a test that starts the server briefly and verifies the response payload.

This stage makes the request path explicit and synchronous.
