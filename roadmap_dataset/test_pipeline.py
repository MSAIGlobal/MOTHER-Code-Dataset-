"""Regression tests for generation, approval, splitting and baseline leakage."""

from argparse import Namespace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from build import export, generate, read_rows, review_packet, write_rows
from merge import merge


class PipelineTest(TestCase):
    def test_reviewed_candidates_merge_against_flat_core(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.jsonl"
            work = root / "drafts"
            reviews = root / "reviews.jsonl"
            reviewed = root / "reviewed"
            merged = root / "merged"
            write_rows(index, [
                {"id": str(i), "document": f"{i}.pdf", "group": str(i), "text": str(i)}
                for i in range(4)
            ])

            def fake_teacher(endpoint, model, unit, token, timeout):
                return {
                    "topic": "Arithmetic", "difficulty": "easy", "turns": [
                        {"question": f"Implement addition by {unit['id']} for integers.",
                         "answer": f"Use integer addition.\n\n```python\ndef add(x):\n    return x + {unit['id']}\n```"},
                        {"question": "What happens with negative integers?",
                         "answer": "Addition works with negative and positive integers."},
                        {"question": "How can I check the zero-input case?",
                         "answer": f"```python\nassert add(0) == {unit['id']}\n```"},
                    ],
                }

            settings = Namespace(index=index, work=work, limit=None, retries=0, timeout=1,
                                 endpoint="http://localhost", model="fixture")
            with patch("build.complete", side_effect=fake_teacher) as teacher:
                self.assertFalse(generate(settings))
                self.assertFalse(generate(settings))
                self.assertEqual(teacher.call_count, 4)

            review_packet(work, reviews)
            approved = [{**row, "decision": "approve"} for row in read_rows(reviews)]
            write_rows(reviews, [{**approved[0], "fingerprint": "stale"}, *approved[1:]])
            with self.assertRaisesRegex(ValueError, "Stale"):
                export(work, reviews, reviewed, 42)
            write_rows(reviews, approved)
            export(work, reviews, reviewed, 42)

            first_train = next(read_rows(reviewed / "train.jsonl"))
            question = first_train["messages"][0]["content"]
            flat = {"category": "code_cot", "text": f"Question:\n\n{question}\n\nAnswer: Baseline.",
                    "source": "fixture"}
            baseline_train = root / "base-train.jsonl"
            baseline_test = root / "base-test.jsonl"
            write_rows(baseline_test, [flat])
            write_rows(baseline_train, [flat, {"question": "Write a loop", "answer": "Use a for loop"}])
            merge(Namespace(baseline_train=[baseline_train], baseline_validation=None,
                            baseline_test=[baseline_test], roadmap=reviewed, out=merged,
                            allow_opaque_text=False))
            report = json.loads((merged / "merge-report.json").read_text())
            self.assertEqual(report["inputs"][1]["counts"]["exact_duplicate"], 1)
            self.assertEqual(report["inputs"][-1]["counts"]["prompt_conflict"], 1)
            self.assertEqual(report["inputs"][-1]["counts"]["cross_split_overlap"], 1)
            self.assertEqual(report["output_rows"], {"test": 2, "train": 2, "validation": 1})
            self.assertEqual(len(list(read_rows(merged / "roadmap-lineage.jsonl"))), 3)
