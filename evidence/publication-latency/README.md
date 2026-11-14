# Publication latency: one observed workload

On source7c8951a and verified journal2468, one read-only production-shaped local
export took2.393 seconds to build frames,1.900 seconds to encode them, and0.017
seconds to serialize2824615 bytes. The observation records Python, source and
journal IDs, payload hash, wall time and process CPU time. It makes no network
request and changes no runtime.

This does not explain every30–40-second live mailbox reply. A separate55-second
process observation sampled the existing coordinator and both known native PIDs
52 times. Both OpenCode37453 and Gemini40463 were present in every sample. Direct
Git/GitHub children appeared in13 samples; this is censored occupancy, not exact
call durations or proof that network time is the entire cause. The live service
and residents remained concurrent; no host settings changed.

The next repair must demonstrate mailbox service and resident reaping while a
publisher is deliberately blocked. Moving publication to a worker can remove
that blocking boundary; it does not establish that all orchestration latency is
fixed. No speedup or statistical confidence interval is claimed from this single
measurement. The candidate remains subject to real process cleanup tests and
independent review before the owner/council runtime activation gate.
