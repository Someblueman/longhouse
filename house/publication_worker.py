"""One durable Pages job, with tagged guardians until all descendants stop.

Only the coordinator writes state.json. Each immutable job keeps its own result.
Both the guardian and executor remain tagged/alive after publication, allowing a
replacement coordinator to clean descendants even if either process crashes.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from .mailbox import directory, read_json, write_json, MAX_RESPONSE, ERRORS
from .record import Record

LIMIT = MAX_RESPONSE + 300_000
JOB_ID = re.compile(r"^[0-9a-f]{64}$")
BOOT = ("import sys;sys.path.insert(0,sys.argv[1]);"
        "from house.publication_worker import main;raise SystemExit(main(sys.argv[2:]))")


def _root(record: Record) -> Path:
    root = record.common / "house-home" / "publication"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def _write(path: Path, value: dict) -> None:
    with directory(path.parent) as parent:
        write_json(parent, path.name, value, LIMIT)


def _read(path: Path) -> dict:
    with directory(path.parent) as parent:
        return read_json(parent, path.name, LIMIT)


def read_state(record: Record) -> dict:
    path = _root(record) / "state.json"
    return _read(path) if path.exists() else {
        "status": "idle", "wanted": None, "published": None, "next_attempt_at": 0}


def _members(pgid: int) -> dict[int, str]:
    result = subprocess.run(["ps", "-axo", "pid=,pgid=,stat=,command="],
                            capture_output=True, text=True, check=True, timeout=5)
    members = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) == 4 and parts[1] == str(pgid) and not parts[2].startswith("Z"):
            members[int(parts[0])] = parts[3]
    return members


def _stop_owned(pgid: int, job: str) -> None:
    """Keep one tagged guardian alive until every other group member is gone.

    A stale/reused group without a tag is never signalled. If inspection is
    denied, leave running state and files intact for host recovery, never infer
    ownership from the group number alone.
    """
    deadline = time.monotonic() + 5
    while True:
        members = _members(pgid)
        if not members:
            return
        tagged = [pid for pid, command in members.items()
                  if "--job " + job in command]
        if not tagged:
            raise ValueError("unidentified publication group; no signal sent")
        keeper = min(tagged)
        targets = [pid for pid in members if pid != keeper]
        if not targets:
            targets = [keeper]
        for pid in targets:
            try:
                if os.getpgid(pid) == pgid:
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if time.monotonic() >= deadline:
            raise ValueError("publication descendants have not stopped")
        time.sleep(0.02)


def _finish(record: Record, state: dict, retry_seconds: float) -> dict:
    job, pgid = state["job_id"], state["pgid"]
    if (not isinstance(job, str) or JOB_ID.fullmatch(job) is None or
            type(pgid) is not int or pgid <= 1):
        raise ValueError("invalid publication process identity; no signal sent")
    _stop_owned(pgid, job)
    child = getattr(record, "_publication_processes", {}).pop(job, None)
    if child is not None:
        child.wait(timeout=5)
    path = _root(record) / job
    response = (_read(path / "result.json") if (path / "result.json").exists()
                else {"ok": False, "error": "publication interrupted without a durable result"})
    if response.get("ok") is True:
        state.update(published=state["target"], last_error=None, next_attempt_at=0)
    else:
        error = str(response.get("error", "publication failed"))[:500]
        state.update(last_error=error, next_attempt_at=time.time() + retry_seconds)
        _write(record.common / "house-home" / "publish-error.json",
               {"error": "PublicationError", "reason": error, "at": time.time()})
    state.update(status="idle", job_id=None, pgid=None, target=None, finished_at=time.time())
    _write(_root(record) / "state.json", state)
    return state


def recover(record: Record, *, retry_seconds: float = 60) -> dict:
    state = read_state(record)
    if state["status"] == "running":
        state = _finish(record, state, retry_seconds)
    return state


def stop(record: Record) -> dict:
    return recover(record)


def drained(record: Record) -> bool:
    if read_state(record)["status"] == "running":
        return False
    with (_root(record) / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
    return True


def tick(record: Record, *, wanted: tuple[str, str] | None = None,
         retry_seconds: float = 60, timeout_seconds: float = 1200) -> dict:
    state = read_state(record)
    if wanted is not None:
        state["wanted"] = list(wanted)
        _write(_root(record) / "state.json", state)
    if state["status"] == "running":
        path = _root(record) / state["job_id"]
        child = getattr(record, "_publication_processes", {}).get(state["job_id"])
        if (child is not None and child.poll() is None and
                not (path / "result.json").exists() and
                time.time() - state["started_at"] < timeout_seconds):
            return state
        state = _finish(record, state, retry_seconds)
    if (not state["wanted"] or state["wanted"] == state["published"] or
            time.time() < state["next_attempt_at"]):
        return state
    runtime = Path(getattr(record, "_mailbox_runtime", ""))
    if runtime.is_symlink() or not runtime.is_file():
        raise ValueError("coordinator has no trusted pinned publication runtime")
    job = hashlib.sha256(os.urandom(32)).hexdigest()
    path = _root(record) / job
    with (_root(record) / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return state
        path.mkdir(mode=0o700)
        gate_read, gate_write = os.pipe()
        child = None
        try:
            with (path / "stdout.log").open("ab") as output, (path / "stderr.log").open("ab") as errors:
                os.chmod(output.name, 0o600)
                os.chmod(errors.name, 0o600)
                child = subprocess.Popen(
                    [sys.executable, "-I", "-c", BOOT, str(runtime),
                     "--repo", str(record.root), "--job", job, "--gate", str(gate_read)],
                    cwd=path, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                    start_new_session=True, pass_fds=(gate_read, lock.fileno()))
            item = {"id": job, "runtime": str(runtime),
                    "runtime_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
                    "pgid": child.pid}
            _write(path / "job.json", item)
            state.update(status="running", job_id=job, pgid=child.pid,
                         target=state["wanted"], started_at=time.time())
            _write(_root(record) / "state.json", state)
            processes = getattr(record, "_publication_processes", {})
            processes[job] = child
            record._publication_processes = processes
            os.write(gate_write, b"go")
        except (OSError, ValueError, subprocess.SubprocessError):
            # Before gate release the new child cannot have spawned descendants.
            if child is not None:
                child.kill()
                child.wait(timeout=5)
            state.update(status="idle", job_id=None, pgid=None, target=None,
                         next_attempt_at=time.time() + retry_seconds)
            _write(_root(record) / "state.json", state)
            raise
        finally:
            os.close(gate_read)
            os.close(gate_write)
    return state


def main(argv=None) -> int:
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument("--repo", required=True)
    options.add_argument("--job", required=True)
    options.add_argument("--gate", type=int)
    options.add_argument("--execute", action="store_true")
    args = options.parse_args(argv)
    if not JOB_ID.fullmatch(args.job):
        return 2
    if not args.execute:
        if args.gate is None or os.read(args.gate, 2) != b"go":
            return 2
        os.close(args.gate)
    record = Record(args.repo)
    path = _root(record) / args.job
    item = _read(path / "job.json")
    if item["id"] != args.job or item["pgid"] != os.getpgrp():
        return 2
    runtime = Path(item["runtime"])
    if runtime.is_symlink() or hashlib.sha256(runtime.read_bytes()).hexdigest() != item["runtime_sha256"]:
        raise ValueError("trusted publication runtime bytes changed")
    if args.execute:
        try:
            from .publish import publish
            result = publish(record, push=True)
            response = {"ok": True, "result": result}
        except (*ERRORS, subprocess.SubprocessError) as error:
            response = {"ok": False, "error": type(error).__name__ + ": " + str(error)[:300]}
        _write(path / "result.json", response)
    else:
        # This tagged guardian survives an executor crash. The executor also
        # stays tagged after returning, so killing this guardian cannot strand
        # a completed publisher's untagged Git descendants.
        child = subprocess.Popen([sys.executable, "-I", "-c", BOOT, str(runtime),
                                  "--repo", str(record.root), "--job", args.job, "--execute"])
        code = child.wait()
        if not (path / "result.json").exists():
            _write(path / "result.json", {"ok": False, "error": f"publisher executor exited {code}"})
    while True:
        time.sleep(3600)  # Coordinator retains ownership until descendant cleanup.


if __name__ == "__main__":
    raise SystemExit(main())
