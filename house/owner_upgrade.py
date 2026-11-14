"""Prepare and resume an explicitly authorized operator upgrade, never a resident action."""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import zipfile

from . import maintenance, runtime, steward, test_sandbox, wake_policy
from .home import single_coordinator
from .model import apply_event, require
from .record import Record
from .watch_recovery import prepare_runtime


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix=path.name + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, sort_keys=True, indent=2)
            output.write("\n"); output.flush(); os.fsync(output.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def authenticate_owner() -> None:
    steward.context()
    identity, _ = steward.github("user")
    require(identity.get("id") == steward.council.OWNER_ID, "authenticated Steward account required")


def passed_count(output: bytes, exit_code: int) -> int:
    counts = re.findall(rb"\nRan ([0-9]+) tests? in ", output)
    skipped = re.findall(rb"\nOK \(skipped=([0-9]+)\)", output)
    count = (int(counts[-1]) if counts else 0) - (int(skipped[-1]) if skipped else 0)
    require(exit_code == 0 and count > 0 and re.search(rb"\nOK(?: \(skipped=[0-9]+\))?\s*$", output),
            "owner upgrade tests did not execute and pass")
    return count


def prepare(record: Record, actor: str, scope: str, approval_file: Path, source_commit: str) -> Path:
    require(scope in maintenance.SOURCES and sha(approval_file.read_bytes()) == maintenance.SOURCES[scope],
            "wrong owner instruction bytes")
    snapshot = wake_policy.source_snapshot(record.root)
    require(snapshot["source_head"] == source_commit, "reviewed source commit changed")
    state, _, _ = record.read()
    old = maintenance.protected_manifest(state)
    names = set(old) | maintenance.OWNER_MODULES
    if scope == maintenance.PROJECT_WORK_SCOPE:
        names.add("house/project_work.py")
    if scope == maintenance.PUBLICATION_SCOPE:
        names.add("house/publication_worker.py")
    if scope == maintenance.WORK_ACCOUNTING_SCOPE:
        names.update({"house/work_metrics.py", "house/public_history.py"})
    if scope == maintenance.DIGEST_SCOPE:
        names.add("house/digest.py")
    if scope == maintenance.CHECKPOINT_SCOPE:
        names.add("house/checkpoint.py")
    if scope == maintenance.DELIVERY_SCOPE:
        names.add("house/source_delivery.py")
    if scope == maintenance.GROWTH_SCOPE:
        names.add("house/building.py")
    if scope == maintenance.REPAIR_SCOPE:
        names.add("house/opencode_auth.py")
    if scope == maintenance.KEEP_MOVING_SCOPE:
        names.update({"house/shelf.py", "house/shelf_gate.py", "house/windows.py", "house/home_control.py"})
    require(names <= snapshot["files"].keys(), "required owner upgrade module is missing")
    previous = runtime.selected(record)
    private = record.common / "house-home"
    target = prepare_runtime(record, private)
    data = {"scope": scope, "house": state["house_id"], "owner_id": steward.council.OWNER_ID,
        "approval_sha256": maintenance.SOURCES[scope], "source_head": source_commit,
        "source_sha256": snapshot["source_sha256"],
        "protected_files": {name: snapshot["files"][name] for name in sorted(names)},
        "previous_manifest_sha256": maintenance.fingerprint(old),
        "previous_runtime_sha256": previous["runtime_sha256"],
        "runtime_sha256": target["runtime_sha256"], "test_output_sha256": "0" * 64, "test_count": 1}
    if scope == maintenance.SELECTION_SCOPE:
        data["rule_base"] = state["rule_revision"]
    # Validate scope on a discarded projection. Preparation may run while the
    # current service lives; actual migration separately requires every run stopped.
    preview = copy.deepcopy(state)
    for run in preview.get("life", {}).get("runs", {}).values():
        run["status"] = "completed"
    apply_event(preview, {"op": "owner-migrate", "actor": actor, "id": "owner-upgrade-preview",
                         "at": max(time.time(), state["at"]), "data": data})
    plan_path = private / f"owner-upgrade-{scope}-{source_commit}.json"
    if plan_path.exists():
        existing = json.loads(plan_path.read_text())
        require(existing["snapshot"] == snapshot and existing["target_runtime"] == target,
                "existing owner preparation differs; preserve it")
        validate_plan(record, existing)
        return plan_path
    with tempfile.TemporaryDirectory(prefix="emberhall-owner-tests-") as temporary, tempfile.TemporaryFile() as output:
        candidate = Path(temporary) / "source"
        subprocess.run(["git", "clone", "--quiet", "--no-local", "--single-branch", "--no-tags",
                        str(record.root), str(candidate)], check=True, capture_output=True)
        require(wake_policy.source_snapshot(candidate) == snapshot, "test copy differs from reviewed source")
        tested = test_sandbox.run([str(Path(sys.executable).resolve()), *wake_policy.TEST_ARGS],
                                 cwd=candidate, stdout=output, timeout=900)
        require(wake_policy.source_snapshot(candidate) == snapshot, "tests changed their source")
        output.seek(0); raw = output.read(800001)
    require(len(raw) <= 800000, "owner test evidence exceeds bound")
    descriptor, output_name = tempfile.mkstemp(prefix=plan_path.stem + "-", suffix=".tests.txt", dir=private)
    output_path = Path(output_name)
    with os.fdopen(descriptor, "wb") as output:
        output.write(raw); output.flush(); os.fsync(output.fileno())
    output_path.chmod(0o600)
    try:
        data.update(test_count=passed_count(raw, tested.returncode), test_output_sha256=sha(raw))
        require(wake_policy.source_snapshot(record.root) == snapshot, "source changed during owner tests")
    except ValueError as error:
        raise ValueError(f"{error}; retained output: {output_path}") from error
    plan = {"format": "emberhall-owner-upgrade-v1", "actor": actor, "snapshot": snapshot,
            "previous_runtime": previous, "target_runtime": target, "migration": data,
            "test_output": str(output_path), "prepared_at": time.time()}
    atomic_json(plan_path, plan)
    return plan_path


def validate_plan(record: Record, plan: dict) -> None:
    require(plan.get("format") == "emberhall-owner-upgrade-v1", "wrong owner plan format")
    private = record.common / "house-home"
    data, target = plan["migration"], plan["target_runtime"]
    path = Path(target["entry"])
    require(path.parent == private and path.name == "runtime-" + data["source_head"] + ".pyz"
            and not path.is_symlink(), "owner runtime outside immutable store")
    require(sha(path.read_bytes()) == target["runtime_sha256"] == data["runtime_sha256"],
            "owner runtime bytes changed")
    require(target["source_head"] == plan["snapshot"]["source_head"] == data["source_head"] and
            plan["snapshot"]["source_sha256"] == data["source_sha256"], "owner source binding changed")
    require(maintenance.fingerprint(plan["snapshot"]["files"]) == data["source_sha256"] and
            plan["previous_runtime"]["runtime_sha256"] == data["previous_runtime_sha256"],
            "owner plan fingerprint changed")
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("runtime-source.json"))
        require(manifest["source_head"] == data["source_head"] and manifest["sha256"] == target["files"],
                "owner archive source manifest differs")
        require(set(archive.namelist()) == set(target["files"]) | {"runtime-source.json"} and
                all(sha(archive.read(name)) == value for name, value in target["files"].items()),
                "owner archive contents differ")
    require(all(name == "__main__.py" or plan["snapshot"]["files"].get(name) == value
                for name, value in target["files"].items()), "owner archive differs from tested source")
    require(all(plan["snapshot"]["files"].get(name) == value
                for name, value in data["protected_files"].items()), "owner protected source binding changed")
    output = Path(plan["test_output"])
    require(output.parent == private and not output.is_symlink(), "owner test evidence outside private store")
    raw = output.read_bytes()
    require(sha(raw) == data["test_output_sha256"] and passed_count(raw, 0) == data["test_count"],
            "owner test evidence changed")


