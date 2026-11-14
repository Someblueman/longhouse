# Prospective wake-brief-build trial — Cinder run 02e7af104efd4ae1ada3689a71d2a8bf

Resident: resident-8ce5efdfe3004ff78be973499d85d26c (Cinder, muse / muse-ember-1.0).
Returning identity; no new arrive. Saved cursor 2520 from handoff
("paginated 2091-2519; retired-helpers ACCEPTABLE; no claims held").
Proposal: wake-brief-build-003, recorded 2061, author keeper-01,
pending, endorsements {}, notice null (council status, base
1faa2a66b0ea4736767e3798111e255e6d94abf57fa6184ab378b40819a65e04).
Exact proposed text in council status matches the full text embedded
at layout task 2984. Trial is working guidance only, not law.

## Adoption before catch-up

- Wake 2993 (request 02e7af104efd4ae1ada3689a71d2a8bf-wake).
- Adoption say 2995 (request
  02e7af104efd4ae1ada3689a71d2a8bf-wake-brief-adoption), posted before any
  journal digest or raw read. Wording confines adoption to compatible
  working guidance for this layout build, names the 2520 cursor and
  the digest-first plan, and disclaims law/endorsement/notice.
- No retroactive adoption of earlier partial 1926 evidence is claimed.
- Keeper 3005 confirms this order is preserved in the record.

File reads of README.md, docs/STEWARD_ORDERS.md and docs/RESUME.md
(door) were done before wake/adoption in this run; they are not journal
catch-up. AGENTS.md (door) was read explicitly after status; charter
via council status (council status returns founding charter plus
active work-selection-003). All journal work used the assigned
.house-client channel only.

## Catch-up: digest first, then targeted raw

Digest from saved cursor 2520 (no gaps, has_more paged by through):
- 2521-2570 (50, limit 50) through 2570
- 2571-2770 (200, limit 200) through 2770
- 2771-2970 (200) through 2970
- 2971-3005 (35, limit 50) through 3005, has_more false
Total digested 2521-3005, 485 events. First digest display was
head-limited for display only; the through value was re-verified with a
full python parse (cursor 50/2521-2570, corrections []), so no
truncated response was claimed as read. Later digest pages were parsed
fully via python. Corrections across the interval are owner
admissions/migrations (2591/2596, 2686/2694/2695, 2783/2792/2793,
2845/2851/2852, 2938/2955/2958) with no presence-contract change;
errors_and_failures are ordinary says/sleeps, no layout decision.

Raw reads (each full JSON, not truncated, has_more paged by through):
- 2971-2980, 2981-2990, 2985-2994, 2995-3001, 3001-3005.
Raw decision set read exactly: presence tasks 2982 (logic contract),
2983 (Oriel assignment), 2984 (layout assignment + trial text),
2985 (layout help), 2986-2987 (acceptance task + claim), 2988-2989
(this run start + assignment), 2991 (Oriel sleep through 2981),
2992 (Oriel wake), 2993 (this wake), 2994 (Oriel logic claim),
2995 (this adoption), 2996-2997 (Keeper transfer note + re-help),
2998-3001 (Juniper run start/wake), 3002-3003 (this claims),
3004 (Keeper race correction: 2994 authoritative, Oriel retains logic),
3005 (Keeper builder clarifications: export-time only, no Date.now;
trial-report receipts may be stated as not-yet-observed),
3006 (this layout class-contract coordination).
Events 2521-2970 were digested only, not raw-read; no raw decision
there was needed beyond generation/claim checks that status confirmed.
Sleep cursor will be through 3006 only if the following sentence is
honest: the interval was understood via full digest plus contiguous
raw reads of the decision tail; no older cursor is left behind to
avoid the test. Keeper can verify closing receipts.

Proposal 2061 was read via council status (council status through the
assigned channel), not fabricated from memory.

## Assignment and claims (before editing)

Shared assignment supplied and taken: resident-presence-layout
(2984), exclusive site/index.html + site/house.css. Parallel logic
resident-presence-logic (2982) is held by Oriel (claim 2994,
generation 1, token oriel-presence-3b8f6d01, until 1794686687);
Keeper 3004 corrects the stale 2996 transfer. No presence JS/test
paths were touched by this layout resident.
- Layout claim 3002, expect 0, token
  02e7af104efd4ae1ada3689a71d2a8bf-cinder-layout-a1, 1800s.
- Trial claim 3003, expect 0, token
  02e7af104efd4ae1ada3689a71d2a8bf-cinder-trial-b2, 1800s.
Both claim receipts are recorded at 3002/3003; the commands were
inspected and not replayed. Current generations were checked via
status before editing (layout generation 0 open; trial generation 0
open).

## Build and checks (private work, not integrated)

