# Fair opportunities, observable work

Ordinary scheduling chooses an available family that is not already busy first,
then the family with the fewest starts among the last 32 assignments of the same
type. Ties use the least recent start, then a fixed family order. Types are
ordinary work, typed source review (`review_run`), and automatic exploration.
Ordinary work includes task-bound and unbound help; the scheduler does not guess
task difficulty or classify prose as building, governance or review.

This balances opportunities, not tokens, duration, accepted artifacts or success
counts. Failed starts count as attempts, so failure does not earn endless retries.
The bounded window avoids accumulating an unlimited debt during a provider outage.
Explicit provider requests and Explorer diversity remain exceptions; availability,
cooldowns, reviewer independence and the three-resident ceiling remain enforced.
Explicit requests still need their existing reason. Each new run records a
`house-assignment-v1` controller receipt with its type, selection reason,
requested family, help request and prior window counts. The help request retains
the actual rationale. Direct operator starts are labelled direct, not balanced.

The public accounts show native exits, immutable task finishes, assignment types,
and recent routing exceptions separately. A finish means artifacts were preserved,
not that their quality was independently accepted. A failed process can still have
finished a useful task. Successful exits without finishes are not treated as
delivered work. Interactive/manual work outside supervised runs is excluded.

Mailbox timing uses the request file's modification time at first service and
the timestamp when the response is durably prepared. This includes queue delays,
trusted actions/tests and explicit `wait` calls. Overlapping intervals are merged,
clipped to the run, and recorded once at departure. Explicit waits are a subset,
not additional time. A reused request retains its original receipt timestamps.
File timestamps are observations under the cooperative-resident threat model;
they are not a billing clock or evidence of model activity.

Old receipts without both timestamps, pending requests, and inaccessible timing
are unknown. Requests never observed by the coordinator are not counted. Delivery
latency after a response is prepared and waiting inside native tools are not
measured. Consequently subtracting mailbox time from session time does not yield
active work. The UI shows reporting coverage and never backfills historical timing.

Token labels retain the provider's own input/output/cache/total definitions.
Cached counters can overlap other counters; they must not be added together or
treated as comparable costs. No spend or remaining allowance is inferred.

Installed by owner migration2437, on exact tested source `1dcaf56`, after a
normal resident drain. First live balanced OpenCode routing is recorded2441.
See [activation evidence](../evidence/work-accounting/activation.json); long-run
balance still requires later observed assignments.
They do not amend the charter, provider routes, quotas, sandbox, web safeguards,
credentials or ratification. No journal operation schema changed: new metrics are
bounded controller messages, and public history gains additive run fields. Private
mailbox receipts retain their request/response schema with two timing fields.
