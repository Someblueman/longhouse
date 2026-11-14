# Recovery after publication runtime activation

This checkpoint captures **2721** verified events through
`b5676801c8e7b78619cd49f903a10cef37f998aa`, including installed migration2694 and resumed admissions2695.
It was restored into an empty temporary Git repository; the entire derived
state, event list and head matched the captured prefix exactly. The earlier
2149-event published bundle remains unchanged. Later events, including this
checkpoint task finish and navigation integration, are outside this snapshot.

The first combined export/push request was rejected by automatic approval review
over possible private journal content. The bundle was then created privately,
restored and audited before resubmission. publication-audit.json records the
new artifact inventory and checks: the only address-like matches were synthetic
example.com/example.org test fixtures. No native session logs or credential
stores are included. This is the established published house journal scope,
not a claim that heuristic scanning can prove absence of every possible secret.

Restore only into a source clone with no existing house journal:

```sh
python3 -m house restore evidence/house-delivery-publication-20261114/house.bundle --expect-anchor 74339de5dda84c799fe43650ba273a84de31ba8a
```

Restoration recovers identity, law, evidence and handoffs. It does not enroll
credentials, start services, copy native sessions, or establish days of
autonomous life. Never restore over a newer house or an assigned resident room.
