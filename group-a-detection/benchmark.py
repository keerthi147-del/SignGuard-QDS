"""
Group A -- Performance & security benchmark for the teleportation-based QDS
simulation. Produces the empirical evidence behind SECURITY_ANALYSIS.md:
runtime scaling, false-accept/false-reject rates, and measured vs
theoretical forgery probability, across a range of signature lengths (n).

Run:
    pip install -r requirements.txt   # needs numpy + matplotlib
    python benchmark.py

Outputs (written next to this script):
    benchmark_results.csv
    benchmark_forgery_probability.png
    benchmark_report.md
"""
import csv
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from qds_core import run_protocol, _binomial_tail

N_VALUES = [8, 16, 32, 64, 128]
THRESHOLD = 0.15
TRIALS = 40
SCENARIOS = ["honest", "channel_manipulation", "forgery", "impersonation", "replay"]


def main():
    rows = []
    timings = {}

    for n in N_VALUES:
        t0 = time.perf_counter()
        for _ in range(5):
            run_protocol("honest", n=n, threshold=THRESHOLD)
        timings[n] = (time.perf_counter() - t0) / 5

        for scenario in SCENARIOS:
            accepts = 0
            mismatch_sum = 0.0
            for _ in range(TRIALS):
                r = run_protocol(scenario, n=n, threshold=THRESHOLD)
                accepts += r["decision"] == "ACCEPT"
                mismatch_sum += r["mismatch_rate"]
            rows.append({
                "n_qubits": n,
                "scenario": scenario,
                "trials": TRIALS,
                "accept_rate": round(accepts / TRIALS, 4),
                "avg_mismatch_rate": round(mismatch_sum / TRIALS, 4),
                "theoretical_forgery_probability": _binomial_tail(n, int(THRESHOLD * n), p=0.5),
                "avg_runtime_sec_per_run": round(timings[n], 5),
            })
            print(f"n={n:4} {scenario:22} accept_rate={rows[-1]['accept_rate']:.2f} "
                  f"avg_mismatch={rows[-1]['avg_mismatch_rate']:.3f} "
                  f"theory_forge_p={rows[-1]['theoretical_forgery_probability']:.2e}")

    with open("benchmark_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Plot: theoretical forgery probability vs n (log scale), and the empirical
    # accept-rate of the forgery scenario at the same n values, side by side.
    theory = [_binomial_tail(n, int(THRESHOLD * n), p=0.5) for n in N_VALUES]
    forge_empirical = [r["accept_rate"] for r in rows if r["scenario"] == "forgery"]
    honest_empirical = [r["accept_rate"] for r in rows if r["scenario"] == "honest"]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogy(N_VALUES, theory, "o-", label="Theoretical P(blind forger accepted)", color="#dc2626")
    ax.semilogy(N_VALUES, [max(x, 1e-4) for x in forge_empirical], "s--",
                label="Empirical forgery accept rate (measured)", color="#f97316")
    ax.semilogy(N_VALUES, [max(x, 1e-4) for x in [1 - h for h in honest_empirical]], "^--",
                label="Empirical honest-signer reject rate (measured)", color="#3b82f6")
    ax.set_xlabel("Signature length n (qubits)")
    ax.set_ylabel("Probability (log scale)")
    ax.set_title(f"Forgery probability vs signature length (threshold={THRESHOLD})")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig("benchmark_forgery_probability.png", dpi=150)

    with open("benchmark_report.md", "w") as f:
        f.write("# SignGuard QDS -- Benchmark report\n\n")
        f.write(f"Threshold = {THRESHOLD}, {TRIALS} trials per (scenario, n) pair.\n\n")
        f.write("## Runtime scaling\n\n| n (qubits) | Avg time per signing+verification round (s) |\n|---|---|\n")
        for n in N_VALUES:
            f.write(f"| {n} | {timings[n]:.5f} |\n")
        f.write("\n## Accept rate and mismatch by scenario\n\n")
        f.write("| n | Scenario | Accept rate | Avg mismatch | Theoretical forgery P |\n|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['n_qubits']} | {r['scenario']} | {r['accept_rate']} | "
                    f"{r['avg_mismatch_rate']} | {r['theoretical_forgery_probability']:.3e} |\n")
        f.write("\nSee `benchmark_forgery_probability.png` for the forgery-probability-vs-n plot, "
                "and `benchmark_results.csv` for the raw data.\n")

    print("\nWrote benchmark_results.csv, benchmark_forgery_probability.png, benchmark_report.md")


if __name__ == "__main__":
    main()
