import json
import tempfile
import unittest
from pathlib import Path

from toolchain.blueprint import (
    BLUEPRINT_NAME,
    blueprint_prompt_contract,
    normalize_blueprint_continuity,
    validate_blueprint,
    validate_snapshot_against_blueprint,
)
from toolchain.regen import MANIFEST_NAME, generate_course_forward, generate_final_reference


class BlueprintTests(unittest.TestCase):
    STAGES = ["00-repository", "01-json"]

    def blueprint(self):
        return {
            "schema_version": 1,
            "reference_stage": "01-json",
            "contracts": [
                {
                    "id": "inventory-json",
                    "name": "Inventory JSON",
                    "introduced_stage": "01-json",
                    "representation": "JSON array validated by JSON Schema",
                    "schema_paths": ["data/inventory.schema.json"],
                    "producer_components": ["inventory-cli"],
                    "consumer_components": ["inventory-cli"],
                    "compatibility_checks": ["python3 -m unittest tests.test_inventory -v"],
                }
            ],
            "components": [
                {
                    "id": "repository-scaffold",
                    "name": "Repository scaffold",
                    "introduced_stage": "00-repository",
                    "retired_after_stage": None,
                    "kind": "operations",
                    "runtime": "local filesystem",
                    "paths": [
                        "README.md",
                        "docs/architecture.md",
                        "docs/data-contracts.md",
                        "data/.gitkeep",
                        "src/.gitkeep",
                        "tests/.gitkeep",
                    ],
                    "inbound_contracts": [],
                    "outbound_contracts": [],
                    "dependencies": [],
                },
                {
                    "id": "inventory-cli",
                    "name": "Inventory CLI",
                    "introduced_stage": "01-json",
                    "retired_after_stage": None,
                    "kind": "application",
                    "runtime": "local Python process",
                    "paths": ["data/inventory.json", "src/inventory.py", "tests/test_inventory.py"],
                    "inbound_contracts": ["inventory-json"],
                    "outbound_contracts": ["inventory-json"],
                    "dependencies": ["repository-scaffold"],
                },
            ],
            "stages": [
                {
                    "name": "00-repository",
                    "purpose": "Establish an empty teaching repository.",
                    "added_components": ["repository-scaffold"],
                    "reused_components": [],
                    "evolved_components": [],
                    "introduced_contracts": [],
                    "inherited_contracts": [],
                    "boundary_shift": "Create the repository boundary.",
                    "required_paths": [],
                    "continuity_checks": [],
                },
                {
                    "name": "01-json",
                    "purpose": "Add visible inventory JSON and its first consumer.",
                    "added_components": ["inventory-cli"],
                    "reused_components": ["repository-scaffold"],
                    "evolved_components": [],
                    "introduced_contracts": ["inventory-json"],
                    "inherited_contracts": [],
                    "boundary_shift": "Add a JSON file boundary.",
                    "required_paths": [],
                    "continuity_checks": ["python3 -m unittest tests.test_inventory -v"],
                },
            ],
        }

    def stage_readme(self, name, paths):
        files = "\n".join(f"- `{path}` - lesson file." for path in paths)
        return (
            f"# TinyWMS lesson: {name}\n\n"
            "## Stage purpose\nTeach visible JSON.\n\n"
            f"## Files in this lesson\n{files}\n\n"
            "## Run the lesson\n```bash\npython3 src/inventory.py\n```\n\n"
            "## Run tests\n```bash\npython3 -m unittest tests.test_inventory -v\n```\n\n"
            "## Student exercises\n1. Change data.\n2. Rerun tests.\n\n"
            "## Continuity note\n- Inherited contract: inventory JSON.\n"
            "- Boundary changed in this stage: JSON is now read by Python.\n\n"
            "## Component assembly update\n- Added: inventory CLI.\n"
            "- Reused unchanged: repository scaffold.\n- Replaced/evolved: none.\n\n"
            "## Cleanup\nNo external resources are created in this stage.\n"
        )

    def reference_files(self):
        blueprint = self.blueprint()
        return {
            "README.md": self.stage_readme(
                "01-json",
                [
                    "README.md",
                    "docs/architecture.md",
                    "docs/data-contracts.md",
                    "data/inventory.json",
                    "data/inventory.schema.json",
                    "src/inventory.py",
                    "tests/test_inventory.py",
                ],
            ),
            "docs/architecture.md": "# Architecture\n",
            "docs/data-contracts.md": "# Contracts\n",
            "data/.gitkeep": "",
            "data/inventory.json": '[{"sku":"A","quantity":1}]\n',
            "data/inventory.schema.json": '{"type":"array"}\n',
            "src/.gitkeep": "",
            "src/inventory.py": "import json\nprint(json.load(open('data/inventory.json')))\n",
            "tests/.gitkeep": "",
            "tests/test_inventory.py": (
                "import json\nimport unittest\nfrom pathlib import Path\n\n"
                "class InventoryTests(unittest.TestCase):\n"
                "    def test_inventory_json_is_visible(self):\n"
                "        items = json.loads(Path('data/inventory.json').read_text())\n"
                "        self.assertEqual(items[0]['sku'], 'A')\n"
            ),
            BLUEPRINT_NAME: json.dumps(blueprint, indent=2) + "\n",
        }

    def make_course(self, root):
        prompt_dir = root / "prompts"
        prompt_dir.mkdir()
        (root / "AGENTS.md").write_text("Keep JSON visible.\n", encoding="utf-8")
        (prompt_dir / "00-repository.md").write_text("Create empty folders.\n", encoding="utf-8")
        (prompt_dir / "01-json.md").write_text("Add inventory JSON.\n", encoding="utf-8")
        return prompt_dir

    def test_rejects_future_component_path_in_predecessor(self):
        blueprint = validate_blueprint(self.blueprint(), self.STAGES)
        with self.assertRaisesRegex(ValueError, "reserved for later"):
            validate_snapshot_against_blueprint(
                "00-repository",
                {
                    "README.md": "x",
                    "docs/architecture.md": "x",
                    "docs/data-contracts.md": "x",
                    "data/.gitkeep": "",
                    "src/.gitkeep": "",
                    "tests/.gitkeep": "",
                    "src/inventory.py": "too early",
                },
                blueprint,
                self.STAGES,
            )

    def test_final_reference_contract_names_assembled_system_proofs(self):
        contract = blueprint_prompt_contract(
            [
                "03-pi-http-server",
                "04-browser",
                "11-orders",
                "13-sqs",
                "14-domain-events",
                "15-pick-ticket-worker",
                "16-callback-demo",
                "17-container-worker",
                "18-aws-deployment",
                "20-final-walkthrough",
            ]
        )

        self.assertIn("tests/test_callback_integration.py", contract)
        self.assertIn("tests/test_deployment_wiring.py", contract)
        self.assertIn("tests/test_http_order_flow.py", contract)
        self.assertIn("evolved at `11-orders`", contract)
        self.assertIn("Do not collapse the SQS command path", contract)

    def test_normalization_adds_stage_owned_teaching_artifacts(self):
        stage_names = [
            "07-api-gateway",
            "08-relational-persistence",
            "03-pi-http-server",
            "04-browser",
            "11-orders",
            "13-sqs",
            "14-domain-events",
            "15-pick-ticket-worker",
            "16-callback-demo",
            "17-container-worker",
            "18-aws-deployment",
            "20-final-walkthrough",
        ]
        stage_names.sort(key=lambda name: int(name.split("-", 1)[0]))
        blueprint = {
            "components": [],
            "contracts": [],
            "stages": [
                {
                    "name": name,
                    "evolved_components": [],
                    "required_paths": [],
                }
                for name in stage_names
            ],
        }

        normalized = normalize_blueprint_continuity(blueprint, stage_names)
        stage07 = next(stage for stage in normalized["stages"] if stage["name"] == "07-api-gateway")
        stage08 = next(stage for stage in normalized["stages"] if stage["name"] == "08-relational-persistence")
        stage11 = next(stage for stage in normalized["stages"] if stage["name"] == "11-orders")
        stage15 = next(stage for stage in normalized["stages"] if stage["name"] == "15-pick-ticket-worker")
        stage20 = next(stage for stage in normalized["stages"] if stage["name"] == "20-final-walkthrough")

        self.assertIn("tests/test_web_app.js", stage07["required_paths"])
        self.assertIn("src/db_adapter.py", stage08["required_paths"])
        self.assertIn("tests/test_http_order_flow.py", stage11["required_paths"])
        self.assertIn("tests/test_sqlite_orders.py", stage11["required_paths"])
        self.assertIn(
            "deploy/pick-ticket-worker/tinywms-pick-ticket-worker.service.in",
            stage15["required_paths"],
        )
        self.assertIn("docs/demo-runbook.md", stage20["required_paths"])
        self.assertIn("tests/test_end_to_end_walkthrough.py", stage20["required_paths"])

    def test_stage_required_path_overrides_later_component_path_ownership(self):
        blueprint_data = self.blueprint()
        blueprint_data["stages"][0]["required_paths"] = ["src/inventory.py"]
        blueprint = validate_blueprint(blueprint_data, self.STAGES)

        validate_snapshot_against_blueprint(
            "00-repository",
            {
                "README.md": "x",
                "docs/architecture.md": "x",
                "docs/data-contracts.md": "x",
                "data/.gitkeep": "",
                "src/.gitkeep": "",
                "tests/.gitkeep": "",
                "src/inventory.py": "explicitly required early",
            },
            blueprint,
            self.STAGES,
        )

    def test_earlier_required_path_remains_available_before_later_component_adopts_it(self):
        stage_names = ["00-repository", "01-middle", "02-app"]
        blueprint = {
            "stages": [
                {"name": "00-repository", "required_paths": ["README.md"]},
                {"name": "01-middle", "required_paths": []},
                {"name": "02-app", "required_paths": []},
            ],
            "components": [
                {
                    "id": "later-app",
                    "introduced_stage": "02-app",
                    "retired_after_stage": None,
                    "paths": ["README.md", "src/future.py"],
                }
            ],
            "contracts": [],
        }

        validate_snapshot_against_blueprint(
            "01-middle",
            {"README.md": "inherited from Stage 0"},
            blueprint,
            stage_names,
        )
        with self.assertRaisesRegex(ValueError, "src/future.py"):
            validate_snapshot_against_blueprint(
                "01-middle",
                {
                    "README.md": "inherited from Stage 0",
                    "src/future.py": "still too early",
                },
                blueprint,
                stage_names,
            )

    def test_rejects_incomplete_stage_component_classification(self):
        blueprint = self.blueprint()
        blueprint["stages"][1]["reused_components"] = []
        with self.assertRaisesRegex(ValueError, "component classification is incomplete"):
            validate_blueprint(blueprint, self.STAGES)

    def test_component_dependency_may_reference_a_contract(self):
        blueprint = self.blueprint()
        blueprint["components"][1]["dependencies"].append("inventory-json")
        validate_blueprint(blueprint, self.STAGES)

    def test_rejects_unresolved_component_dependency(self):
        blueprint = self.blueprint()
        blueprint["components"][1]["dependencies"].append("missing-id")
        with self.assertRaisesRegex(ValueError, "unknown component or contract dependency"):
            validate_blueprint(blueprint, self.STAGES)

    def test_unknown_contract_component_reports_field_and_declared_ids(self):
        blueprint = self.blueprint()
        blueprint["contracts"][0]["producer_components"] = ["missing-inventory-producer"]
        blueprint["contracts"][0]["consumer_components"] = ["lambda-order-handler"]
        with self.assertRaises(ValueError) as raised:
            validate_blueprint(blueprint, self.STAGES)
        message = str(raised.exception)
        self.assertIn("producer_components references unknown component 'missing-inventory-producer'", message)
        self.assertIn("consumer_components references unknown component 'lambda-order-handler'", message)
        self.assertIn("inventory-cli", message)

    def test_normalizes_component_and_contract_continuity_for_every_stage(self):
        blueprint = self.blueprint()
        for stage in blueprint["stages"]:
            stage["added_components"] = []
            stage["reused_components"] = []
            stage["introduced_contracts"] = []
            stage["inherited_contracts"] = []

        normalized = normalize_blueprint_continuity(blueprint, self.STAGES)

        self.assertEqual(normalized["stages"][0]["added_components"], ["repository-scaffold"])
        self.assertEqual(normalized["stages"][1]["added_components"], ["inventory-cli"])
        self.assertEqual(normalized["stages"][1]["reused_components"], ["repository-scaffold"])
        self.assertEqual(normalized["stages"][1]["introduced_contracts"], ["inventory-json"])
        validate_blueprint(normalized, self.STAGES)

    def test_final_reference_normalizes_model_continuity_bookkeeping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            reference_dir = root / "reference" / "01-json"
            files = self.reference_files()
            invalid_blueprint = self.blueprint()
            for stage in invalid_blueprint["stages"]:
                stage["added_components"] = []
                stage["reused_components"] = []
                stage["introduced_contracts"] = []
                stage["inherited_contracts"] = []
            files[BLUEPRINT_NAME] = json.dumps(invalid_blueprint, indent=2) + "\n"

            def requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "01-json",
                            "summary": "reference with incomplete derived bookkeeping",
                            "files": [
                                {"path": path, "content": content}
                                for path, content in files.items()
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            generate_final_reference(
                prompt_dir,
                reference_dir,
                seed_output_root=None,
                api_key="test-key",
                requester=requester,
                max_validation_retries=0,
            )

            written = json.loads((reference_dir / BLUEPRINT_NAME).read_text(encoding="utf-8"))
            self.assertEqual(written["stages"][1]["added_components"], ["inventory-cli"])
            self.assertEqual(written["stages"][1]["reused_components"], ["repository-scaffold"])

    def test_final_reference_preserves_an_existing_valid_blueprint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            reference_dir = root / "reference" / "01-json"
            reference_dir.mkdir(parents=True)
            stable_blueprint = self.blueprint()
            (reference_dir / BLUEPRINT_NAME).write_text(
                json.dumps(stable_blueprint, indent=2) + "\n",
                encoding="utf-8",
            )

            files = self.reference_files()
            regenerated_blueprint = self.blueprint()
            regenerated_blueprint["components"][1]["inbound_contracts"] = [
                "sql-relational-persistence"
            ]
            files[BLUEPRINT_NAME] = json.dumps(regenerated_blueprint, indent=2) + "\n"

            def requester(generation_input, schema, model, api_key, base_url):
                return {
                    "stages": [
                        {
                            "name": "01-json",
                            "summary": "reference with a newly invented contract ID",
                            "files": [
                                {"path": path, "content": content}
                                for path, content in files.items()
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            generate_final_reference(
                prompt_dir,
                reference_dir,
                seed_output_root=None,
                api_key="test-key",
                requester=requester,
                max_validation_retries=0,
            )

            written = json.loads((reference_dir / BLUEPRINT_NAME).read_text(encoding="utf-8"))
            self.assertEqual(written, normalize_blueprint_continuity(stable_blueprint, self.STAGES))

    def test_final_reference_retry_receives_the_rejected_blueprint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            reference_dir = root / "reference" / "01-json"
            valid_files = self.reference_files()
            calls = []

            def reference_requester(generation_input, schema, model, api_key, base_url):
                calls.append(generation_input)
                if len(calls) == 1:
                    invalid_files = dict(valid_files)
                    invalid_blueprint = self.blueprint()
                    invalid_blueprint["contracts"][0]["consumer_components"] = [
                        "lambda-order-handler"
                    ]
                    invalid_files[BLUEPRINT_NAME] = json.dumps(invalid_blueprint, indent=2) + "\n"
                    return {
                        "stages": [
                            {
                                "name": "01-json",
                                "summary": "reference with a dangling component ID",
                                "files": [
                                    {"path": path, "content": content}
                                    for path, content in invalid_files.items()
                                ],
                                "delete_files": [],
                            }
                        ]
                    }

                self.assertIn("PREVIOUS REJECTED STRUCTURED PLAN", generation_input)
                self.assertIn("lambda-order-handler", generation_input)
                self.assertIn("declared component IDs", generation_input)
                return {
                    "stages": [
                        {
                            "name": "01-json",
                            "summary": "corrected final reference",
                            "files": [
                                {"path": path, "content": content}
                                for path, content in valid_files.items()
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            generate_final_reference(
                prompt_dir,
                reference_dir,
                seed_output_root=None,
                api_key="test-key",
                requester=reference_requester,
                max_validation_retries=1,
            )

            self.assertEqual(len(calls), 2)
            self.assertTrue((reference_dir / BLUEPRINT_NAME).is_file())

    def test_final_reference_drives_forward_generation_without_leaking_blueprint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            reference_dir = root / "reference" / "01-json"
            reference_files = self.reference_files()

            def reference_requester(generation_input, schema, model, api_key, base_url):
                self.assertIn("FINAL-FIRST REFERENCE REQUIREMENT", generation_input)
                return {
                    "stages": [
                        {
                            "name": "01-json",
                            "summary": "complete final reference",
                            "files": [
                                {"path": path, "content": content}
                                for path, content in reference_files.items()
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            generate_final_reference(
                prompt_dir,
                reference_dir,
                api_key="test-key",
                requester=reference_requester,
            )

            calls = []

            def forward_requester(generation_input, schema, model, api_key, base_url):
                names = schema["properties"]["stages"]["items"]["properties"]["name"]["enum"]
                calls.append((generation_input, names))
                if names == ["00-repository"]:
                    self.assertIn("future_components_do_not_implement", generation_input)
                    return {
                        "stages": [
                            {
                                "name": "00-repository",
                                "summary": "empty scaffold",
                                "files": [
                                    {"path": "README.md", "content": "# Repository\n"},
                                    {"path": "docs/architecture.md", "content": "# Architecture\n"},
                                    {"path": "docs/data-contracts.md", "content": "# Contracts\n"},
                                    {"path": "data/.gitkeep", "content": ""},
                                    {"path": "src/.gitkeep", "content": ""},
                                    {"path": "tests/.gitkeep", "content": ""},
                                ],
                                "delete_files": [],
                            }
                        ]
                    }
                self.assertEqual(names, ["01-json"])
                self.assertIn("FROZEN BASELINE SNAPSHOT: 00-repository", generation_input)
                self.assertIn("REFERENCE IMPLEMENTATION EXCERPTS", generation_input)
                self.assertIn("src/inventory.py", generation_input)
                self.assertIn("import json", generation_input)
                return {
                    "stages": [
                        {
                            "name": "01-json",
                            "summary": "inventory JSON",
                            "files": [
                                {"path": "README.md", "content": reference_files["README.md"]},
                                {"path": "data/inventory.json", "content": reference_files["data/inventory.json"]},
                                {
                                    "path": "data/inventory.schema.json",
                                    "content": reference_files["data/inventory.schema.json"],
                                },
                                {"path": "src/inventory.py", "content": reference_files["src/inventory.py"]},
                                {
                                    "path": "tests/test_inventory.py",
                                    "content": reference_files["tests/test_inventory.py"],
                                },
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            output_root = root / "generated"
            generated = generate_course_forward(
                prompt_dir,
                output_root,
                reference_dir,
                api_key="test-key",
                requester=forward_requester,
            )

            self.assertEqual([path.name for path in generated], self.STAGES)
            self.assertEqual(len(calls), 2)
            self.assertFalse((output_root / "01-json" / BLUEPRINT_NAME).exists())
            self.assertTrue((output_root / "01-json" / "src" / "inventory.py").exists())

    def test_final_reference_borrows_predecessor_checkpoint_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompt_dir = self.make_course(root)
            seed_root = root / "generated"
            seed_dir = seed_root / "00-repository"
            seed_files = {
                "README.md": "# Frozen repository checkpoint\n",
                "docs/architecture.md": "# Frozen architecture\n",
                "docs/data-contracts.md": "# Frozen contracts\n",
                "data/.gitkeep": "",
                "src/.gitkeep": "",
                "tests/.gitkeep": "",
                "infra/lambda.yaml": (
                    "AWSTemplateFormatVersion: '2010-09-09'\n"
                    "Resources:\n"
                    "  Function:\n"
                    "    Type: AWS::Lambda::Function\n"
                    "    Properties:\n"
                    "      Handler: src.lambda_inventory.handler\n"
                    "      Code:\n"
                    "        ZipFile: |\n"
                    "          def handler(event, context): return {}\n"
                ),
                "infra/rds.yaml": (
                    "AWSTemplateFormatVersion: '2010-09-09'\n"
                    "Parameters:\n"
                    "  DatabaseName:\n"
                    "    Type: String\n"
                    "Resources:\n"
                    "  Subnets:\n"
                    "    Type: AWS::RDS::DBSubnetGroup\n"
                    "    Properties:\n"
                    "      SubnetIds: []\n"
                    "  Database:\n"
                    "    Type: AWS::RDS::DBInstance\n"
                    "    Properties:\n"
                    "      MasterUsername: tinywms\n"
                    "      MasterUserPassword: change-me-in-a-real-deployment\n"
                ),
                "deploy/rds/README.md": "old RDS instructions\n",
            }
            for relative_name, content in seed_files.items():
                target = seed_dir / relative_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            (seed_dir / MANIFEST_NAME).write_text(
                json.dumps(
                    {
                        "stage": "00-repository",
                        "source_prompt": "00-repository.md",
                        "generated_files": sorted(seed_files),
                    }
                ),
                encoding="utf-8",
            )
            seed_before = {
                path.relative_to(seed_dir).as_posix(): path.read_text(encoding="utf-8")
                for path in seed_dir.rglob("*")
                if path.is_file()
            }
            reference_files = self.reference_files()

            def reference_requester(generation_input, schema, model, api_key, base_url):
                self.assertIn("FROZEN BASELINE SNAPSHOT: 00-repository", generation_input)
                self.assertIn("Frozen means the source checkpoint on disk is read-only", generation_input)
                self.assertIn("REFERENCE SEED REPAIR REQUIREMENTS", generation_input)
                self.assertIn("docs/architecture.md", generation_input)
                delta_paths = {
                    "README.md",
                    "data/inventory.json",
                    "data/inventory.schema.json",
                    "src/inventory.py",
                    "tests/test_inventory.py",
                    BLUEPRINT_NAME,
                }
                return {
                    "stages": [
                        {
                            "name": "01-json",
                            "summary": "final reference delta over the frozen checkpoint",
                            "files": [
                                {"path": path, "content": reference_files[path]}
                                for path in sorted(delta_paths)
                            ],
                            "delete_files": [],
                        }
                    ]
                }

            reference_dir = root / "reference" / "01-json"
            generate_final_reference(
                prompt_dir,
                reference_dir,
                seed_output_root=seed_root,
                api_key="test-key",
                requester=reference_requester,
            )

            seed_after = {
                path.relative_to(seed_dir).as_posix(): path.read_text(encoding="utf-8")
                for path in seed_dir.rglob("*")
                if path.is_file()
            }
            self.assertEqual(seed_after, seed_before)
            self.assertEqual(
                (reference_dir / "docs" / "architecture.md").read_text(encoding="utf-8"),
                "# Frozen architecture\n",
            )
            manifest = json.loads((reference_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["inherits_from"], "00-repository")
            self.assertIn("infra/lambda.yaml", manifest["changed_files"])
            self.assertIn("infra/rds.yaml", manifest["changed_files"])
            self.assertIn("deploy/rds/README.md", manifest["changed_files"])
            self.assertIn(
                "Handler: index.handler",
                (reference_dir / "infra" / "lambda.yaml").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "SubnetIds: !Ref DatabaseSubnetIds",
                (reference_dir / "infra" / "rds.yaml").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
