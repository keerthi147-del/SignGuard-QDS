# SignGuard QDS -- Security analysis

An informal security argument for the protocol in
`group-a-detection/qds_core.py`, referencing the empirical results in
`group-a-detection/benchmark_report.md` and
`group-a-detection/benchmark_forgery_probability.png`. This is a
prototype-level argument, not a peer-reviewed cryptographic proof -- see
the limitations at the end.

## Threat model addressed by the PS

- **Forgery**: attacker produces a valid-looking signature without access
  to the signer's private random choices.
- **Impersonation**: attacker signs a message purporting to be a
  different, legitimate signer.
- **Replay**: attacker reuses previously observed signing material
  against a new message.
- **Quantum channel manipulation**: attacker (eavesdropper) interferes
  with the quantum transmission between signer and verifier.

Classical RSA/ECC signatures are vulnerable to a quantum adversary running
Shor's algorithm (the motivation given in the PS background). The
protocol here does not rely on the hardness of factoring or discrete log
at all -- it relies only on quantum mechanics (no-cloning, measurement
disturbance), which is what gives QDS its "information-theoretic"
security claim, as opposed to RSA/ECC's computational security claim.

## 1. Forgery / impersonation resistance

**Argument.** An attacker attempting to forge (or impersonate) a
signature does not possess the signer's private `(basis, bit)` choices at
the time they must commit their fake qubits, since these are only
revealed classically at signing time. Any qubit the attacker presents is
therefore uncorrelated with the signer's actual choices for that specific
challenge, giving each qubit an independent ~1/2 probability of matching
the verifier's later check by chance alone.

**Bound.** Treating each qubit's match/mismatch as an independent
Bernoulli(0.5) trial, the probability that a forged signature of length
`n` nonetheless passes a mismatch-rate threshold `t` is the binomial tail

```
P(forgery accepted) = sum_{i=0}^{floor(t*n)} C(n,i) * 0.5^n
```

which decays exponentially in `n` (Chernoff-bound behaviour). At
`t = 0.15`: ~3.5e-2 at n=8, ~9.6e-6 at n=32, ~7.8e-17 at n=128 (see
`benchmark_forgery_probability.png`). This is the paper-standard argument
for this style of QDS scheme, and it is verified empirically, not just
computed: the benchmark's measured forgery accept-rate tracks the
theoretical curve (both drop to 0/40 observed successes by n=32 in our
trials).

## 2. Replay resistance

**Argument.** Two mechanisms combine here:
- The no-cloning theorem means an attacker who intercepts a qubit cannot
  produce an independent copy to reuse later without disturbing or
  consuming the original (Section 3's intercept-resend disturbance
  applies to *any* interception, not just the channel-manipulation
  scenario specifically).
- Even a successfully captured, already-measured qubit set is only
  correlated with the specific challenge `(basis, bit)` it was measured
  against. A fresh message triggers a fresh, independently random
  challenge, so old material behaves like a blind guess against it --
  the same ~1/2 per-qubit match probability and binomial bound as
  Section 1 apply.

**Empirical result.** The `replay` scenario in the benchmark shows ~50%
average mismatch and 0/40 accepted at n >= 16, consistent with this
argument.

## 3. Channel manipulation (eavesdropping) detection

**Argument.** This follows the same disturbance principle used to detect
eavesdropping in BB84: an eavesdropper who intercepts a qubit must
measure it (collapsing it) before resending a substitute, and has no way
to know the correct basis in advance. When her guessed basis is wrong
(probability 1/2), the substitute qubit she forwards is uncorrelated with
the original in the basis that matters, corrupting the correlation the
verifier is checking for.

**Empirical result.** The benchmark shows a ~25-30% mismatch rate under
eavesdropping, high enough to reliably breach a 15% threshold (0/40 to
2/40 accepted across n=16..128 in our trials), while staying below the
~50% seen for outright forgery -- consistent with the intercept-resend
model, since only a fraction of intercepted qubits are disturbed in a way
that produces a detectable mismatch.

## 4. Honest-party correctness

With small channel noise (`noise = 0.02` bit-flip probability per qubit
in `run_protocol`), the honest scenario shows ~1-2% average mismatch and
was accepted in all 40/40 trials at every tested `n` from 8 to 128 -- the
threshold of 15% comfortably tolerates this noise floor without letting
attacks through, which is the design trade-off a real deployment would
need to tune against its actual expected channel noise.

## Limitations of this analysis

- This is an **empirical + standard-textbook argument**, not a
  peer-reviewed security proof. A rigorous treatment would need finite-key
  statistical analysis (the binomial bound above assumes an idealized
  attacker strategy) and a formal adversary model.
- The protocol assumes an **authenticated classical channel** for
  revealing `(basis, bit)` and Alice's teleportation-correction bits --
  if an attacker can also tamper with classical communication
  undetected, additional authentication is required and is out of scope
  here.
- Only single-signer, single-verifier distribution is modeled. Real QDS
  literature also covers multi-verifier non-repudiation guarantees,
  which this prototype does not implement.
- The noise model is a simple i.i.d. bit-flip, not a physically
  calibrated depolarizing or dephasing channel.
