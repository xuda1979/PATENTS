# Falcon Signature Scheme - Real Benchmark Report

> **All data in this report comes from actual algorithm execution. No values are simulated, interpolated, or hand-written.**

## 1. Experiment Environment

| Item | Value |
|------|-------|
| **Implementation** | [tprest/falcon.py](https://github.com/tprest/falcon.py) (pure Python, MIT license) |
| **Author** | Thomas Prest (co-author of the Falcon specification) |
| **Python** | 3.13.6 (MSC v.1944 32-bit) |
| **Platform** | Windows 11 (10.0.26200) |
| **Timestamp (UTC)** | 2026-03-09T12:19:56Z |
| **Keygen iterations** | 3 per parameter set |
| **Sign/Verify iterations** | 10 per parameter set |

### Implementation Provenance

The implementation used is `tprest/falcon.py` — a faithful pure-Python implementation of the Falcon signature scheme by Thomas Prest, one of the original Falcon designers. It implements:

- **NTRU key generation** (`ntrugen.py`): solving $fG - gF = q \pmod{\Phi_n}$
- **Fast Fourier sampling** (`ffsampling.py`): the ffSampling / ffNP algorithm over the Falcon tree
- **Discrete Gaussian sampling** (`samplerz.py`): SamplerZ with provable closeness
- **Signature compression** (`encoding.py`): Falcon's canonical encoding
- **SHAKE256-based hashing** to points in $\mathbb{Z}_q[x]/(\Phi_n)$

This is **not** a toy implementation. It follows the Falcon Round 3 specification and passes Known Answer Tests (KATs).

## 2. Key and Signature Sizes

| Parameter | Security Level | SK (bytes) | VK (bytes) | Signature (bytes) |
|-----------|---------------|------------|------------|-------------------|
| Falcon-256 | ~NIST-1 (reduced) | 1,792 | 448 | 356 |
| Falcon-512 | NIST-1 (128-bit) | 3,584 | 896 | 666 |
| Falcon-1024 | NIST-5 (256-bit) | 7,168 | 1,792 | 1,280 |

**Observations:**
- Signature sizes are compact — Falcon-512 signatures at 666 bytes are among the smallest of all post-quantum signature schemes at NIST-1 security.
- Key sizes scale linearly: doubling $n$ doubles all key/signature sizes.
- These sizes match the Falcon specification exactly (sig_bytelen values in the source code: 356, 666, 1280).

## 3. Performance Results

### 3.1 Key Generation

| Parameter | Mean (ms) | Median (ms) | Stdev (ms) | Min (ms) | Max (ms) | Iterations |
|-----------|-----------|-------------|------------|----------|----------|------------|
| Falcon-256 | 1,204.9 | 1,066.0 | 692.7 | 592.1 | 1,956.6 | 3 |
| Falcon-512 | 5,749.3 | 5,410.5 | 1,869.1 | 4,072.8 | 7,764.6 | 3 |
| Falcon-1024 | 21,201.6 | 20,722.9 | 1,362.7 | 20,142.8 | 22,739.1 | 3 |

**Analysis:**
- Key generation is the most expensive operation, dominated by NTRU polynomial generation (solving the NTRU equation).
- The scaling from $n=256$ to $n=1024$ is roughly $17.6\times$, consistent with the super-linear complexity of the extended-GCD / Babai lifting in `ntrugen`.
- The high variance in Falcon-256 keygen (CV = 57.5%) reflects the probabilistic nature of NTRU generation — the algorithm retries until a suitable $(f,g,F,G)$ quadruple is found.
- **Important note:** Key generation is a one-time operation. In the threshold Falcon scheme proposed in our patent, distributed key generation (DKG) occurs only once during system setup.

### 3.2 Signing

| Parameter | Mean (ms) | Median (ms) | Stdev (ms) | Min (ms) | Max (ms) | Iterations |
|-----------|-----------|-------------|------------|----------|----------|------------|
| Falcon-256 | 16.8 | 17.1 | 0.9 | 15.6 | 18.6 | 10 |
| Falcon-512 | 41.6 | 40.2 | 5.2 | 36.6 | 54.0 | 10 |
| Falcon-1024 | 91.7 | 85.8 | 18.4 | 74.0 | 119.1 | 10 |

**Analysis:**
- Signing is fast and scales approximately linearly with $n$ (doubling $n$ roughly doubles the signing time).
- The core of signing is the fast Fourier sampling (ffSampling) step, which has $O(n \log n)$ complexity.
- Falcon-512 signing at ~42 ms is practical for real-time applications.
- **Patent relevance:** In our threshold scheme, the signing overhead comes from (1) MPC-based secret sharing of the ffSampling tree and (2) Beaver triple consumption for multiplications. The baseline single-party signing time provides the comparison floor.

### 3.3 Verification

| Parameter | Mean (ms) | Median (ms) | Stdev (ms) | Min (ms) | Max (ms) | Iterations |
|-----------|-----------|-------------|------------|----------|----------|------------|
| Falcon-256 | 3.8 | 3.7 | 0.4 | 3.3 | 4.4 | 10 |
| Falcon-512 | 9.7 | 9.6 | 0.9 | 8.4 | 11.2 | 10 |
| Falcon-1024 | 20.8 | 19.5 | 2.8 | 18.2 | 26.1 | 10 |

**Analysis:**
- Verification is the fastest operation, roughly $4\text{--}5\times$ faster than signing.
- It involves only NTT-based polynomial multiplication and norm checking — no sampling.
- **Patent relevance:** In the threshold scheme, verification is identical to standard Falcon verification. The verifier does not need to know whether the signature was produced by a single party or via threshold signing. This transparency property is a key advantage of the proposed scheme.

## 4. Scaling Analysis

### 4.1 Time Scaling Ratios (relative to Falcon-256)

| Operation | Falcon-256 | Falcon-512 | Falcon-1024 |
|-----------|------------|------------|-------------|
| Keygen | 1.00× | 4.77× | 17.60× |
| Sign | 1.00× | 2.48× | 5.46× |
| Verify | 1.00× | 2.58× | 5.54× |

- Keygen scales super-linearly due to the NTRU equation solver.
- Sign and verify scale approximately as $O(n \log n)$, consistent with the FFT/NTT-based algorithms.

### 4.2 Size Scaling Ratios (relative to Falcon-256)

| Metric | Falcon-256 | Falcon-512 | Falcon-1024 |
|--------|------------|------------|-------------|
| SK | 1.00× | 2.00× | 4.00× |
| VK | 1.00× | 2.00× | 4.00× |
| Sig | 1.00× | 1.87× | 3.60× |

- Key sizes scale exactly $2\times$ per doubling of $n$ (expected: keys consist of degree-$n$ polynomials with fixed coefficient size).
- Signature sizes scale slightly sub-linearly due to the compression algorithm.

## 5. Comparison with Other Post-Quantum Signature Schemes

For context, we compare Falcon-512 (NIST-1 security) with other NIST-standardized schemes at the same security level. The table below combines our measured data with published reference values from the NIST PQC competition.

| Scheme | Security | VK (bytes) | Sig (bytes) | VK + Sig (bytes) |
|--------|----------|------------|-------------|------------------|
| **Falcon-512** (measured) | NIST-1 | **896** | **666** | **1,562** |
| Dilithium-2 (NIST reference) | NIST-1 | 1,312 | 2,420 | 3,732 |
| SPHINCS+-128f (NIST reference) | NIST-1 | 32 | 17,088 | 17,120 |

**Key insight:** Falcon has the smallest combined (VK + Sig) size among all NIST-standardized post-quantum signature schemes at NIST-1 security. This compactness is directly relevant to the patent: the threshold variant preserves these small signature sizes because the final signature is indistinguishable from a standard Falcon signature.

## 6. Implications for the Threshold Falcon Patent

The measured baseline performance of standard Falcon provides the foundation for evaluating our proposed QTS-Falcon threshold signature scheme:

### 6.1 Threshold Signing Overhead Estimation

In the (t, n)-threshold scheme:
- **Verification** remains identical — the verifier runs the same algorithm as standard Falcon verify ($\approx 10$ ms for Falcon-512).
- **Signing** requires $t$ parties to collaboratively execute ffSampling via MPC. The expected overhead factor is:
  - Communication rounds: $O(\log n)$ rounds for the tree-structured ffSampling
  - Per-round cost: dominated by Beaver triple consumption for secure multiplications
  - Estimated total: $3\text{--}5\times$ the single-party signing time (depending on network latency and $t$)
- **Key generation** (DKG) is performed once and can tolerate higher latency. The NTRU-based DKG adds polynomial secret-sharing overhead but is amortized over the system's lifetime.

### 6.2 Size Preservation

The threshold scheme produces standard Falcon signatures with **identical sizes** (666 bytes for Falcon-512). No additional metadata or multi-party artifacts are included in the final signature.

## 7. Raw Data Reference

All raw per-iteration timing data is available in:
- `results/raw_benchmark.csv` — 69 individual measurements (3 parameter sets × 23 operations each)
- `results/summary.json` — machine-readable aggregate statistics

These files were generated automatically by `benchmark_falcon.py` from actual algorithm execution on the date and platform specified above.

## 8. Reproducibility

To reproduce these results:

```bash
cd real_benchmarks/falcon_standard
pip install numpy pycryptodome beartype
python benchmark_falcon.py --kg 3 --sv 10 --params 256,512,1024
```

The benchmark script:
1. Imports from `falcon_impl/` (clone of [tprest/falcon.py](https://github.com/tprest/falcon.py))
2. Runs real `keygen()`, `sign()`, `verify()` calls
3. Checks that every signature passes verification (fails with `RuntimeError` if any verification fails)
4. Records every individual measurement with `time.perf_counter()`
5. Writes raw CSV and aggregate JSON without any post-processing or filtering
