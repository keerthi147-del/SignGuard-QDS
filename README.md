# SignGuard -- Quantum-Inspired Cyber Threat Detection for Digital Signature Security
### PS 26141 -- Egreen Quanta (Blockchain & Cybersecurity)

This version implements what the problem statement actually asks for: a
simulated **teleportation-based Quantum Digital Signature (QDS)** protocol,
with threat detection driven by **quantum measurement statistics**, not
classical crypto and not AI/ML.

```
signguard/
├── group-a-detection/   # qds_core.py -- the quantum simulation itself.
│                        #   No Flask, no DB. Runs and self-tests standalone.
│                        #   benchmark.py -- performance + security benchmark,
│                        #   produces benchmark_report.md, benchmark_results.csv
│                        #   and benchmark_forgery_probability.png
├── group-b-api/         # Flask API wrapping qds_core.py with a database,
│                        #   login and a built-in interactive /docs page.
├── group-c-dashboard/   # Dashboard showing each run's per-qubit
│                        #   measurement log, mismatch rate and decision.
└── docs/
    ├── MATHEMATICAL_MODEL.md   # protocol equations, referenced by the code
    └── SECURITY_ANALYSIS.md    # security argument for each threat + limitations
```

## What's actually simulated (all with plain numpy -- no Qiskit needed)

- **Bell-state entanglement**: a fresh 2-qubit Bell pair `(|00>+|11>)/sqrt(2)`
  is created for every signature qubit.
- **Quantum teleportation**: a full 3-qubit statevector simulation --
  CNOT + Hadamard + Bell-basis measurement + classical Pauli correction --
  moves the signer's qubit to the verifier without ever copying it (the
  no-cloning theorem is respected: only teleportation, never duplication).
- **Pauli eigenstates**: every signature qubit is one of the four Pauli
  eigenstates -- `|0>`, `|1>` (Z-basis) or `|+>`, `|->` (X-basis) --
  chosen and later revealed at random by the signer.
- **Projective measurement**: the verifier measures each teleported qubit
  in the basis the signer reveals, using the Born rule (`qds_core._measure`).
- **Statistical threshold decision, no AI/ML**: the fraction of qubits
  where the verifier's outcome disagrees with the signer's revealed bit
  (the *mismatch rate*) is compared to a fixed threshold to ACCEPT or
  REJECT. A blind attacker's probability of slipping past that threshold
  is computed exactly with the binomial distribution -- this is the
  **forgery probability analysis** the PS asks for.

`group-a-detection/qds_core.py` includes a self-test: teleporting random
states and checking the fidelity comes out to 1.0, i.e. teleportation is
implemented correctly. Run it directly to see this.

## The five scenarios (cover every threat in the PS)

| Scenario | What it models | Typical result at n=32, threshold=15% |
|---|---|---|
| `honest` | Genuine signer and verifier, small channel noise | ~2-3% mismatch -> ACCEPT |
| `channel_manipulation` | An eavesdropper intercepts the teleported qubits and resends her own (intercept-resend, the classic quantum-channel attack) | ~25-40% mismatch -> REJECT |
| `forgery` | An attacker who never received the signer's real quantum states tries to forge a signature | ~40-50% mismatch -> REJECT |
| `impersonation` | An attacker signs pretending to be someone else, without holding that identity's real states | ~35-55% mismatch -> REJECT |
| `replay` | An attacker reuses old, already-measured qubits against a fresh random challenge for a new message | ~50% mismatch -> REJECT |

The honest case stays low because a correctly teleported Pauli eigenstate,
measured in the same basis it was prepared in, is deterministic. Every
attack scenario breaks that correlation, which is exactly the
information-theoretic security guarantee QDS relies on -- not computation,
but physics.

## Quick start

### 1. Group A -- run the quantum core on its own
```bash
cd group-a-detection
pip install -r requirements.txt
python qds_core.py
```
Prints the self-test fidelity and one example run of all five scenarios,
no server needed.

### 2. Run the app (API + web UI, one command)
```bash
cd group-b-api/app
pip install -r ../requirements.txt
python main.py
```
Open **http://localhost:5000**. Sign up, then use **Sign** (upload a file, get a
signature ID), **Verify** (upload the same file, or a tampered copy, plus the ID),
**My signatures**, and **Attack lab** (the five simulated attacks).
Data lives in `group-b-api/signguard_qds_v2.db`. There is no default admin account.

### Optional -- run the benchmark
```bash
cd group-a-detection && python benchmark.py
```

## API

- `POST /api/signup` `{email, username, password}` and `POST /api/login` `{email or username, password}` -> `{token, user}`
- `POST /api/sign` (multipart `file`) -> `{signature_id, doc_hash, ...}`
- `POST /api/verify` (multipart `file`, `signature_id`) -> ACCEPT/REJECT + mismatch data
- `GET /api/signatures`, `GET /api/me`, `POST /api/logout`

Older endpoints:

- `POST /api/login` -> `{email, password}` -> `{token}` (send back as `X-Token` header)
- `POST /api/run/<scenario>?n=32&threshold=0.15` -> runs one QDS round for
  `scenario` in `honest|channel_manipulation|forgery|impersonation|replay`
- `GET /api/dashboard` -> history, per-decision counts, per-scenario stats, timeline

## Documentation

- `docs/MATHEMATICAL_MODEL.md` -- the protocol's equations end to end:
  Pauli eigenstate preparation, the teleportation circuit, the
  verification decision rule, and the binomial forgery-probability
  formula.
- `docs/SECURITY_ANALYSIS.md` -- the security argument for each of the
  four threats in the PS, backed by the benchmark's empirical results,
  plus an explicit limitations section (finite-key effects, classical
  channel authentication assumption, single-verifier scope).

## Honest limitations -- say these in the demo

- This is a **classical simulation of quantum mechanics** (statevectors in
  numpy), the same way Qiskit's simulator works, not real quantum
  hardware. Nothing here claims otherwise.
- Each signature qubit is teleported independently with a fresh Bell pair.
  A production QDS scheme would also need to handle multi-party
  distribution and long-term key/state storage, which isn't modeled here.
- The channel noise model (`noise=0.02` in `run_protocol`) is a simple
  random bit-flip, not a physically calibrated depolarizing/dephasing
  channel.
- `n=32` qubits per signature and `threshold=0.15` are prototype defaults
  you can tune via the API's query parameters -- they are reasonable
  demo values, not a value derived from a specific QDS paper's security
  proof.
- No AI/ML is used anywhere, per the PS's requirement -- every decision
  comes from the binomial/statistical analysis in `qds_core.py`.

## Document signing: how it works and what it simplifies

The SHA-256 of the uploaded file plus a secret per-signature nonce is expanded into
the (basis, bit) of each signature qubit. Verification re-derives them from the file
you upload and measures the stored qubits, so a changed file gives ~50% mismatch.
Simplification: the server plays signer and verifier, and it measures a stored copy of
the qubit states so a signature can be checked more than once. Real qubits collapse
when measured. Files are hashed and discarded, never stored.
