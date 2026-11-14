"""Independent operator acceptance using real disposable Git records and CLIs.

Council times are synthetic; these checks are not a real notice or wake trial.
"""
import base64
from pathlib import Path
import time
import uuid
from unittest.mock import patch

from house import council, life, project_work
from house.governance import digest
from house.record import Record
from tests.support import HouseCase
from tests.test_council import approval
from tests.test_shelf import idea


class ProjectWorkAcceptanceTests(HouseCase):
    def setUp(self):
        super().setUp()
        self.repo = self.new_repo("project-routing")
        self.record = Record(self.repo)
        with patch("house.record.uuid.uuid4", side_effect=[uuid.uuid4(), uuid.UUID(council.APPROVED_HOUSE)]):
            self.record.found("Routing fixture", "Original charter")
        for actor in ("alice", "bob", "carol", "dana"):
            self.send("arrive", {"name": actor}, actor)
        self.send("life", {"kind": "identity", "agent": "codex", "model": "gpt-6.1-sol"})
        self.send("council-authorize", approval())
        policy = (Path(__file__).parents[1] / "docs/WORK_SELECTION_PROPOSAL.md").read_text()
        self.send("council-propose", {"proposal": "selection", "mode": "rule", "title": "Selection",
            "text": policy, "reason": "Synthetic fixture", "base": self.record.read()[0]["rule_revision"]})
        self.send("task", {"task": "trial", "title": "Trial", "description": "Synthetic fixture"})
        self.send("claim", {"task": "trial", "expect": 0, "token": "trial", "seconds": 60})
        self.send("finish", {"task": "trial", "token": "trial", "result": "Synthetic fixture",
            "artifacts": {"fixture.txt": {"sha256": digest("fixture"),
                        "base64": base64.b64encode(b"fixture").decode()}}})
        self.send("council-trial", {"proposal": "selection", "task": "trial", "evidence": "Synthetic"})
        for actor in ("bob", "carol"):
            self.send("council-endorse", {"proposal": "selection", "evidence": "Synthetic"}, actor)
        self.send("council-notice", {"proposal": "selection", "repository": council.REPOSITORY,
            "issue": council.ISSUE, "comment_id": 1, "text_sha256": digest(policy)})
        future = time.time() + council.WAIT_SECONDS + 1
        with patch("house.record.time.time", return_value=future):
            self.send("council-sync", {"repository": council.REPOSITORY, "issue": council.ISSUE,
                "owner_id": council.OWNER_ID, "checked_at": future, "comments": []})
            self.send("council-enact", {"proposal": "selection"})
        self.send("shelf", {"kind": "explore-start", "round": "ideas", "expect": 0,
                            "token": "ideas", "seconds": 60})
        self.send("shelf", {"kind": "explore-publish", "round": "ideas", "token": "ideas",
                            "ideas": [idea("a"), idea("b")]})
        for name, pick, candidates, seconds in (("slow", "a", "ab", 604800), ("urgent", "b", "b", 259200)):
            self.send("shelf", {"kind": "choice-open", "choice": name, "milestones": {
                key: {"milestone": "Working fixture", "seconds": seconds} for key in candidates}})
            for actor in ("bob", "carol", "dana"):
                self.send("shelf", {"kind": "choice-vote", "choice": name, "idea": pick,
                                    "reason": "Independent fixture choice"}, actor)

    def send(self, op, data, actor="alice"):
        return self.record.append(op, actor, data)

    def offer(self, key, *extra):
        return self.cli("task", key, "--as", "alice", "--title", key,
                        "--description", "Bounded fixture", *extra)

    def demand(self):
        state = self.record.read()[0]
        return life.workload(state, state["at"])

    def test_real_cli_prefers_recorded_project_deadlines_not_titles(self):
        self.offer("urgent-project-looking-housekeeping", "--ready")
        self.offer("second", "--project", "slow", "--ready")
        self.offer("first", "--project", "urgent", "--ready")
        self.offer("blocked", "--project", "urgent")
        state = self.record.read()[0]
        ready = self.demand()["ready_tasks"]
        self.assertEqual({"first", "second", "urgent-project-looking-housekeeping"}, set(ready))
        self.assertEqual({"task": "first", "task_generation": 0},
                         project_work.first(state, state["at"], ready, []))
        self.assertEqual({"task": "second", "task_generation": 0},
                         project_work.first(state, state["at"], [k for k in ready if k != "first"], []))
        self.assertIsNone(project_work.first(state, state["at"], ["urgent-project-looking-housekeeping"], []))
        self.assertNotIn("ready", self.record.read()[0]["tasks"]["blocked"])
        self.send("shelf", {"kind": "project-drop", "project": "urgent", "lesson": "Synthetic closure"})
        self.assertNotIn("first", self.demand()["ready_tasks"])
        self.assertEqual(self.record.read()[0], Record(self.repo).read()[0])

