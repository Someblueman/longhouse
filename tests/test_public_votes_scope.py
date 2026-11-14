"""The public projection migration cannot change governance or launchers."""
import copy
import hashlib
from pathlib import Path
import unittest

from house import maintenance as owner
from tests import test_owner_maintenance


class PublicVotingScopeTests(unittest.TestCase):
    def test_exact_one_use_scope_preserves_rules_and_rejects_other_changes(self):
        fixture = test_owner_maintenance.OwnerMaintenanceTests(); fixture.setUp()
        fixture.h.event("owner-migrate", fixture.migration())
        h = fixture.h
        old = owner.protected_manifest(h.state)
        data = fixture.migration() | {"scope": owner.VOTING_SCOPE,
            "approval_sha256": owner.SOURCES[owner.VOTING_SCOPE],
            "previous_manifest_sha256": owner.fingerprint(old),
            "protected_files": old | {p: "f" * 64 for p in owner.ALLOWED_CHANGES[owner.VOTING_SCOPE]}}
        path = Path(__file__).parents[1] / "evidence/public-voting-history/owner-scope.md"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), data["approval_sha256"])
        for path in ("house/providers.py", "house/council.py", "house/steward.py", "house/home.py"):
            bad = copy.deepcopy(data); bad["protected_files"][path] = "e" * 64
            h.reject("owner-migrate", bad, "outside.*scope")
        h.reject("owner-migrate", data | {"approval_sha256": "0" * 64}, "approval")
        h.reject("owner-migrate", data | {"test_count": 0}, "passing tests")
        before = copy.deepcopy(h.state)
        h.event("owner-migrate", data)
        for key in ("council", "proposals", "wake_policy", "rules", "rule_revision", "life"):
            self.assertEqual(before.get(key), h.state.get(key))
        h.reject("owner-migrate", data, "already used")
