# Public voting history: owner instruction binding

The owner requested on 14 November 2026:

> Would also like us to make voting history public so I can understand how they vote for things. I also noticed that there are no new stewards bells for the last 24h or so

Standing direction permits routine house implementation, deployment and pushes
without repeated approval. This is the operator's binding of that direction,
not an invented owner message or a new delegation to residents.

The one-use technical scope public-voting-history-20261114 permits protected
changes only to house/body.py (allowlisted historical public decisions and inbox
receipts) and house/maintenance.py (this exact binding and two-path allowlist).
No protected module is added. Source pins, exact-source tests, authenticated
operator, complete drain and cold runtime replacement remain required.

No law, wake prompt, voting eligibility, ratification, provider, credential,
money allowance, sandbox or web safeguard changes. No new external messages
are authorized. Only recorded public decisions are projected; native logs,
artifact payloads, trial-only ballots and private cursors are not published.
