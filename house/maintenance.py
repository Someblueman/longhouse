"""Explicit owner maintenance, outside the resident council and mailbox.

These receipts are cooperative operator attribution, not cryptographic identity.
The operator authenticates GitHub before appending; resident tools expose neither
operation. Initial authorization and all council state remain untouched.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType

from . import council
from .governance import canonical, digest
from .model import require

OPENCODE_APPROVAL = (
    "Owner report, 13 November 2026: opencode should work now as well\n"
    "Owner direction after the existing one-day cooldown was explained: you can override it\n"
    "Scope: one early OpenCode retry for budget event300, not a success claim, "
    "new credential, provider change, council change or recurring bypass.\n"
)
OPENCODE_SHA256 = hashlib.sha256(OPENCODE_APPROVAL.encode()).hexdigest()
GROWTH_SHA256 = "b75e6dad4f16a7e23b3b9b808b5d9465b9c17160408a2b316cf312f32132ba9b"
RETRY_SCOPE = "opencode-retry-20261113"
GROWTH_SCOPE = "room-growth-20261113"
REPAIR_SCOPE = "opencode-cli-repair-20261113"
LAUNCHER_SCOPE = "opencode-launcher-20261113"
CONTINUITY_SCOPE = "resident-continuity-20261113"
NAMING_SCOPE = "resident-names-20261113"
INTEGRATION_SCOPE = "integration-acceptance-20261113"
REPORT_SCOPE = "report-retention-20261113"
CHECKPOINT_SCOPE = "resident-checkpoints-20261113"
BACKLOG_SCOPE = "ready-backlog-20261113"
BACKLOG_SHA256 = "df1df5907e1f8e2999eebdf374b162fb1db59413ae716db7d978298d45dff2d3"
RESTORED_SCOPE = "opencode-restored-20261113"
KEEP_MOVING_SCOPE = "keep-moving-20261114"
KEEP_MOVING_SHA256 = "ecc055f87751fe3dbab42c5b143736de025c57b88e9b741d94b18146fbef5eb8"
WEB_REPAIR_SCOPE = "native-web-repair-20261114"
MUSE_TRUST_SCOPE = "muse-workspace-trust-20261114"
WORKSPACE_SCOPE = "resident-workspaces-20261114"
SELECTION_SCOPE = "work-selection-repair-20261114"
EXPLORER_SCOPE = "explorer-dispatch-20261114"
DELIVERY_SCOPE = "source-delivery-20261114"
REVIEW_TOOLS_SCOPE = "source-review-tools-20261114"
PROJECT_CHECKS_SCOPE = "project-checks-20261114"
DIGEST_SCOPE = "wake-digest-command-20261114"
WORK_ACCOUNTING_SCOPE = "work-accounting-refresh-20261114"
PUBLICATION_SCOPE = "publication-worker-refresh-20261114"
VOTING_SCOPE = "public-voting-history-20261114"
DIAGNOSTICS_SCOPE = "integration-diagnostics-20261114"
SELECTION_SHA256 = "e01580a8a78bbbb5b9286635b85df68bd43b8f8a4785cf9df477765767ba1df8"
RESTORED_SHA256 = "4fa255013b0b0bb0021b5461e6cb25f084de67bb55557cff7c773f137d233fde"
VERIFIED_KEY_RUN = "fc2795f6b6824fc3ae4b9229e8667b61"
KEY_BUDGET_SEQUENCE = 594
KEY_BUDGET_UNTIL = 1794689129.189377
FAILED_CLI_RUN = "6eec53281c2641f28677a9a7bcc41e8d"
FAILED_CLI_SHA256 = "cb62a75b5184f48c6050e1be789a1786c1a64087fc99f11213c4d140dc661dab"
FAILED_CLI_OBSERVATION = 465
FAILED_BOOTSTRAP_RUN = "2c9fc6bd10574c84bf0e45aba78a054c"
FAILED_BOOTSTRAP_SHA256 = "034347cdaac227cd535f60f5d01d91fa83a90b458245e4aaa0ea61da787a7406"
FAILED_BOOTSTRAP_OBSERVATION = 530
SOURCES = {VOTING_SCOPE: "27fa743f14d4e09df5345df54e8dc4c743c77fed90fe327d8497e9c1ab45d999",
           RETRY_SCOPE: OPENCODE_SHA256, GROWTH_SCOPE: GROWTH_SHA256,
           REPAIR_SCOPE: GROWTH_SHA256, LAUNCHER_SCOPE: GROWTH_SHA256,
           CONTINUITY_SCOPE: GROWTH_SHA256, NAMING_SCOPE: GROWTH_SHA256,
           INTEGRATION_SCOPE: GROWTH_SHA256, REPORT_SCOPE: GROWTH_SHA256,
           CHECKPOINT_SCOPE: GROWTH_SHA256, BACKLOG_SCOPE: BACKLOG_SHA256,
           RESTORED_SCOPE: RESTORED_SHA256, KEEP_MOVING_SCOPE: KEEP_MOVING_SHA256,
           WEB_REPAIR_SCOPE: KEEP_MOVING_SHA256, MUSE_TRUST_SCOPE: KEEP_MOVING_SHA256,
           WORKSPACE_SCOPE: KEEP_MOVING_SHA256, SELECTION_SCOPE: SELECTION_SHA256,
           EXPLORER_SCOPE: KEEP_MOVING_SHA256, DELIVERY_SCOPE: KEEP_MOVING_SHA256,
           REVIEW_TOOLS_SCOPE: KEEP_MOVING_SHA256, PROJECT_CHECKS_SCOPE: KEEP_MOVING_SHA256,
           DIGEST_SCOPE: KEEP_MOVING_SHA256,
           DIAGNOSTICS_SCOPE: "29085159f29f29bf1feebaaca9b57693b8156cfa49e8d7cd5e32f50a03be6ded",
           PUBLICATION_SCOPE: "ccb2cb1cfc0432417e2cde28ea424e59708f633ddf83b0b99bc30721285f5c08",
           WORK_ACCOUNTING_SCOPE: "5ad50252f356345a1ccf7f3bdc7d909446cd801f8a3bc45347506561c2198dce"}
RETRY_BUDGET_SEQUENCE = 300
RETRY_BUDGET_UNTIL = 1794676437.592195
OWNER_MODULES = {"house/maintenance.py", "house/owner_upgrade.py"}
ALLOWED_CHANGES = {
    VOTING_SCOPE: {"house/maintenance.py", "house/body.py"},
    DIAGNOSTICS_SCOPE: {"house/maintenance.py", "house/integrate.py"},
    PUBLICATION_SCOPE: OWNER_MODULES | {"house/home.py", "house/publication_worker.py"},
    WORK_ACCOUNTING_SCOPE: OWNER_MODULES | {"house/home.py", "house/mailbox.py",
        "house/body.py", "house/work_metrics.py", "house/publish.py",
        "house/public_history.py", "house/test_sandbox.py"},
    DIGEST_SCOPE: OWNER_MODULES | {"house/digest.py", "house/__main__.py", "house/mailbox.py"},
    PROJECT_CHECKS_SCOPE: OWNER_MODULES | {"house/integrate.py"},
    REVIEW_TOOLS_SCOPE: OWNER_MODULES | {"house/integrate.py", "house/resident_actions.py",
        "house/source_delivery.py", "house/home.py"},
    DELIVERY_SCOPE: OWNER_MODULES | {"house/source_delivery.py", "house/home.py", "house/life.py", "house/integrate.py"},
    EXPLORER_SCOPE: {"house/maintenance.py", "house/home.py", "house/life.py"},
    SELECTION_SCOPE: OWNER_MODULES | {"house/shelf.py", "house/shelf_gate.py"},
    WORKSPACE_SCOPE: {"house/maintenance.py", "house/files.py", "house/home_work.py", "house/home.py",
        "house/mailbox.py", "house/mailbox_jobs.py", "house/resident_actions.py",
        "house/checkpoint.py", "house/integrate.py"},
    MUSE_TRUST_SCOPE: {"house/maintenance.py", "house/providers.py"},
    WEB_REPAIR_SCOPE: {"house/maintenance.py", "house/opencode_tool.py", "house/steward.py"},
    KEEP_MOVING_SCOPE: OWNER_MODULES | {"house/shelf.py", "house/shelf_gate.py", "house/model.py",
                                 "house/__main__.py", "house/mailbox.py", "house/windows.py",
                                 "house/home_control.py", "house/providers.py", "house/opencode_tool.py",
                                 "house/wake_policy.py", "house/life.py", "house/home.py", "house/body.py"},
    RESTORED_SCOPE: {"house/maintenance.py", "house/body.py"},
    BACKLOG_SCOPE: OWNER_MODULES | {"house/home.py", "house/life.py",
                    "house/model.py", "house/__main__.py", "house/mailbox.py"},
    CHECKPOINT_SCOPE: OWNER_MODULES | {"house/checkpoint.py", "house/resident_actions.py", "house/home.py"},
    REPORT_SCOPE: {"house/maintenance.py", "house/home.py", "house/home_work.py"},
    INTEGRATION_SCOPE: {"house/maintenance.py", "house/integrate.py"},
    NAMING_SCOPE: OWNER_MODULES | {"house/model.py", "house/__main__.py", "house/mailbox.py",
                                  "house/home.py", "house/body.py"},
    CONTINUITY_SCOPE: OWNER_MODULES | {"house/life.py", "house/home.py", "house/body.py"},
    LAUNCHER_SCOPE: OWNER_MODULES,
    REPAIR_SCOPE: OWNER_MODULES | {"house/providers.py", "house/opencode_tool.py", "house/opencode_auth.py", "house/home.py", "house/body.py"},
    RETRY_SCOPE: OWNER_MODULES | {"house/model.py", "house/wake_policy.py",
        "house/body.py", "house/watch_recovery.py", "house/life.py", "house/home.py"},
    GROWTH_SCOPE: OWNER_MODULES | {"house/building.py", "house/life.py", "house/council.py",
        "house/body.py", "house/resident_actions.py", "house/mailbox.py", "house/home.py",
        "house/model.py", "house/wake_policy.py", "house/watch_recovery.py"},
}


def protected_manifest(state: dict) -> dict:
    return state.get("maintenance", {}).get("protected_files",
                                            state["wake_policy"]["protected_files"])


def fingerprint(manifest: dict) -> str:
    return digest(canonical(manifest).decode())


def _owner(state: dict, event: dict) -> None:
    data = event["data"]
    require(state["house_id"] == council.APPROVED_HOUSE and
            data.get("house") == state["house_id"], "wrong maintenance house")
    require(data.get("owner_id") == council.OWNER_ID and
            event["actor"] == state["council"]["authorized_by"], "owner operator required")
    require(state["residents"][event["actor"]]["awake"], "owner operator is asleep")
    require(data.get("scope") in SOURCES and
            data.get("approval_sha256") == SOURCES[data["scope"]], "wrong owner approval")


def _sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class FailedAttempt:
    previous_scope: str
    run: str
    output_sha256: str
    observation: int
    start: int
    end: int
    exit_code: int
    output_file: str = "stderr.log"


# Fixed historical incidents, not operator-supplied exception policies.
FAILED_ATTEMPTS = MappingProxyType({
    REPAIR_SCOPE: FailedAttempt(RETRY_SCOPE, FAILED_CLI_RUN, FAILED_CLI_SHA256,
                               FAILED_CLI_OBSERVATION, 462, 466, 1),
    LAUNCHER_SCOPE: FailedAttempt(REPAIR_SCOPE, FAILED_BOOTSTRAP_RUN, FAILED_BOOTSTRAP_SHA256,
                                 FAILED_BOOTSTRAP_OBSERVATION, 527, 531, 2),
    BACKLOG_SCOPE: FailedAttempt(LAUNCHER_SCOPE, "85cecff20f114d5b805b8474e19a6120",
        "54107bb23032fd6b4795f360605c528537a554362c170b0693bcdd9e71a945cf",
        594, 592, 596, 1, "stdout.jsonl"),
})
RELEASE_SCOPES = (RETRY_SCOPE, REPAIR_SCOPE, LAUNCHER_SCOPE, BACKLOG_SCOPE)


def approved_hold(scope: str) -> tuple[int, float]:
    if scope == BACKLOG_SCOPE:
        return KEY_BUDGET_SEQUENCE, KEY_BUDGET_UNTIL
    return RETRY_BUDGET_SEQUENCE, RETRY_BUDGET_UNTIL


def failure_proven(state: dict, scope: str) -> bool:
    proof = FAILED_ATTEMPTS[scope]
    failed = state.get("life", {}).get("runs", {}).get(proof.run, {})
    return (failed.get("status") == "completed" and failed.get("outcome") == "failed" and
            failed.get("exit_code") == proof.exit_code and failed.get("usage") == {} and
            failed.get("started_sequence") == proof.start and failed.get("ended_sequence") == proof.end and
            failed.get("agent") == "opencode" and failed.get("resident") not in state["residents"])


def verified_key_resolution(state: dict, event: dict) -> dict:
    """Retire one obsolete authentication hold after its exact native repair."""
    life = state.get("life", {})
    budget = life.get("budgets", {}).get("opencode", {})
    require(budget.get("sequence") == KEY_BUDGET_SEQUENCE and
            budget.get("until") == KEY_BUDGET_UNTIL and
            life.get("budget_observations", {}).get("opencode") == KEY_BUDGET_SEQUENCE,
            "authentication hold changed; preserve newer failure")
    require(event["at"] < KEY_BUDGET_UNTIL, "authentication hold already elapsed")
    permit = state.get("maintenance", {}).get("releases", {}).get(BACKLOG_SCOPE, {})
    run = life.get("runs", {}).get(VERIFIED_KEY_RUN, {})
    require(permit.get("consumed_run") == VERIFIED_KEY_RUN and
            run.get("status") == "completed" and run.get("outcome") == "success" and
            run.get("exit_code") == 0 and run.get("started_sequence") == 929 and
            run.get("ended_sequence") == 957 and run.get("agent") == "opencode" and
            run.get("model") == "opencode-go/deepseek-v4.1-flash" and
            run.get("usage", {}).get("input_tokens", 0) > 0 and
            run.get("usage", {}).get("output_tokens", 0) > 0 and
            state["residents"].get(run.get("resident"), {}).get("agent") == "opencode",
            "exact successful native key verification required")
    return {"scope": RESTORED_SCOPE, "verified_run": VERIFIED_KEY_RUN,
            "previous": copy.deepcopy(budget), "at": event["at"],
            "sequence": state["sequence"] + 1}



def enact_selection_repair(state: dict, event: dict) -> None:
    """One exact owner correction, not a resident-accessible ratification waiver."""
    from . import shelf_gate
    data = event["data"]
    require(data["rule_base"] == state["rule_revision"], "selection repair rule base changed")
    old = state["proposals"].get("work-selection-002", {})
    require(old.get("status") == "pending" and old.get("base") == state["rule_revision"]
            and digest(old.get("text", "")) == shelf_gate.POLICY_SHA256,
            "selection repair requires exact pending predecessor")
    key = shelf_gate.REVISED_POLICY_ID
    require(key not in state["proposals"] and key not in state["council"]["rules"]
            and shelf_gate.policy(state) is None, "selection repair already has a policy")
    require(not any(c["status"] == "open" for c in state.get("shelf", {}).get("choices", {}).values()),
            "finish existing choices before selection repair")
    seq, at = state["sequence"] + 1, event["at"]
    title = "Choose worthwhile work, or reject the shortlist"
    authority = {"method": "direct-owner", "scope": SELECTION_SCOPE,
                 "approval_sha256": SELECTION_SHA256, "sequence": seq}
    state["proposals"][key] = {"mode": "rule", "author": event["actor"], "title": title,
        "text": shelf_gate.REVISED_POLICY_TEXT, "base": state["rule_revision"],
        "reason": "Owner requested correction and immediate activation without the notice delay.",
        "status": "enacted", "proposed_at": at, "trial": None, "endorsements": {},
        "notice": None, "enacted_at": at, "enacted_sequence": seq, "ratification": authority}
    state["council"]["rules"][key] = {"title": title, "text": shelf_gate.REVISED_POLICY_TEXT,
        "status": "active", "enacted_at": at, "enacted_sequence": seq, "ratification": authority}
    old.update(status="superseded", superseded_by=key)
    council.render(state, event, key)


def apply(state: dict, event: dict) -> None:
    _owner(state, event)
    data, scope = event["data"], event["data"]["scope"]
    seq = state["sequence"] + 1
    if event["op"] == "owner-migrate":
        council.fields(data, {"scope", "approval_sha256", "house", "owner_id",
            "source_head", "source_sha256", "protected_files", "previous_manifest_sha256",
            "previous_runtime_sha256", "runtime_sha256", "test_output_sha256", "test_count"}
            | ({"rule_base"} if scope == SELECTION_SCOPE else set()))
        old = protected_manifest(state)
        maintenance = state.get("maintenance", {})
        require(scope not in maintenance.get("migrations", {}), "owner migration already used")
        require(data["previous_manifest_sha256"] == fingerprint(old), "stale protected manifest")
        manifest = data["protected_files"]
        extra = OWNER_MODULES | ({"house/building.py"} if scope == GROWTH_SCOPE else set())
        if scope == REPAIR_SCOPE:
            extra.add("house/opencode_auth.py")
        if scope == PUBLICATION_SCOPE:
            extra.add("house/publication_worker.py")
        if scope == WORK_ACCOUNTING_SCOPE:
            extra.update({"house/work_metrics.py", "house/public_history.py"})
        if scope == DIGEST_SCOPE:
            extra.add("house/digest.py")
        if scope == CHECKPOINT_SCOPE:
            extra.add("house/checkpoint.py")
        if scope == DELIVERY_SCOPE:
            extra.add("house/source_delivery.py")
        if scope == KEEP_MOVING_SCOPE:
            extra.update({"house/shelf.py", "house/shelf_gate.py", "house/windows.py", "house/home_control.py"})
        require(isinstance(manifest, dict) and set(manifest) == set(old) | extra
                and all(_sha(value) for value in manifest.values()), "invalid replacement manifest")
        changes = {name for name in manifest if manifest[name] != old.get(name)}
        require(changes <= ALLOWED_CHANGES[scope], "source change outside owner maintenance scope")
        require(isinstance(data["source_head"], str) and
                re.fullmatch(r"[0-9a-f]{40}", data["source_head"]), "invalid source commit")
        require(all(_sha(data[key]) for key in ("source_sha256", "previous_runtime_sha256",
                "runtime_sha256", "test_output_sha256")), "invalid maintenance digest")
        require(type(data["test_count"]) is int and data["test_count"] > 0,
                "owner migration requires executed passing tests")
        require(not any(run["status"] == "active" for run in
                state.get("life", {}).get("runs", {}).values()), "drain native residents before migration")
        resolution = verified_key_resolution(state, event) if scope == RESTORED_SCOPE else None
        if scope == SELECTION_SCOPE:
            enact_selection_repair(state, event)
        entry = copy.deepcopy(data) | {"at": event["at"], "sequence": seq, "actor": event["actor"]}
        current = copy.deepcopy(maintenance)
        current.setdefault("migrations", {})[scope] = entry
        current.update(protected_files=dict(manifest), at=event["at"],
                       room_growth=current.get("room_growth", False) or scope == GROWTH_SCOPE)
        state["maintenance"] = current
        if scope == WORKSPACE_SCOPE:
            current["workspace_layout_sequence"] = seq
        if resolution is not None:
            current.setdefault("provider_restored", {})["opencode"] = resolution
            del state["life"]["budgets"]["opencode"]
        if scope == CONTINUITY_SCOPE:
            current["resident_returns"] = True
        if scope == NAMING_SCOPE:
            current["resident_names"] = True
        if scope == GROWTH_SCOPE:
            from .building import initialize
            initialize(state)
    elif event["op"] == "owner-provider-release":
        extra = {"expected_observation", "failed_run", "failed_output_sha256"} if scope in FAILED_ATTEMPTS else set()
        council.fields(data, {"scope", "approval_sha256", "house", "owner_id",
                              "agent", "expected_sequence", "expected_until"} | extra)
        require(scope in RELEASE_SCOPES and data["agent"] == "opencode", "only approved OpenCode hold may release")
        current = state.get("maintenance", {})
        require(scope in current.get("migrations", {}), "owner retry runtime is not authorized")
        require(scope not in current.get("releases", {}), "owner release already used")
        sequence, until = approved_hold(scope)
        require(type(data["expected_sequence"]) is int and data["expected_sequence"] == sequence and
                type(data["expected_until"]) in (int, float) and
                data["expected_until"] == until, "wrong approved hold")
        observation = sequence
        if scope in FAILED_ATTEMPTS:
            proof = FAILED_ATTEMPTS[scope]
            original = current.get("releases", {}).get(proof.previous_scope, {})
            require(original.get("consumed_run") == proof.run and
                    data["failed_run"] == proof.run and data["failed_output_sha256"] == proof.output_sha256 and
                    type(data["expected_observation"]) is int and data["expected_observation"] == proof.observation,
                    "repair credit requires the exact spent pre-provider attempt")
            require(failure_proven(state, scope),
                    "repair credit does not cover a model attempt or an uncertain failure")
            observation = proof.observation
        budget = state["life"]["budgets"].get("opencode", {})
        require(budget.get("sequence") == data["expected_sequence"] and
                budget.get("until") == data["expected_until"] and
                state["life"].get("budget_observations", {}).get("opencode") == observation,
                "provider hold changed; do not erase new failure")
        require(event["at"] < budget["until"], "provider hold already elapsed")
        current.setdefault("releases", {})[scope] = copy.deepcopy(data) | {
            "at": event["at"], "sequence": seq, "previous": copy.deepcopy(budget)}
    else:
        raise ValueError("unknown owner maintenance operation")


def retry_permit(state: dict, agent: str, at: float) -> dict | None:
    """Return the still-valid one-use credit, without shortening any cooldown."""
    if agent != "opencode":
        return None
    life = state.get("life", {})
    budget = life.get("budgets", {}).get(agent, {})
    for scope in reversed(RELEASE_SCOPES):
        release = state.get("maintenance", {}).get("releases", {}).get(scope)
        if not release or "consumed_run" in release or at >= release["expected_until"]:
            continue
        if scope in FAILED_ATTEMPTS and not failure_proven(state, scope):
            continue
        observation = release.get("expected_observation", release["expected_sequence"])
        if (life.get("budget_observations", {}).get(agent) == observation and
                budget.get("sequence") == release["expected_sequence"] and
                budget.get("until") == release["expected_until"]):
            return release
    return None
