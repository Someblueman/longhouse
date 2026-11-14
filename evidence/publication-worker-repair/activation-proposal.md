# Proposed nonblocking Pages runtime activation

Status: **proposal only; no new scope or authority has been recorded.**
Candidate `42e5e07` has48 independently executed host checks; the ordinary
independent integration gate remains pending. Update this proposal with its
accepted source commit and full gate result before requesting the final decision.

The proposed owner-authorized change is limited to four protected paths:

- `house/home.py`: dispatch/reap one durable publication worker while continuing
  resident mailbox service; request both journal and source changes.
- `house/publication_worker.py`: newly pinned worker with tagged ownership,
  crash/timeout/shutdown cleanup, coalescing and bounded retries.
- `house/owner_upgrade.py`: require publisher drain before migration and include
  the new helper in this scope's protected manifest.
- `house/maintenance.py`: add only the exact one-use scope, approval digest,
  permitted paths and manifest validation for this repair.

No council rule, wake text, provider, credential, sandbox, web safeguard, spending
limit or ratification process changes. No active resident should be interrupted:
prepare the exact source through the trusted owner gate, pause new admissions,
wait for legitimate sleep/exit and all trusted jobs, replace the existing service's
runtime arguments, then resume. Verify installed hashes and actual publication.
Existing approval2437 covered a different exact nine-path scope and is already
consumed; it is not reused for this new helper. Authority metadata stays unchanged
until the required owner decision is recorded. A source commit is not installation.
