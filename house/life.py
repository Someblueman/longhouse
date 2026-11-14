"""Recorded places, continuing ambitions and supervised resident lifetimes.

This is a projection, not a process monitor. Only the supervisor's observed
receipts establish process starts/stops; an arrival alone is not proof of liveness.
"""
from __future__ import annotations

import math
import re

from .model import require, string

CONTROLLER = "watch-keeper"
KINDS = {"codex", "opencode", "muse", "agy"}
ROOMS = {"door": "The Door", "hearth": "The Hearth", "workshop": "The Workshop",
         "archive": "The Archive", "council": "The Council", "bedroom": "The Beds"}


def number(value, name, minimum=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= minimum,
            f"invalid {name}")
    return value


def fields(data, required, optional=()):
    require(set(required) <= data.keys() <= set(required) | set(optional), "invalid life fields")


def identifier(data, key):
    value = string(data, key, 100)
    require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", value) is not None, f"invalid {key}")
    return value


def empty():
    return {"rooms": {key: {"name": name} for key, name in ROOMS.items()},
            "ambitions": {}, "runs": {}, "budgets": {}, "requests": {}, "presence": {}}


def latest_run(state: dict, resident: str, *, exclude: str | None = None) -> dict | None:
    runs = (item for key, item in state.get("life", {}).get("runs", {}).items()
            if key != exclude and item["resident"] == resident)
    return max(runs, key=lambda item: item["started_sequence"], default=None)


def return_eligible(state: dict, resident: str, agent: str, model: str, at: float) -> bool:
    """A stopped supervised mind may return; its run and workspace never do."""
    if state.get("maintenance", {}).get("resident_returns") is not True:
        return False
    person = state["residents"].get(resident)
    if not person or person["awake"] is not False:
        return False
    runs = state.get("life", {}).get("runs", {})
    if any(item["resident"] == resident and item["status"] == "active" for item in runs.values()):
        return False
    previous = latest_run(state, resident)
    if not previous or previous["status"] != "completed" or (previous["agent"], previous["model"]) != (agent, model):
        return False
    if ("agent" in person or "model" in person) and (person.get("agent"), person.get("model")) != (agent, model):
        return False
    return not any(task.get("owner") == resident and task["status"] == "claimed" and task["until"] > at
                   for task in state["tasks"].values())


def provider_available(state: dict, agent: str, at: float) -> bool:
    from .maintenance import retry_permit
    return (state.get("life", {}).get("budgets", {}).get(agent, {}).get("until", 0) <= at
            or retry_permit(state, agent, at) is not None)


def backlog_enabled(state: dict) -> bool:
    from .maintenance import BACKLOG_SCOPE
    return "wake_policy" not in state or BACKLOG_SCOPE in state.get("maintenance", {}).get("migrations", {})


EXPLORER_ADMISSION_SECONDS = 900


def explorer_reserved(run: dict, at: float) -> bool:
    """A wake gets a finite chance to claim the real, separately fenced role."""
    return (run["status"] == "active" and "explore_generation" in run
            and at < run["started_at"] + EXPLORER_ADMISSION_SECONDS)


def explorer_owner(state: dict, at: float) -> str | None:
    record = state.get("shelf", {})
    expedition = record.get("rounds", {}).get(record.get("explorer"))
    if (expedition and expedition["until"] > at
            and state["residents"][expedition["owner"]]["awake"]):
        return expedition["owner"]
    return None


def explorer_demand(state: dict, at: float) -> int | None:
    from . import shelf, shelf_gate
    from .maintenance import EXPLORER_SCOPE
    if (EXPLORER_SCOPE not in state.get("maintenance", {}).get("migrations", {})
            or not shelf_gate.enabled(state) or shelf_gate.policy(state) is None):
        return None
    record = state.get("shelf", shelf.empty())
    if len(shelf.shelf_ids(record)) >= 3:
        return None
    if explorer_owner(state, at) is not None:
        return None
    if any(explorer_reserved(run, at) for run in state.get("life", {}).get("runs", {}).values()):
        return None
    return record["generation"]


