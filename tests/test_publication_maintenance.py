"""Synthetic approval fixtures; the actual owner reply is separately byte-bound."""
import copy
import hashlib
from pathlib import Path
import unittest

from house import council, maintenance as owner
from tests import test_council
from tests.test_wake_policy import approval


class PublicationMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.h = test_council.CouncilTests()
        self.h.setUp()
        self.h.authorize()
        self.h.event("council-wake-authorize", approval())
        old = owner.protected_manifest(self.h.state)
        manifest = old | {p: "d" * 64 for p in owner.ALLOWED_CHANGES[owner.PUBLICATION_SCOPE]}
        self.data = {
            "scope": owner.PUBLICATION_SCOPE,
            "approval_sha256": owner.SOURCES[owner.PUBLICATION_SCOPE],
            "house": self.h.state["house_id"], "owner_id": council.OWNER_ID,
            "source_head": "a" * 40, "source_sha256": "b" * 64,
            "protected_files": manifest, "previous_manifest_sha256": owner.fingerprint(old),
            "previous_runtime_sha256": "c" * 64, "runtime_sha256": "d" * 64,
            "test_output_sha256": "e" * 64, "test_count": 1,
        }

    def test_exact_approval_one_use_and_authority_unchanged(self):
        artifact = Path(__file__).resolve().parents[1] / "evidence/publication-worker-repair/owner-authorization.md"
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),
                         self.data["approval_sha256"])
        before = copy.deepcopy(self.h.state)
        self.h.event("owner-migrate", self.data)
        for key in ("council", "proposals", "wake_policy", "rules", "rule_revision", "life"):
            self.assertEqual(before.get(key), self.h.state.get(key))
        self.assertEqual(owner.protected_manifest(self.h.state), self.data["protected_files"])
        self.h.reject("owner-migrate", self.data, "already used")

    def test_outside_scope_and_wrong_manifest_refused(self):
        for path in ("house/providers.py", "house/steward.py", "house/council.py",
                     "house/wake_policy.py"):
            bad = copy.deepcopy(self.data)
            bad["protected_files"][path] = "f" * 64
            self.h.reject("owner-migrate", bad, "outside.*scope")
        for path in ("house/publication_worker.py",):
            bad = copy.deepcopy(self.data)
            del bad["protected_files"][path]
            self.h.reject("owner-migrate", bad, "replacement manifest")
        bad = copy.deepcopy(self.data)
        bad["protected_files"]["house/unapproved.py"] = "f" * 64
        self.h.reject("owner-migrate", bad, "replacement manifest")

    def test_live_resident_missing_tests_and_wrong_approval_refused(self):
        self.h.reject("owner-migrate", self.data | {"test_count": 0}, "passing tests")
        self.h.reject("owner-migrate", self.data | {"approval_sha256": "0" * 64}, "approval")
        self.h.state.setdefault("life", {}).setdefault("runs", {})["live"] = {"status": "active"}
        self.h.reject("owner-migrate", self.data, "drain native")
