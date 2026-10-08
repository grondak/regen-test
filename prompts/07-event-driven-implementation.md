# Event-driven implementation

## contract
```json
{
  "runtime": "python",
  "files": [
    {
      "path": "app.py",
      "body_template": "class EventBus:\n    def __init__(self):\n        self.listeners = []\n\n    def subscribe(self, listener):\n        self.listeners.append(listener)\n\n    def publish(self, event_name, payload):\n        for listener in self.listeners:\n            listener(event_name, payload)\n\n\ndef main():\n    bus = EventBus()\n\n    def on_user_created(event_name, payload):\n        print(event_name, payload)\n\n    bus.subscribe(on_user_created)\n    bus.publish(\"user.created\", {\"id\": 1, \"name\": \"Ada\"})\n",
      "variables": {}
    },
    {
      "path": "test_app.py",
      "body_template": "import unittest\n\nimport app\n\n\nclass EventDrivenTests(unittest.TestCase):\n    def test_event_is_received(self):\n        seen = []\n        bus = app.EventBus()\n        bus.subscribe(lambda event_name, payload: seen.append((event_name, payload)))\n        bus.publish(\"user.created\", {\"id\": 1})\n        self.assertEqual(seen[0][0], \"user.created\")\n        self.assertEqual(seen[0][1][\"id\"], 1)\n",
      "variables": {}
    },
    {
      "path": "requirements.txt",
      "body_template": "# Generated requirements for the Python app\n"
    }
  ]
}
```
