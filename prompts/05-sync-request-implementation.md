# Synchronous request implementation

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "import json\nfrom http.server import BaseHTTPRequestHandler, HTTPServer\n\n\nclass Handler(BaseHTTPRequestHandler):\n    def do_GET(self):\n        if self.path == \"/health\":\n            body = json.dumps({\"status\": \"ok\"}).encode(\"utf-8\")\n            self.send_response(200)\n            self.send_header(\"Content-Type\", \"application/json\")\n            self.send_header(\"Content-Length\", str(len(body)))\n            self.end_headers()\n            self.wfile.write(body)\n        else:\n            self.send_response(404)\n            self.end_headers()\n\n    def log_message(self, format, *args):\n        return\n\n\ndef main():\n    server = HTTPServer((\"127.0.0.1\", 8000), Handler)\n    print(\"Serving on 127.0.0.1:8000\")\n    server.serve_forever()\n\n\nif __name__ == \"__main__\":\n    main()\n",
      "variables": {}
    },
    {
      "path": "test_app.py",
      "body_template": "import json\nimport threading\nimport time\nimport unittest\nfrom urllib.request import urlopen\n\nimport app\n\n\nclass SyncRequestTests(unittest.TestCase):\n    def test_health_endpoint(self):\n        server = app.HTTPServer((\"127.0.0.1\", 8001), app.Handler)\n        thread = threading.Thread(target=server.serve_forever, daemon=True)\n        thread.start()\n        try:\n            time.sleep(0.1)\n            with urlopen(\"http://127.0.0.1:8001/health\") as response:\n                payload = json.loads(response.read().decode(\"utf-8\"))\n            self.assertEqual(payload[\"status\"], \"ok\")\n        finally:\n            server.shutdown()\n            server.server_close()\n",
      "variables": {}
    },
    {
      "path": "requirements.txt",
      "body_template": "# Generated requirements for the Python app\n"
    }
  ]
}
```
