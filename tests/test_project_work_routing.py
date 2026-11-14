"""Real reducer admissions and coordinator selection, with native launch replaced."""
import copy
import json
from unittest.mock import patch

from house import home, life, project_work
from house.model import apply_event
from house.governance import digest
from house.home_work import git
from tests.support import HouseCase
from tests.test_project_work import projects, start_data


class ProjectRoutingTests(HouseCase):
    def setUp(self):
        super().setUp()
        self.record = projects(self)
        self.repo = self.record.root

    def offer(self, key, project=None, ready=True):
        data = {"task": key, "title": "No routing hints", "description": "One owned fixture", "ready": ready}
        if project:
            data["project"] = project
        self.record.append("task", "alice", data)

    def state(self):
        return self.record.read()[0]

    def pick(self, at=None):
        state = self.state()
        at = state["at"] if at is None else at
        demand = life.workload(state, at)
        return project_work.first(state, at, demand["ready_tasks"], demand["pending_help"])

    def help(self, key, **extra):
        self.record.append("life", "alice", {"kind": "help", "request": key, "reason": "No routing hints", **extra})

    def start(self, key, **extra):
        self.record.append("life", life.CONTROLLER, start_data(key, **extra))

    def finish(self, key):
        self.record.append("life", life.CONTROLLER, {"kind": "run-finish", "run": key,
            "outcome": "interrupted", "exit_code": None, "usage": {}, "elapsed_seconds": 1})

    def test_deadline_then_ids_order_projects_before_unrelated_help(self):
        self.offer("housekeeping")
        self.help("unrelated")
        self.offer("a-late", "later")
        self.offer("z-early", "earlier")
        self.offer("b-early", "earlier")
        self.assertEqual({"task": "b-early", "task_generation": 0}, self.pick())
        self.start("first", backlog=True, task="b-early", task_generation=0)
        self.assertEqual({"task": "z-early", "task_generation": 0}, self.pick())
        self.start("second", backlog=True, task="z-early", task_generation=0)
        self.assertEqual({"task": "a-late", "task_generation": 0}, self.pick())
        self.assertEqual("pending", self.state()["life"]["requests"]["unrelated"]["status"])
        state = self.state()
        state["shelf"]["projects"]["later"]["deadline"] = state["shelf"]["projects"]["earlier"]["deadline"]
        self.assertEqual({"task": "z-early", "task_generation": 0}, project_work.first(
            state, state["at"] + project_work.ADMISSION_SECONDS, ["a-late", "z-early"], []))

    def test_blocked_done_live_claim_and_inactive_project_never_reenter_backlog(self):
        self.offer("blocked", "earlier", ready=False)
        self.offer("leased", "earlier")
        self.offer("done", "earlier")
        for key in ("leased", "done"):
            self.record.append("claim", "alice", {"task": key, "expect": 0, "token": key, "seconds": 60})
        self.record.append("finish", "alice", {"task": "done", "token": "done", "result": "Fixture",
            "artifacts": {"x": {"sha256": digest("x"), "base64": "eA=="}}})
        self.assertIsNone(self.pick())
        self.offer("stale-project", "later")
        self.record.append("shelf", "alice", {"kind": "project-drop", "project": "later", "lesson": "Fixture"})
        self.assertNotIn("stale-project", life.workload(self.state(), self.state()["at"])["ready_tasks"])
        self.offer("ordinary")
        self.assertEqual(["ordinary"], life.workload(self.state(), self.state()["at"])["ready_tasks"])
        state = self.state()
        state["shelf"]["projects"]["earlier"]["status"] = "done"
        self.assertIsNone(project_work.first(state, state["at"] + 100, ["leased", "done", "blocked"], []))

    def test_typed_task_help_and_completed_source_run_have_project_priority(self):
        self.help("unrelated")
        self.offer("assist-work", "earlier")
        self.help("project-assist", task="assist-work")
        self.offer("later-work", "later")
        self.assertEqual({"help_request": "project-assist"}, self.pick())
        self.start("helper", help_request="project-assist")
        self.assertEqual({"task": "later-work", "task_generation": 0}, self.pick())
        self.finish("helper")
        state = self.state()
        # Source-review requests are normally created by the delivery module.
        # Synthetic projection isolates the routing contract from its owner gate.
        run = state["life"]["runs"]["helper"]
        run.update(task="assist-work")
        state["life"]["requests"]["project-assist"]["status"] = "resolved"
        state["life"]["requests"]["source"] = {"status": "pending", "review_run": "helper"}
        self.assertEqual({"help_request": "source"}, project_work.first(state, state["at"], ["later-work"], ["unrelated", "source"]))
        # Older launches can link through an actual finish within that run.
        run.pop("task")
        state["tasks"]["assist-work"].update(status="done", owner=run["resident"],
                                              finished_at=run["started_sequence"] + 1)
        run["ended_sequence"] += 1
        self.assertEqual({"help_request": "source"}, project_work.first(state, state["at"], [], ["unrelated", "source"]))
        state["tasks"]["assist-work"]["finished_at"] = run["ended_sequence"] + 1
        self.assertIsNone(project_work.first(state, state["at"], [], ["source"]))

    def test_racing_admissions_reserve_once_without_claim_or_generation_change(self):
        self.offer("work", "earlier")
        children = [self.process("life", "--as", life.CONTROLLER, "--data", json.dumps(
            start_data(key, backlog=True, task="work", task_generation=0))) for key in ("one", "two")]
        codes = []
        for child in children:
            child.communicate(timeout=20); codes.append(child.returncode)
        self.assertEqual([0, 2], sorted(codes))
        task = self.state()["tasks"]["work"]
        self.assertEqual(("open", None, None, 0), (task["status"], task["owner"], task["token"], task["generation"]))
        self.assertIsNone(self.pick())
        self.assertEqual([], life.workload(self.state(), self.state()["at"])["idle_residents"])
        # A hint grants no exclusive edit or claim ownership.
        self.record.append("claim", "bob", {"task": "work", "expect": 0, "token": "real", "seconds": 60})
        self.assertEqual("bob", self.state()["tasks"]["work"]["owner"])

    def test_crash_expiry_and_generation_change_release_hint(self):
        self.offer("work", "earlier")
        self.start("crash", backlog=True, task="work", task_generation=0)
        self.finish("crash")
        self.assertEqual({"task": "work", "task_generation": 0}, self.pick())
        self.start("unresponsive", backlog=True, task="work", task_generation=0)
        state = self.state()
        expiry = state["life"]["runs"]["unresponsive"]["started_at"] + project_work.ADMISSION_SECONDS
        self.assertIsNone(self.pick(expiry - .001))
        self.assertEqual({"task": "work", "task_generation": 0}, self.pick(expiry))
        self.assertEqual(1, life.workload(state, expiry)["uncovered_tasks"])
        with patch("house.record.time.time", return_value=expiry):
            self.start("replacement", backlog=True, task="work", task_generation=0)
        self.record.append("ready", "alice", {"task": "work", "expect": 0, "ready": True, "project": "later"})
        self.assertEqual({"task": "work", "task_generation": 1}, self.pick())
        self.rejected("life", life.CONTROLLER, start_data("stale", backlog=True, task="work", task_generation=0), "generation changed")

    def test_project_help_cannot_bypass_blocking_lease_or_inactive_project(self):
        self.offer("assist", "earlier", ready=False)
        self.help("project-help", task="assist")
        state = self.state()
        self.assertEqual([], life.workload(state, state["at"])["pending_help"])
        self.rejected("life", life.CONTROLLER, start_data("bad", help_request="project-help"), "project help demand changed")
        self.record.append("ready", "alice", {"task": "assist", "expect": 0, "ready": True})
        self.help("duplicate", task="assist")
        self.assertEqual({"help_request": "duplicate"}, self.pick())
        self.start("helper", help_request="duplicate")
        self.assertIsNone(self.pick())
        self.rejected("life", life.CONTROLLER, start_data("racer", help_request="project-help"), "project help demand changed")
        self.finish("helper")
        self.record.append("claim", "bob", {"task": "assist", "expect": 1, "token": "actual", "seconds": 60})
        self.assertIsNone(self.pick())
        self.record.append("release", "bob", {"task": "assist", "token": "actual", "note": "Fixture release"})
        self.record.append("shelf", "alice", {"kind": "project-drop", "project": "earlier", "lesson": "Fixture"})
        state = self.state()
        self.assertEqual([], life.workload(state, state["at"])["pending_help"])
        self.record.append("ready", "alice", {"task": "assist", "expect": 2, "ready": True, "clear_project": True})
        self.assertIn("project-help", life.workload(self.state(), self.state()["at"])["pending_help"])

    def test_atomic_revalidation_respects_project_state_owner_pause_quota_and_cap(self):
        self.offer("work", "earlier")
        data = start_data("blocked", backlog=True, task="work", task_generation=0)
        self.record.append("ready", "alice", {"task": "work", "expect": 0, "ready": False})
        self.rejected("life", life.CONTROLLER, data, "generation changed")
        self.rejected("life", life.CONTROLLER, data | {"task_generation": 1}, "demand changed")
        self.record.append("ready", "alice", {"task": "work", "expect": 1, "ready": True})
        state = self.state()
        event = {"id": "guard", "op": "life", "actor": life.CONTROLLER, "at": state["at"],
                 "data": data | {"task_generation": 2}}
        cases = [("paused", lambda s: s.update(maintenance={"admissions": {"until": s["at"] + 60}})),
                 ("cooling down", lambda s: s["life"]["budgets"].update(codex={"until": s["at"] + 60})),
                 ("demand changed", lambda s: s["shelf"]["projects"]["earlier"].update(status="dropped"))]
        for message, mutate in cases:
            candidate = copy.deepcopy(state); mutate(candidate)
            with self.assertRaisesRegex(ValueError, message):
                apply_event(candidate, event)
        for key in ("one", "two", "three"):
            self.start(key)
        self.rejected("life", life.CONTROLLER, event["data"], "three residents")

    def test_coordinator_tick_selects_projects_before_queued_review_and_keeps_fairness(self):
        self.offer("maintenance")
        self.offer("later-work", "later")
        self.offer("earlier-work", "earlier")
        self.help("unrelated-review")
        runtime = self.root / "fixture.pyz"; runtime.write_bytes(b"inert")
        coordinator = home.Coordinator(self.record, runtime)
        calls = []
        def admit(kind, help_id, **kwargs):
            calls.append((kind, help_id, kwargs))
            run = str(len(calls))
            extra = {"help_request": help_id} if help_id else {}
            if kwargs["backlog"]:
                extra["backlog"] = True
            if "task_id" in kwargs:
                extra.update(task=kwargs["task_id"], task_generation=kwargs["task_generation"])
            data = start_data(run, **extra) | {"agent": kind, "model": home.providers.DEFAULTS[kind]}
            self.record.append("life", life.CONTROLLER, data)
            coordinator.running[run] = None
            return run
        with patch.object(coordinator, "start", side_effect=admit), patch.object(coordinator, "reap", return_value=[]), \
                patch("house.source_delivery.queue_review"):
            result = coordinator.tick(poll=False)
        self.assertEqual(["earlier-work", "later-work", None], [c[2].get("task_id") for c in calls])
        self.assertEqual([None, None, "unrelated-review"], [c[1] for c in calls])
        self.assertEqual(["codex", "opencode", "muse"], [c[0] for c in calls])
        self.assertEqual(3, len(result["started"]))

    def test_real_start_records_binding_prompt_and_work_mode_despite_pending_source(self):
        self.offer("work", "earlier")
        (self.repo / "source.txt").write_text("fixture source")
        git(self.repo, "add", "source.txt")
        git(self.repo, "-c", "commit.gpgsign=false", "-c", "user.name=Fixture",
            "-c", "user.email=fixture@local", "commit", "-m", "Synthetic source")
        runtime = self.root / "fixture.pyz"; runtime.write_bytes(b"inert")
        coordinator = home.Coordinator(self.record, runtime)
        with patch("house.home.time.time", return_value=self.state()["at"]), \
                patch("house.home.active_policy", return_value={"revision": "fixture"}), \
                patch("house.home.active_prompt", return_value="Synthetic fixture"), \
                patch("house.home.pending_contributions", return_value=[{"run": "unrelated", "paths": ["x"]}]), \
                patch("house.home.providers.command", side_effect=ValueError("Stop before launching any native process")):
            run = coordinator.start("codex", backlog=True, task_id="work", task_generation=0)
        item = self.state()["life"]["runs"][run]
        self.assertEqual(("work", 0, "work", "failed"),
                         (item["task"], item["task_generation"], item["mode"], item["outcome"]))
        prompt = (coordinator.private / run / "prompt.txt").read_text()
        self.assertIn("Suggested project task: work; generation 0; project earlier;", prompt)
        self.assertEqual({"task": "work", "task_generation": 0}, self.pick())
        self.assertEqual({}, coordinator.running)

    def test_prompt_supplies_exact_task_and_keeps_unrelated_review_subordinate(self):
        self.offer("work", "earlier")
        self.start("assigned", backlog=True, task="work", task_generation=0)
        state = self.state()
        coordinator = object.__new__(home.Coordinator)
        coordinator.record, coordinator.private = self.record, self.root
        with patch("house.home.pending_contributions", return_value=[{"run": "unrelated", "paths": ["house/x.py"]}]), \
                patch("house.home.active_prompt", return_value="Fixture prompt"):
            text = coordinator.prompt(state, "assigned", "resident-assigned", self.repo, self.repo / ".house-client", None)
        self.assertIn("Suggested project task: work; generation 0; project earlier;", text)
        self.assertIn("Full task: One owned fixture", text)
        self.assertIn("not ownership", text)
        self.assertIn("leave unrelated reviews queued", text)

