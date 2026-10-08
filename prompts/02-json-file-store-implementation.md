# JSON file store implementation

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "import json\nfrom pathlib import Path\n\n\nDATA_PATH = Path(\"data.json\")\n\n\ndef write_data():\n    payload = {\n        \"id\": 1,\n        \"name\": \"${name}\",\n        \"status\": \"active\"\n    }\n    DATA_PATH.write_text(json.dumps(payload, indent=2), encoding=\"utf-8\")\n    return payload\n\n\ndef read_data():\n    return json.loads(DATA_PATH.read_text(encoding=\"utf-8\"))\n\n\ndef main():\n    payload = write_data()\n    print(json.dumps(read_data(), indent=2))\n    return payload\n\n\nif __name__ == \"__main__\":\n    main()\n",
      "variables": { "name": "student" }
    },
    {
      "path": "test_app.py",
      "body_template": "import json\nimport tempfile\nimport unittest\nfrom pathlib import Path\n\nimport app\n\n\nclass JsonFileStoreTests(unittest.TestCase):\n    def test_round_trip_serialization(self):\n        with tempfile.TemporaryDirectory() as tmpdir:\n            app.DATA_PATH = Path(tmpdir) / \"data.json\"\n            payload = app.main()\n            self.assertEqual(payload[\"name\"], \"student\")\n            stored = json.loads(app.DATA_PATH.read_text(encoding=\"utf-8\"))\n            self.assertEqual(stored[\"id\"], 1)\n            self.assertEqual(stored[\"status\"], \"active\")\n",
      "variables": {}
    },
    {
      "path": "requirements.txt",
      "body_template": "# Generated requirements for the Python app\n"
    }
  ]
}
```