def workload(state: dict, at: float) -> dict:
    """Count declared work and unclaimed native capacity, not apparent CPU activity."""
    from .home_control import paused
    life = state.get("life", {})
    active = {key: run for key, run in life.get("runs", {}).items() if run["status"] == "active"}
    active_residents = {run["resident"] for run in active.values()}
    requests = life.get("requests", {})
    from . import project_work
    project_routing = project_work.enabled(state)
    pending = [key for key, request in requests.items() if request["status"] == "pending"
               and project_work.help_available(state, request, at, help_id=key)]
    reserved = {request.get("task") for request in requests.values()
                if request["status"] == "pending" or
                (request["status"] == "assigned" and request.get("run") in active)}
    claimed = {task["owner"] for task in state["tasks"].values()
               if task["status"] == "claimed" and (task["until"] > at or task["owner"] in active_residents)}
    task_reservations = {run["task"] for run in active.values()
                         if "task" in run and project_work.reserved(
                             run, at, state["tasks"].get(run["task"], {}))} if project_routing else set()
    exploring = explorer_owner(state, at)
    idle = [run["resident"] for key, run in active.items() if run["resident"] not in claimed
            and run["resident"] != exploring
            and not explorer_reserved(run, at)
            and not (project_routing and "task" in run)
            and not (requests.get(run.get("help_request"), {}).get("status") == "assigned")]
    ready = [key for key, task in state["tasks"].items()
             if backlog_enabled(state) and task.get("ready") is True and task["status"] != "done" and task["until"] <= at
             and not (task["status"] == "claimed" and task["owner"] in active_residents)
             and key not in reserved and key not in task_reservations
             and (not project_routing or "project" not in task
                  or project_work.active_project(state, task["project"], at) is not None)]
    uncovered = max(0, len(ready) - len(idle))
    explore = explorer_demand(state, at)
    return {"ready_tasks": ready, "idle_residents": idle, "pending_help": pending,
            "uncovered_tasks": uncovered, "explore_generation": explore,
            "wanted_starts": 0 if paused(state, at) else min(max(0, 3 - len(active)),
                                 max(1 if not active else 0, len(pending) + uncovered + (explore is not None)))}


