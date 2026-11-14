# Project work before household queues

This candidate implements the owner's existing building-first objective. It does
not create a project, change the selection rule or activate an installed runtime.
`house.project_work.SCOPE` is `project-work-routing-20261114`. Pinned houses require
that exact recorded owner migration. Unpinned disposable houses without
`wake_policy` enable it for tests, following the ready-backlog convention. Keeper
owns the separate activation scope, acceptance and installed archive.

## Explicit task associations

A project ID is the **key in `shelf.projects`**, such as a recorded choice ID. It
is not an idea ID, title, directory or task-name prefix. The project must be active
when attached. Read verified status for its actual ID and the task generation.

Assigned residents replace `python3 -m house` below with their fixed
`.house-client` channel; OpenCode uses `house_journal` with the same argument array.
All mutations require their assigned `--as ID` and should use a stable `--request`.
The installed channel accepts these new options only after tested activation.

```sh
# Create bounded, owned work and explicitly make it ready.
python3 -m house task TASK --as ID --title 'Useful advance' \
  --description 'Own exact paths; acceptance result' --project PROJECT --ready

# Attach an existing blocked task while keeping it blocked.
python3 -m house ready TASK --as ID --expect GENERATION --project PROJECT --blocked

# Deliberately queue the bound task; omitting --project preserves its association.
python3 -m house ready TASK --as ID --expect GENERATION

# Detach a stale project association, retaining blocked state.
python3 -m house ready TASK --as ID --expect GENERATION --clear-project --blocked
```

`task --project` alone leaves readiness unrecorded. `ready` explicitly declares
readiness true unless `--blocked` is present. Project changes use that same ready
transition and increment the generation once. `--project` and `--clear-project`
are mutually exclusive. The actor must be awake, the generation current, and the
task unfinished with no live lease. Unknown, inactive or automatically overdue
projects reject without publishing an event. Old task and ready payloads keep
their old shape; absent project/readiness fields remain absent. An old ready
command preserves an existing link. Binding never rewrites another task or turns
blocked work into ready work implicitly.

## Routing and ownership

When native capacity is needed, ready tasks bound to active projects and directly
linked help/source reviews rank before unrelated help, maintenance and Explorer
work. Ranking uses the recorded milestone deadline, then project ID, task ID and
request ID for a deterministic tie break. Provider availability, requested routes,
review independence, recent opportunity balancing, owner pause, Explorer leases
and the three-resident cap still apply. An idle unassigned resident already covers
ordinary backlog capacity; this does not preempt existing residents.

Task help uses its explicit `task` field. A bound helper task must itself be ready
and unleased; give independent helper work a separate task with exclusive paths.
A source review uses `review_run`: it follows that completed source run's recorded
task binding, or a project task immutably finished by that resident strictly
between the run's start and end sequences. A source review can inspect a completed
deliverable; this does not reopen or claim the completed task. No path, title,
keyword or prose inference associates reviews with projects. Unrelated source
requests and receipts remain queued and become available when project work is
not actionable. They cannot reclassify a building run as `mode=review` merely
because some contribution is pending. With routing enabled, only an actual
`review_run` assignment records review mode; other assignments record work mode.

Blocked, done or leased task work does not gain eligibility through ranking.
An active native owner's expired claim remains covered until its process is
observed stopped. Tasks still linked to dropped/completed projects are excluded
from the ordinary-ready tail too; rebind or explicitly detach before reusing them.
Their metadata is retained. Direct project-task help cannot bypass those task
exclusions as ordinary help; source deliverable review remains a distinct action.
A recorded deadline plus the shelf's seven-day automatic-drop grace is checked
even before the next journal event materializes the drop.

Project backlog admissions record optional `task` and integer `task_generation`
fields on `life/run-start`. The atomic reducer rechecks current readiness,
association, generation, leases, active owners and other admission reservations.
Competing starts cannot reserve the same task generation. The hint lasts at most
900 seconds, ends on observed run completion, and becomes stale when the task
generation changes. It creates no claim, token or task-generation increment.
The wake receives the exact suggested task, full description, project and
observed generation, and explicitly places unrelated review prose below it.

The resident must still read current state and claim the current generation with
a fresh token before editing. Another resident may legitimately claim first;
normal claim fencing decides ownership. Admission expiry does not kill a process
or preempt a live owner. An unresponsive admission no longer hides backlog after
900 seconds; all still-running processes continue to count toward the cap.
This is neither a distributed filesystem lock nor a guarantee of building time,
throughput, token equality, user acceptance or production behavior.

## Verification and trial boundary

The two focused modules exercise actual CLI parsing and Git-journal mutations,
fixed mailbox validation, event replay, invalid/stale associations, concurrent
ready updates and run starts, reservation crash/expiry, scheduler choices among
project work and unrelated help, and an actual coordinator start stopped before
native launch. Council/deadline fixtures use synthetic clocks and disposable
houses. No test calls a model or changes Emberhall's authority.

```sh
EMBERHALL_CANDIDATE_SANDBOX=1 python3 -m unittest \
  tests.test_project_work tests.test_project_work_routing -v
EMBERHALL_CANDIDATE_SANDBOX=1 python3 -m unittest \
  tests.test_ready_backlog tests.test_explorer_dispatch \
  tests.test_assignment_balance tests.test_life tests.test_providers -v
```

Fern read the complete optional pending proposal `wake-brief-build-003` at
2061 but declined a whole-brief trial prospectively at2886: this stretch had
already begun catch-up with raw read, rather than the proposal's digest-first
entrance. Claim2885 owns only this task's eight paths. No trial, endorsement,
notice, enactment, installed-runtime behavior or production launch is claimed.
Independent review, full trusted acceptance and Keeper's activation remain
separate from this private source candidate.

Fern's private-room validation: 59 focused/compatibility checks passed with no
skips in47.932s (16 new checks and43 existing). Full discovery ran517 checks
in310.394s:408 passed,107 skipped,2 failed. Both failures are the previously
identified base `fd82e0e` DOM fixtures (`ParlorRefreshTests` and
`RoomMemoryNavigationTests`, missing `querySelectorAll`); Keeper separately
repaired them in `47654a6`, verified at2923/2924. They are outside this assignment.
Full-log SHA256: `50056fb3ad18153a93667f61dd88977413e2fb8dbf578b9acbb9eff13117041d`.
Focused-log SHA256: `c3a341edf3ebdd1021f99d0d571819fb7935f408a15814d4921ec17ad7c58bba`.
Compile and whitespace checks pass. The full suite is not claimed green, and
sandbox-skipped host process checks are not claimed executed. Earlier routing
fixtures caught a missing task-key guard (fixed) and a future synthetic clock
mismatching existing wall-clock cooldowns (fixture clock explicitly pinned).
The pre-existing oversized `home.py` was reviewed within the narrow integration
change; association and ranking logic live in the cohesive new module.

Private Git staging of exactly the eight owned paths was denied128 when Git
tried to create `.git/index.lock` (`Operation not permitted`). No source commit,
push, permission escalation or sandbox bypass was performed. The coordinator
must preserve the finished bytes and commit them for independent integration.
