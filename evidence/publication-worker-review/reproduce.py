"""Inert host-process regression probe; candidate imports come only from argv[1]."""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

candidate = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(candidate))
from house import publication_worker as worker
from house.watch import group_stopped
from tests.test_publication_worker import _init_repo, _make_test_runtime

assert Path(worker.__file__).resolve() == candidate / "house/publication_worker.py"
results = []


def await_file(path):
    deadline = time.monotonic() + 5
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert path.exists(), "inert worker did not reach its fixture boundary"


with tempfile.TemporaryDirectory(prefix="emberhall-publication-orphan-") as temporary:
    root = Path(temporary)
    repo = root / "repo"
    repo.mkdir()
    record = _init_repo(repo)
    child_file = root / "child.pid"
    code = f'''
import subprocess, sys, time
from pathlib import Path

def publish(record, *, push=False):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)",
                              "emberhall-inert-publication-review-child"])
    Path({str(child_file)!r}).write_text(str(child.pid))
    time.sleep(60)
'''
    record._mailbox_runtime = _make_test_runtime(root, code)
    state = worker.tick(record, wanted_head=record.read()[2])
    process = record._publication_processes[state["job_id"]]
    descendant = None
    try:
        await_file(child_file)
        descendant = int(child_file.read_text())
        assert os.getpgid(descendant) == process.pid
        process.kill()
        process.wait(timeout=5)
        try:
            worker.recover(record)
            error = None
        except ValueError as exception:
            error = str(exception)
        results.append({"case": "worker_dies_with_live_descendant", "error": error,
                        "owned_group_stopped_by_recovery": group_stopped(process.pid),
                        "regression": error is not None})
    finally:
        # Only the one inert descendant created above; never an unrelated group.
        if descendant is not None:
            command = subprocess.run(["ps", "-p", str(descendant), "-o", "args="],
                                     capture_output=True, text=True).stdout
            if "emberhall-inert-publication-review-child" in command:
                assert os.getpgid(descendant) == process.pid
                os.kill(descendant, signal.SIGKILL)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        assert group_stopped(process.pid), "fixture group cleanup failed"

with tempfile.TemporaryDirectory(prefix="emberhall-publication-retry-") as temporary:
    root = Path(temporary)
    repo = root / "repo"
    repo.mkdir()
    record = _init_repo(repo)
    record._mailbox_runtime = _make_test_runtime(root, '''
def publish(record, *, push=False):
    raise OSError("inert simulated failure; no network")
''')
    first = worker.tick(record, wanted_head=record.read()[2])
    child = record._publication_processes[first["job_id"]]
    try:
        child.wait(timeout=5)
        started = time.monotonic()
        second = worker.tick(record)
        elapsed = time.monotonic() - started
        restarted = second.get("job_id") not in (None, first["job_id"])
        results.append({"case": "failed_publish_without_new_request_or_poll", "restarted": restarted,
                        "tick_seconds": elapsed, "published_head": second.get("published_head"),
                        "regression": restarted})
    finally:
        worker.stop(record)
        assert group_stopped(child.pid), "first fixture group cleanup failed"
        if second.get("pgid"):
            assert group_stopped(second["pgid"]), "retry fixture group cleanup failed"

report = {"candidate_source_commit": "ccd4f17036c09e6bb76e9d3b1a39c9b427c420e7",
          "candidate_worker_sha256": hashlib.sha256(Path(worker.__file__).read_bytes()).hexdigest(),
          "results": results, "fixture_groups_cleaned": True,
          "network_calls": False, "model_calls": False,
          "process_identity_mocks": False}
print(json.dumps(report, indent=2))
raise SystemExit(1 if any(result["regression"] for result in results) else 0)
