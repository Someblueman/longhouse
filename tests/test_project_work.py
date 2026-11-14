"""Disposable real journals and CLI/mailbox calls; no live owner or model trial."""
import base64
import copy
import json
import uuid
from unittest.mock import patch

from house import council, life, project_work, shelf_gate
from house.governance import digest
from house.model import apply_event
from house.record import Record
from tests.support import HouseCase
from tests.test_council import approval
from tests.test_mailbox import MailboxCase
from tests.test_shelf import idea


def projects(case):
    """Enact a policy and choose two projects in a separate synthetic house."""
    record = Record(case.new_repo("project-journal"))
    with patch("house.record.uuid.uuid4", side_effect=[uuid.uuid4(), uuid.UUID(council.APPROVED_HOUSE)]):
        record.found("Synthetic project house", "Fixture charter")
    for name in ("alice", "bob", "carol", "dana", life.CONTROLLER):
        record.append("arrive", name, {"name": name})
    def send(op, data, actor="alice"):
        return record.append(op, actor, data)
    send("council-authorize", approval())
    state = record.read()[0]
    send("council-propose", {"proposal": "selection", "mode": "rule", "title": "Fixture selection",
        "text": shelf_gate.REVISED_POLICY_TEXT, "reason": "Synthetic policy fixture", "base": state["rule_revision"]})
    send("task", {"task": "trial", "title": "Fixture", "description": "Synthetic trial"})
    send("claim", {"task": "trial", "expect": 0, "token": "trial", "seconds": 60})
    send("finish", {"task": "trial", "token": "trial", "result": "Synthetic evidence only",
        "artifacts": {"trial.txt": {"sha256": digest("fixture"), "base64": base64.b64encode(b"fixture").decode()}}})
    send("council-trial", {"proposal": "selection", "task": "trial", "evidence": "Fixture"})
    for actor in ("bob", "carol"):
        send("council-endorse", {"proposal": "selection", "evidence": "Fixture"}, actor)
    send("council-notice", {"proposal": "selection", "repository": council.REPOSITORY,
        "issue": council.ISSUE, "comment_id": 42, "text_sha256": digest(shelf_gate.REVISED_POLICY_TEXT)})
    at = record.read()[0]["at"] + council.WAIT_SECONDS + 1
    with patch("house.record.time.time", return_value=at):
        send("council-sync", {"repository": council.REPOSITORY, "issue": council.ISSUE,
            "owner_id": council.OWNER_ID, "checked_at": at, "comments": []})
        send("council-enact", {"proposal": "selection"})
    send("life", {"kind": "identity", "agent": "codex", "model": "gpt-6.1-sol"})
    send("shelf", {"kind": "explore-start", "round": "fixture", "expect": 0, "token": "fixture", "seconds": 60})
    send("shelf", {"kind": "explore-publish", "round": "fixture", "token": "fixture",
                   "ideas": [idea(key) for key in ("a", "b", "c")]})
    for key, picked, seconds in (("later", "a", 86400), ("earlier", "b", 3600)):
        store = record.read()[0]["shelf"]
        candidates = [k for k, v in store["ideas"].items() if v["status"] == "shelved"]
        send("shelf", {"kind": "choice-open", "choice": key,
            "milestones": {k: {"milestone": "A usable fixture", "seconds": seconds} for k in candidates}})
        for actor in ("bob", "carol", "dana"):
            send("shelf", {"kind": "choice-vote", "choice": key, "idea": picked, "reason": "Fixture"}, actor)
    return record


def start_data(run, **extra):
    return {"kind": "run-start", "run": run, "resident": "resident-" + run,
            "agent": "codex", "model": "gpt-6.1-sol", "source_head": "a" * 40,
            "workspace": "residents/" + run, "policy_revision": "fixture", "mode": "work", **extra}


