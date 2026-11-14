"""Owner routing scope does not delegate authority or change protected limits."""
import copy
import hashlib
from pathlib import Path
import unittest

from house import maintenance as owner, project_work
from tests import test_owner_maintenance


class ProjectWorkScopeTests(unittest.TestCase):
    def test_one_use_scope_adds_only_routing_and_preserves_active_rules(self):
        fixture = test_owner_maintenance.OwnerMaintenanceTests(); fixture.setUp()
        fixture.h.event("owner-migrate", fixture.migration())
        h = fixture.h
        old = owner.protected_manifest(h.state)
        self.assertEqual(project_work.SCOPE, owner.PROJECT_WORK_SCOPE)
        self.assertFalse(project_work.enabled(h.state))
        data = fixture.migration() | {"scope": owner.PROJECT_WORK_SCOPE,
            "approval_sha256": owner.SOURCES[owner.PROJECT_WORK_SCOPE],
            "previous_manifest_sha256": owner.fingerprint(old),
            "protected_files": old | {p: "f" * 64 for p in owner.ALLOWED_CHANGES[owner.PROJECT_WORK_SCOPE]}}
        path = Path(__file__).parents[1] / "evidence/project-work-routing/owner-scope.md"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), data["approval_sha256"])
        missing = copy.deepcopy(data); missing["protected_files"].pop("house/project_work.py")
        h.reject("owner-migrate", missing, "manifest")
        for name in ("house/providers.py", "house/council.py", "house/steward.py", "house/wake_policy.py", "house/mailbox.py"):
            bad = copy.deepcopy(data); bad["protected_files"][name] = "e" * 64
            h.reject("owner-migrate", bad, "outside.*scope")
        h.reject("owner-migrate", data | {"approval_sha256": "0" * 64}, "approval")
        h.reject("owner-migrate", data | {"test_count": 0}, "passing tests")
        before = copy.deepcopy(h.state)
        h.event("owner-migrate", data)
        self.assertTrue(project_work.enabled(h.state))
        for key in ("council", "proposals", "wake_policy", "rules", "rule_revision", "life", "tasks", "shelf"):
            self.assertEqual(before.get(key), h.state.get(key))
        h.reject("owner-migrate", data, "already used")
