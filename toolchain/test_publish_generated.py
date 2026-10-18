import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from toolchain.publish_generated import MANIFEST_NAME, publish_course


class PublishGeneratedTests(unittest.TestCase):
    def make_course(self, root: Path) -> tuple[Path, Path, Path]:
        prompt_dir = root / "prompts"
        source = root / "generated"
        templates = root / "templates"
        prompt_dir.mkdir()
        source.mkdir()
        templates.mkdir()
        (prompt_dir / "00-repository.md").write_text("Repository\n", encoding="utf-8")
        (prompt_dir / "01-json.md").write_text("JSON\n", encoding="utf-8")
        (templates / "README.generated.md").write_text("# Published course\n", encoding="utf-8")
        (templates / "gitignore.generated").write_text(".regen.json\n__pycache__/\n", encoding="utf-8")

        stages = [
            ("00-repository", None, ["README.md"]),
            ("01-json", "00-repository", ["README.md", "data/inventory.json"]),
        ]
        for name, inherited, files in stages:
            stage = source / name
            stage.mkdir()
            (stage / "README.md").write_text(f"# {name}\n", encoding="utf-8")
            (stage / "empty-folder").mkdir()
            if "data/inventory.json" in files:
                (stage / "data").mkdir()
                (stage / "data" / "inventory.json").write_text('{"inventory": []}\n', encoding="utf-8")
            cache = stage / "__pycache__"
            cache.mkdir()
            (cache / "ignored.pyc").write_bytes(b"cache")
            manifest = {
                "stage": name,
                "source_prompt": f"{name}.md",
                "model": "test-model",
                "inherits_from": inherited,
                "summary": name,
                "changed_files": files,
                "deleted_files": [],
                "generated_files": files,
            }
            (stage / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        return source, prompt_dir, templates

    def make_clean_repository(self, root: Path) -> Path:
        destination = root / "course"
        destination.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=destination, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=destination, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=destination, check=True)
        (destination / "LICENSE").write_text("Teaching example\n", encoding="utf-8")
        stale = destination / "99-stale-stage"
        stale.mkdir()
        (stale / "old.txt").write_text("old\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=destination, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=destination, check=True)
        return destination

    def test_publish_copies_only_course_files_and_preserves_unmanaged_root_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source, prompt_dir, templates = self.make_course(root)
            destination = self.make_clean_repository(root)

            changes = publish_course(source, prompt_dir, destination, templates)

            self.assertTrue(changes)
            self.assertEqual((destination / "README.md").read_text(), "# Published course\n")
            self.assertTrue((destination / "01-json" / "data" / "inventory.json").is_file())
            self.assertFalse((destination / "00-repository" / "empty-folder").exists())
            self.assertFalse((destination / "00-repository" / MANIFEST_NAME).exists())
            self.assertFalse((destination / "00-repository" / "__pycache__").exists())
            self.assertFalse((destination / "99-stale-stage").exists())
            self.assertTrue((destination / "LICENSE").is_file())

    def test_publish_refuses_a_dirty_destination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source, prompt_dir, templates = self.make_course(root)
            destination = self.make_clean_repository(root)
            (destination / "notes.txt").write_text("do not overwrite me\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "uncommitted or untracked changes"):
                publish_course(source, prompt_dir, destination, templates)

            self.assertEqual((destination / "notes.txt").read_text(), "do not overwrite me\n")

    def test_publish_requires_every_prompt_defined_stage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source, prompt_dir, templates = self.make_course(root)
            destination = self.make_clean_repository(root)
            for path in (source / "01-json").rglob("*"):
                if path.is_file():
                    path.unlink()
            for path in sorted((source / "01-json").rglob("*"), reverse=True):
                if path.is_dir():
                    path.rmdir()
            (source / "01-json").rmdir()

            with self.assertRaisesRegex(RuntimeError, "complete prompt-defined stage sequence"):
                publish_course(source, prompt_dir, destination, templates)


if __name__ == "__main__":
    unittest.main()
