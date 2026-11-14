# Proposed nonblocking Pages runtime activation

Status: **owner authorized on 14 November; preparation/installation in progress.**
See [the actual authorization](owner-authorization.md). The earlier proposal is
preserved as the requested scope; it no longer requires a user decision.
Candidate `42e5e07` was independently accepted by Sable at journal2637 as
`c254f795ba477f54bf9ffc150413085c18b48d85`; coordinator delivery2649 verified
remote equality. The exact integration suite collected481 checks:378 executed
and passed,103 skipped. The separate exact-byte host witness executed48 with
zero skips. [Integration evidence](integration-validation.json) retains failures
and the [full gate log](integration-tests.txt). The [proposed authorization](owner-authorization-proposal.md)
was approved by the owner. It is limited to the four paths below and changes no law.

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
consumed; it is not reused for this new helper. The actual owner decision now authorizes its exact technical scope. A source commit is not installation.
