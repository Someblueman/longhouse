"""A failed integration gate keeps bounded, private diagnostic evidence."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from house import test_sandbox
from house.home_work import contribution, git, room
from house.integrate import DIAGNOSTIC_LIMIT, failure_diagnostics, integrate
from tests.support import HouseCase


PASSING = (
    "import pathlib,unittest\n"
    "class Document(unittest.TestCase):\n"
    " def test_document(self): self.assertEqual(pathlib.Path('document.txt').read_text(), 'changed\\n')\n")

FAILING = (
    "import unittest\n"
    "class Document(unittest.TestCase):\n"
    " def test_document(self):\n"
    "  self.assertEqual('actual-value-marker-741', 'expected-value-marker-963')\n")


class DiagnosticsTailTests(unittest.TestCase):
    def test_large_invalid_utf8_tail_is_clipped_and_identified(self):
        with tempfile.TemporaryDirectory(prefix="house-diagnostics-") as directory:
            root = Path(directory)
            log = root / "large.tests.log"
            data = (b"start\n" + b"\xff\xfe broken \x80 bytes\n"
                    + b"x" * (DIAGNOSTIC_LIMIT * 2) + b"\nfinal-failure-marker\n")
            log.write_bytes(data)
            diagnostics = failure_diagnostics(log, 3)
            self.assertEqual(diagnostics["bytes"], len(data))
            self.assertEqual(diagnostics["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(diagnostics["tail_bytes"], DIAGNOSTIC_LIMIT)
            self.assertTrue(diagnostics["clipped"])
            self.assertIn("final-failure-marker", diagnostics["tail"])
            small = root / "small.tests.log"
            small.write_bytes(b"one\xfftwo")
            tiny = failure_diagnostics(small, 1)
            self.assertFalse(tiny["clipped"])
            self.assertEqual(tiny["bytes"], 7)
            self.assertEqual(tiny["tail"], "one\ufffdtwo")
            missing = failure_diagnostics(root / "absent.tests.log", 2)
            self.assertEqual(missing["kind"], "failed-tests")
            self.assertIn("unavailable", missing["reason"])
            self.assertNotIn("tail", missing)


@unittest.skipIf(os.environ.get("EMBERHALL_CANDIDATE_SANDBOX") == "1",
                 "host-only sandbox boundary fixture cannot nest macOS sandboxes")
class IntegrationDiagnosticsTests(HouseCase):
    def setUp(self):
        super().setUp()
        self.record.append("arrive", "watch-keeper", {"name": "Clock"})
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_document.py").write_text(
            "import pathlib,unittest\nclass Document(unittest.TestCase):\n"
            " def test_document(self): self.assertIn(pathlib.Path('document.txt').read_text(), ['base\\n','changed\\n'])\n")
        (self.repo / "document.txt").write_text("base\n")
        git(self.repo, "add", ".")
        git(self.repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test", "-c", "user.email=test@local",
            "commit", "-m", "Base source")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.private = self.record.common / "house-home"
        self.private.mkdir()

    def candidate(self, run, test_source):
        self.record.append("life", "watch-keeper", {"kind": "run-start", "run": run,
            "resident": "author-" + run, "agent": "codex", "model": "gpt-6.1-sol",
            "source_head": self.base, "workspace": "residents/" + run,
            "policy_revision": "fixture", "mode": "work"})
        self.record.append("arrive", "author-" + run, {"name": "Author"})
        workspace = room(self.record, self.private, run, self.base)
        (workspace / "document.txt").write_text("changed\n")
        (workspace / "tests/test_document.py").write_text(test_source)
        (self.private / run).mkdir()
        contribution(workspace, self.base, self.private / run / "contribution.json", journal_artifacts={})
        self.record.append("life", "watch-keeper", {"kind": "run-finish", "run": run,
            "outcome": "success", "exit_code": 0, "usage": {}, "elapsed_seconds": 1})
        return workspace

    def notices(self):
        return [event for event in self.record.read()[1]
                if event["op"] == "say" and event["data"].get("text", "").startswith("house-integration-v1 ")]

    def notice_payload(self, event):
        return json.loads(event["data"]["text"][len("house-integration-v1 "):])

    def test_failed_gate_reports_hashed_tail_and_excludes_it_from_journal(self):
        self.candidate("one", FAILING)
        result = integrate(self.record, "one", "alice", publish=True)
        self.assertEqual(result["status"], "tests-failed")
        self.assertNotEqual(result["test_exit"], 0)
        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["kind"], "failed-tests")
        self.assertEqual(diagnostics["source"], "untrusted candidate output")
        log = self.private / (result["candidate"] + ".tests.log")
        data = log.read_bytes()
        self.assertGreater(len(data), 0)
        self.assertEqual(diagnostics["bytes"], len(data))
        self.assertEqual(diagnostics["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(diagnostics["limit_bytes"], DIAGNOSTIC_LIMIT)
        self.assertEqual(diagnostics["tail_bytes"], min(len(data), DIAGNOSTIC_LIMIT))
        self.assertFalse(diagnostics["clipped"])
        self.assertIn("FAIL: test_document", diagnostics["tail"])
        self.assertIn("actual-value-marker-741", diagnostics["tail"])
        # The private receipt and the full log/candidate stay available privately.
        self.assertEqual(json.loads((self.private / "one/integration.json").read_text()), result)
        self.assertTrue((self.private / result["candidate"]).is_dir())
        # Failed source is never merged.
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.base)
        self.assertEqual((self.repo / "document.txt").read_text(), "base\n")
        # The shared journal notice keeps ordinary outcome fields, not raw output.
        event = self.notices()[-1]
        payload = self.notice_payload(event)
        self.assertNotIn("diagnostics", payload)
        self.assertNotIn("actual-value-marker-741", event["data"]["text"])
        self.assertNotIn(result["candidate"], event["data"]["text"])
        self.assertEqual(payload["status"], "tests-failed")
        self.assertEqual(payload["test_exit"], result["test_exit"])
        self.assertEqual(payload["base"], result["base"])
        self.assertEqual(payload["contribution"], result["contribution"])

    def test_success_and_replay_do_not_manufacture_diagnostics(self):
        self.candidate("one", PASSING)
        accepted = integrate(self.record, "one", "alice", publish=True)
        self.assertEqual(accepted["status"], "integrated")
        self.assertNotIn("diagnostics", accepted)
        path = self.private / "one/integration.json"
        original = path.read_bytes()
        head = git(self.repo, "rev-parse", "HEAD")
        journal = self.record.read()[2]
        self.assertEqual(integrate(self.record, "one", "bob", publish=True), accepted)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(self.record.read()[2], journal)

    def test_old_integrated_receipt_replays_byte_for_byte(self):
        workspace = self.candidate("one", PASSING)
        (self.repo / "document.txt").write_text("changed\n")
        git(self.repo, "add", "document.txt")
        git(self.repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test", "-c",
            "user.email=test@local", "commit", "-m", "Curated acceptance")
        accepted = {"run": "one", "actor": "alice", "status": "integrated",
                    "contribution": git(workspace, "rev-parse", "HEAD"),
                    "canonical_commit": git(self.repo, "rev-parse", "HEAD")}
        path = self.private / "one/integration.json"
        path.write_text(json.dumps(accepted))
        original = path.read_bytes()
        journal = self.record.read()[2]
        self.assertEqual(integrate(self.record, "one", "bob"), accepted)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.record.read()[2], journal)

    def test_changed_candidate_after_passing_tests_gets_honest_reason(self):
        self.candidate("one", PASSING)
        real_run = test_sandbox.run

        def tamper(command, cwd, *, stdout, timeout):
            completed = real_run(command, cwd, stdout=stdout, timeout=timeout)
            (Path(cwd) / "document.txt").write_text("tampered after tests\n")
            return completed

        with patch("house.integrate.test_sandbox.run", side_effect=tamper):
            result = integrate(self.record, "one", "alice", publish=True)
        self.assertEqual(result["status"], "tests-failed")
        self.assertEqual(result["test_exit"], 0)
        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["kind"], "candidate-changed")
        self.assertIn("changed during acceptance", diagnostics["reason"])
        self.assertTrue(diagnostics["dirty"])
        self.assertNotIn("tail", diagnostics)
        self.assertEqual((self.repo / "document.txt").read_text(), "base\n")
        payload = self.notice_payload(self.notices()[-1])
        self.assertNotIn("diagnostics", payload)


if __name__ == "__main__":
    unittest.main()
