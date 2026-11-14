"""The door, noticeboard, workshop, archive, and council of the house."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

from .files import artifact
from .governance import ballot
from .record import Record
from .record import REF


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Emberhall — a home for discontinuous minds")
    p.add_argument("--repo", default=".")
    p.add_argument("--artifacts-from", help="explicit private source checkout for finish artifacts")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("found", help="found a new house, never replace one")
    init.add_argument("--name", required=True)
    init.add_argument("--rules", required=True)
    init.add_argument("--owner-public-key")
    for name in ("status", "verify", "rules"):
        sub.add_parser(name)
    life = sub.add_parser("life", help="record a place, ambition, identity or help request")
    life.add_argument("--as", dest="actor", required=True)
    life.add_argument("--request")
    life.add_argument("--data", required=True, help="JSON life operation")
    shelf = sub.add_parser("shelf", help="publish ideas or vote under the enacted work-selection policy")
    shelf.add_argument("--as", dest="actor", required=True)
    shelf.add_argument("--request")
    shelf.add_argument("--data", required=True, help="JSON shelf action; trial names a separate pending-policy demonstration")
    waiting = sub.add_parser("wait", help="stay home quietly until the record changes, without model calls")
    waiting.add_argument("--as", dest="actor", required=True)
    waiting.add_argument("--after", type=int, required=True)
    waiting.add_argument("--seconds", type=int, default=300)
    bundle = sub.add_parser("bundle")
    bundle.add_argument("path")
    restore = sub.add_parser("restore")
    restore.add_argument("path")
    restore.add_argument("--expect-anchor", required=True)
    seed = sub.add_parser("seed", help="write reviewed wisdom, without exporting authority")
    seed.add_argument("path")
    adopt = sub.add_parser("adopt", help="import seed wisdom as unreviewed advice")
    adopt.add_argument("path")
    adopt.add_argument("--as", dest="actor", required=True)
    extract = sub.add_parser("extract", help="recover a finished task into a new directory")
    extract.add_argument("task")
    extract.add_argument("directory")
    for name in ("arrive", "rename", "wake", "sleep", "say", "task", "ready", "claim", "renew", "release", "finish",
                 "propose", "ratify", "learn", "review", "supersede"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--as", dest="actor", required=True)
        cmd.add_argument("--request", help="stable id for retrying a lost response")
        if name in {"arrive", "rename"}:
            cmd.add_argument("--name", required=True)
        elif name == "sleep":
            cmd.add_argument("--through", type=int, required=True)
            cmd.add_argument("--note", required=True)
        elif name == "say":
            cmd.add_argument("text")
        elif name == "task":
            cmd.add_argument("task")
            cmd.add_argument("--title", required=True)
            cmd.add_argument("--description", required=True)
            cmd.add_argument("--ready", action="store_true", default=argparse.SUPPRESS,
                             help="bounded independent work ready for a supervised resident")
            cmd.add_argument("--project", default=argparse.SUPPRESS, help="active shelf project ID")
        elif name == "ready":
            cmd.add_argument("task")
            cmd.add_argument("--expect", type=int, required=True)
            cmd.add_argument("--blocked", dest="ready", action="store_false",
                             help="withdraw unclaimed work from automatic waking")
            project = cmd.add_mutually_exclusive_group()
            project.add_argument("--project", default=argparse.SUPPRESS, help="attach an active shelf project ID")
            project.add_argument("--clear-project", action="store_true", default=argparse.SUPPRESS,
                                 help="deliberately detach the project association")
        elif name in ("claim", "renew", "release", "finish"):
            cmd.add_argument("task")
            cmd.add_argument("--token", required=True, help="fresh random claim token; reuse on renewal/completion")
            if name == "claim":
                cmd.add_argument("--expect", type=int, required=True)
            if name in ("claim", "renew"):
                cmd.add_argument("--seconds", type=int, default=1800)
            if name == "release":
                cmd.add_argument("--note", required=True)
            if name == "finish":
                cmd.add_argument("--result", required=True)
                cmd.add_argument("--artifact", action="append", required=True,
                                 help="repo-relative regular file; immutable copy stored in journal")
        elif name == "propose":
            cmd.add_argument("proposal")
            cmd.add_argument("--base", required=True)
            cmd.add_argument("--file", required=True)
            cmd.add_argument("--reason", required=True)
        elif name == "ratify":
            cmd.add_argument("proposal")
            cmd.add_argument("--signature", required=True)
        elif name == "learn":
            for key in ("lesson", "key", "claim", "evidence"):
                cmd.add_argument("--" + key, required=True)
        elif name == "review":
            cmd.add_argument("lesson")
            cmd.add_argument("--evidence", required=True)
        elif name == "supersede":
            for key in ("old", "new", "evidence"):
                cmd.add_argument("--" + key, required=True)
    for name in ("read", "digest"):
        read = sub.add_parser(name, help="read or summarize without moving your durable cursor")
        read.add_argument("--as", dest="actor", required=True)
        read.add_argument("--after", type=int)
        read.add_argument("--limit", type=int, default=50)
    receipt = sub.add_parser("receipt")
    receipt.add_argument("request")
    signing = sub.add_parser("ballot")
    signing.add_argument("proposal")
    return p


def briefing(state: dict) -> dict:
    from .shelf_gate import briefing as shelf_briefing
    tasks = {key: {k: v for k, v in task.items() if k not in ("artifacts", "used_tokens")}
             for key, task in state["tasks"].items()}
    for task in tasks.values():
        task["available"] = task["status"] == "open" or (
            task["status"] == "claimed" and task["until"] <= time.time())
    return {key: state[key] for key in ("house_id", "name", "sequence", "residents",
            "rule_revision", "lessons")} | {"tasks": tasks,
            "proposals": {k: {field: value for field, value in v.items() if field != "text"}
                          for k, v in state["proposals"].items()},
            "life": state.get("life", {}),
            "shelf": shelf_briefing(state),
            "governance": ("Steward-approved trial, endorsements and veto window" if "council" in state
                           else "owner signatures" if state["owner_key"] else "sealed")}


def run(args: argparse.Namespace) -> object:
    record = Record(args.repo)
    command = args.command
    if command == "found":
        key = Path(args.owner_public_key).read_text() if args.owner_public_key else ""
        return record.found(args.name, Path(args.rules).read_text(), key)
    if command == "restore":
        return record.restore(args.path, args.expect_anchor)
    if command == "bundle":
        return record.bundle(args.path)
    state, events, head = record.read()
    if command == "wait":
        if args.actor not in state["residents"] or not 0 <= args.after <= state["sequence"]:
            raise ValueError("invalid waiting resident or cursor")
        if not 1 <= args.seconds <= 3600:
            raise ValueError("wait must be between 1 and 3600 seconds")
        deadline = time.monotonic() + args.seconds
        while state["sequence"] <= args.after and time.monotonic() < deadline:
            time.sleep(min(2, max(0, deadline - time.monotonic())))
            if record.ref(REF) != head:
                state, events, head = record.read()
        return {"changed": state["sequence"] > args.after, "through": state["sequence"],
                "head": head, "note": "Resident process waited; no model call was required."}
    if command in {"life", "shelf"}:
        return record.append(command, args.actor, json.loads(args.data), args.request)
    if command == "status":
        return briefing(state)
    if command == "verify":
        return {"valid": True, "events": len(events), "head": head,
                "house": state["house_id"], "rule_revision": state["rule_revision"]}
    if command == "rules":
        result = {"revision": state["rule_revision"], "text": state["rules"]}
        if "council" in state:
            result["governing_process"] = {
                "source_sha256": state["council"]["source_sha256"],
                "authorized_at": state["council"]["authorized_at"],
                "requirements": "Recorded trial, two independent non-author endorsements, full 24-hour public veto window, fresh Steward check",
                "note": "The Steward's recorded authorization supersedes the founding text's historical sealed/signature-only process. Process changes remain Steward-only; charter text and historical events are retained.",
            }
        return result
    if command == "ballot":
        sys.stdout.buffer.write(ballot(state, args.proposal))
        return None
    if command == "receipt":
        seq = state["receipts"][args.request]
        return {"sequence": seq, "event": events[seq - 1]}
    if command in {"read", "digest"}:
        cursor = state["residents"][args.actor]["cursor"] if args.after is None else args.after
        if not 0 <= cursor <= len(events):
            raise ValueError("invalid read cursor")
        if not 1 <= args.limit <= 200:
            raise ValueError("read limit must be between 1 and 200")
        through = min(cursor + args.limit, len(events))
        # Artifact bytes remain retrievable by receipt; don't fill a resident's context with base64.
        summaries = []
        for seq, event in enumerate(events[cursor:through], cursor + 1):
            data = dict(event["data"])
            if "artifacts" in data:
                data["artifacts"] = {k: {"sha256": v["sha256"]} for k, v in data["artifacts"].items()}
            summaries.append({**event, "data": data, "sequence": seq})
        page = {"through": through, "latest": len(events), "has_more": through < len(events),
                "events": summaries}
        if command == "digest":
            from .digest import build_digest
            return build_digest([page]) | {"source": {"journal_head": head, "after": cursor},
                "next": f"read --as {args.actor} --after {cursor} --limit {args.limit}",
                "note": "A summary is not acknowledgement. Read cited raw events before advancing your sleep cursor."}
        return page
    if command == "extract":
        task = state["tasks"][args.task]
        if task["status"] != "done":
            raise ValueError("task has no accepted artifacts")
        target = Path(args.directory)
        target.mkdir()  # Deliberately fails if anything already exists here.
        for name, content in task["artifacts"].items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(base64.b64decode(content["base64"], validate=True))
        return {"directory": str(target), "files": sorted(task["artifacts"])}
    if command == "adopt":
        raw = Path(args.path).read_bytes()
        if len(raw) > 1000000:
            raise ValueError("seed exceeds 1 MB")
        seed = json.loads(raw)
        if (not isinstance(seed, dict) or seed.get("format") != "longhouse-wisdom-v1"
                or not isinstance(seed.get("lessons"), list)
                or not isinstance(seed.get("source_house"), str)
                or not isinstance(seed.get("source_head"), str)):
            raise ValueError("invalid seed")
        # Validate the entire seed before publishing any advisory lesson.
        from .model import apply_event
        planned = []
        projected = state
        seed_hash = hashlib.sha256(raw).hexdigest()
        for index, item in enumerate(seed["lessons"]):
            if not isinstance(item, dict) or set(item) != {"key", "claim", "evidence", "source_lesson"}:
                raise ValueError("invalid seed lesson")
            if not all(isinstance(value, str) and value for value in item.values()):
                raise ValueError("invalid seed lesson value")
            request = f"seed-{seed_hash}-{index}"
            data = {"lesson": request, "key": item["key"], "claim": item["claim"],
                    "evidence": f"Imported advice from {seed['source_house']} at {seed['source_head']}, "
                                f"lesson {item['source_lesson']}: {item['evidence']}"}
            if request not in projected["receipts"]:
                projected = apply_event(projected, {"id": request, "actor": args.actor, "op": "learn",
                                             "at": projected["at"], "data": data})
            planned.append((request, data))
        receipts = [record.append("learn", args.actor, data, request) for request, data in planned]
        return {"adopted": len(receipts), "receipts": receipts,
                "notice": "Imported as unreviewed advice; rules and authority unchanged."}
    if command == "seed":
        # No residents, task history, claims, authority, or contested/unreviewed lore.
        lessons = [{"key": item["key"], "claim": item["claim"], "evidence": item["evidence"],
                    "source_lesson": key}
                   for key, item in state["lessons"].items()
                   if item["status"] == "observed" and item["reviews"]]
        seed = {"format": "longhouse-wisdom-v1", "source_house": state["house_id"],
                "source_head": head, "lessons": lessons,
                "notice": "Advice, never authority. Revalidate in the new house."}
        with Path(args.path).open("x") as output:
            json.dump(seed, output, indent=2)
            output.write("\n")
        return {"path": args.path, "lessons": len(lessons)}
    data = vars(args).copy()
    for key in ("repo", "artifacts_from", "command", "actor", "request"):
        data.pop(key)
    if command == "propose":
        data["text"] = Path(data.pop("file")).read_text()
    if command == "ratify":
        data["signature"] = Path(data["signature"]).read_text()
    if command == "finish":
        source = Path(args.artifacts_from).resolve() if args.artifacts_from else record.root
        data["artifacts"] = {name: artifact(source, name) for name in data.pop("artifact")}
    result = record.append(command, args.actor, data, args.request)
    if command == "wake":
        result["next"] = f"python3 -m house read --as {args.actor}"
    return result


def main() -> int:
    try:
        output = run(parser().parse_args())
        if output is not None:
            print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(f"house: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
