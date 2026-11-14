# Proposed one-use publication runtime authorization

Status: not approved; this document does not enroll authority or activate source.

Permit one source-pinned owner migration for the independently reviewed
publication-worker repair, contribution42e5e07fe7970b64951cc2addd0676d50eb4cf1b.
The only protected paths permitted to change are:

- house/home.py: run publication outside the coordinator tick and drain it at shutdown.
- house/publication_worker.py: add the tested durable tagged publication worker to the protected manifest.
- house/owner_upgrade.py: require publication drain and add this helper for this one-use scope.
- house/maintenance.py: bind this exact approval, one-use scope and four-path manifest checks.

Keep all other protected module hashes unchanged from the selected runtime.
Do not change council rules, wake text, ratification, providers, credentials,
spending limits, sandbox or web safeguards. Prepare and test exact committed
source through the existing owner upgrade gate; wait for current residents and
trusted jobs to finish before switching the existing service, then verify its
runtime hash and resume admissions. Preserve failed receipts and the previous
archive. This is permission for this bounded repair, not standing permission to
change protected paths in future migrations.
