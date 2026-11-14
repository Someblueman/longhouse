"""Deterministic journal transitions. Rejected events never reach the ref."""
from __future__ import annotations

import base64
import hashlib
import math
import re
import unicodedata

from .governance import ballot, canonical, digest, verify_signature


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def string(data: dict, key: str, limit: int = 20000) -> str:
    value = data.get(key)
    require(isinstance(value, str) and 0 < len(value) <= limit, f"invalid {key}")
    return value


# Actual installed routes/model families; ordinary words such as Ember remain names.
TECHNICAL_NAME_WORDS = frozenset({"codex", "muse", "agy", "opencode", "openai", "meta",
                                 "gpt", "gemini", "hydrogen", "argon", "kimi", "minimax", "deepseek"})


def validate_resident_name(state: dict, actor: str, name: object) -> str:
    """Validate a new display name without changing durable resident identity."""
    require(isinstance(name, str) and len(name) <= 100, "invalid resident name")
    name = unicodedata.normalize("NFC", name.strip())
    require(bool(name) and name.isprintable(), "resident name must be nonempty printable text")
    folded = name.casefold()
    require(not (set(re.findall(r"[a-z]+", folded)) & TECHNICAL_NAME_WORDS),
            "choose a personal name, not a provider or model label")
    require(not re.fullmatch(r"[0-9a-f]{8,}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", folded)
            and not re.match(r"(?:resident|agent|run)[-_]", folded)
            and not re.search(r"[-_](?:[0-9]+|[0-9a-f]{4,})$", folded),
            "choose a personal name, not an automatic ID")
    require(all(other == actor or unicodedata.normalize("NFC", person["name"].strip()).casefold() != folded
                for other, person in state["residents"].items()), "resident name is already taken")
    return name


def integer(data: dict, key: str, minimum: int, maximum: int) -> int:
    value = data.get(key)
    require(type(value) is int and minimum <= value <= maximum, f"invalid {key}")
    return value


