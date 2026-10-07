# Hello, World implementation

This implementation prompt is a structured contract, not a raw code dump. The generator reads the metadata and assembles files from templates.

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "def main():\n    print(\"${message}\")\n\n\nif __name__ == \"__main__\":\n    main()\n",
      "variables": {
        "message": "Hello, World!"
      }
    },
    {
      "path": "test_app.py",
      "body_template": "import contextlib\nimport io\nimport unittest\n\nimport app\n\n\nclass AppTests(unittest.TestCase):\n    def test_main_prints_hello_world(self):\n        with contextlib.redirect_stdout(io.StringIO()) as stdout:\n            app.main()\n        self.assertEqual(stdout.getvalue(), \"${message}\\n\")\n",
      "variables": {
        "message": "Hello, World!"
      }
    }
  ]
}
```
