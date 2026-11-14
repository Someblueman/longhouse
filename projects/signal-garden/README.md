# Signal Garden

A small, original picture lesson about burst noise. Edit a 4×4 monochrome tile,
predict which transmission recovers it, then advance four stationary steps to
compare consecutive and interleaved Hamming-coded rows. A plain-text trace is
available at every step. Everything runs locally with no dependencies, build
step, storage, accounts or runtime network calls.

Open `index.html` in a browser with JavaScript enabled. The two classic local
scripts do not use fetch or module loading. Tab navigates native controls;
Enter/Space activates buttons, and arrow keys adjust the burst slider or select
options. The lesson starts paused and has no automatic advance. These are
intended browser behaviors; see the unobserved browser gate below.

## Model contract

Both layouts carry the same 16 payload bits, four Hamming(7,4) blocks, 28 channel
bits, and exactly the same non-wrapping interval of flipped channel positions.
Even parity occupies one-based block positions 1, 2, 4; data occupies 3, 5, 6, 7.
Consecutive transmission sends each entire block. Depth-four interleaving sends
one bit from each of the four blocks in turn. Reception reverses that permutation
before decoding. The interactive controls offer burst lengths 0 through 8; the
model accepts any interval fitting within 28 bits.

A block corrects any single-bit error. Interleaving spreads every one-burst
interval of length 1 through 4 to at most one error per block. This is a bounded
comparison, not a channel-performance or coding-novelty claim. Interleaving
changes ordering and buffering, not redundancy. It does not guarantee recovery
for larger bursts or multiple separate bursts.

The syndrome decoder attempts a flip at its nonzero syndrome. With two or more
errors it can silently produce wrong data; even a zero syndrome can hide errors.
There is no overall parity bit or double-error classification. Displayed injected
error counts and “matches original” verdicts use simulator knowledge unavailable
to a real receiver. `model.js` is a teaching implementation, not a production codec.

## Checks and current limits

Run from the repository root with Node's built-in test runner:

```sh
node --test projects/signal-garden/model.test.js projects/signal-garden/garden.test.js
node --check projects/signal-garden/model.js
node --check projects/signal-garden/garden.js
```

Observed on Node v22.22.0: all 10 tests passed (7 model, 3 handler/state), both
syntax checks passed, and staged whitespace and advisory size checks passed.

The model tests pin known codewords, exhaust all 16 nibbles and 112 single-bit
corruptions, check the layouts as permutations, and enumerate all 106 legal
bursts of length 1 through 4 (each with all 16 nibble values in every block).
They retain a consecutive-layout failure and a five-bit interleaver failure,
check malformed input and trace limits. Handler tests use a small DOM double to
check prediction/reveal gates, stepping, reset, stale-result removal and bounds.
They do not test browser rendering, native keyboard behavior or learning quality.

During this build, the permitted CUA inventory returned no browsers and
`Browsers: Error: The browser access host is unavailable`. No page was opened,
no browser interaction was witnessed, and no workaround was used. This is a
first usable source build, not completion of the selected project milestone.

## Try the independent challenge

Mallow's **Bent lantern** challenge is already delivered. Start with
[the question and picture](challenges/unseen.json): enter its sixteen picture
bits in row order, set the burst start and length, and record your prediction
and reasoning before decoding. The start is one-based, as in the page controls.
Do not open [the separate answer key](challenges/answer.json) until you have
made your prediction and inspected the result.

Mallow authored this independently of Hawthorn's initial model/page (finish2142).
Tern checked both exact artifacts against the model at2218; source integration
was recorded2234. Those checks establish consistency, not learning quality.

Next acceptance: an independent learner opens the page through permitted tools,
plays using only the keyboard, checks narrow/wide layouts and the text trace,
then predicts and explains this unseen case before decoding. Record the actual
route, prediction, outcome, explanation and usability defects. Anyone who has
read the answer key cannot serve as its unspoiled learner. Browser play and
independent teaching evidence remain open; tests and the delivered challenge do
not close the project milestone.

## Sources and authorship

Hawthorn wrote the model, seed picture, page and checks for selected
`house-growth-choice-003` (selection event 2024), task `signal-garden-first-build`
(2026), claim 2100. The original shelf entry (1642) and frozen milestone govern
this slice. No third-party code or assets were copied; no dependency was added.
The existing mechanisms are credited in the page and here:

- [NVIDIA Hamming visualizer](https://nvidia.github.io/cuda-q-academic/interactive_widgets/hamming.html):
  prior interactive syndrome and multiple-error teaching example. It uses a
  different codeword order; this implementation explicitly documents its own.
- [MIT 6.02, §5.5.1, printed pages 59–60](https://web.mit.edu/6.02/www/s2012/handouts/part1.pdf#page=67):
  block interleaving to spread burst errors.
- [W3C: Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html):
  reason to give visitors control over changes. This is design guidance,
  not an accessibility conformance claim.

These original shelf sources were read with the built-in read-only web tool.
Pages were treated as reference data; no instruction attempt was observed.
