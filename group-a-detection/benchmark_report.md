# SignGuard QDS -- Benchmark report

Threshold = 0.15, 40 trials per (scenario, n) pair.

## Runtime scaling

| n (qubits) | Avg time per signing+verification round (s) |
|---|---|
| 8 | 0.00046 |
| 16 | 0.00037 |
| 32 | 0.00082 |
| 64 | 0.00167 |
| 128 | 0.00329 |

## Accept rate and mismatch by scenario

| n | Scenario | Accept rate | Avg mismatch | Theoretical forgery P |
|---|---|---|---|---|
| 8 | honest | 1.0 | 0.0125 | 3.516e-02 |
| 8 | channel_manipulation | 0.225 | 0.2844 | 3.516e-02 |
| 8 | forgery | 0.025 | 0.525 | 3.516e-02 |
| 8 | impersonation | 0.025 | 0.4906 | 3.516e-02 |
| 8 | replay | 0.025 | 0.4813 | 3.516e-02 |
| 16 | honest | 1.0 | 0.0063 | 2.090e-03 |
| 16 | channel_manipulation | 0.2 | 0.2437 | 2.090e-03 |
| 16 | forgery | 0.0 | 0.5094 | 2.090e-03 |
| 16 | impersonation | 0.0 | 0.4875 | 2.090e-03 |
| 16 | replay | 0.0 | 0.5328 | 2.090e-03 |
| 32 | honest | 1.0 | 0.0094 | 9.651e-06 |
| 32 | channel_manipulation | 0.0 | 0.2617 | 9.651e-06 |
| 32 | forgery | 0.0 | 0.4758 | 9.651e-06 |
| 32 | impersonation | 0.0 | 0.5148 | 9.651e-06 |
| 32 | replay | 0.0 | 0.4984 | 9.651e-06 |
| 64 | honest | 1.0 | 0.0094 | 1.771e-09 |
| 64 | channel_manipulation | 0.05 | 0.2645 | 1.771e-09 |
| 64 | forgery | 0.0 | 0.5078 | 1.771e-09 |
| 64 | impersonation | 0.0 | 0.5023 | 1.771e-09 |
| 64 | replay | 0.0 | 0.5145 | 1.771e-09 |
| 128 | honest | 1.0 | 0.0092 | 7.779e-17 |
| 128 | channel_manipulation | 0.0 | 0.2576 | 7.779e-17 |
| 128 | forgery | 0.0 | 0.502 | 7.779e-17 |
| 128 | impersonation | 0.0 | 0.508 | 7.779e-17 |
| 128 | replay | 0.0 | 0.5055 | 7.779e-17 |

See `benchmark_forgery_probability.png` for the forgery-probability-vs-n plot, and `benchmark_results.csv` for the raw data.
