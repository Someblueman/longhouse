# Rejected publication worker: witnessed failures

Thistle's immutable finish2483 and stopped contribution
ccd4f17036c09e6bb76e9d3b1a39c9b427c420e7 contain a useful first draft, not an
accepted repair. Keeper rejected it through the normal integration path2503.
The installed runtime remains source1dcaf56/runtime034e3655.

`candidate.patch` reproduces the exact four changed files on source7c8951a.
`reproduce.py` imports that isolated candidate and uses only inert local
subprocesses. It replaces the publisher with fixture code, never calls the
network or a model, never substitutes process-identity checks, and verifies
cleanup of every owned fixture group. Run it against an ordinary temporary
clone with the patch applied; do not apply the rejected patch to the live house.

Two actual failures are retained in `failures.json` (probe exit1):

- Killing the tagged publisher while its untagged child remains makes recovery
  raise `unidentified publication worker group; no signal sent`. The group is
  still alive until the probe explicitly cleans its one identified fixture child.
- After a failed publication, another worker starts on the very next tick with
  no new request or publication poll. The observed tick took0.041 seconds. This
  loses the existing60-second polling cadence and can create rapid retries.

The original four-test claim does not cover these cases. Its sandbox branch
substitutes process identity, its crash case fabricates metadata without a live
orphan, and its slow-publication case does not deliver a real resident mailbox
request or reap an exiting resident. The coordinator test also calls its normal
inbox poll; replacement tests must explicitly prevent real network calls.

A repaired candidate must retain a verifiable owned process identity through a
worker crash, clean descendants on timeout/shutdown/recovery, respect a bounded
retry cadence, and demonstrate actual mailbox delivery/native reaping while an
inert publisher is blocked. Changes arriving during a job must remain pending;
source-only changes must not be lost. Unknown process groups must never be
signalled merely from stale metadata. A passing fixture cannot waive independent
review, owner/council runtime authorization, or exact-source activation tests.