class ProjectAssociationTests(HouseCase):
    def setUp(self):
        super().setUp()
        self.record = projects(self)
        self.repo = self.record.root

    def offer(self, key="work", **extra):
        return self.record.append("task", "alice", {"task": key, "title": "Uninformative title",
            "description": "Explicit owned fixture", **extra})

    def test_actual_cli_bind_block_detach_and_old_events_keep_their_shape(self):
        self.cli("task", "old", "--as", "alice", "--title", "Legacy", "--description", "Legacy")
        self.cli("task", "bound", "--as", "alice", "--title", "Bound", "--description", "Bound",
                 "--project", "later")
        self.assertNotIn("ready", self.record.read()[0]["tasks"]["bound"])
        self.cli("ready", "bound", "--as", "bob", "--expect", "0", "--blocked", "--project", "earlier")
        self.assertEqual([], life.workload(self.record.read()[0], self.record.read()[0]["at"])["ready_tasks"])
        self.cli("ready", "bound", "--as", "alice", "--expect", "1")
        self.cli("ready", "bound", "--as", "alice", "--expect", "2", "--clear-project")
        state, events, _ = self.record.read()
        self.assertNotIn("project", state["tasks"]["old"])
        self.assertNotIn("project", state["tasks"]["bound"])
        self.assertTrue(state["tasks"]["bound"]["ready"])
        self.assertEqual(3, state["tasks"]["bound"]["generation"])
        self.assertEqual(events[-2]["data"], {"task": "bound", "expect": 1, "ready": True})
        replay = None
        for event in events:
            replay = apply_event(replay, event)
        self.assertEqual(state, replay)

    def test_invalid_projects_sleep_and_mutually_exclusive_flags_do_not_mutate(self):
        self.offer()
        for project in ("missing", "A usable fixture", None, 3, ""):
            self.rejected("task", "alice", {"task": "bad", "title": "Bad", "description": "Bad",
                                           "project": project}, "project")
            self.rejected("ready", "alice", {"task": "work", "expect": 0, "ready": False,
                                            "project": project}, "project")
        before = self.record.read()[2]
        self.cli("ready", "work", "--as", "alice", "--expect", "0", "--project", "later",
                 "--clear-project", success=False)
        self.assertEqual(before, self.record.read()[2])
        self.rejected("ready", "alice", {"task": "work", "expect": 0, "ready": False,
                      "clear_project": False}, "clear_project")
        self.record.append("sleep", "bob", {"through": 0, "note": "Asleep"})
        self.rejected("task", "bob", {"task": "asleep", "title": "X", "description": "X", "project": "later"}, "sleeping")
        self.rejected("ready", "bob", {"task": "work", "expect": 0, "ready": False, "project": "later"}, "sleeping")

    def test_live_lease_done_and_inactive_associations_reject_without_mutation(self):
        self.offer(project="later", ready=True)
        self.record.append("claim", "alice", {"task": "work", "expect": 0, "token": "own", "seconds": 60})
        for change in ({"project": "earlier"}, {"clear_project": True}):
            self.rejected("ready", "bob", {"task": "work", "expect": 1, "ready": True, **change}, "live lease")
        self.record.append("finish", "alice", {"task": "work", "token": "own", "result": "Fixture",
            "artifacts": {"x": {"sha256": digest("x"), "base64": "eA=="}}})
        self.rejected("ready", "bob", {"task": "work", "expect": 1, "ready": True, "project": "earlier"}, "done")
        self.record.append("shelf", "alice", {"kind": "project-drop", "project": "later", "lesson": "Fixture dropped"})
        self.rejected("task", "alice", {"task": "inactive", "title": "X", "description": "X", "project": "later"}, "inactive")

    def test_simultaneous_cli_association_updates_have_one_generation_winner(self):
        self.offer()
        children = [self.process("ready", "work", "--as", actor, "--expect", "0", "--blocked", "--project", project)
                    for actor, project in (("alice", "later"), ("bob", "earlier"))]
        codes = []
        for child in children:
            child.communicate(timeout=20); codes.append(child.returncode)
        self.assertEqual([0, 2], sorted(codes))
        self.assertEqual(1, self.record.read()[0]["tasks"]["work"]["generation"])

    def test_pinned_gate_preserves_old_projection_and_requires_exact_migration(self):
        self.offer()
        state = self.record.read()[0]
        state["wake_policy"] = {"fixture": True}
        legacy = copy.deepcopy(state)
        event = {"id": "binding", "op": "ready", "actor": "alice", "at": state["at"],
                 "data": {"task": "work", "expect": 0, "ready": False, "project": "later"}}
        # Backlog is separately activated; that does not activate project work.
        from house.maintenance import BACKLOG_SCOPE
        state["maintenance"] = {"migrations": {BACKLOG_SCOPE: {}}}
        with self.assertRaisesRegex(ValueError, "project work runtime"):
            apply_event(copy.deepcopy(state), event)
        state["maintenance"]["migrations"][project_work.SCOPE] = {}
        result = apply_event(state, event)
        self.assertEqual("later", result["tasks"]["work"]["project"])
        self.assertNotIn("project", legacy["tasks"]["work"])


class ProjectMailboxTests(MailboxCase):
    def test_fixed_mailbox_parses_project_options_and_retains_actor_boundary(self):
        # The fixed mailbox runs against its normal synthetic journal. Unknown
        # associations reach reducer validation through the real parser/server.
        self.arrive()
        before = self.record.read()[2]
        error = self.collect(self.start("task", "x", "--as", self.resident, "--title", "X",
                             "--description", "X", "--project", "not-a-project"), success=False)
        self.assertIn("unknown or inactive project", error)
        self.assertEqual(before, self.record.read()[2])
        self.call("task", "x", "--as", self.resident, "--title", "X", "--description", "X")
        self.call("ready", "x", "--as", self.resident, "--expect", "0", "--blocked", "--clear-project")
        self.collect(self.start("ready", "x", "--as", "alice", "--expect", "1", "--clear-project"), success=False)
