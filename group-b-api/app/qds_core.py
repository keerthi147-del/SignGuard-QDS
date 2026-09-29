"""
Group A -- Quantum-inspired core for teleportation-based Quantum Digital
Signatures (QDS), simulated on a classical computer with numpy statevectors.

No AI/ML anywhere in this file -- everything here is quantum-mechanics
simulation (superposition, entanglement, Born-rule measurement) plus
statistical threshold decisions, exactly as the problem statement asks for.

Run this file directly to see a self-test (checks the teleportation math is
correct) and one example run of every attack scenario.
"""
import math
import os
import random
import numpy as np

# ---------------------------------------------------------------------------
# Single-qubit states: Pauli-Z eigenstates |0>,|1> and Pauli-X eigenstates |+>,|->
# ---------------------------------------------------------------------------
ZERO = np.array([1, 0], dtype=complex)
ONE = np.array([0, 1], dtype=complex)
PLUS = (ZERO + ONE) / math.sqrt(2)
MINUS = (ZERO - ONE) / math.sqrt(2)
H = (1 / math.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)


def prepare_state(basis: str, bit: int) -> np.ndarray:
    """One of the four Pauli eigenstates used as a signature qubit."""
    if basis == "Z":
        return ONE.copy() if bit else ZERO.copy()
    return MINUS.copy() if bit else PLUS.copy()


def _measure(state: np.ndarray, basis: str) -> int:
    """Projective measurement of a single qubit in the Z or X basis (Born rule)."""
    if basis == "X":
        state = H @ state  # rotate X-basis into computational basis
    p0 = abs(state[0]) ** 2
    return 0 if random.random() < p0 else 1


# ---------------------------------------------------------------------------
# Quantum teleportation of one qubit through a fresh Bell pair.
# 3-qubit statevector, basis order q0 (message) - q1 (Alice) - q2 (Bob).
# ---------------------------------------------------------------------------
def teleport(psi: np.ndarray, eavesdrop: bool = False) -> tuple[np.ndarray, dict]:
    """
    Teleports psi from Alice to Bob using a fresh Bell pair.
    If eavesdrop=True, Eve intercepts the qubit in transit, measures it in a
    randomly chosen basis, and forwards her own re-prepared qubit instead --
    the standard intercept-resend attack on a quantum channel.
    Returns (bob_state, log).
    """
    log = {"eavesdropped": eavesdrop}
    if eavesdrop:
        eve_basis = random.choice(["Z", "X"])
        eve_bit = _measure(psi, eve_basis)
        psi = prepare_state(eve_basis, eve_bit)  # Eve resends her (disturbed) guess
        log["eve_basis"], log["eve_bit"] = eve_basis, eve_bit

    # Fresh Bell pair on qubits 1,2: (|00> + |11>)/sqrt2
    bell = np.zeros(4, dtype=complex)
    bell[0b00] = bell[0b11] = 1 / math.sqrt(2)

    # Combined 3-qubit state: psi (x) bell, index = 4*a + 2*b + c
    v = np.zeros(8, dtype=complex)
    for a in range(2):
        for bc in range(4):
            v[4 * a + bc] = psi[a] * bell[bc]

    # CNOT(control=q0, target=q1): if a==1, flip b
    v2 = np.zeros(8, dtype=complex)
    for a in range(2):
        for b in range(2):
            for c in range(2):
                b2 = b ^ a
                v2[4 * a + 2 * b2 + c] = v[4 * a + 2 * b + c]
    v = v2

    # Hadamard on q0
    v2 = np.zeros(8, dtype=complex)
    for a in range(2):
        for b in range(2):
            for c in range(2):
                for a2 in range(2):
                    v2[4 * a2 + 2 * b + c] += H[a2, a] * v[4 * a + 2 * b + c]
    v = v2

    # Alice measures q0,q1 (Born rule over the marginal), Bob's q2 collapses accordingly
    probs = {}
    for a in range(2):
        for b in range(2):
            amp = np.array([v[4 * a + 2 * b + c] for c in range(2)])
            probs[(a, b)] = float(np.vdot(amp, amp).real)
    r, cum, outcome = random.random(), 0.0, (0, 0)
    for k, p in probs.items():
        cum += p
        if r <= cum:
            outcome = k
            break
    m0, m1 = outcome
    amp = np.array([v[4 * m0 + 2 * m1 + c] for c in range(2)])
    bob = amp / math.sqrt(probs[(m0, m1)])

    # Classical correction based on Alice's measurement
    if m1 == 1:
        bob = X @ bob
    if m0 == 1:
        bob = Z @ bob

    log["alice_measured"] = (m0, m1)
    return bob, log


def _self_test(trials: int = 300) -> float:
    """Fidelity check: teleporting random states should reproduce them exactly."""
    fidelities = []
    for _ in range(trials):
        basis, bit = random.choice(["Z", "X"]), random.randint(0, 1)
        psi = prepare_state(basis, bit)
        bob, _ = teleport(psi)
        fidelities.append(abs(np.vdot(psi, bob)) ** 2)
    return sum(fidelities) / len(fidelities)


# ---------------------------------------------------------------------------
# QDS signing/verification protocol
# ---------------------------------------------------------------------------
def _binomial_tail(n: int, k: int, p: float = 0.5) -> float:
    """P(X <= k) for X ~ Binomial(n, p) -- the classic QDS forgery-probability bound."""
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, k + 1))


