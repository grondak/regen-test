# Session 6 — Client/server and HTTP

**Stage:** `03-pi-http-server` · **Repo support:** Yes · **Run from:** `03-pi-http-server/`

**Concept (20 min):** client/server, request/response, GET, URL, port, status, headers, MIME/content type.
**Demo (20 min):** a tiny Python HTTP service returns `inventory.json`; query it with a browser and `curl`.

## Run sheet
```bash
python3 src/http_server.py                          # prints:  listening on 8000
```
In a second terminal:
```bash
curl -i http://127.0.0.1:8000/inventory             # status line, headers, blank line, body
curl -s http://127.0.0.1:8000/inventory | python3 -m json.tool
curl -i http://127.0.0.1:8000/nothing               # 404 with a JSON error body
curl -I http://127.0.0.1:8000/inventory             # HEAD request: this server answers 501 Unsupported method
```
Browser: open `http://<pi-address>:8000/inventory` from a laptop on the same network. This is the first time a second computer talks to the Pi's program.

Change the port and the data:
```bash
TINYWMS_PORT=8080 python3 src/http_server.py
TINYWMS_INVENTORY_FILE=/tmp/inventory-changed.json python3 src/http_server.py     # file from session 5
```
Edit the file and `curl` again: the server reads the file on every request, so no restart is needed.

## Talking points
- A URL has four parts here: scheme `http`, host, port `8000`, path `/inventory`. The port picks the program on the machine; the host picks the machine.
- Read the response out loud: `HTTP/1.0 200 OK`, `Content-Type: application/json`, `Content-Length: ...`. The status code says what happened; the content type tells the client how to read the body.
- The same server, `0.0.0.0`, listens on all interfaces. That is why other machines can reach it, and why EC2 needs a firewall rule in session 8.
- Show the code: `src/http_server.py` is about 60 lines: a handler class, a `do_GET`, `if path == '/inventory'`.

## Caveats
- Only GET is implemented. `curl -I` (HEAD) and `curl -X POST` get a `501 Unsupported method` HTML page from Python's default handler; use that as a preview of session 18.
- Unknown paths return 404 with a JSON body; there is no HTML error page.
