import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from toolchain.regen import discover_prompt_files, generate_app


ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "hello-world.md"


class RegenTests(unittest.TestCase):
    def test_prompt_discovery_and_generation(self):
        prompt_files = discover_prompt_files(ROOT / "prompts")
        self.assertIn(PROMPT, prompt_files)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "generated" / "hello-world"
            generated = generate_app(PROMPT, output_dir)

            self.assertTrue((generated / "app.py").exists())
            self.assertTrue((generated / "test_app.py").exists())

            app_code = (generated / "app.py").read_text(encoding="utf-8")
            self.assertIn('print("Hello, World!")', app_code)

            result = subprocess.run(
                [sys.executable, str(generated / "app.py")],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout, "Hello, World!\n")

            test_result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(generated), "-p", "test_app.py"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(test_result.returncode, 0, test_result.stdout + test_result.stderr)


if __name__ == "__main__":
    unittest.main()