def run_protocol(scenario: str, n: int = 32, threshold: float = 0.15, noise: float = 0.02) -> dict:
    """
    Simulates one teleportation-based QDS signing + verification round.

    scenario:
      honest              -- genuine signer, genuine verifier, small channel noise
      channel_manipulation-- an eavesdropper intercepts the teleported qubits
      forgery             -- an attacker without the signer's real states tries to forge
      impersonation       -- an attacker signs as someone else, same mechanism as forgery
      replay              -- an attacker reuses old, already-measured qubits for a new message
    """
    signer_basis = [random.choice(["Z", "X"]) for _ in range(n)]
    signer_bit = [random.randint(0, 1) for _ in range(n)]
    eavesdrop = scenario == "channel_manipulation"

    # Step 1: signer prepares signature qubits and teleports them to the verifier
    # (this is the "quantum public key distribution" step)
    teleported = []
    for i in range(n):
        psi = prepare_state(signer_basis[i], signer_bit[i])
        bob, _ = teleport(psi, eavesdrop=eavesdrop)
        # small realistic channel noise: random bit-flip with low probability
        if random.random() < noise:
            bob = X @ bob
        teleported.append(bob)

    if scenario in ("forgery", "impersonation"):
        # Attacker never received the real teleported states -- they only have
        # their own guessed qubits, unrelated to the signer's actual random choices.
        teleported = []
        for i in range(n):
            guess = prepare_state(random.choice(["Z", "X"]), random.randint(0, 1))
            teleported.append(guess)

    if scenario == "replay":
        # Attacker reuses qubits from an earlier (already measured/collapsed) session,
        # then the signer/verifier issue a fresh random challenge for the new message.
        old_basis = [random.choice(["Z", "X"]) for _ in range(n)]
        old_bit = [random.randint(0, 1) for _ in range(n)]
        teleported = [prepare_state(old_basis[i], old_bit[i]) for i in range(n)]

    # Step 2: verifier measures each qubit in the basis the signer reveals for THIS message
    outcomes = [_measure(teleported[i], signer_basis[i]) for i in range(n)]
    mismatches = sum(1 for i in range(n) if outcomes[i] != signer_bit[i])
    mismatch_rate = mismatches / n
    decision = "ACCEPT" if mismatch_rate <= threshold else "REJECT"

    forgery_probability = _binomial_tail(n, int(threshold * n), p=0.5)

    return {
        "scenario": scenario,
        "n_qubits": n,
        "threshold": threshold,
        "mismatches": mismatches,
        "mismatch_rate": round(mismatch_rate, 4),
        "decision": decision,
        "forgery_probability": forgery_probability,
        "sample": [
            {"i": i, "basis": signer_basis[i], "expected_bit": signer_bit[i], "measured_bit": outcomes[i],
             "match": signer_bit[i] == outcomes[i]}
            for i in range(min(n, 16))
        ],
    }


# ---------------------------------------------------------------------------
# Document-bound signing: the document's SHA-256 fingerprint (plus a secret
# per-signature nonce) decides every (basis, bit) of the signature qubits.
# ---------------------------------------------------------------------------
import hashlib


def derive_challenge(doc_hash: str, nonce: str, n: int):
    """Expand SHA-256(doc_hash || nonce || counter) into n bases and n bits."""
    stream, ctr = b"", 0
    while len(stream) * 8 < 2 * n:
        stream += hashlib.sha256(f"{doc_hash}|{nonce}|{ctr}".encode()).digest()
        ctr += 1
    bits = [(stream[k // 8] >> (k % 8)) & 1 for k in range(2 * n)]
    return ["X" if bits[2 * i] else "Z" for i in range(n)], [bits[2 * i + 1] for i in range(n)]


def sign_document(doc_hash: str, n: int = 32, noise: float = 0.02):
    """Signer prepares the document-derived qubits and teleports them to the verifier.
    Returns (nonce, teleported_states). The states are what the verifier holds."""
    nonce = os.urandom(16).hex()
    bases, bits = derive_challenge(doc_hash, nonce, n)
    states = []
    for i in range(n):
        bob, _ = teleport(prepare_state(bases[i], bits[i]))
        if random.random() < noise:
            bob = X @ bob
        states.append(bob)
    return nonce, states


def verify_document(states, doc_hash: str, nonce: str, threshold: float = 0.15) -> dict:
    """Verifier re-derives the challenge from the document it was GIVEN, measures the
    stored qubits in those bases and counts mismatches against the derived bits."""
    n = len(states)
    bases, bits = derive_challenge(doc_hash, nonce, n)
    outcomes = [_measure(states[i], bases[i]) for i in range(n)]
    mismatches = sum(outcomes[i] != bits[i] for i in range(n))
    rate = mismatches / n
    return {
        "n_qubits": n, "threshold": threshold, "mismatches": mismatches,
        "mismatch_rate": round(rate, 4),
        "decision": "ACCEPT" if rate <= threshold else "REJECT",
        "forgery_probability": _binomial_tail(n, int(threshold * n), p=0.5),
        "sample": [{"i": i, "basis": bases[i], "expected_bit": bits[i], "measured_bit": outcomes[i],
                    "match": bits[i] == outcomes[i]} for i in range(min(n, 16))],
    }


def state_to_json(s):  # for database storage
    return [[float(a.real), float(a.imag)] for a in s]


def state_from_json(j):
    return np.array([complex(a, b) for a, b in j], dtype=complex)


if __name__ == "__main__":
    fid = _self_test()
    print(f"Teleportation self-test average fidelity: {fid:.4f} (should be ~1.0)\n")
    for s in ["honest", "channel_manipulation", "forgery", "impersonation", "replay"]:
        r = run_protocol(s, n=32, threshold=0.15)
        print(f"{s:22} mismatch={r['mismatch_rate']*100:5.1f}%  decision={r['decision']:6}  "
              f"P(forger accepted)={r['forgery_probability']:.2e}")
