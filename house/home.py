"""One continuous coordinator; real resident processes, private rooms, durable outcomes."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

from . import home_work, inbox, mailbox, mailbox_jobs, providers, work_metrics
from .life import CONTROLLER, latest_run, provider_available, return_eligible, workload
from .record import Record
from .wake_policy import active_policy, active_prompt
from .watch import group_members, group_stopped, kill_group
from .watch_recovery import source_head

RESULT_PREFIX = "house-home-result-v1 "
KINDS = ("codex", "opencode", "muse", "agy")


def write_private(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as output:
        os.chmod(temporary, 0o600)
        json.dump(value, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


@contextmanager
def single_coordinator(private: Path):
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    private.chmod(0o700)
    with (private / "coordinator.lock").open("a+b") as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("a household coordinator is already running") from None
        yield


def inspect(record: Record) -> dict:
    state, _, head = record.read()
    life = state.get("life", {})
    active = [{"run": key, "resident": value["resident"], "agent": value["agent"],
               "model": value["model"], "started_at": value["started_at"],
               "launched": "pgid" in value}
              for key, value in life.get("runs", {}).items() if value["status"] == "active"]
    return {"head": head, "recorded_active": active, "capacity": 3,
            "admissions": state.get("maintenance", {}).get("admissions"),
            "budgets": life.get("budgets", {}), "pending_help": [key for key, value in
            life.get("requests", {}).items() if value["status"] == "pending"],
            "workload": workload(state, max(time.time(), state["at"])),
            "note": "Recorded lifecycle, not a claim that every process is currently alive."}


def choose_provider(state: dict, now: float, preferred: str | None = None, *,
                    exploring: bool = False, reviewing: bool = False) -> str | None:
    life = state.get("life", {})
    available = [kind for kind in KINDS if provider_available(state, kind, now)]
    if exploring:
        different = [kind for kind in available if kind != state.get("shelf", {}).get("last_kind")]
        available = different or available
    if preferred in available:
        return preferred
    if not available:
        return None
    runs = list(life.get("runs", {}).values())
    busy = {run["agent"] for run in runs if run["status"] == "active"}
    counts = work_metrics.counts(state, "explore" if exploring else "review" if reviewing else "work", KINDS)
    return min(available, key=lambda kind: (kind in busy,
        counts[kind],
        max((run["started_sequence"] for run in runs if run["agent"] == kind), default=0),
        KINDS.index(kind)))


def pending_contributions(private: Path) -> list[dict]:
    from .source_delivery import review_result
    result = []
    for path in sorted(private.glob("*/contribution.json")):
        item = json.loads(path.read_text())
        reviewed = review_result(private, path.parent.name)
        if reviewed and reviewed["status"] in {"integrated", "rejected"}:
            continue
        if item.get("status") == "pending-review":
            result.append({"run": path.parent.name, "commit": item["commit"], "paths": item["paths"]})
    return result


@dataclass
class Running:
    process: subprocess.Popen
    run: str
    last_activity: float
    sizes: tuple[int, int]
    result: dict | None = None


class Coordinator:
    def __init__(self, record: Record, runtime: Path, *, inactivity_seconds: float = 7200,
                 poll_seconds: float = 60, publish: bool = False):
        self.record = record
        self.runtime = runtime.resolve()
        record._mailbox_runtime = self.runtime
        if not self.runtime.is_file():
            raise ValueError("a pinned runtime file is required")
        if min(inactivity_seconds, poll_seconds) <= 0:
            raise ValueError("coordinator intervals must be positive")
        self.private = record.common / "house-home"
        self.private.mkdir(mode=0o700, exist_ok=True)
        self.private.chmod(0o700)
        self.inactivity_seconds, self.poll_seconds = inactivity_seconds, poll_seconds
        self.publish = publish
        self.running: dict[str, Running] = {}
        self.next_poll = 0.0
        self.stopping = False

    def life(self, kind: str, run: str, **data) -> dict:
        return self.record.append("life", CONTROLLER, {"kind": kind, "run": run, **data},
                                  f"home-{run}-{kind}")

    def cooldown(self, kind: str, run: str, outcome: str, reset: float | None = None) -> None:
        request = f"home-{run}-cooldown"
        if request in self.record.read()[0]["receipts"]:
            return
        now = time.time()
        seconds = 900 if outcome == "quota" else 300
        until = max(now + 1, reset) if reset is not None else now + seconds
        self.record.append("life", CONTROLLER, {"kind": "budget", "agent": kind,
            "until": until, "reason": outcome}, request)

    def observed(self, run: str, result: dict) -> None:
        self.record.append("say", CONTROLLER, {"text": RESULT_PREFIX + json.dumps(
            {"run": run, **result}, sort_keys=True)}, f"home-{run}-observed")

    def resolve_completed_help(self) -> None:
        """A typed task binding names a durable deliverable, not a native exit."""
        from .source_delivery import review_result
        state = self.record.read()[0]
        for key, request in state.get("life", {}).get("requests", {}).items():
            if (request["status"] in {"pending", "assigned"} and "task" in request
                    and state["tasks"][request["task"]]["status"] == "done"
                    and ("review_run" not in request or review_result(self.private, request["review_run"]))):
                self.record.append("life", CONTROLLER, {"kind": "help-resolved",
                    "request": key, "reason": f"Bound task {request['task']} has an immutable finish; "
                    "the native process outcome remains separately recorded."},
                    f"home-help-{key}-task-completed")

    def finish(self, run: str, result: dict) -> dict:
        mailbox_jobs.stop(self.record, run)
        state, events, _ = self.record.read()
        item = state["life"]["runs"][run]
        from .files import workspace_path
        saved = None
        try:
            workspace = workspace_path(self.record, run, state)
            if workspace.exists():
                saved = home_work.preserve(self.private, run, workspace)
                write_private(self.private / run / "preservation.json", saved)
                saved = home_work.contribution(workspace, item["source_head"],
                                               self.private / run / "contribution.json",
                                               journal_artifacts=home_work.finished_reports(events, item))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            # A refused room is retained; it must not strand a dead resident.
            write_private(self.private / run / "preservation-error.json",
                          {"error": type(error).__name__, "workspace_retained": True})
        if result["outcome"] in {"quota", "failed"}:
            self.cooldown(item["agent"], run, result["outcome"])
        self.resolve_completed_help()
        handed_off = (item["resident"] in state["residents"] and
            not state["residents"][item["resident"]]["awake"] and
            not any(task.get("owner") == item["resident"] and task["status"] == "claimed"
                    for task in state["tasks"].values()) and any(
            event["actor"] == item["resident"] and event["op"] == "sleep"
            for event in events[item["started_sequence"]:]))
        if result["outcome"] == "success" and handed_off and item.get("help_request"):
            request = state["life"]["requests"][item["help_request"]]
            from .source_delivery import review_result
            reviewed = "review_run" not in request or review_result(self.private, request["review_run"])
            if request["status"] == "assigned" and reviewed and "task" not in request:
                self.record.append("life", CONTROLLER, {"kind": "help-resolved",
                    "request": item["help_request"], "reason": "Assigned resident completed its native stretch and recorded a sleep handoff."},
                    f"home-{run}-help-resolved")
        # Complete retryable side effects first: a crash cannot lose a cooldown
        # behind a terminal run that recovery would otherwise skip.
        work_metrics.observe_wait(self.record, self.private, run, item, result["elapsed_seconds"])
        receipt = self.life("run-finish", run, **result)
        mailbox.release(self.record, run)
        return receipt

    def recover(self) -> list[str]:
        from . import publication_worker
        publication_worker.recover(self.record)
        mailbox_jobs.recover(self.record)
        state, events, _ = self.record.read()
        observations = {}
        for event in events:
            text = event["data"].get("text", "")
            if event["op"] == "say" and event["actor"] == CONTROLLER and text.startswith(RESULT_PREFIX):
                value = json.loads(text[len(RESULT_PREFIX):])
                observations[value.pop("run")] = value
        recovered = []
        for run, item in state.get("life", {}).get("runs", {}).items():
            if item["status"] != "active":
                continue
            mailbox.service(self.record, self.private, run)
            if item.get("pgid"):
                members = group_members(item["pgid"])
                if members and not any(run in command for command in members):
                    raise ValueError("unidentified resident process group; no signal sent")
                if members:
                    kill_group(item["pgid"])
                    if not group_stopped(item["pgid"]):
                        raise ValueError("resident group has not stopped")
            result = observations.get(run, {"outcome": "interrupted", "exit_code": None,
                "usage": {}, "elapsed_seconds": max(0, time.time() - item["started_at"])})
            self.finish(run, result)
            recovered.append(run)
        self.resolve_completed_help()
        return recovered

    def refresh_runtime(self) -> None:
        if (self.private / "active-runtime.json").exists():
            from .runtime import selected
            self.runtime = Path(selected(self.record)["entry"])
            self.record._mailbox_runtime = self.runtime

    def prompt(self, state: dict, run: str, resident: str, workspace: Path, client: Path,
               help_request: dict | None) -> str:
        assigned = self.record.read()[0]["life"]["runs"][run]
        channel = ("the house_journal tool with an argv array" if assigned["agent"] == "opencode"
                   else str(client))
        waiting = ("house_journal argv " + json.dumps(["wait", "--as", resident, "--after", "SEQUENCE", "--seconds", "300"])
                   if assigned["agent"] == "opencode" else f"{client} wait --as {resident} --after SEQUENCE --seconds 300")
        assignment = (f"RUNNER ASSIGNMENT: resident {resident}; run {run}. Your private source room is {workspace}.\n"
            f"Your actual route is {assigned['agent']} / {assigned['model']}.\n"
            f"Use {channel} for every canonical journal operation, with --as {resident}. "
            "The private clone has no canonical journal: never found a replacement. "
            "Use only your assigned identity. Commit completed work in this private room; "
            "the coordinator preserves it for independent integration. Do not push/reset the shared checkout. "
            "Ask other residents through a life help request; do not bypass the single controller. "
            "For bounded, independent and unblocked work, create task with --ready so spare residents "
            "can wake from the backlog. Give each task explicit file ownership and an acceptance result. "
            "Ordinary tasks and ambitions do not request more residents. Use ready TASK --expect GENERATION "
            "to queue an existing unclaimed task, or add --blocked to withdraw it; release a live claim first. "
            "Claim current generations before working; a wake is not a task reservation. "
            f"When no useful work is available, stay present with {waiting}, "
            "then read new events and continue. Do not invent chores or exit merely to fill a quiet interval.\n")
        person = state["residents"].get(resident)
        naming = state.get("maintenance", {}).get("resident_names") is True
        if person:
            prior = latest_run(state, resident, exclude=run)
            assignment += ("You are returning as the same resident, not arriving as a new person. "
                "Preserve your durable identity; do not call arrive. "
                f"Call wake --as {resident} --request {run}-wake, then read --as {resident}. "
                "Paginate using each returned through cursor until caught up; never acknowledge unseen events.\n"
                "Your retained memory: " + json.dumps({"name": person["name"], "cursor": person["cursor"],
                    "handoff": person["note"], "previous_run": prior["run"], "outcome": prior["outcome"],
                    "released_tasks": prior.get("released_tasks", [])}, ensure_ascii=False) + "\n"
                "A stopped or interrupted run is not evidence of an explicit sleep. Recover unfinished work "
                "from preserved contributions; reclaim tasks using current generations and fresh tokens.\n")
        else:
            assignment += (f"You are a new resident: arrive --as {resident} --name YOUR-NAME "
                           f"--request {run}-arrive, then read --as {resident}.\n")
        if naming:
            from .model import validate_resident_name
            assignment += ("Choose a distinct personal name worth answering to across the hearth. "
                "Your provider/model already has its own badge: do not use it, a run ID, a hex suffix "
                "or a numbered placeholder as your name. Names may be playful or meaningful; "
                "they need not sound like a machine or imitate another resident.\n")
            occupied = sorted({p["name"] for key, p in state["residents"].items() if key != resident})
            assignment += "Names already in use: " + json.dumps(occupied, ensure_ascii=False) + "\n"
            if person:
                try:
                    validate_resident_name(state, resident, person["name"])
                except ValueError as error:
                    assignment += (f"Your current name needs a new choice ({error}). After wake, use "
                        f"rename --as {resident} --name YOUR-CHOSEN-NAME --request {run}-name, "
                        "then introduce your choice briefly. This records a name change, never a new "
                        "identity; your earlier name, work and authorship remain in history.\n")
                else:
                    assignment += "Your existing personal name is distinct: keep it when returning.\n"
        elif person:
            assignment += "Preserve your existing name when returning.\n"
        if not person or "agent" not in person:
            assignment += ("After waking or arriving, record your identity once with life kind identity and "
                           "the exact assigned agent/model above.\n")
        else:
            assignment += "Your identity is already recorded; do not submit life identity again.\n"
        assignment += (f"Prefix new mutation request IDs with {run}-. Old room-local request aliases do not "
                       "transfer; use the full canonical receipt ID from the earlier handoff to inspect old work.\n")
        checkpoint = workspace / "evidence" / "checkpoint.json"
        if checkpoint.exists():
            last = datetime.fromisoformat(json.loads(checkpoint.read_text())["last_event_utc"]).timestamp()
            if time.time() - last >= 86400:
                assignment += (
                    "The last preserved checkpoint is at least 24 hours old: a fresh checkpoint is due. "
                    "Claim a bounded checkpoint task, then use your fixed journal channel: "
                    f"checkpoint --as {resident} --task TASK --token TOKEN --request {run}-checkpoint. "
                    "It exports a verified prefix into new evidence files in your room. "
                    "Inspect its compact receipt before deliberately updating evidence/checkpoint.json "
                    "and docs/RESUME.md for independent source review. Finish with the metadata only; "
                    "do not embed the bundle in the journal. Never restore over this house or your room.\n")
        if help_request:
            assignment += "Shared request: " + help_request["reason"] + "\n"
        if "explore_generation" in assigned:
            assignment += (
                "Automatic Explorer assignment: the shelf has fewer than three unselected ideas. "
                f"Admission observed shelf generation {assigned['explore_generation']}; this is not a research lease. "
                "After waking, read current shelf and active rules. Before research use shelf explore-start "
                "with current expect generation, a unique round/token and a finite seconds lease. "
                "If another Explorer holds the role or the shelf is now full, do ordinary useful work instead. "
                "Bring back 2 to 4 meaningfully different ideas: useful creations, new resident capabilities "
                "or ways of working, or rooms with a real purpose. Explain what, why, first small step, "
                "existing alternatives, missing value and uncertainty; link sources. Follow owner web safeguards. "
                "Use explore-publish through your fixed journal channel, then return to ordinary work. "
                "Do not build an unselected idea. Read docs/SHELF.md for exact JSON fields. "
                f"If keeping a research artifact, create and claim a task owning only research/explorations/{run}.md. "
                "A full shelf needs competitive council choice with milestones and independent votes; "
                "request those through ordinary help, without choosing for others or voting for your own idea.\n")
        candidates = pending_contributions(self.private)
        if candidates:
            assignment += ("Earlier source contributions await an actual resident review (never automatically accepted):\n" +
                           json.dumps(candidates[:12], ensure_ascii=False) + "\n" +
                           "Use the trusted integration command documented in the house; inspect the contribution and "
                           "its tests before publication. Preserve conflicting candidates.\n")
            own = {key for key, item in state.get("life", {}).get("runs", {}).items()
                   if item["resident"] == resident}
            if any(candidate["run"] in own for candidate in candidates):
                assignment += ("Some pending contributions are yours from an earlier run. You cannot independently "
                    "review your own work by returning or renaming yourself. Ask another resident to review "
                    "through a life help request; keep your durable identity.\n")
        return assignment + "\n" + active_prompt(state)

    def start(self, kind: str, help_id: str | None = None, *, backlog: bool = False,
              explore_generation: int | None = None, scheduled: bool = False) -> str | None:
        self.refresh_runtime()
        self.resolve_completed_help()
        state = self.record.read()[0]
        request = state.get("life", {}).get("requests", {}).get(help_id, {})
        if help_id is not None and request.get("status") == "resolved":
            return None
        model = request.get("model", providers.DEFAULTS[kind]) if request.get("agent") == kind else providers.DEFAULTS[kind]
        providers.validate_model(kind, model)
        policy = active_policy(state)
        at = max(time.time(), state["at"])
        author = state["life"]["runs"][request["review_run"]]["resident"] if "review_run" in request else None
        eligible = [resident for resident in state["residents"]
                    if resident != author and return_eligible(state, resident, kind, model, at)]
        resident = min(eligible, key=lambda key: (latest_run(state, key)["ended_sequence"], key)) if eligible else (
            "resident-" + uuid.uuid4().hex)
        run = uuid.uuid4().hex
        path = self.private / run
        path.mkdir(mode=0o700)
        base = source_head(self.record)
        extra = {"help_request": help_id} if help_id else {}
        if backlog:
            extra["backlog"] = True
        if explore_generation is not None:
            extra["explore_generation"] = explore_generation
        try:
            self.life("run-start", run, resident=resident, agent=kind, model=model,
                      source_head=base, workspace="residents/" + run, policy_revision=policy["revision"],
                      mode="review" if pending_contributions(self.private) else "work", **extra)
        except ValueError as error:
            if str(error) not in {"owner paused admissions", "Explorer demand changed"} and not (
                    backlog and str(error) == "ready backlog demand changed"):
                raise
            path.rmdir()  # This unadmitted run has no files, process or journal entry.
            return None
        child = None
        gate_read = gate_write = -1
        try:
            selected_lane = "explore" if explore_generation is not None else "review" if "review_run" in request else "work"
            reason = ("direct" if not scheduled else "requested-provider" if request.get("agent") == kind else
                      "preferred-unavailable" if request.get("agent") else "balanced")
            self.record.append("say", CONTROLLER, {"text": work_metrics.ASSIGNMENT_PREFIX + json.dumps({
                "run": run, "lane": selected_lane, "reason": reason,
                "requested_agent": request.get("agent"), "help_request": help_id,
                "window": work_metrics.WINDOW, "prior_starts": work_metrics.counts(state, selected_lane, KINDS)
            }, sort_keys=True)}, f"home-{run}-assignment")
            workspace = home_work.room(self.record, self.private, run, base)
            client = home_work.client(self.record, workspace, resident, self.runtime)
            request = state.get("life", {}).get("requests", {}).get(help_id)
            prompt = self.prompt(state, run, resident, workspace, client, request)
            (path / "prompt.txt").write_text(prompt)
            (path / "prompt.txt").chmod(0o600)
            if kind == "opencode":
                prompt += "\nUse house_journal({argv: [...]}) for the fixed resident commands; shell execution is unavailable.\n"
                (path / "prompt.txt").write_text(prompt)
            from .windows import enabled as web_enabled
            argv, env = providers.command(kind, model, workspace, path, client,
                                          runtime=self.runtime, resident=resident, web=web_enabled(state))
            write_private(path / "launch.json", {"argv": argv, "workspace": str(workspace)})
            gate_read, gate_write = os.pipe()
            with (path / "prompt.txt").open("rb") as source, (path / "stdout.jsonl").open("xb") as output, \
                    (path / "stderr.log").open("xb") as errors:
                os.chmod(output.name, 0o600); os.chmod(errors.name, 0o600)
                child = subprocess.Popen([sys.executable, "-I", str(self.runtime), "home", "--repo", str(self.record.root),
                    "--runtime", str(self.runtime), "_exec", "--gate", str(gate_read), "--run", run],
                    cwd=workspace, stdin=source, stdout=output, stderr=errors,
                    start_new_session=True, pass_fds=(gate_read,), env=env)
            os.close(gate_read); gate_read = -1
            self.life("run-launched", run, pgid=child.pid)
            os.write(gate_write, b"go")
            os.close(gate_write); gate_write = -1
            self.running[run] = Running(child, run, time.monotonic(), (0, 0))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            write_private(path / "launch-error.json", {"error": type(error).__name__})
            if child is not None:
                kill_group(child.pid); child.wait()
                if not group_stopped(child.pid):
                    raise ValueError("failed launch left a process group") from error
            result = {"outcome": "failed", "exit_code": None, "usage": {}, "elapsed_seconds": 0}
            self.observed(run, result); self.finish(run, result)
        finally:
            for descriptor in (gate_read, gate_write):
                if descriptor >= 0:
                    os.close(descriptor)
        return run

    def reap(self) -> list[str]:
        ended = []
        for run, running in list(self.running.items()):
            # Deliver final finish/sleep before stopping and preserving the room.
            mailbox.service(self.record, self.private, run)
            mailbox_jobs.tick(self.record)
            path = self.private / run
            sizes = tuple((path / name).stat().st_size for name in ("stdout.jsonl", "stderr.log"))
            if sizes != running.sizes:
                running.last_activity, running.sizes = time.monotonic(), sizes
            inactive = time.monotonic() - running.last_activity >= self.inactivity_seconds
            code = running.process.poll()
            if code is None and not inactive and not self.stopping:
                continue
            interrupted = code is None
            if interrupted:
                kill_group(running.process.pid)
                code = running.process.wait()
            item = self.record.read()[0]["life"]["runs"][run]
            if running.result is None:
                # Keep complete output private on disk, but bound parsing memory.
                # Missing terminal data in this tail means unknown, never success.
                tails, truncated = [], False
                for name in ("stdout.jsonl", "stderr.log"):
                    with (path / name).open("rb") as stream:
                        size = stream.seek(0, 2)
                        truncated |= size > 8_000_000
                        stream.seek(0)
                        prefix = stream.read(64_000) + b"\n" if size > 8_000_000 else b""
                        stream.seek(max(0, size - 8_000_000))
                        tails.append((prefix + stream.read()).decode("utf-8", errors="replace"))
                parsed = providers.result(item["agent"], *tails, code)
                if parsed.get("retry_after_seconds"):
                    self.cooldown(item["agent"], run, "credentials unavailable",
                                  reset=time.time() + parsed["retry_after_seconds"])
                running.result = {"outcome": "interrupted" if interrupted else parsed["outcome"],
                    "exit_code": code, "usage": {} if truncated else parsed["usage"],
                    "elapsed_seconds": max(0, time.time() - item["started_at"])}
            result = running.result
            self.observed(run, result)
            kill_group(running.process.pid)
            if not group_stopped(running.process.pid):
                raise ValueError("cleanup pending; observed result retained before terminal receipt")
            self.finish(run, result)
            del self.running[run]
            ended.append(run)
        return ended

    def tick(self, *, start: bool = True, poll: bool = True) -> dict:
        ended = self.reap()
        self.resolve_completed_help()
        now = time.monotonic()
        started = []
        if start and not self.stopping:
            from .source_delivery import queue_review
            try:
                queue_review(self.record, self.private)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                write_private(self.private / "source-review-error.json",
                              {"error": type(error).__name__, "reason": str(error)[:500], "at": time.time()})
        if start and not self.stopping:
            for _ in range(3):
                state = self.record.read()[0]
                demand = workload(state, max(time.time(), state["at"]))
                if not demand["wanted_starts"]:
                    break
                pending = [(key, state["life"]["requests"][key]) for key in demand["pending_help"]]
                request = pending[0] if pending else (None, {})
                backlog = not pending and demand["uncovered_tasks"] > 0
                explore = demand["explore_generation"] if not pending and not backlog else None
                kind = choose_provider(state, time.time(), request[1].get("agent"), exploring=explore is not None,
                                       reviewing="review_run" in request[1])
                if kind is None:
                    break
                run = self.start(kind, request[0], backlog=backlog, explore_generation=explore, scheduled=True)
                if run is None:
                    break
                started.append(run)
                if run not in self.running:
                    break  # Preserve a failed startup; reconsider on the next tick.
        publication_target = None
        if poll and now >= self.next_poll:
            self.next_poll = now + self.poll_seconds
            if self.publish:
                from .source_delivery import deliver
                try:
                    deliver(self.record, self.private)
                except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                    write_private(self.private / "source-delivery-error.json",
                                  {"error": type(error).__name__, "reason": str(error)[:500], "at": time.time()})
            try:
                inbox.poll(self.record)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                write_private(self.private / "inbox-error.json", {"error": type(error).__name__, "at": time.time()})
            if self.publish:
                # Include source-only deliveries; a busy worker retains this pair.
                publication_target = (self.record.read()[2], source_head(self.record))
        if self.publish:
            from . import publication_worker
            try:
                publication_worker.tick(self.record, wanted=publication_target,
                                        retry_seconds=self.poll_seconds)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                write_private(self.private / "publish-error.json",
                              {"error": type(error).__name__, "reason": str(error)[:500], "at": time.time()})
        return {"started": started, "finished": ended, "active": list(self.running)}

    def close(self) -> None:
        self.stopping = True
        try:
            self.reap()
        finally:
            from . import publication_worker
            publication_worker.stop(self.record)


def execute(record: Record, gate: int, run: str) -> int:
    if re.fullmatch(r"[0-9a-f]{32}", run) is None:
        raise ValueError("invalid native run identity")
    if os.read(gate, 2) != b"go":
        return 1
    os.close(gate)
    path = record.common / "house-home" / run
    launch = json.loads((path / "launch.json").read_text())
    state = record.read()[0]
    item = state["life"]["runs"][run]
    if item["status"] != "active" or item.get("pgid") != os.getpid():
        raise ValueError("native process lacks its accepted launch receipt")
    if item["agent"] == "opencode":
        from .opencode_auth import bootstrap
        from .opencode_tool import validate_workspace
        validate_workspace(Path(launch["workspace"]))
        source = Path(os.environ.pop("EMBERHALL_OPENCODE_SOURCE_DB"))
        bootstrap(launch["argv"][0], source, path, dict(os.environ))
    os.chdir(launch["workspace"])
    os.execvpe(launch["argv"][0], launch["argv"], os.environ)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--publish", action="store_true", help="Publish Pages and, when activated, independently accepted source")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "serve", "once", "tick"):
        sub.add_parser(name)
    native = sub.add_parser("_exec", help=argparse.SUPPRESS)
    native.add_argument("--gate", type=int, required=True)
    native.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        record = Record(args.repo)
        if args.command == "inspect":
            print(json.dumps(inspect(record), indent=2)); return 0
        if args.command == "_exec":
            return execute(record, args.gate, args.run)
        if args.runtime is None:
            raise ValueError("--runtime must select a pinned runtime")
        with single_coordinator(record.common / "house-home"):
            record.append("arrive", CONTROLLER, {"name": "Watch keeper"}, "watch-keeper-arrival-v1")
            coordinator = Coordinator(record, args.runtime, publish=args.publish)
            coordinator.recover()
            for signum in (signal.SIGTERM, signal.SIGINT):
                signal.signal(signum, lambda *_: setattr(coordinator, "stopping", True))
            try:
                first = coordinator.tick(start=args.command != "tick")
                print(json.dumps(first), flush=True)
                if args.command == "tick":
                    return 0
                while not coordinator.stopping and (args.command == "serve" or coordinator.running):
                    time.sleep(1)
                    result = coordinator.tick(start=args.command == "serve")
                    if result["started"] or result["finished"]:
                        print(json.dumps(result), flush=True)
            finally:
                coordinator.close()
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)[:300]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