def apply(state, event):
    data, actor, at = event["data"], event["actor"], event["at"]
    seq = state["sequence"] + 1
    life = state.setdefault("life", empty())
    kind = string(data, "kind", 40)
    growth = state.get("maintenance", {}).get("room_growth") is True
    if kind in {"room-plan", "room-open", "room-repurpose", "room-close"}:
        from .building import apply as build
        build(state, event)
    elif kind == "identity":
        fields(data, {"kind", "agent", "model"})
        from .providers import validate_model
        validate_model(data["agent"], data["model"])
        resident = state["residents"][actor]
        require("agent" not in resident, "resident kind already recorded")
        assigned = [r for r in life["runs"].values() if r["resident"] == actor]
        require(not assigned or (assigned[-1]["agent"], assigned[-1]["model"]) ==
                (data["agent"], data["model"]), "identity differs from actual assigned route")
        resident.update(agent=data["agent"], model=data["model"])
    elif kind == "room":
        require(not growth, "new rooms require room-plan and witnessed construction")
        fields(data, {"kind", "room", "name"})
        room = identifier(data, "room")
        require(room not in life["rooms"], "room already exists")
        life["rooms"][room] = {"name": string(data, "name", 100), "sequence": seq}
    elif kind == "activity":
        fields(data, {"kind", "room"}, {"task"})
        require(data["room"] in life["rooms"], "unknown room")
        if "task" in data:
            task = state["tasks"].get(data["task"], {})
            require(task.get("owner") == actor and task.get("status") == "claimed"
                    and task["until"] > at, "activity requires own live task")
        if growth:
            from .building import activity
            room = life["rooms"][data["room"]]
            require(room.get("status") != "construction" or data.get("task") == room["task"],
                    "construction activity must name its construction task")
            activity(state, actor, data["room"], at, seq)
        life["presence"][actor] = {**data, "at": at, "sequence": seq}
    elif kind == "ambition":
        fields(data, {"kind", "ambition", "title", "description", "status", "next_step", "expect"})
        key = identifier(data, "ambition")
        old = life["ambitions"].get(key, {})
        require(type(data["expect"]) is int and data["expect"] == old.get("generation", 0),
                "ambition generation changed")
        require(data["status"] in {"growing", "resting", "fulfilled"}, "invalid ambition status")
        for name in ("title", "description", "next_step"):
            string(data, name)
        life["ambitions"][key] = {**data, "generation": data["expect"] + 1,
                                  "resident": actor, "sequence": seq, "at": at}
    elif kind == "help":
        fields(data, {"kind", "request", "reason"}, {"task", "agent", "model", "review_run"})
        key = identifier(data, "request")
        require(key not in life["requests"], "help request exists")
        string(data, "reason")
        if "review_run" in data:
            from .source_delivery import enabled
            require(enabled(state), "source delivery is not enabled")
            source = life["runs"].get(identifier(data, "review_run"), {})
            require(source.get("status") == "completed", "source review requires a stopped contribution")
        if "task" in data:
            require(data["task"] in state["tasks"], "unknown help task")
        if "agent" in data:
            require(data["agent"] in KINDS, "unknown agent kind")
        if "model" in data:
            require("agent" in data, "a model preference requires its agent kind")
            from .providers import validate_model
            validate_model(data["agent"], data["model"])
        life["requests"][key] = {**data, "resident": actor, "status": "pending", "at": at}
    else:
        require(actor == CONTROLLER, "only the supervisor records process observations")
        if kind == "run-start":
            from .home_control import paused
            require(not paused(state, at), "owner paused admissions")
            fields(data, {"kind", "run", "resident", "agent", "model", "source_head",
                          "workspace", "policy_revision", "mode"}, {"help_request", "backlog", "explore_generation",
                                                          "task", "task_generation"})
            from .providers import validate_model
            validate_model(data["agent"], data["model"])
            run = identifier(data, "run")
            resident = identifier(data, "resident")
            require(run not in life["runs"], "run already exists")
            require(resident not in state["residents"] or
                    return_eligible(state, resident, data["agent"], data["model"], at),
                    "run resident already exists and is not eligible to return")
            active = [r for r in life["runs"].values() if r["status"] == "active"]
            require(len(active) < 3, "three residents are already home")
            require(all(r["resident"] != resident for r in active), "resident already running")
            require(provider_available(state, data["agent"], at),
                    "provider is cooling down")
            require(data["mode"] in {"work", "review"}, "invalid work mode")
            require(re.fullmatch("[0-9a-f]{40}", data["source_head"]) is not None,
                    "invalid source head")
            string(data, "policy_revision", 100)
            require(data["workspace"] == "residents/" + run, "invalid private workspace")
            if "explore_generation" in data:
                require(type(data["explore_generation"]) is int and
                        not {"help_request", "backlog"} & data.keys(), "invalid Explorer admission")
                require(explorer_demand(state, at) == data["explore_generation"],
                        "Explorer demand changed")
            if {"task", "task_generation"} & data.keys():
                from .project_work import validate_admission
                validate_admission(state, data, at)
            if "backlog" in data:
                require(data["backlog"] is True and "help_request" not in data,
                        "invalid backlog admission")
                require(workload(state, at)["uncovered_tasks"] > 0,
                        "ready backlog demand changed")
            if "help_request" in data:
                request = life["requests"].get(data["help_request"], {})
                require(request.get("status") == "pending", "help already taken")
                from .project_work import help_available
                require(help_available(state, request, at, help_id=data["help_request"]),
                        "project help demand changed")
                if "review_run" in request:
                    require(resident != life["runs"][request["review_run"]]["resident"],
                            "source reviewer must be independent")
                request.update(status="assigned", run=run)
            from .maintenance import retry_permit
            permit = retry_permit(state, data["agent"], at)
            if permit is not None:
                permit.update(consumed_run=run, consumed_sequence=seq, consumed_at=at)
            life["runs"][run] = {**data, "status": "active", "started_at": at,
                                 "started_sequence": seq}
        elif kind == "run-launched":
            fields(data, {"kind", "run", "pgid"})
            run = life["runs"][data["run"]]
            require(run["status"] == "active" and "pgid" not in run, "run already launched/ended")
            require(type(data["pgid"]) is int and data["pgid"] > 1, "invalid process group")
            run.update(pgid=data["pgid"], launched_sequence=seq)
        elif kind == "run-finish":
            fields(data, {"kind", "run", "outcome", "exit_code", "usage", "elapsed_seconds"})
            run = life["runs"][data["run"]]
            require(run["status"] == "active", "run already ended")
            require(data["outcome"] in {"success", "quota", "interrupted", "failed"}, "invalid outcome")
            require(data["exit_code"] is None or type(data["exit_code"]) is int, "invalid exit code")
            require(isinstance(data["usage"], dict), "invalid usage")
            for key, value in data["usage"].items():
                require(key in {"input_tokens", "output_tokens", "cached_input_tokens", "total_tokens"},
                        "unknown usage field")
                number(value, key)
            number(data["elapsed_seconds"], "elapsed seconds")
            run.update(outcome=data["outcome"], exit_code=data["exit_code"], usage=dict(data["usage"]),
                       elapsed_seconds=data["elapsed_seconds"], status="completed", ended_at=at,
                       ended_sequence=seq)
            if run["resident"] in state["residents"]:
                state["residents"][run["resident"]]["awake"] = False
            # The supervisor has confirmed the entire process group stopped.
            # Fence its old tokens immediately, preserving the generation and
            # token history. Unconfirmed/manual disappearances still use expiry.
            released = []
            for task_id, task in state["tasks"].items():
                if task["owner"] == run["resident"] and task["status"] == "claimed":
                    released.append(task_id)
                    task.update(status="open", owner=None, token=None, until=0,
                                interrupted_run=data["run"])
            run["released_tasks"] = released
            # Native exit success alone does not prove a help request was handled.
            # The supervisor separately records an accepted handoff as resolved.
            if "help_request" in run:
                request = life["requests"][run["help_request"]]
                if request.get("run") == data["run"] and request["status"] == "assigned":
                    request.update(status="pending")
                    request.pop("run", None)
        elif kind == "budget":
            fields(data, {"kind", "agent", "until", "reason"})
            require(data["agent"] in KINDS, "unknown agent kind")
            number(data["until"], "cooldown", at)
            string(data, "reason", 1000)
            life.setdefault("budget_observations", {})[data["agent"]] = seq
            previous = life["budgets"].get(data["agent"], {})
            # A second concurrent failure cannot shorten an existing quota wait.
            if data["until"] >= previous.get("until", 0):
                life["budgets"][data["agent"]] = {**data, "at": at, "sequence": seq}
        elif kind == "help-resolved":
            fields(data, {"kind", "request", "reason"})
            request = life["requests"][data["request"]]
            string(data, "reason")
            require(request["status"] != "resolved", "request already resolved")
            request.update(status="resolved", resolution=data["reason"], resolved_at=at)
        else:
            raise ValueError("unknown life operation")
