# Publication repair: independent host witness

Hawthorn's stopped contribution `42e5e07fe7970b64951cc2addd0676d50eb4cf1b`
contains exactly the four files in `host-validation.json`. Keeper independently
matched those committed bytes to immutable finish2573 and the isolated source
used for the final host run2572. **All48 tests executed and passed, zero skipped,
102.449 seconds.** The raw output is retained unchanged in `host-tests.txt`.

The actual inert subprocess cases exercise blocked publication while a real
resident mailbox reply is delivered and its native fixture is reaped; either
single tagged guardian/executor crash with an untagged descendant; failed-publish
retry cadence; source/journal changes during a job and source-only changes after
success; timeout, restart and shutdown cleanup; and refusal to kill an unknown
group. Existing coordinator and owner-upgrade checks also executed. No process
identity was mocked and no real provider or network operation was used.

Earlier host2560 passed9 tests against older home/worker bytes. It is preserved
in the journal but does not certify the final guards. Hawthorn explicitly caught
that distinction at2564; this final witness binds the corrected bytes. Its native
sandbox's six process skips remain honest skips, not substituted successes.

The process lesson2574 was independently reviewed2583 and preserves its limit:
simultaneous loss of all tagged ownership witnesses is not proven recoverable.
The source was independently accepted2637 and delivered2649 as `c254f795`;
[integration-validation.json](integration-validation.json) binds its passing full gate
and preserves prior timeouts/source races. The trusted runtime migration still
requires the proposed owner authorization. This evidence does not claim deployment
or a measured production speedup.
The installed archive remains034e3655/source1dcaf56 unless a later migration says
otherwise. The original rejected draft and failures remain in
`../publication-worker-review/`.
