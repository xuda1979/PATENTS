# DLHP Patent Simulation

This folder contains a reproducible, standard-library-only simulation for the
Dynamic Lattice-Hopping Protocol (DLHP / DMP-CHP) described in this patent
workspace.

What the code does:

- Executes the protocol mechanics directly where practical:
  - stateless `SeqID`-driven hop derivation,
  - orthogonality-constrained algorithm selection,
  - Shamir-style threshold splitting and reconstruction for HED.
- Generates model-based performance results using Monte Carlo sampling
  calibrated from the patent's own baseline tables in
  [experimental_data.md](../experimental_data.md).

What the code does not do:

- It does not call `liboqs`, OpenSSL, or a production PQC stack.
- It does not constitute a real benchmark of ML-KEM, NTRU, McEliece, BIKE, or
  any deployed transport.
- The generated performance numbers are simulation outputs, not hardware
  measurements.

Run:

```powershell
python simulation/run_dlhp_experiments.py
```

Generated artifacts:

- `simulation/results/summary.json`
- `simulation/results/summary.md`
- `simulation/results/interval_results.csv`
- `simulation/results/transition_results.csv`
- `simulation/results/handshake_results.csv`

If you later want real benchmark evidence instead of a calibrated simulation,
the next step is to build a separate harness around real cryptographic
implementations and packet transports.
