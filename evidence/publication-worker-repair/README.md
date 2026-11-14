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
and preserves prior timeouts/source races.

## Installed and observed

The owner explicitly authorized the upgrade and reiterated standing permission
for routine reversible house work. Migration2694 installed source `b73d558` and
runtime SHA256 `21d6828b3c98f77b0a5aec6ef5edc080e1f6a084046f3b64567b936b8e62c8ee`.
The exact-source activation gate collected487, executed384 and skipped103;
all executed checks passed in246.589 seconds. [activation.json](activation.json)
binds the source, protected manifest, approval, drain, service replacement and
first successful real background publication. [Raw gate output](activation-tests.txt)
is retained unchanged. Admissions resumed2695 and Gemini returned normally2696–2699.
The two runtime paths were the only semantic LaunchAgent changes; Standard
ProcessType and all other properties were preserved. No resident was forcibly
interrupted. This establishes installation and successful publication, not a
measured production speedup or sustained equal model output.

The original rejected draft and failures remain in `../publication-worker-review/`.
