"""Explicit project associations and finite scheduling hints; never task ownership."""
from __future__ import annotations

from .model import require, string

SCOPE = "project-work-routing-20261114"
ADMISSION_SECONDS = 900


def enabled(state: dict) -> bool:
    return "wake_policy" not in state or SCOPE in state.get("maintenance", {}).get("migrations", {})


def active_project(state: dict, project: str, at: float) -> dict | None:
    item = state.get("shelf", {}).get("projects", {}).get(project)
    # The shelf materializes automatic drops at the next event. Do not schedule
    # already overdue work in the interval before that transition is recorded.
    if item and item["status"] == "active" and at < item["deadline"] + 7 * 86400:
        return item
    return None


def association(state: dict, data: dict, at: float) -> str:
    require(enabled(state), "project work runtime not enabled")
    project = string(data, "project", 100)
    require(active_project(state, project, at) is not None, "unknown or inactive project")
    return project


def reserved(run: dict, at: float, task: dict) -> bool:
    return (run["status"] == "active" and "task" in run
            and run.get("task_generation") == task.get("generation")
            and at < run["started_at"] + ADMISSION_SECONDS)


def available(state: dict, task_id: str, at: float, *, help_id: str | None = None) -> bool:
    task = state["tasks"].get(task_id, {})
    runs = state.get("life", {}).get("runs", {})
    active = {key: run for key, run in runs.items() if run["status"] == "active"}
    if (task.get("ready") is not True or task.get("status") == "done" or task.get("until", 0) > at
            or any(run["resident"] == task.get("owner") for run in active.values())
            or any(run.get("task") == task_id and reserved(run, at, task) for run in active.values())):
        return False
    if "project" in task and active_project(state, task["project"], at) is None:
        return False
    return not any(key != help_id and request.get("task") == task_id
                   and ((request["status"] == "pending" and help_id is None) or
                        (request["status"] == "assigned" and request.get("run") in active))
                   for key, request in state.get("life", {}).get("requests", {}).items())


def help_available(state: dict, request: dict, at: float, *, help_id: str) -> bool:
    """A project-bound help task cannot become an ordinary dispatch fallback."""
    task = state["tasks"].get(request.get("task"), {})
    if not enabled(state) or "project" not in task:
        return True
    if "review_run" in request:
        # Reviewing a completed deliverable is separate from claiming its task.
        return active_project(state, task["project"], at) is not None
    return available(state, request["task"], at, help_id=help_id)


def help_projects(state: dict, request: dict, at: float, *, help_id: str) -> set[str]:
    """Follow typed task/run receipts only; prose and source paths are not links."""
    tasks = state["tasks"]
    linked = set()
    task_id = request.get("task")
    if task_id in tasks and available(state, task_id, at, help_id=help_id):
        linked.add(task_id)
    if "review_run" in request:
        run = state.get("life", {}).get("runs", {}).get(request["review_run"], {})
        if run.get("status") == "completed":
            if run.get("task") in tasks:
                linked.add(run["task"])
            # Older runs have no admission binding. An immutable task finish
            # within that exact resident's run is also an explicit source link.
            linked.update(key for key, task in tasks.items()
                          if task.get("status") == "done" and task.get("owner") == run["resident"]
                          and run["started_sequence"] < task.get("finished_at", 0) < run["ended_sequence"])
    return {tasks[key]["project"] for key in linked if "project" in tasks[key]
            and active_project(state, tasks[key]["project"], at) is not None}


def first(state: dict, at: float, ready: list[str], pending: list[str]) -> dict | None:
    """Deadline, project ID and task/request ID provide a stable total ordering."""
    if not enabled(state):
        return None
    choices = []
    for task_id in ready:
        task = state["tasks"][task_id]
        project = task.get("project")
        if project and available(state, task_id, at):
            item = active_project(state, project, at)
            if item:
                choices.append(((item["deadline"], project, task_id, ""),
                                {"task": task_id, "task_generation": task["generation"]}))
    for key in pending:
        request = state["life"]["requests"][key]
        for project in help_projects(state, request, at, help_id=key):
            item = active_project(state, project, at)
            choices.append(((item["deadline"], project, request.get("task", ""), key),
                            {"help_request": key}))
    return min(choices, key=lambda pair: pair[0])[1] if choices else None


def validate_admission(state: dict, data: dict, at: float) -> None:
    require(enabled(state), "project work runtime not enabled")
    task_id = string(data, "task", 100)
    task = state["tasks"].get(task_id, {})
    require(type(data.get("task_generation")) is int
            and data["task_generation"] == task.get("generation"), "project task generation changed")
    require("project" in task and available(state, task_id, at), "project task demand changed")
    require(data.get("backlog") is True and not {"help_request", "explore_generation"} & data.keys(),
            "invalid project task admission")
