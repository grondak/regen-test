# Lambda implementation

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "def handler(event, context):\n    return {\n        \"statusCode\": 200,\n        \"body\": {\"message\": \"processed\", \"event\": event}\n    }\n\n\ndef main():\n    print(handler({\"type\": \"user.created\"}, None))\n",
      "variables": {}
    },
    {
      "path": "test_app.py",
      "body_template": "import unittest\n\nimport app\n\n\nclass LambdaTests(unittest.TestCase):\n    def test_handler_returns_status_code(self):\n        response = app.handler({\"type\": \"user.created\"}, None)\n        self.assertEqual(response[\"statusCode\"], 200)\n        self.assertEqual(response[\"body\"][\"message\"], \"processed\")\n",
      "variables": {}
    },
    {
      "path": "requirements.txt",
      "body_template": "# Generated requirements for the Python app\n"
    }
  ]
}
```
