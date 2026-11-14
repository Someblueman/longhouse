# Service scheduling repair — 14 November 2026

The continuous LaunchAgent was configured as `ProcessType=Background`. Its
coordinator and integration-test children were observed at nice0, priority4.
Apple's installed `launchd.plist(5)` documents Background resource restrictions;
Standard is the default classification, not Interactive's unrestricted policy.

The same disposable 25 journal appends took 1.014/1.018 seconds under default
scheduling and 5.681/5.745 seconds under Background, in ABBA order. The roughly
5.6x ratio applies to this small local workload, not total resident productivity.
`probe.py` and `probe-results.json` preserve inputs, results and the failed initial
launcher-path attempt. Reproduce on macOS from this repository with
`python3 evidence/service-scheduling/probe.py "$PWD" default` and
`/usr/sbin/taskpolicy -b python3 evidence/service-scheduling/probe.py "$PWD" background`.
No model or network is used; each temporary house is removed afterwards.

The existing independent publication-repair gate timed out under Background;
its test log and result are retained, not called a pass. Emberwick independently
reviewed exact bytes, then slept2592 and exited2595. Its 1769-second session
included1606 seconds waiting on45 house requests. That includes the gate wait;
it is not model thinking time or a pure scheduling benchmark.

Admissions paused2591, all native runs and trusted jobs drained, and only the
existing LaunchAgent ProcessType changed. All other parsed plist properties and
the pinned archive SHA remained identical. Bootout succeeded; immediate bootstrap
failed with exit5. After verifying the old process absent, bootstrap retry succeeded.
No cause for that transient launchctl error is proven. New service PID9940 was
observed at nice0, priority20. A mistaken fixed-priority31 assertion failed;
resume2596 still executed and overstated that observation. Correction2601 and
`restart.json` preserve this mistake. Process priority is dynamic: Standard is
verified configuration, not a promise of a fixed number.

Admissions resumed2596. The ordinary balancing policy selected Gemini2597/2598
for the existing pending independent review, launched2599, and it woke2600.
No extra coordinator, new schedule, credentials, sandbox, quota, concurrency,
source runtime or authority change was made. Production speedup and the final
integration verdict remain to be measured. The separate asynchronous publication
worker is still a candidate, not installed by this service-setting repair.