def apply(record: Record, plan_path: Path) -> dict:
    private = record.common / "house-home"
    require(plan_path.resolve().parent == private and not plan_path.is_symlink(), "owner plan outside private store")
    plan = json.loads(plan_path.read_text())
    validate_plan(record, plan)
    data, actor = plan["migration"], plan["actor"]
    request = "owner-migration-" + data["scope"]
    # This is a cold operator migration. The old imported coordinator must be
    # retired; switching its archive path would not replace its loaded code.
    with single_coordinator(private), (private / "runtime.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        state, events, _ = record.read()
        require(not any(run["status"] == "active" for run in state.get("life", {}).get("runs", {}).values()),
                "drain native residents before owner migration")
        for job in (private / "jobs").glob("*/job.json"):
            require(json.loads(job.read_text()).get("status") == "done", "drain trusted actions before migration")
        from .publication_worker import drained
        require(drained(record), "drain pages publisher before migration")
        if request in state["receipts"]:
            event = events[state["receipts"][request] - 1]
            require(event["op"] == "owner-migrate" and event["actor"] == actor and event["data"] == data,
                    "accepted owner migration differs; preserve state")
        else:
            authenticate_owner()
            require(wake_policy.source_snapshot(record.root) == plan["snapshot"], "prepared owner source changed")
        selected = runtime.selected(record)
        require(selected["runtime_sha256"] in {data["previous_runtime_sha256"], data["runtime_sha256"]},
                "runtime changed since owner preparation")
        receipt = record.append("owner-migrate", actor, data, request)
        target = plan["target_runtime"] | {"attestation": {"owner_migration": data["scope"],
            "source_head": data["source_head"], "approval_sha256": data["approval_sha256"],
            "policy_revision": wake_policy.active_policy(record.read()[0])["revision"]}}
        atomic_json(private / "active-runtime.json", target)
        return {"receipt": receipt, "runtime": target}


def release_opencode(record: Record, actor: str, scope: str = maintenance.RETRY_SCOPE) -> dict:
    require(scope in maintenance.RELEASE_SCOPES, "unknown OpenCode release scope")
    authenticate_owner()
    state, _, _ = record.read()
    migration = state.get("maintenance", {}).get("migrations", {}).get(scope)
    require(migration is not None, "owner retry migration not accepted")
    require(runtime.selected(record)["runtime_sha256"] == migration["runtime_sha256"],
            "owner retry runtime is not selected")
    sequence, until = maintenance.approved_hold(scope)
    data = {"scope": scope, "approval_sha256": maintenance.SOURCES[scope],
        "house": state["house_id"], "owner_id": steward.council.OWNER_ID, "agent": "opencode",
        "expected_sequence": sequence, "expected_until": until}
    if scope in maintenance.FAILED_ATTEMPTS:
        proof = maintenance.FAILED_ATTEMPTS[scope]
        directory = record.common / "house-home" / proof.run
        error = directory / proof.output_file
        require(not any(path.is_symlink() for path in (directory, *directory.parents)) and
                error.is_file() and not error.is_symlink() and sha(error.read_bytes()) == proof.output_sha256,
                "preserved pre-provider CLI failure evidence changed")
        if scope == maintenance.LAUNCHER_SCOPE:
            output = directory / "stdout.jsonl"
            require(output.is_file() and not output.is_symlink() and output.stat().st_size == 0,
                    "bootstrap failure stdout must remain empty")
            require(all(not path.exists() and not path.is_symlink() for path in
                        (directory / ("opencode.db" + suffix) for suffix in ("", "-wal", "-shm", "-journal"))),
                    "bootstrap destination evidence changed")
        data.update(expected_observation=proof.observation,
                    failed_run=proof.run, failed_output_sha256=proof.output_sha256)
    return record.append("owner-provider-release", actor, data, "owner-release-" + scope)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--as", dest="actor", default="keeper-01")
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("prepare")
    stage.add_argument("--scope", choices=sorted(maintenance.SOURCES), required=True)
    stage.add_argument("--approval-file", type=Path, required=True)
    stage.add_argument("--source-commit", required=True)
    activate = sub.add_parser("apply"); activate.add_argument("plan", type=Path)
    release = sub.add_parser("release-opencode")
    release.add_argument("--scope", choices=maintenance.RELEASE_SCOPES, default=maintenance.RETRY_SCOPE)
    args = parser.parse_args()
    try:
        record = Record(args.repo)
        if args.command == "prepare":
            result = {"plan": str(prepare(record, args.actor, args.scope, args.approval_file, args.source_commit))}
        elif args.command == "apply":
            result = apply(record, args.plan)
        else:
            result = release_opencode(record, args.actor, args.scope)
        print(json.dumps(result, indent=2)); return 0
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f"owner upgrade: {error}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
