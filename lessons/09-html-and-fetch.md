# Session 9 — HTML, the DOM, and `fetch()`

**Stage:** `04-browser` · **Repo support:** Yes · **Run from:** `04-browser/`

**Concept (20 min):** HTML structure, the DOM idea, the browser as client, `fetch()`; JavaScript only as far as needed to consume JSON.
**Demo (20 min):** a static page calls the inventory endpoint with `fetch()` and builds an HTML table.

## Run sheet
```bash
python3 src/http_server.py                  # serves the page AND /inventory from one origin
# browser: http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/index.html    # the page itself is just an HTTP response with Content-Type text/html
curl -i http://127.0.0.1:8000/app.js        # so is the script (application/javascript)
```

**Walk the three files (about 60 lines in total):**
- `src/web/index.html`: `<table>`, an empty `<tbody id="inventory-body">`, a status line, an error `<pre>`, a Refresh button, `<script src="app.js">`.
- `src/web/app.js`: `fetch(inventoryUrl)` → check `response.ok` → `response.json()` → `renderInventory(items)` builds rows → `catch` writes the error text. Button click calls it again.
- `src/web/style.css`: only presentation, not the lesson.

**Live experiments (each is a visible teaching moment):**
1. Open DevTools → Network: reload and see the four requests (page, script, CSS, `/inventory`). Click `/inventory` and compare the response with `curl -i`.
2. Edit `style.css` (e.g. table borders), reload: change appears with no server restart.
3. Change what is rendered in `app.js` (e.g. show `unit` in uppercase), reload.
4. Stop the server, click Refresh: the page shows "Failed to load inventory" and the error text. Every network call can fail; the page must say so.
5. Edit `data/inventory.json`, click Refresh: new data, no code change (the server reads the file on each request).

## Talking points
- The browser is just another HTTP client, like `curl`, with a layout engine. It asked for the same `/inventory`.
- The DOM: the browser turns HTML into a tree of objects; JavaScript finds a node (`getElementById`) and changes it.
- `window.TINYWMS_API_BASE_URL || window.location.origin` is the one line that later lets the same page talk to API Gateway.

## Caveats
- `app.js` writes values into the page with `innerHTML`; fine for trusted sample data, an injection risk once users supply text. A good one-sentence aside before the order form.
- Pointing this page at a different host (EC2, API Gateway) needs CORS headers; the Python server sends none. Mention it before session 12.
- Serving only `src/web` with `python3 -m http.server` (as the stage-20 runbook suggests) does not work: that server has no `/inventory`, so the table shows an error. Use `src/http_server.py`.
