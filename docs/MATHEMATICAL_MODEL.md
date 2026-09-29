# SignGuard QDS -- Mathematical model

This document describes the protocol implemented in
`group-a-detection/qds_core.py`, so it can be read and cited independently
of the code.

## 1. Signature qubits: Pauli eigenstates

For each of the `n` bits in a signature, the signer picks a uniformly
random basis `b_i in {Z, X}` and a uniformly random bit `s_i in {0,1}`,
and prepares the qubit in the corresponding Pauli eigenstate:

```
Z-basis:  |0>            (s_i = 0)      |1>              (s_i = 1)
X-basis:  |+> = (|0>+|1>)/sqrt(2)  (s_i = 0)   |-> = (|0>-|1>)/sqrt(2)  (s_i = 1)
```

`(b_i, s_i)` for i = 1..n is the signer's private signing key for this
message. It is revealed to the verifier only at signing time (Section 4).

## 2. Distribution by quantum teleportation

Each signature qubit `|psi_i>` is transmitted to the verifier by
teleportation through a freshly generated Bell pair
`|Phi+> = (|00> + |11>)/sqrt(2)`, using the standard three-qubit protocol:

1. Combine the message qubit with the Bell pair: `|psi_i> (x) |Phi+>`
2. Apply CNOT with the message qubit as control, Alice's half of the Bell
   pair as target
3. Apply a Hadamard gate to the message qubit
4. Alice measures her two qubits in the computational basis, obtaining
   two classical bits `(m0, m1)`, and sends them to the verifier over a
   classical channel
5. The verifier applies the correction `X^{m1} Z^{m0}` to their half of
   the Bell pair, recovering `|psi_i>` exactly (up to global phase)

No qubit is copied at any point (respecting the no-cloning theorem) --
the original is destroyed by Alice's measurement in step 4, which is what
makes teleportation different from classical retransmission and is the
basis for the channel-manipulation detection in Section 5.

`qds_core.teleport()` implements this exactly as an 8-dimensional
statevector computation. `qds_core._self_test()` verifies it: teleporting
300 random Pauli-eigenstate qubits and computing fidelity
`|<psi|rho_out|psi>|^2` against the original state gives 1.0000.

## 3. Verification: projective measurement

At verification time, for each qubit the verifier measures their copy in
basis `b_i` (revealed by the signer). By the Born rule, if the verifier's
qubit is genuinely `|psi_i>` in basis `b_i`, the outcome equals `s_i` with
probability 1 (ignoring channel noise). `qds_core._measure()` implements
this: for the X basis it applies a Hadamard before measuring in the
computational basis, which is the standard change-of-basis trick.

## 4. Verification decision: statistical threshold, no AI/ML

Let `k` = number of qubits where the verifier's measured bit disagrees
with the signer's revealed bit `s_i` ("mismatches"), out of `n` total.
The decision rule is:

```
mismatch_rate = k / n
decision = ACCEPT   if mismatch_rate <= threshold
           REJECT   otherwise
```

`threshold` defaults to 0.15 (15%) in this prototype. This is a fixed,
explainable statistical rule -- no model is trained and no learned
parameters are involved anywhere in the decision.

## 5. Why each attack raises the mismatch rate

- **Forgery / impersonation**: an attacker without the signer's real
  `(b_i, s_i)` pairs can only guess a basis and bit for each qubit they
  present to the verifier. When the verifier measures in the *signer's*
  revealed basis, an attacker who guessed the wrong basis (probability
  1/2) gets an outcome uniformly random with respect to `s_i`
  (probability 1/2 of matching by chance). Expected mismatch rate
  approx=0.5 x 0.5 + 0 x 0.5 = 0.25 in the simplest model; the
  implementation's guessed-state approach empirically lands near 0.5,
  since the guessed state need not even share the right basis identity.
  Either way it sits far above a 15% threshold.
- **Replay**: reusing previously-measured (collapsed) qubits against a
  *new*, independently random challenge `(b_i, s_i)` for a new message
  behaves the same way as forgery -- the old qubits carry no information
  correlated with the new random challenge.
- **Channel manipulation (intercept-resend)**: an eavesdropper measures
  the qubit in a randomly guessed basis before teleportation completes,
  then forwards a freshly prepared qubit in that basis/outcome. When her
  guessed basis differs from the signer's actual basis (probability 1/2),
  her resent qubit is only correlated with the original by chance,
  disturbing roughly 1/4 of all qubits on average -- the same
  intercept-resend disturbance rate used to detect eavesdropping in BB84.

## 6. Forgery probability (exact, binomial)

If an attacker's forged qubits are uncorrelated with the signer's
revealed bits (mismatch probability 1/2 per qubit, independent across
qubits), the probability that they are nonetheless accepted is exactly
the binomial tail:

```
P(forgery accepted) = P(Binomial(n, 0.5) <= floor(threshold * n))
                     = sum_{i=0}^{floor(threshold*n)}  C(n, i) * 0.5^n
```

implemented in `qds_core._binomial_tail()`. This probability decays
exponentially in `n` (see `docs/../group-a-detection/benchmark_forgery_probability.png`):
approximately 3.5% at n=8, down to ~7.8e-17 at n=128 for threshold=0.15 --
i.e. choosing a longer signature makes blind forgery astronomically
unlikely, which is the standard security argument used in QDS literature
for this style of scheme.
