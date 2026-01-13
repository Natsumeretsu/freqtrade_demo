from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "tools" / "local_rag_eval_models.py"


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("local_rag_eval_models", str(_SCRIPT_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLocalRagEvalModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_eval_module()

    def test_model_slug_is_stable(self) -> None:
        m = self.mod
        self.assertEqual(m._model_slug("Xenova/bge-m3"), "xenova__bge-m3")
        self.assertEqual(m._model_slug("Xenova/bge-large-zh-v1.5"), "xenova__bge-large-zh-v1.5")
        self.assertEqual(m._model_slug("Qwen/Qwen3-Embedding-8B"), "qwen__qwen3-embedding-8b")
        self.assertEqual(m._model_slug("  "), "unknown")

    def test_match_expected_uses_suffix(self) -> None:
        m = self.mod
        fp = r"D:\Code\python\freqtrade_demo\docs\knowledge\source_registry.md"
        self.assertTrue(m._match_any_expected(fp, ("docs/knowledge/source_registry.md",)))
        self.assertTrue(m._match_any_expected(fp.lower(), ("docs/knowledge/source_registry.md",)))
        self.assertFalse(m._match_any_expected(fp, ("docs/knowledge/not_exist.md",)))

    def test_load_suite_default_cases(self) -> None:
        m = self.mod
        cases_path = _REPO_ROOT / "docs" / "tools" / "vbrain" / "local_rag_eval_cases.json"
        suite = m._load_suite(cases_path)
        self.assertGreaterEqual(suite.default_k, 1)
        self.assertGreaterEqual(len(suite.cases), 5)
        self.assertTrue(any("Alpha158" in c.query for c in suite.cases))


if __name__ == "__main__":
    unittest.main()
