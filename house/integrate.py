"""Review private source contributions before a serialized fast-forward publication.

Candidates and failures remain in private Git clones. No reset, stash, forced
update or patch overwrite is used on the shared source checkout.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from .home_work import git
from .record import Record
from . import test_sandbox
from .files import workspace_path


INSPECTION_LIMIT = 64_000
DIAGNOSTIC_LIMIT = 8_000
DIAGNOSTIC_CHUNK = 64 * 1024
# Receipt fields that must never reach the journal notice: a private candidate
# name and raw candidate-authored test output. The durable private receipt keeps
# both; the shared notice keeps the ordinary outcome fields only.
JOURNAL_EXCLUDED_FIELDS = frozenset({"candidate", "diagnostics"})


def source(record: Record, run: str, actor: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run):
        raise ValueError("invalid run ID")
    state, _, _ = record.read()
    item = state.get("life", {}).get("runs", {}).get(run)
    if not item or item["status"] != "completed":
        raise ValueError("contribution requires a stopped resident")
    if actor not in state["residents"]:
        raise ValueError("integrator must be a resident")
    if actor == item["resident"] or not state["residents"][actor]["awake"]:
        raise ValueError("integration requires a different, awake resident")
    workspace = workspace_path(record, run, state)
    report = json.loads((record.common / "house-home" / run / "contribution.json").read_text())
    if (any(not isinstance(report.get(key), str) or not re.fullmatch(r"[0-9a-f]{40}", report[key])
            for key in ("base", "commit")) or report["base"] != item["source_head"]
            or report["commit"] != git(workspace, "rev-parse", "HEAD")):
        raise ValueError("contribution identity changed")
    return workspace, report


def changed_paths(workspace: Path, base: str, commit: str) -> list[str]:
    output = subprocess.run(["git", "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv",
                             "--no-renames", "--name-only", "-z", base, commit, "--"],
                            cwd=workspace, capture_output=True, check=True, timeout=30).stdout
    return [p.decode("utf-8") for p in output.split(b"\0") if p]


def inspect_contribution(record: Record, run: str, actor: str, path: str | None = None) -> dict:
    """Read committed bytes only; no acceptance, tests, receipt writes or host paths."""
    workspace, report = source(record, run, actor)
    paths = changed_paths(workspace, report["base"], report["commit"])
    if path is not None and path not in paths:
        raise ValueError("inspection path must be an exact changed contribution path")
    result = {"run": run, "base": report["base"], "contribution": report["commit"],
              "paths": paths, "status": "inspection", "limit_bytes": INSPECTION_LIMIT}
    command = ["git", "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
               "--no-color", report["base"], report["commit"], "--"]
    if path is not None:
        command.append(path)
    # Stream a bounded prefix rather than buffering an arbitrarily large diff.
    with subprocess.Popen(command, cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        data = proc.stdout.read(INSPECTION_LIMIT + 1)
        truncated = len(data) > INSPECTION_LIMIT
        if truncated:
            proc.terminate()
        code = proc.wait(timeout=30)
        if code and not truncated:
            raise ValueError("contribution diff unavailable")
    result.update(diff=data[:INSPECTION_LIMIT].decode("utf-8", errors="replace"), truncated=truncated)
    if path is not None:
        result["path"] = path
        tree = subprocess.run(["git", "--literal-pathspecs", "ls-tree", "-z", report["commit"], "--", path],
                              cwd=workspace, capture_output=True, check=True, timeout=30).stdout
        if not tree:
            result["content_status"] = "deleted"
        else:
            mode, kind, oid = tree.split(b"\t", 1)[0].split()
            if mode not in (b"100644", b"100755") or kind != b"blob":
                result["content_status"] = "not-regular-file"
            elif int(git(workspace, "cat-file", "-s", oid.decode())) > INSPECTION_LIMIT:
                result["content_status"] = "too-large"
            else:
                blob = subprocess.run(["git", "cat-file", "blob", oid.decode()], cwd=workspace,
                                      capture_output=True, check=True, timeout=30).stdout
                try:
                    content = blob.decode("utf-8")
                    if "\0" in content:
                        raise ValueError("binary")
                    result.update(content_status="complete", content=content)
                except (UnicodeDecodeError, ValueError):
                    result["content_status"] = "binary"
    return result


def failure_diagnostics(log: Path, test_exit: int) -> dict:
    """Identify the retained test log and include a bounded tail.

    The log is candidate-authored data, never instructions. Read it in fixed
    chunks so an arbitrarily large log cannot be buffered, report the hash of
    all retained bytes, and keep only the last DIAGNOSTIC_LIMIT bytes of text.
    """
    digest = hashlib.sha256()
    size = 0
    tail = b""
    try:
        with log.open("rb") as stream:
            while True:
                block = stream.read(DIAGNOSTIC_CHUNK)
                if not block:
                    break
                size += len(block)
                digest.update(block)
                tail = (tail + block)[-DIAGNOSTIC_LIMIT:]
    except OSError:
        return {"kind": "failed-tests", "test_exit": test_exit,
                "source": "untrusted candidate output",
                "reason": "retained test log is unavailable"}
    return {"kind": "failed-tests", "test_exit": test_exit,
            "source": "untrusted candidate output", "log_file": log.name,
            "bytes": size, "sha256": digest.hexdigest(),
            "limit_bytes": DIAGNOSTIC_LIMIT, "tail_bytes": len(tail),
            "clipped": size > len(tail),
            "tail": tail.decode("utf-8", errors="replace")}


def check_plan(candidate: Path, base: str, head: str) -> tuple[str, list[list[str]]]:
    paths = changed_paths(candidate, base, head)
    project_only = bool(paths) and all(re.fullmatch(r"projects/[A-Za-z0-9_-]+/.+", p) for p in paths)
    if not project_only:
        return "foundation", [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]]
    # Test each affected project, including its unchanged tests. No dependency install.
    projects = sorted({"/".join(p.split("/")[:2]) for p in paths})
    # unittest's CLI exits 5 for zero discovered tests. A prose-only project
    # legitimately has none: report Ran 0 tests, then run its syntax checks.
    # Loading errors and actual failures still make the result unsuccessful.
    runner = ("import sys,unittest;"
              "suite=unittest.defaultTestLoader.discover(sys.argv[1]);"
              "result=unittest.TextTestRunner(verbosity=2).run(suite);"
              "raise SystemExit(not result.wasSuccessful())")
    commands = [[sys.executable, "-c", runner, project]
                for project in projects if (candidate / project).is_dir()]
    for name in paths:
        path = candidate / name
        if path.is_symlink():
            raise ValueError("project acceptance requires regular files")
        if not path.is_file():
            continue  # Deleted files have no syntax to check.
        if path.suffix == ".py":
            commands.append([sys.executable, "-c", "import ast,sys;ast.parse(open(sys.argv[1]).read(), filename=sys.argv[1])", name])
        elif path.suffix == ".json":
            commands.append([sys.executable, "-c", "import json,sys;json.load(open(sys.argv[1]))", name])
        elif path.suffix in {".js", ".mjs", ".cjs"}:
            commands.append(["node", "--check", name])
    return "projects:" + ",".join(projects), commands


def integrate(record: Record, run: str, actor: str, *, publish: bool = False,
              reject: str | None = None) -> dict:
    if reject is not None and (publish or not reject.strip() or len(reject) > 4000):
        raise ValueError("rejection needs a bounded reason and cannot publish")
    private = record.common / "house-home"
    private.mkdir(mode=0o700, exist_ok=True)
    with (private / "integration.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        workspace, report = source(record, run, actor)
        head = git(record.root, "rev-parse", "HEAD")
        path = private / run / "integration.json"
        if path.exists():
            try:
                accepted = json.loads(path.read_text())
            except json.JSONDecodeError:
                # A stopped writer may have left an old non-atomic receipt.
                # Preserve its bytes; it cannot authorize acceptance. Re-review.
                path.replace(path.with_name("integration-incomplete-" + uuid.uuid4().hex + ".json"))
                accepted = {}
            if not isinstance(accepted, dict):
                raise ValueError("invalid integration receipt; preserve it")
            if accepted.get("status") == "integrated":
                # Both fields exist in durable receipts: normal merges record
                # candidate_head; operator-curated acceptance records canonical_commit.
                anchors = [accepted[key] for key in ("canonical_commit", "candidate_head") if key in accepted]
                if (accepted.get("run") != run or accepted.get("contribution") != report["commit"]
                        or not anchors or any(not isinstance(anchor, str)
                            or not re.fullmatch(r"[0-9a-f]{40}", anchor)
                            or anchor != anchors[0] for anchor in anchors)):
                    raise ValueError("accepted contribution receipt is inconsistent; preserve it")
                ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", anchors[0], head],
                                          cwd=record.root, capture_output=True)
                if ancestor.returncode != 0:
                    raise ValueError("accepted contribution is outside current source history; preserve it")
                if "candidate_head" in accepted:
                    contains = subprocess.run(["git", "merge-base", "--is-ancestor", report["commit"],
                                               accepted["candidate_head"]], cwd=record.root, capture_output=True)
                    if contains.returncode != 0:
                        raise ValueError("accepted contribution is absent from its merge commit; preserve it")
                return accepted
            if accepted.get("status") == "rejected":
                if accepted.get("run") != run or accepted.get("contribution") != report["commit"]:
                    raise ValueError("rejected contribution receipt is inconsistent; preserve it")
                return accepted
        if reject is not None:
            receipt = {"run": run, "actor": actor, "base": head, "contribution": report["commit"],
                       "status": "rejected", "reason": reject}
            save_result(record, actor, path, receipt)
            return receipt
        if git(record.root, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("shared source has uncommitted work; preserve it")
        candidate = private / ("integration-" + uuid.uuid4().hex)
        subprocess.run(["git", "clone", "--quiet", "--no-local", "--single-branch", "--no-tags",
                        str(record.root), str(candidate)], check=True, capture_output=True)
        git(candidate, "remote", "remove", "origin")
        git(candidate, "fetch", "--quiet", str(workspace), report["commit"])
        receipt = {"run": run, "actor": actor, "base": head, "contribution": report["commit"],
                   "candidate": candidate.name, "status": "conflict"}
        merged = subprocess.run(["git", "-C", str(candidate), "-c", "commit.gpgsign=false",
                                 "-c", "user.name=Emberhall integrator", "-c", "user.email=house@local",
                                 "merge", "--no-edit", report["commit"]], capture_output=True, text=True)
        (candidate.parent / (candidate.name + ".merge.log")).write_text(merged.stdout + merged.stderr)
        if merged.returncode == 0:
            receipt["candidate_head"] = git(candidate, "rev-parse", "HEAD")
            scope, commands = check_plan(candidate, head, receipt["candidate_head"])
            receipt.update(test_scope=scope, test_commands=commands)
            test_exit = 0
            log = candidate.parent / (candidate.name + ".tests.log")
            with log.open("w") as output:
                output.write("Acceptance scope: " + scope + "\n")
                for command in commands:
                    output.write(json.dumps(command) + "\n"); output.flush()
                    tested = test_sandbox.run(command, cwd=candidate, stdout=output, timeout=900)
                    test_exit = tested.returncode
                    if test_exit:
                        break
            actual_head = git(candidate, "rev-parse", "HEAD")
            dirty = bool(git(candidate, "status", "--porcelain", "--untracked-files=all"))
            unchanged = actual_head == receipt["candidate_head"] and not dirty
            receipt.update(status="reviewed" if test_exit == 0 and unchanged else "tests-failed",
                           test_exit=test_exit)
            if test_exit:
                # The exact retained log is the only diagnostic source; no
                # path lookup or re-run is offered.
                receipt["diagnostics"] = failure_diagnostics(log, test_exit)
            elif not unchanged:
                # Tests passed for bytes that no longer exist in the candidate.
                # Say so instead of pretending a named test failed.
                receipt["diagnostics"] = {
                    "kind": "candidate-changed", "test_exit": 0,
                    "reason": "candidate source changed during acceptance; tests do not apply to retained bytes",
                    "expected_head": receipt["candidate_head"], "actual_head": actual_head,
                    "dirty": dirty}
        if publish and receipt["status"] == "reviewed":
            if head != git(record.root, "rev-parse", "HEAD") or git(record.root, "status", "--porcelain", "--untracked-files=all"):
                raise ValueError("shared source changed during review; candidate retained")
            # Git itself refuses overwrites if an interactive writer dirties a
            # touched path between the check and this fast-forward operation.
            git(record.root, "fetch", "--quiet", str(candidate), receipt["candidate_head"])
            git(record.root, "merge", "--ff-only", receipt["candidate_head"])
            receipt["status"] = "integrated"
        save_result(record, actor, path, receipt)
        return receipt


def save_result(record: Record, actor: str, path: Path, receipt: dict):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as output:
        temporary.chmod(0o600)
        output.write(json.dumps(receipt, indent=2) + "\n")
        output.flush(); os.fsync(output.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    record.append("say", actor, {"text": "house-integration-v1 " + json.dumps({
        k: v for k, v in receipt.items() if k not in JOURNAL_EXCLUDED_FIELDS}, sort_keys=True)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("run")
    parser.add_argument("--as", dest="actor", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true", help="accept tested candidate by fast-forward")
    mode.add_argument("--inspect", action="store_true", help="read bounded committed diff without running or accepting it")
    mode.add_argument("--reject", metavar="REASON", help="decline this candidate, preserving its source")
    parser.add_argument("--path", help="exact changed path to inspect, with committed text when small")
    args = parser.parse_args()
    try:
        if args.path is not None and not args.inspect:
            raise ValueError("--path requires --inspect")
        record = Record(args.repo)
        result = (inspect_contribution(record, args.run, args.actor, args.path) if args.inspect else
                  integrate(record, args.run, args.actor, publish=args.publish, reject=args.reject))
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"integration retained for review: {type(error).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