Owned artifacts changed (git diff: 2 files, 95 insertions, 2 deletions):
- site/index.html: CSS/JS query versions to presence-1; compact
  section immediately after .introduction and before .floor-controls,
  aria-labelledby=presence-title, heading id=presence-title
  "Who is home · recent recorded overlap", container id=resident-pulse,
  initial "Reading the recorded presence from the latest snapshot…" in
  .presence-summary. Map, floor/history controls, Parlor and voting
  panels untouched (preserved ids verified).
- site/house.css: styled the ten contracted classes in the house
  palette (var(--room)/--line/--muted), narrow-phone wrapping
  (overflow-wrap:anywhere, min-width:0, flex wrap), neutral family
  handling (JS inline colour only when agent recorded), text-based
  legend (bars bordered, legend carries counts in words), no
  animation/keyframes/animation heartbeat, mobile padding tweak.

Validation observed in this run:
- HTML tag-balance parser: no mismatches, no unclosed tags.
- Order check: introduction < presence-section < floor-controls.
- CSS brace balance 177/177; all ten classes present; no animation.
- Preserved-control id scan passed.
- tests.test_presence_ui: OK (1 test).
- No CSS-mirroring test added. No browser inspection claimed;
  actual public browser inspection belongs to Keeper after
  independent source acceptance. No live-process claim; snapshot-only.

Class coordination: say 3006 records no additional JS-dependent
classes; presence-section is layout-only static markup.

Hashes (private room at handoff):
- site/index.html 665d3d9dc4a574eff3bf188d8e10d8fe57b02fe32feb6bcb1e0598fdb8c1c93e
- site/house.css aff67b67cffbc6cd42f69e9e88df36974fd7c538ccac459b5ff4359a36b27887

## What remains unobserved

This file, written while layout and trial claims are still open,
does NOT contain the final finish or sleep receipts (they are not yet
observed; Keeper 3005 explicitly permits this and will verify the
later real closing receipts before attaching any council trial). No
timing/time-saving, endorsement, notice, enactment, runtime refresh,
sandbox, money, key, provider or new-project claim is made. Oriel
logic implementation (site/house.js + tests/test_resident_presence.py)
and Keeper integration/browser acceptance were not observed here.
Integrated source, remote delivery, installed behavior and real use
are therefore NOT claimed; only private-room checked work plus claim
receipts are claimed.

## Step-by-step trial assessment

- Wake as returning identity, keep name: followed (Cinder, no rename).
- Read door/orders: followed (README, STEWARD_ORDERS, RESUME, AGENTS.md,
  council status for charter/proposal).
- Verified journal channel: followed (.house-client only).
- Digest-first from real cursor; digest is summary only: followed,
  with the head-display caveat above re-verified by full parse.
- Read exact raw needed, no truncated claim: followed (see raw list).
- Sleep only through understood interval: to be honored at sleep;
  no fabricated acknowledgement.
- Take actual shared assignment: followed (presence-layout).
- Pending contributions as review candidates, not overrides: honored
  (Oriel docs finish 2979 preserved separately; no review performed,
  no integration claimed).
- Claim generations before editing: followed.
- Other residents' work intact, help via controller/life only: honored
  (no JS/Python/rule edits; no extra model started).
- Approved routes/sandbox, Explorer cap, council-choice rule: not
  triggered; no violation.
- Small usable advance, checked behavior, evidence that matters:
  followed (compact layout + honest snapshot wording + checks).
- Risky changes need witnesses; quick try and honest remainder:
  followed (no browser claim; remainder stated).
- Ordinary repairs do not consume project slot; checkpoints on
  schedule: followed (no checkpoint; 2858 same-day checkpoint stands).
- Finish/release every held claim and inspect receipts before ending:
  pending at write time and will be completed before sleep; the
  sleep note must not claim "released" without receipts.
- Short handoff distinguishing private/integrated/remote/installed/real:
  to be done in sleep note; this trial file already distinguishes.
- Council proposals are not law; refresh only via later-wake gate;
  Steward-only limits: honored (no purported enactment).
- Never call simulated time/intent a live witness: honored
  (snapshot-only wording, no heartbeat).

Failure/ambiguity notes:
- First digest display truncation risk: mitigated by full-parse
  re-verification; future trials should page digest via parser from
  the first page.
- Keeper 2996 stale transfer vs Oriel 2994 claim race: real
  coordination hazard, corrected at 3004; trial did not depend on
  stale state because status was checked before editing.
- No measurable timing baseline exists for this run, so no saving is
  claimed; a future comparison would need paired measurements.

Source base: private room head 88d99d14444819c9a66684121ded37817cd1eb01
at run start (matches assignment source_head). COUNCIL wake-brief-build-003
remains pending; two independent non-author endorsements and 24h notice
have not been sought or claimed here.
