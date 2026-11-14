"""Public Workshop projection: declared readiness and explicit project links only."""
import json

from house.body import export, public_task
from tests.support import HouseCase


def fake_task(ready="absent", project="absent", title="Work", status="open"):
    task = {"title": title, "status": status, "owner": None, "until": 0, "generation": 0,
            "token": "secret-token", "used_tokens": ["secret-token"], "description": "private note"}
    if ready != "absent":
        task["ready"] = ready
    if project != "absent":
        task["project"] = project
    return task


class PublicTaskProjectionTests(HouseCase):
    def test_readiness_exported_only_when_recorded(self):
        ready = public_task("a-ready", fake_task(ready=True))
        blocked = public_task("a-blocked", fake_task(ready=False))
        unknown = public_task("a-unknown", fake_task())
        self.assertTrue(ready["ready"])
        self.assertFalse(blocked["ready"])
        self.assertNotIn("ready", unknown)

    def test_project_exported_only_when_recorded_and_never_inferred(self):
        linked = public_task("project-work-visibility-build", fake_task(project="night-ferry"))
        alias = public_task("other", {**fake_task(), "project_id": "signal-garden"})
        tricky = public_task("project-x", fake_task(title="project: night-ferry build"))
        self.assertEqual(linked["project"], "night-ferry")
        self.assertEqual(linked["project_id"], "night-ferry")
        self.assertEqual(alias["project"], "signal-garden")
        self.assertEqual(alias["project_id"], "signal-garden")
        self.assertNotIn("project", tricky)
        self.assertNotIn("project_id", tricky)
        empty = public_task("empty", fake_task(project="   "))
        self.assertNotIn("project", empty)
        self.assertNotIn("ready", empty)

    def test_public_task_hides_tokens_notes_and_descriptions(self):
        exported = public_task("work", fake_task(ready=True, project="night-ferry"))
        public = json.dumps(exported)
        for secret in ("secret-token", "private note"):
            self.assertNotIn(secret, public)
        self.assertEqual(set(exported), {"id", "title", "owner", "status", "until",
                                          "generation", "ready", "project", "project_id"})

    def test_journal_ready_transitions_keep_historical_frames_unknown(self):
        self.record.append("task", "alice", {"task": "work", "title": "Work", "description": "Bounded"})
        before = export(self.record)
        frame_before = next(f for f in before["frames"] if f["tasks"])
        task_before = next(t for t in frame_before["tasks"] if t["id"] == "work")
        self.assertNotIn("ready", task_before)
        self.assertNotIn("project", task_before)
        self.assertNotIn("project_id", task_before)

        self.cli("ready", "work", "--as", "alice", "--expect", "0")
        after = export(self.record)
        # Historical frames must never gain future readiness.
        self.assertEqual(after["frames"][:len(before["frames"])], before["frames"])
        task_after = next(t for t in after["frames"][-1]["tasks"] if t["id"] == "work")
        self.assertTrue(task_after["ready"])
        self.assertEqual(task_after["generation"], 1)

        self.cli("ready", "work", "--as", "alice", "--expect", "1", "--blocked")
        blocked_export = export(self.record)
        self.assertEqual(blocked_export["frames"][:len(before["frames"])], before["frames"])
        task_blocked = next(t for t in blocked_export["frames"][-1]["tasks"] if t["id"] == "work")
        self.assertFalse(task_blocked["ready"])
        self.assertEqual(task_blocked["generation"], 2)

    def test_exported_history_has_no_private_task_fields(self):
        self.record.append("task", "alice", {"task": "work", "title": "Work", "description": "SECRET-NOTE"})
        self.cli("ready", "work", "--as", "alice", "--expect", "0")
        public = json.dumps(export(self.record))
        self.assertNotIn("SECRET-NOTE", public)
        self.assertNotIn("used_tokens", public)


if __name__ == "__main__":
    import unittest
    unittest.main()
