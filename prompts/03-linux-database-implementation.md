# Linux database implementation

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "import sqlite3\n\n\nDB_PATH = \"students.db\"\n\n\ndef init_db():\n    conn = sqlite3.connect(DB_PATH)\n    conn.execute(\"CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT)\")\n    conn.execute(\"INSERT OR REPLACE INTO students (id, name) VALUES (?, ?)\", (1, \"${student_name}\"))\n    conn.commit()\n    conn.close()\n\n\ndef list_students():\n    conn = sqlite3.connect(DB_PATH)\n    rows = conn.execute(\"SELECT id, name FROM students ORDER BY id\").fetchall()\n    conn.close()\n    return rows\n\n\ndef main():\n    init_db()\n    for row in list_students():\n        print(row)\n\n\nif __name__ == \"__main__\":\n    main()\n",
      "variables": { "student_name": "Ada" }
    },
    {
      "path": "test_app.py",
      "body_template": "import os\nimport sqlite3\nimport unittest\n\nimport app\n\n\nclass LinuxDatabaseTests(unittest.TestCase):\n    def test_insert_and_query(self):\n        if os.path.exists(app.DB_PATH):\n            os.remove(app.DB_PATH)\n        app.init_db()\n        rows = app.list_students()\n        self.assertEqual(rows, [(1, \"Ada\")])\n",
      "variables": {}
    },
    {
      "path": "requirements.txt",
      "body_template": "# Generated requirements for the Python app\n"
    }
  ]
}
```
