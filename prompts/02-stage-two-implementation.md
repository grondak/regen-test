# Stage Two implementation

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "import sys\n\n\ndef main(name: str | None = None):\n    target = name or \"World\"\n    print(f\"Hello, {target}!\")\n\n\nif __name__ == \"__main__\":\n    main(sys.argv[1] if len(sys.argv) > 1 else None)\n",
      "variables": {}
    },
    {
      "path": "test_app.py",
      "body_template": "import io\nimport contextlib\nimport unittest\n\nimport app\n\n\nclass AppTests(unittest.TestCase):\n    def test_default_greeting(self):\n        with contextlib.redirect_stdout(io.StringIO()) as stdout:\n            app.main()\n        self.assertEqual(stdout.getvalue(), \"Hello, World!\\n\")\n\n    def test_custom_greeting(self):\n        with contextlib.redirect_stdout(io.StringIO()) as stdout:\n            app.main(\"Class\")\n        self.assertEqual(stdout.getvalue(), \"Hello, Class!\\n\")\n",
      "variables": {}
    },
    {
      "path": "requirements.txt",
      "body_template": "# Generated requirements for the Python app\n"
    }
  ]
}
```
