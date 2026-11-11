"""Loader-accurate import test: imports gnothi exactly the way Hermes's own
plugin loader does (spec_from_file_location on __init__.py, with
submodule_search_locations set to the plugin dir, under a package name), then
calls register() against a fake ctx and checks the real registrations — not
just static source shape (DEV-12)."""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent


class FakeCtx:
    def __init__(self):
        self.tools = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": Path(path), "description": description}


def _load_plugin_module(module_name: str) -> types.ModuleType:
    init_file = PLUGIN_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name, init_file, submodule_search_locations=[str(PLUGIN_DIR)])
    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name
    module.__path__ = [str(PLUGIN_DIR)]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class LoaderDiscovery(unittest.TestCase):
    def test_register_wires_all_three_tools_and_the_skill(self):
        module = _load_plugin_module("gnothi_loader_discovery_test")
        ctx = FakeCtx()
        module.register(ctx)

        self.assertEqual(set(ctx.tools.keys()), {"verify_claim", "evaluate_difference", "qualify_conclusion"})
        for name, entry in ctx.tools.items():
            self.assertEqual(entry["toolset"], "gnothi")
            self.assertTrue(callable(entry["handler"]))
            self.assertIn("description", entry["schema"])
            self.assertTrue(entry["schema"]["description"].strip())
            self.assertIn("parameters", entry["schema"])

        self.assertIn("gnothi", ctx.skills)
        skill_path = ctx.skills["gnothi"]["path"]
        self.assertTrue(skill_path.exists(), f"bundled SKILL.md missing at {skill_path}")

    def test_registered_handlers_actually_work_end_to_end(self):
        module = _load_plugin_module("gnothi_loader_discovery_test2")
        ctx = FakeCtx()
        module.register(ctx)

        out = json.loads(ctx.tools["verify_claim"]["handler"]({
            "claim": "x", "metric": "mean", "evidence": {"values": [1, 2, 3], "claimed_value": 2.0},
        }))
        self.assertEqual(out["verdict"], "true")

        out2 = json.loads(ctx.tools["evaluate_difference"]["handler"]({
            "data_a": [1, 2, 3, 4, 5], "data_b": [1, 2, 3, 4, 5], "paired": False,
        }))
        self.assertIn(out2["verdict"], ("inconclusive", "supported", "not_supported"))


if __name__ == "__main__":
    unittest.main()
