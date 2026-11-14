"""Publish a bounded, public dollhouse projection at every verified journal event."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import re
import subprocess
import time

from .model import apply_event
from .record import Record
from .work_metrics import public_observation

ROOMS = {"door": "The door", "hearth": "Hearth", "workshop": "Workshop",
         "archive": "Archive", "council": "Council"}
KINDS = {"codex", "opencode", "muse", "agy"}
WATCH_PREFIX = "house-watch-v1 "


def label(value: object, limit: int = 180) -> str:
    """Public labels are plain, bounded strings, never rendered as HTML."""
    return " ".join(str(value).split())[:limit]


def usage(value: object) -> dict:
    """Never publish arbitrary provider responses, credentials or log text."""
    if not isinstance(value, dict):
        return {}
    allowed = {"input_tokens", "output_tokens", "total_tokens", "cached_tokens", "cached_input_tokens",
               "requests", "remaining", "limit", "used"}
    return {k: v for k, v in value.items() if k in allowed and
            type(v) in (int, float) and math.isfinite(v) and v >= 0}


def shelf_view(state: dict) -> dict:
    """Public real work only; never publish Explorer tokens or isolated trials."""
    from . import shelf_gate
    shelf = state.get("shelf", {})
    ideas = []
    for key, idea in shelf.get("ideas", {}).items():
        history = []
        for entry in idea["history"]:
            public = {k: label(v, 2000) if isinstance(v, str) else v
                      for k, v in entry.items()}
            if "choice" in entry:
                choice = shelf["choices"][entry["choice"]]
                public["reasons"] = [label(v["reason"], 2000) for v in choice["votes"].values()
                                     if v["counted"]]
            history.append(public)
        ideas.append({"id": key, **{k: label(idea[k], 2000) for k in
            ("title", "what", "why", "first_step", "author", "status")},
            "sources": list(idea["sources"]), "losses": idea["losses"], "history": history})
    projects = [{"id": key, "title": label(shelf["ideas"][p["idea"]]["title"], 2000),
                 **{k: label(p[k], 2000) if isinstance(p[k], str) else p[k]
                    for k in ("idea", "owner", "status", "milestone", "deadline", "extended", "lesson")
                    if k in p}} for key, p in shelf.get("projects", {}).items()]
    expedition = shelf.get("rounds", {}).get(shelf.get("explorer"))
    return {"enabled": shelf_gate.enabled(state), "policy": shelf_gate.policy(state),
            "ideas": ideas, "projects": projects, "explorer": {
                "resident": expedition["owner"], "agent": expedition["agent"],
                "until": expedition["until"]} if expedition else None}


def voting_view(state: dict, identities: dict, event_times: dict, origins: dict | None = None) -> dict:
    """Allowlisted decisions as known at this frame, never trial votes or raw logs."""
    def person(actor):
        resident = state["residents"].get(actor, {})
        identity = identities.get(actor, {})
        return {"id": actor, "name": label(resident.get("name", actor), 100),
                "agent": label(identity.get("agent", "unrecorded"), 30)}

    shelf = state.get("shelf", {})
    choices = []
    for key, choice in shelf.get("choices", {}).items():
        candidates = [{"id": idea, "title": label(shelf["ideas"][idea]["title"], 200),
                       "author": person(shelf["ideas"][idea]["author"]),
                       "milestone": label(choice["milestones"][idea]["milestone"], 20000),
                       "seconds": choice["milestones"][idea]["seconds"]}
                      for idea in choice["candidates"]]
        votes = [{"resident": person(actor), "idea": vote["idea"],
                  "reason": label(vote["reason"], 20000), "counted": vote["counted"],
                  "sequence": vote["sequence"], "at": event_times[vote["sequence"]]}
                 for actor, vote in choice["votes"].items()]
        choices.append({"id": key, "status": choice["status"], "owner": person(choice["owner"]),
                        "opened_sequence": choice["opened_sequence"],
                        "closed_sequence": choice.get("closed_sequence"),
                        "selection_version": choice.get("selection_version", 1),
                        "winner": choice.get("winner"), "candidates": candidates, "votes": votes})
    proposals = []
    origins = origins or {}
    for key, proposal in state["proposals"].items():
        notice = proposal.get("notice")
        trial = proposal.get("trial")
        rule = state.get("council", {}).get("rules", {}).get(key, {})
        proposals.append({"id": key, "title": label(proposal.get("title", key), 200),
            "mode": proposal.get("mode", "legacy"), "author": person(proposal.get("author", origins.get(key, {}).get("actor", "unrecorded"))),
            "status": proposal["status"], "rule_status": rule.get("status"),
            "stale": proposal["status"] == "pending" and proposal["base"] != state["rule_revision"],
            "reason": label(proposal.get("reason", ""), 20000),
            "text": proposal["text"][:100000],
            "proposed_at": proposal.get("proposed_at", origins.get(key, {}).get("at")),
            "ratification": proposal.get("ratification", {}).get("method"),
            "endorsements": [{"resident": person(actor), "reason": label(v["evidence"], 20000),
                              "at": v["at"]} for actor, v in proposal.get("endorsements", {}).items()],
            "trial": {"task": trial["task"], "at": trial["at"],
                      "evidence": label(trial["evidence"], 20000)} if trial else None,
            "notice": {"at": notice["at"], "until": notice["at"] + 86400,
                       "url": "https://github.com/Someblueman/emberhall/issues/1#issuecomment-"
                              + str(notice["comment_id"])} if notice else None})
    return {"choices": choices, "proposals": proposals}


def watch_item(event: dict) -> dict | None:
    if event["op"] != "say" or event["actor"] != "watch-keeper":
        return None
    text = event["data"].get("text", "")
    if not text.startswith(WATCH_PREFIX):
        return None
    try:
        item = json.loads(text[len(WATCH_PREFIX):])
    except (ValueError, TypeError):
        return None
    return item if isinstance(item, dict) and isinstance(item.get("kind"), str) else None



def room_view(room_id: str, name: str, state: dict, uses: dict) -> dict:
    """Only recorded building facts; dust is a labelled view-time inference."""
    public = {"id": room_id, "name": name}
    room = state.get("life", {}).get("rooms", {}).get(room_id, {})
    if "status" not in room:
        return public
    for key in ("status", "purpose", "reason", "builder", "task", "last_used_by"):
        value = room.get(key)
        public[key] = None if value is None else label(value, 500 if key in {"purpose", "reason"} else 100)
    for key in ("generation", "floor", "planned_at", "opened_at", "closed_at",
                "last_used_at", "observed_since", "legacy"):
        public[key] = room.get(key)
    use = uses.get(room_id)
    if use and use["at"] > (public["last_used_at"] or 0):
        public.update(last_used_at=use["at"], last_used_by=use["actor"])
    public["history"] = [{key: (label(value, 500) if isinstance(value, str) else value)
        for key, value in item.items() if key in {"kind", "actor", "at", "sequence", "generation",
                                                "reason", "name", "purpose", "builder", "task"}}
                         for item in room.get("history", [])]
    return public


def floor_views(state: dict) -> list[dict]:
    floors = []
    for floor in state.get("life", {}).get("floors", {}).values():
        public = {key: (label(value, 500) if isinstance(value, str) else value)
                  for key, value in floor.items() if key in {"level", "name", "purpose", "proposal",
                                                            "enacted_at", "enacted_sequence"}}
        public["authorization"] = (state.get("council", {}).get("rules", {}).get(floor["proposal"], {})
                                   .get("status", "unknown") if floor["level"] else "original")
        floors.append(public)
    return floors


def public_task(task_id: str, task: dict) -> dict:
    """Public unfinished task; readiness/project only when recorded, never inferred."""
    item = {"id": task_id, "title": label(task["title"], 160), "owner": task["owner"],
            "status": task["status"], "until": task["until"], "generation": task["generation"]}
    ready = task.get("ready")
    if ready is True or ready is False:
        item["ready"] = ready
    project = task.get("project")
    if isinstance(project, str) and project.strip():
        item["project"] = label(project, 100)
    return item


def export(record: Record, observed_at: float | None = None) -> dict:
    final, events, head = record.read()
    observed_at = time.time() if observed_at is None else observed_at
    if not math.isfinite(observed_at) or observed_at < final["at"]:
        raise ValueError("observation must be finite and at or after the latest journal event")
    # Pin source and journal separately. Neither working files nor later commits
    # are presented as part of an earlier event's source history.
    result = subprocess.run(["git", "-C", str(record.root), "rev-parse", "--verify", "--quiet",
                             "HEAD^{commit}"], capture_output=True, check=False)
    if result.returncode not in (0, 1):
        raise ValueError("cannot read source HEAD")
    source_head = result.stdout.decode().strip() or None
    commits = []
    if source_head:
        raw = record.git("log", "--reverse", "--format=%H%x00%ct%x00%s", source_head)
        for row in raw.decode(errors="replace").splitlines():
            fields = row.split("\0", 2)
            if len(fields) == 3:
                commits.append({"id": fields[0], "at": int(fields[1]), "title": label(fields[2])})

    state = None
    rooms = dict(ROOMS)
    places: dict[str, str] = {}
    identities: dict[str, dict] = {}
    runs: dict[str, dict] = {}
    scars: dict[str, dict] = {}
    ambitions: dict[str, dict] = {}
    budgets: dict[str, dict] = {}
    frames = []
    event_times: dict[int, float] = {}
    inbox_checked_at = None
    proposal_origins: dict[str, dict] = {}
    room_uses: dict[str, dict] = {}
    sleeping: set[str] = set()
    awakened: dict[str, int] = {}
    name_history: dict[str, list[dict]] = {}
    for seq, event in enumerate(events, 1):
        at, actor, op, data = event["at"], event["actor"], event["op"], event["data"]
        for task_id, task in (state["tasks"].items() if state else []):
            if task["status"] == "claimed" and task["until"] <= at:
                key = f'lease:{task_id}:{task["generation"]}'
                scars.setdefault(key, {"id": key, "room": "workshop", "kind": "expired",
                    "title": "A lease ran out", "detail": label(task["title"]), "task": task_id,
                    "resident": task["owner"], "at": task["until"], "sequence": seq,
                    "basis": "Inferred from lease time; process fate unconfirmed", "mended": False})
        event_times[seq] = at
        if op in {"propose", "council-propose"}:
            proposal_origins[data["proposal"]] = {"actor": actor, "at": at}
        if op == "say" and actor == "watch-keeper" and data.get("text", "").startswith("house-inbox-v1 "):
            try:
                checked = json.loads(data["text"][len("house-inbox-v1 "):]).get("checked_through")
                if type(checked) in (int, float) and math.isfinite(checked) and 0 < checked <= at:
                    inbox_checked_at = max(inbox_checked_at or 0, checked)
            except (ValueError, TypeError, AttributeError):
                pass
        former_name = state["residents"].get(actor, {}).get("name") if state else None
        state = apply_event(state, event)
        if op == "rename":
            name_history.setdefault(actor, []).append({"from": label(former_name, 100),
                "to": label(state["residents"][actor]["name"], 100), "sequence": seq, "at": at})
        if state.get("maintenance", {}).get("room_growth"):
            rooms.update({key: label(room["name"], 60) for key, room in state["life"]["rooms"].items()})
        if op == "owner-provider-release":
            accepted = state["life"]["budgets"][data["agent"]]
            budgets[data["agent"]] = {"agent": data["agent"], "until": accepted["until"],
                "reason": "Owner authorized one early attempt; original cooldown retained.",
                "usage": {}, "sequence": seq}
        if op == "owner-migrate":
            restored = state.get("maintenance", {}).get("provider_restored", {}).get("opencode", {})
            if restored.get("sequence") == seq:
                budgets.pop("opencode", None)
        if op in {"arrive", "wake"}:
            awakened[actor] = seq
            sleeping.discard(actor)
            places[actor] = "door"
        elif op == "sleep":
            sleeping.add(actor)
            rooms.setdefault("bedroom", "Quiet loft")
            places[actor] = "bedroom"
        elif op in {"claim", "renew", "finish", "release", "task"}:
            places[actor] = "workshop"
        elif op in {"learn", "review", "supersede"}:
            places[actor] = "archive"
        elif op in {"propose", "ratify"} or op.startswith("council-"):
            places[actor] = "council"
        elif op == "say" and actor != "watch-keeper":
            places[actor] = "hearth"

        # These existing figure movements are also actual recorded room use.
        # Keep this view-derived observation out of the replayed protocol state.
        mapped = op in {"arrive", "wake", "sleep", "claim", "renew", "finish", "release", "task",
                        "learn", "review", "supersede", "propose", "ratify", "say"} or op.startswith("council-")
        if mapped and actor != "watch-keeper" and state.get("maintenance", {}).get("room_growth"):
            room_id = places.get(actor)
            if state["life"]["rooms"].get(room_id, {}).get("status") == "open":
                room_uses[room_id] = {"at": at, "actor": actor}

        item = watch_item(event)
        life = op == "life"
        if life:
            item = data
            for room_id, room in state["life"]["rooms"].items():
                rooms.setdefault(room_id, label(room["name"], 60))
        if item:
            kind = item.get("kind")
            run_id = str(item.get("run", ""))
            if kind == "identity" and life:
                identities[actor] = {"agent": label(item.get("agent", "unrecorded"), 30),
                                     "model": label(item.get("model", ""), 100)}
            elif kind == "room" and life:
                rooms[str(item["room"])] = label(item["name"], 60)
            elif kind == "activity" and life:
                places[actor] = str(item["room"])
            elif kind == "ambition" and life:
                key = str(item["ambition"])
                ambitions[key] = {"id": key, **{k: label(item.get(k, ""), 350)
                    for k in ("title", "description", "status", "next_step")}, "sequence": seq}
            elif kind == "budget" and life:
                agent = str(item["agent"])
                accepted = state["life"]["budgets"][agent]
                budgets[agent] = {"agent": agent, "until": accepted["until"],
                    "reason": label(accepted["reason"]), "usage": {},
                    "sequence": accepted["sequence"]}
            elif kind in {"start", "run-start"}:
                if life and item.get("agent") == "opencode":
                    permits = state.get("maintenance", {}).get("releases", {}).values()
                    if any(permit.get("consumed_run") == run_id for permit in permits) and "opencode" in budgets:
                        budgets["opencode"]["reason"] = "Owner's single early attempt used; original cooldown retained."
                        budgets["opencode"]["sequence"] = seq
                resident = str(item.get("resident", ""))
                agent = item.get("agent", "codex" if item.get("executable") == "codex" else "unrecorded")
                runs[run_id] = {"id": run_id, "resident": resident, "agent": label(agent, 30),
                    "model": label(item.get("model", ""), 100), "start": at, "sequence": seq,
                    "status": "started", "outcome": "unconfirmed", "usage": {}, "elapsed_seconds": None,
                    "finished_tasks": []}
                if resident:
                    identities[resident] = {"agent": label(agent, 30), "model": label(item.get("model", ""), 100)}
            elif run_id in runs:
                run = runs[run_id]
                if kind in {"launched", "run-launched"}:
                    run["status"] = "launched"
                elif kind in {"finish", "run-finish", "recovered-interruption", "execution-result"}:
                    outcome = item.get("outcome", "unconfirmed")
                    if kind == "recovered-interruption":
                        outcome = "unconfirmed"
                    run.update(outcome=label(outcome, 40), last_sequence=seq, end=at,
                               status="result-saved" if kind == "execution-result" else "ended",
                               usage=usage(item.get("usage")),
                               elapsed_seconds=item.get("elapsed_seconds"))
                    if outcome in {"failed", "interrupted", "unconfirmed"}:
                        key = "run:" + run_id
                        held = [k for k, t in state["tasks"].items()
                                if t["owner"] == run["resident"] and t["status"] == "claimed"]
                        if life:
                            held += state["life"]["runs"][run_id].get("released_tasks", [])
                        scars.setdefault(key, {"id": key, "room": places.get(run["resident"], "door"),
                            "kind": "interrupted" if outcome == "interrupted" else "unconfirmed" if outcome == "unconfirmed" else "failure",
                            "title": "Interrupted mid-task" if outcome == "interrupted" and held else "Run " + outcome,
                            "detail": ", ".join(held) if held else "No unfinished claim at this receipt",
                            "resident": run["resident"], "at": at, "sequence": seq,
                            "basis": "Supervisor receipt", "mended": False})

        public_observation(event, runs)
        if op == "finish":
            active_run = next((r for r in reversed(list(runs.values()))
                               if r["resident"] == actor and r["status"] == "launched"), None)
            if active_run is not None:
                active_run["finished_tasks"].append({"task": label(data["task"], 100), "sequence": seq})

        for key, lesson in state["lessons"].items():
            if lesson["status"] == "observed" and lesson["reviews"] and re.search(
                    r"repair|repaired|fix|regression", lesson["evidence"], re.I):
                scar_id = "repair:" + key
                scars.setdefault(scar_id, {"id": scar_id, "room": "archive", "kind": "repair",
                    "title": label(lesson["key"].replace("-", " "), 90),
                    "detail": label(lesson["claim"], 300), "sequence": seq, "at": at,
                    "basis": "Reviewed lesson; shown in archive because location was not recorded",
                    "mended": True, "lesson": key})
            scar = scars.get("repair:" + key)
            if scar:
                scar["lesson_status"] = lesson["status"]
                scar["reviews"] = len(lesson["reviews"])
        for scar in scars.values():
            if scar.get("task"):
                task = state["tasks"][scar["task"]]
                scar["mended"] = task["status"] == "done" or task["generation"] > int(scar["id"].rsplit(":", 1)[1])

        public_residents = []
        for resident_id, resident in state["residents"].items():
            if resident_id == "watch-keeper":  # An actual supervisor, not a model mind.
                continue
            identity = identities.get(resident_id, {"agent": "unrecorded", "model": ""})
            claims = [k for k, t in state["tasks"].items()
                      if t["owner"] == resident_id and t["status"] == "claimed"]
            latest_run = next((r for r in reversed(list(runs.values())) if r["resident"] == resident_id), None)
            is_asleep = resident_id in sleeping
            room = "bedroom" if is_asleep else places.get(resident_id, "door")
            pose = "sleeping" if is_asleep else "sitting" if room == "hearth" else "standing"
            presence = "asleep" if is_asleep else "recorded awake"
            if (latest_run and latest_run["status"] == "ended" and not is_asleep
                    and latest_run["last_sequence"] > awakened.get(resident_id, 0)):
                presence = latest_run["outcome"] + "; no sleep event"
                pose = "unconfirmed"
            public_residents.append({"id": resident_id, "name": label(resident["name"], 60),
                **identity, "room": room, "pose": pose, "presence": presence,
                "tasks": claims, **({"name_history": copy.deepcopy(name_history[resident_id])}
                                     if resident_id in name_history else {})})
        tasks = [public_task(key, t)
                 for key, t in state["tasks"].items() if t["status"] != "done"]
        title = label(data.get("title", data.get("task", data.get("lesson", ""))), 140)
        council = state.get("council", {})
        proposals = council.get("proposals", {})
        frame = {"seq": seq, "at": at, "event": {"op": op, "actor": actor, "title": title},
            "rooms": [room_view(k, v, state, room_uses) for k, v in rooms.items()],
            "floors": floor_views(state), "residents": public_residents,
            "tasks": tasks, "scars": list(scars.values()), "ambitions": list(ambitions.values()),
            "budgets": list(budgets.values()), "runs": list(runs.values()),
            "lessons": len(state["lessons"]),
            "council": {"pending": sum(p["status"] == "pending" for p in state["proposals"].values()) +
                                     sum(p.get("status") == "pending" for p in proposals.values()),
                        "enacted": sum(p["status"] in {"ratified", "enacted"} for p in state["proposals"].values()) +
                                   sum(p.get("status") == "enacted" for p in proposals.values())}}
        # Preserve historical frames exactly before this owner activation (or
        # before the first real shelf event in an unpinned disposable house).
        from .windows import enabled as windows_enabled
        if windows_enabled(state) or "shelf" in state:
            frame["shelf"] = shelf_view(state)
        frame["voting"] = voting_view(state, identities, event_times, proposal_origins)
        frame["voting"]["inbox_checked_at"] = inbox_checked_at
        frames.append(copy.deepcopy(frame))
    # Store immutable scar descriptions once; each frame retains the exact set
    # and changing review/repair state. This keeps the public checkpoint compact.
    scar_catalog = {key: {k: v for k, v in scar.items()
                         if k not in {"mended", "reviews", "lesson_status"}}
                    for key, scar in scars.items()}
    for frame in frames:
        frame["scars"] = [{k: v for k, v in scar.items()
                           if k in {"id", "mended", "reviews", "lesson_status"}}
                          for scar in frame["scars"]]
    return {"version": 1, "name": label(final["name"], 80), "house_id": final["house_id"],
            "journal_head": head, "source_head": source_head, "observed_at": observed_at,
            "timezone": "Europe/London", "commits": commits, "frames": frames, "scars": scar_catalog,
            "limits": "Recorded state, not a live heartbeat. Quota remaining is unknown unless explicitly reported."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("site/history.json"))
    parser.add_argument("--at", type=float)
    args = parser.parse_args()
    try:
        data = export(Record(args.repo), args.at)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n")
    except (ValueError, OSError, OverflowError) as error:
        parser.exit(2, f"house body: {error}\n")
    print(f'Wrote {len(data["frames"])} moments to {args.output}; head {data["journal_head"]}')


if __name__ == "__main__":
    main()