def apply_event(previous: dict | None, event: dict) -> dict:
    """Update a caller-owned disposable projection; discard it on any exception.

    Only Record publishes validated events. No caller may reuse a projection after
    failed validation, or share it with a persisted cache or another operation.
    Event data stays independent from the derived mutable projection.
    """
    require(set(event) == {"id", "op", "actor", "at", "data"}, "invalid event envelope")
    string(event, "id", 200)
    string(event, "op", 40)
    at = event["at"]
    require(type(at) in (int, float) and math.isfinite(at) and at > 0, "invalid clock")
    data = event["data"]
    require(isinstance(data, dict), "invalid data")
    op = event["op"]
    if previous is None:
        require(op == "found" and event["actor"] == "founder", "missing foundation")
        rules = string(data, "rules", 100000)
        key = data.get("owner_key", "")
        require(isinstance(key, str) and "\n" not in key, "invalid owner key")
        if key:
            require(key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-")), "invalid owner key")
        return {"version": 1, "house_id": string(data, "house_id", 100),
                "name": string(data, "name", 100), "owner_key": key,
                "rules": rules, "rule_revision": digest(rules),
                "residents": {}, "tasks": {}, "proposals": {}, "lessons": {},
                "sequence": 1, "at": at, "receipts": {event["id"]: 1}}
    state = previous
    require(event["id"] not in state["receipts"], "duplicate request id in journal")
    require(at >= state["at"], "clock moved backwards")
    seq = state["sequence"] + 1
    actor = event["actor"]
    if op == "arrive":
        require(actor not in state["residents"], "resident already exists")
        string(event, "actor", 100)
        name = (validate_resident_name(state, actor, data.get("name"))
                if state.get("maintenance", {}).get("resident_names") is True else string(data, "name", 100))
        state["residents"][actor] = {"name": name,
                                         "awake": True, "cursor": 0, "note": "Just arrived."}
    else:
        require(actor in state["residents"], "unknown resident: arrive first")
        resident = state["residents"][actor]
        if op in {"owner-migrate", "owner-provider-release"}:
            from .maintenance import apply
            apply(state, event)
        elif op == "owner-admissions":
            from .home_control import apply
            apply(state, event)
        elif op == "life":
            from .life import apply
            apply(state, event)
        elif op == "shelf":
            from .shelf_gate import apply
            apply(state, event)
        elif op.startswith("council-"):
            from .council import apply
            apply(state, event)
        elif op == "rename":
            require(state.get("maintenance", {}).get("resident_names") is True, "resident names are not enabled")
            require(set(data) == {"name"}, "rename accepts only your own name")
            require(resident["awake"], "sleeping residents cannot rename themselves")
            resident["name"] = validate_resident_name(state, actor, data["name"])
        elif op == "wake":
            resident["awake"] = True
        elif op == "sleep":
            cursor = integer(data, "through", 0, previous["sequence"])
            require(cursor >= resident["cursor"], "cursor cannot go backwards")
            resident.update(awake=False, cursor=cursor, note=string(data, "note"))
        elif op == "say":
            string(data, "text")
        elif op == "task":
            task_id = string(data, "task", 100)
            require(task_id not in state["tasks"], "task already exists")
            if "ready" in data:
                from .life import backlog_enabled
                require(backlog_enabled(state), "ready backlog runtime not enabled")
                require(type(data["ready"]) is bool and resident["awake"],
                        "task readiness requires an awake resident and boolean")
            if "project" in data:
                from .project_work import association
                require(resident["awake"], "sleeping residents cannot attach projects")
                association(state, data, at)
            state["tasks"][task_id] = {"title": string(data, "title", 500),
                "description": string(data, "description"), "status": "open",
                "generation": 0, "owner": None, "until": 0, "token": None, "used_tokens": []}
            if "ready" in data:
                state["tasks"][task_id]["ready"] = data["ready"]
            if "project" in data:
                state["tasks"][task_id]["project"] = data["project"]
        elif op == "ready":
            from .life import backlog_enabled
            require(backlog_enabled(state), "ready backlog runtime not enabled")
            require({"task", "expect", "ready"} <= data.keys() <=
                    {"task", "expect", "ready", "project", "clear_project"}
                    and not {"project", "clear_project"} <= data.keys() and type(data["ready"]) is bool,
                    "invalid readiness fields")
            require(resident["awake"], "sleeping residents cannot change readiness")
            task = state["tasks"][string(data, "task", 100)]
            require(task["status"] != "done", "task is done")
            require(task["until"] <= at, "task has a live lease; release before changing readiness")
            require(type(data["expect"]) is int and data["expect"] == task["generation"],
                    "task generation changed")
            if "project" in data:
                from .project_work import association
                association(state, data, at)
                task["project"] = data["project"]
            if "clear_project" in data:
                from .project_work import enabled
                require(enabled(state), "project work runtime not enabled")
                require(data["clear_project"] is True, "invalid clear_project")
                task.pop("project", None)
            task.update(ready=data["ready"], generation=task["generation"] + 1)
        elif op == "claim":
            task = state["tasks"][string(data, "task", 100)]
            require(task["status"] != "done", "task is done")
            require(task["until"] <= at, "task has a live lease")
            require(data.get("expect") == task["generation"], "claim generation changed")
            token = string(data, "token", 100)
            require(token not in task["used_tokens"], "claim token has already been used")
            task["used_tokens"].append(token)
            ttl = integer(data, "seconds", 1, 86400)
            task.update(owner=actor, token=token, until=at + ttl,
                        generation=task["generation"] + 1, status="claimed")
        elif op in ("renew", "finish", "release"):
            task = state["tasks"][string(data, "task", 100)]
            require(task["status"] == "claimed" and task["owner"] == actor and
                    task["token"] == data.get("token") and task["until"] > at,
                    "stale, expired, or foreign task lease")
            if op == "renew":
                task["until"] = at + integer(data, "seconds", 1, 86400)
            elif op == "release":
                task.update(status="open", owner=None, token=None, until=0)
                string(data, "note")
            else:
                string(data, "result")
                artifacts = data.get("artifacts", {})
                require(isinstance(artifacts, dict) and 0 < len(artifacts) <= 32,
                        "finish requires immutable artifacts")
                for name, artifact in artifacts.items():
                    require(isinstance(name, str) and name and not name.startswith("/") and
                            all(p not in ("..", ".", "") for p in name.split("/")) and
                            "\\" not in name, "invalid artifact path")
                    require(isinstance(artifact, dict) and set(artifact) == {"sha256", "base64"},
                            "invalid artifact")
                    content = base64.b64decode(artifact["base64"], validate=True)
                    require(len(content) <= 1000000, "artifact exceeds 1 MB")
                    require(hashlib.sha256(content).hexdigest() == artifact["sha256"],
                            "artifact digest mismatch")
                task.update(status="done", until=0, result=data["result"],
                            artifacts={name: dict(value) for name, value in artifacts.items()},
                            finished_at=seq)
        elif op == "propose":
            proposal = string(data, "proposal", 100)
            require(proposal not in state["proposals"], "proposal already exists")
            require(data.get("base") == state["rule_revision"], "stale rule revision")
            state["proposals"][proposal] = {"text": string(data, "text", 100000),
                "reason": string(data, "reason"), "base": data["base"], "status": "pending"}
        elif op == "ratify":
            require("council" not in state, "use the Steward-approved council process")
            proposal = string(data, "proposal", 100)
            item = state["proposals"][proposal]
            require(item["status"] == "pending" and item["base"] == state["rule_revision"],
                    "proposal is no longer current")
            verify_signature(state["owner_key"], ballot(state, proposal),
                             string(data, "signature", 20000))
            # A revision identifies a transition, not just its text. Returning to
            # old wording must never revive approvals for an earlier incarnation.
            revision = digest(canonical({"parent": state["rule_revision"],
                                         "proposal": proposal,
                                         "text": digest(item["text"])}).decode())
            state.update(rules=item["text"], rule_revision=revision)
            item["status"] = "ratified"
        elif op == "learn":
            lesson = string(data, "lesson", 100)
            require(lesson not in state["lessons"], "lesson already exists")
            key = string(data, "key", 100)
            evidence = string(data, "evidence")
            state["lessons"][lesson] = {"key": key, "claim": string(data, "claim"),
                "evidence": evidence, "status": "observed", "reviews": [], "author": actor}
            peers = [v for v in state["lessons"].values()
                     if v["key"] == key and v["status"] != "superseded"]
            if len(peers) > 1:
                for peer in peers:
                    peer["status"] = "contested"
        elif op == "review":
            lesson = state["lessons"][string(data, "lesson", 100)]
            require(actor != lesson["author"], "independent review required")
            require(actor not in lesson["reviews"], "already reviewed")
            require(lesson["status"] == "observed", "resolve contradictions before review")
            string(data, "evidence")
            lesson["reviews"].append(actor)
        elif op == "supersede":
            old = state["lessons"][string(data, "old", 100)]
            new_id = string(data, "new", 100)
            new = state["lessons"][new_id]
            require(data["old"] != new_id and old["key"] == new["key"] and
                    old["status"] != "superseded" and new["status"] != "superseded",
                    "invalid supersession")
            string(data, "evidence")
            old.update(status="superseded", replaced_by=new_id)
            remaining = [v for v in state["lessons"].values()
                         if v["key"] == new["key"] and v["status"] != "superseded"]
            if len(remaining) == 1:
                new.update(status="observed", reviews=[])
        else:
            raise ValueError(f"unknown operation: {op}")
    if "shelf" in state or "shelf_trials" in state:
        from .shelf_gate import advance
        advance(state, at, seq)
    state.update(sequence=seq, at=at)
    state["receipts"][event["id"]] = seq
    return state
