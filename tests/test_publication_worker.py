"""Real inert publication processes; no network, model calls or identity mocks."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import zipfile

from house import publication_worker as worker
from house.home import Coordinator
from house.home_work import git
from house.record import Record
from tests.support import HouseCase, SOURCE


def _ps_allowed():
    try:
        subprocess.run(["ps", "-axo", "pid=,pgid=,stat=,command="],
                       capture_output=True, check=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


PS_ALLOWED = _ps_allowed()


def _make_test_runtime(root: Path, code: str) -> Path:
    runtime = root / "publisher.pyz"
    with zipfile.ZipFile(runtime, "w") as archive:
        for path in (SOURCE / "house").glob("*.py"):
            if path.name != "publish.py":
                archive.write(path, "house/" + path.name)
        archive.writestr("house/publish.py", code)
        archive.writestr("__main__.py", "import sys\nfrom house.home import main\nraise SystemExit(main(sys.argv[2:]))\n")
    return runtime


class PublicationCase(HouseCase):
    def setUp(self):
        super().setUp()
        (self.repo / "source.txt").write_text("initial\n")
        git(self.repo, "add", "source.txt")
        git(self.repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test",
            "-c", "user.email=test@local", "commit", "-m", "Initial source")

    def target(self):
        return self.record.read()[2], git(self.repo, "rev-parse", "HEAD")

    def runtime(self, code):
        self.record._mailbox_runtime = _make_test_runtime(self.root, code)
        return self.record._mailbox_runtime

    def await_file(self, path):
        deadline = time.monotonic() + 10
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(path.exists(), "inert worker never reached fixture boundary")


class PublicationStateTests(PublicationCase):
    def test_spawn_failure_retains_both_heads_and_bounds_retry(self):
        self.runtime("def publish(record, *, push=False): raise AssertionError('must not run')\n")
        target = self.target()
        with patch.object(worker.subprocess, "Popen", side_effect=OSError("inert spawn failure")) as spawn:
            with self.assertRaisesRegex(OSError, "inert spawn failure"):
                worker.tick(self.record, wanted=target)
            state = worker.read_state(self.record)
            self.assertEqual(state["wanted"], list(target))
            self.assertIsNone(state["published"])
            self.assertGreater(state["next_attempt_at"], time.time() + 55)
            source_only = (target[0], "f" * 40)
            state = worker.tick(self.record, wanted=source_only)
            self.assertEqual(state["wanted"], list(source_only))
            self.assertEqual(spawn.call_count, 1)

    def test_selected_runtime_runs_and_keeps_result_guarded(self):
        self.runtime("def publish(record, *, push=False): return {'inert': True}\n")
        target = self.target()
        state = worker.tick(self.record, wanted=target)
        child = self.record._publication_processes[state["job_id"]]
        try:
            result = worker._root(self.record) / state["job_id"] / "result.json"
            self.await_file(result)
            self.assertTrue(json.loads(result.read_text())["ok"])
            self.assertIsNone(child.poll())
            self.assertFalse(worker.drained(self.record))
            # Do not ask for production cleanup when ps is unavailable. This
            # fixture owns the newly spawned group directly; cleanup assertions
            # and durable result acceptance belong to the host-only tests.
            self.assertIsNone(state["published"])
        finally:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)

    def test_drain_requires_idle_state_and_unheld_kernel_lock(self):
        self.assertTrue(worker.drained(self.record))
        with (worker._root(self.record) / "worker.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertFalse(worker.drained(self.record))
        worker._write(worker._root(self.record) / "state.json", {"status": "running"})
        self.assertFalse(worker.drained(self.record))


@unittest.skipUnless(PS_ALLOWED, "real process ownership requires host ps; no identity substitute")
class PublicationProcessTests(PublicationCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(worker.stop, self.record)

    def start_blocked(self, *, descendants=False):
        marker = self.root / "started"
        release = self.root / "release"
        child_file = self.root / "child.pid"
        code = f'''
import os, subprocess, sys, time
from pathlib import Path

def publish(record, *, push=False):
    Path({str(marker)!r}).write_text(str(os.getpid()))
    if {descendants!r}:
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
        Path({str(child_file)!r}).write_text(str(child.pid))
    while not Path({str(release)!r}).exists(): time.sleep(0.02)
    return {{'fixture': True}}
'''
        self.runtime(code)
        state = worker.tick(self.record, wanted=self.target())
        self.await_file(child_file if descendants else marker)
        return state, marker, release, child_file

    def settle(self, *, retry_seconds=60):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = worker.tick(self.record, retry_seconds=retry_seconds)
            if state["status"] == "idle":
                return state
            time.sleep(0.02)
        self.fail("publication did not settle")

    def test_failure_waits_for_cadence_then_retries(self):
        flag = self.root / "fail"
        flag.touch()
        self.runtime(f'''from pathlib import Path

def publish(record, *, push=False):
    if Path({str(flag)!r}).exists(): raise OSError('inert failure')
    return {{'fixture': True}}
''')
        first = worker.tick(self.record, wanted=self.target())
        state = self.settle()
        self.assertIsNone(state["published"])
        self.assertIn("inert failure", state["last_error"])
        self.assertGreater(state["next_attempt_at"], time.time() + 55)
        flag.unlink()
        for _ in range(3):
            self.assertEqual(worker.tick(self.record)["status"], "idle")
        self.assertEqual(len(list(worker._root(self.record).glob("*/job.json"))), 1)
        # Advance only the retry clock; process identity is always real.
        with patch.object(worker.time, "time", return_value=state["next_attempt_at"] + 1):
            second = worker.tick(self.record)
        self.assertNotEqual(second["job_id"], first["job_id"])
        self.assertEqual(self.settle()["published"], list(self.target()))

    def test_changes_while_busy_include_source_only_and_coalesce(self):
        first, _, release, _ = self.start_blocked()
        source = self.target()[1]
        self.record.append("say", "alice", {"text": "new journal"})
        worker.tick(self.record, wanted=self.target())
        (self.repo / "source.txt").write_text("new source\n")
        git(self.repo, "add", "source.txt")
        git(self.repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test",
            "-c", "user.email=test@local", "commit", "-m", "Source only")
        latest = self.target()
        self.assertNotEqual(latest[1], source)
        state = worker.tick(self.record, wanted=latest)
        self.assertEqual(state["job_id"], first["job_id"])
        self.assertEqual(state["target"], first["target"])
        self.assertEqual(state["wanted"], list(latest))
        self.assertEqual(len(list(worker._root(self.record).glob("*/job.json"))), 1)
        release.touch()
        self.assertEqual(self.settle()["published"], list(latest))
        self.assertEqual(len(list(worker._root(self.record).glob("*/job.json"))), 2)
        # A source-only change after success must also trigger a new snapshot.
        (self.repo / "source.txt").write_text("another source-only change\n")
        git(self.repo, "add", "source.txt")
        git(self.repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test",
            "-c", "user.email=test@local", "commit", "-m", "Another source-only change")
        latest_source = self.target()
        self.assertEqual(latest_source[0], latest[0])
        self.assertNotEqual(latest_source[1], latest[1])
        worker.tick(self.record, wanted=latest_source)
        self.assertEqual(self.settle()["published"], list(latest_source))

    def test_either_tagged_process_can_crash_without_stranding_descendants(self):
        for crash_guardian in (True, False):
            with self.subTest(crash_guardian=crash_guardian):
                first, marker, _, child_file = self.start_blocked(descendants=True)
                pgid = first["pgid"]
                executor = int(marker.read_text())
                victim = pgid if crash_guardian else executor
                os.kill(victim, signal.SIGKILL)
                if crash_guardian:
                    self.record._publication_processes[first["job_id"]].wait(timeout=5)
                # New Record loses every in-memory Popen ownership witness.
                replacement = Record(self.repo)
                state = worker.recover(replacement)
                self.assertEqual(state["status"], "idle")
                self.assertIsNone(state["published"])
                self.assertEqual(worker._members(pgid), {})
                self.assertNotEqual(os.getpgid(os.getpid()), pgid)
                child_file.unlink()
                marker.unlink()
                self.record._publication_processes.pop(first["job_id"]).wait(timeout=5)
                state["next_attempt_at"] = 0
                worker._write(worker._root(self.record) / "state.json", state)

    def test_timeout_shutdown_and_restart_preserve_pending_target(self):
        for action in ("timeout", "shutdown", "restart"):
            with self.subTest(action=action):
                state, marker, _, child_file = self.start_blocked(descendants=True)
                target, pgid = state["target"], state["pgid"]
                if action == "timeout":
                    worker.tick(self.record, timeout_seconds=0)
                elif action == "shutdown":
                    worker.stop(self.record)
                else:
                    replacement = Coordinator(Record(self.repo), self.record._mailbox_runtime, publish=True)
                    replacement.recover()
                    replacement.close()
                after = worker.read_state(self.record)
                self.assertEqual(after["status"], "idle")
                self.assertEqual(after["wanted"], target)
                self.assertIsNone(after["published"])
                self.assertEqual(worker._members(pgid), {})
                process = self.record._publication_processes.pop(state["job_id"], None)
                if process is not None: process.wait(timeout=5)
                # Permit the next independent subcase to run immediately.
                after["next_attempt_at"] = 0
                worker._write(worker._root(self.record) / "state.json", after)
                child_file.unlink()
                marker.unlink()

    def test_unknown_group_is_not_signalled(self):
        unknown = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"],
                                   start_new_session=True)
        try:
            state = {"status": "running", "job_id": "a" * 64,
                     "pgid": unknown.pid, "target": self.target(), "wanted": self.target()}
            worker._write(worker._root(self.record) / "state.json", state)
            with self.assertRaisesRegex(ValueError, "unidentified publication group"):
                worker.recover(self.record)
            self.assertIsNone(unknown.poll())
            self.assertEqual(worker.read_state(self.record)["status"], "running")
        finally:
            unknown.kill()
            unknown.wait(timeout=5)
            worker._write(worker._root(self.record) / "state.json", {"status": "idle"})

    def test_blocked_publication_allows_real_mailbox_reply_and_native_reaping(self):
        from tests import test_home as home_tests
        fixture = home_tests.HomeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        coord = fixture.coordinator
        coord.publish = True
        coord.poll_seconds = 60
        marker, release = fixture.root / "pub-started", fixture.root / "pub-release"
        runtime = _make_test_runtime(fixture.root, f'''import time
from pathlib import Path

def publish(record, *, push=False):
    Path({str(marker)!r}).touch()
    while not Path({str(release)!r}).exists(): time.sleep(0.02)
    return {{'fixture': True}}
''')
        coord.runtime = fixture.record._mailbox_runtime = runtime
        fixture.delay = 30
        run = coord.start("codex")
        resident = fixture.record.read()[0]["life"]["runs"][run]["resident"]
        # Disable unrelated external operations explicitly, not process identity.
        with patch("house.home.inbox.poll"), patch("house.source_delivery.deliver"):
            coord.tick(start=False)
            self.await_file(marker)
            workspace = Path(json.loads((coord.private / run / "launch.json").read_text())["workspace"])
            client = subprocess.Popen([str(workspace / ".house-client"), "arrive", "--as", resident,
                                       "--name", "Inert resident", "--request", "inert-arrival"],
                                      cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 10
                while client.poll() is None and time.monotonic() < deadline:
                    coord.tick(start=False, poll=False)
                    time.sleep(0.02)
                out, err = client.communicate(timeout=2)
                self.assertEqual(client.returncode, 0, err)
                self.assertIn("sequence", json.loads(out))
                self.assertFalse(release.exists())
                self.assertEqual(worker.read_state(fixture.record)["status"], "running")
                coord.running[run].process.terminate()
                fixture.drain(coord)
                self.assertEqual(fixture.record.read()[0]["life"]["runs"][run]["status"], "completed")
                self.assertEqual(worker.read_state(fixture.record)["status"], "running")
                self.assertFalse(release.exists())
            finally:
                if client.poll() is None: client.kill()
                client.communicate(timeout=5)
                coord.close()
