# Simulation Folder Status

## Warning

This folder contains **deprecated statistical simulation artifacts**.

These files are **not** produced by a real Falcon implementation, **not** produced by a real threshold Falcon implementation, and **must not** be used as experimental evidence, benchmark evidence, patent evidence, or performance claims.

## Why this folder is deprecated

The scripts in this folder model behavior using manually configured parameters and pseudo-random sampling.
They do **not** execute:

- the Falcon reference implementation,
- `liboqs`,
- a threshold Falcon protocol,
- a real MPC / Beaver-triple engine,
- or a real distributed signing system.

Therefore, any outputs generated here are only simulation artifacts and are **not real measurements**.

## Files that should not be cited as real data

- `simulation/run_experiments.py`
- `simulation/results/raw_samples.csv`
- `simulation/results/summary.json`
- `simulation/results/summary.md`
- `simulation/plot_results.py`

## Allowed use

At most, these files may be kept as historical scratch work or discarded entirely.
They must not be presented as algorithm-faithful experiments.

## Requirement going forward

Any future experimental results must be generated only from:

- a real Falcon implementation,
- a real threshold Falcon implementation,
- real logging,
- and auditable raw measurement files.
