# Analytical Simulation Plan and Results
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

## Scope Note

All numerical results in this file are produced by the analytical simulation script
`simulation/mwg_ew_simulation.py`.

These numbers are intended to:

1. make the patent effects reproducible from explicit assumptions,
2. show the expected operating region before silicon benchmarking, and
3. provide a consistent source for the disclosure and technical specification.

Unless a future appendix explicitly marks a row as **measured**, no table below should
be described as hardware benchmark evidence.

---

## 1. Simulation Objectives

The simulation is designed to answer six questions that matter directly for the patent:

1. how much external-memory traffic can be removed from a target FFN block;
2. how the rank choice changes the latency-quality frontier;
3. how partial versus full FFN replacement changes end-to-end benefit;
4. whether the released memory can be converted into larger KV-cache context;
5. how grouped-token descriptor reuse affects efficiency and quality drift; and
6. how much distributed-training synchronization volume can be eliminated.

---

## 2. Simulation Model

### 2.1 Effective Read Model

For a dense projection with fp16 weights:

`Traffic_dense = 2 d m`

For an MWG-EW low-rank block with rank `r`:

`Traffic_factor = 2 (d r + r m)`

The simulation does not stop at the raw low-rank footprint. It converts this into an
effective external-memory read:

`Traffic_effective = alpha * Traffic_factor + P_G / W`

where:

1. `alpha` is the descriptor compaction factor;
2. `P_G` is the amortized generator-transfer term; and
3. `W` is the grouped-token reuse window.

For the patent-grade basis-bank path, the script uses `alpha = 0.72`.

### 2.2 End-to-End Latency Model

The end-to-end latency is modeled as a fixed non-target share plus a target-block share:

`Latency_total = L_fixed + L_target`

`L_target = rho * [(1 - p) * 1 + p * C_path]`

where:

1. `p` is the FFN replacement ratio;
2. `rho` is the target-block share of the baseline runtime; and
3. `C_path` mixes memory pressure and extra local compute for generation and fused execution.

This keeps the model conservative: unchanged layers, attention, framework overhead, and
 non-target work still dominate a substantial fraction of total latency.

### 2.3 Peak Memory and Context Model

Peak model memory is estimated by removing the dense FFN resident share and replacing it
with the compact MWG-EW resident share:

`Peak_MWG = Peak_dense - M_target * (1 - Traffic_effective / Traffic_dense)`

The released HBM is then mapped to additional KV-cache capacity under a fixed 80 GiB card
budget with a `0.75 MiB/token` KV-cache cost.

### 2.4 Distributed-Training Communication Model

Dense baseline synchronization is modeled as:

`AllReduce_dense = Sync_non_target + Sync_target_dense`

After MWG-EW replacement:

`AllReduce_mwg = Sync_non_target + (1 - p) * Sync_target_dense + p * Sync_generator`

In the patent-grade setup, the dense baseline is `1024 MiB/step`, the non-target traffic
is `96 MiB/step`, and full FFN replacement leaves only `96 MiB/step` of generator-side
synchronization for the target path.

---

## 3. Workload Profiles and Assumptions

| Profile | Dimensions | Descriptor Path | Dense Baseline | Main Use |
| --- | --- | --- | --- | --- |
| 1B pilot | `d=2048`, `m=5632`, one projection | Direct low-rank factors | `2.8 ms`, `357 tokens/s`, ppl `8.2` | Fast kernel correctness and single-projection tuning |
| 8B patent-grade | `d=4096`, `m=14336`, three FFN projections | Basis-bank coefficients | `4.2 s`, `290 tokens/s`, val loss `2.14` | Disclosure-grade tradeoff study |

Common assumptions:

1. fp16 target blocks;
2. patent-grade dense gated-FFN footprint of `336.0 MiB` per block;
3. 80 GiB device memory budget for context-capacity calculations;
4. grouped-token reuse windows of `1`, `2`, `4`, and `8`; and
5. HBM sensitivity evaluated at `1.6`, `2.4`, and `3.2 TB/s`.

---

## 4. 1B Pilot Single-Projection Sweep

This sweep is mainly for kernel bring-up. It shows that even a direct-factor path without
the basis-bank compaction already moves the workload out of the dense memory regime.

| Rank | Effective Read (MiB/token) | Latency (ms) | Tokens/s | Perplexity | Loss Increase |
| --- | --- | --- | --- | --- | --- |
| Dense | 22.0 | 2.80 | 357.00 | 8.20 | 0.00% |
| 32 | 0.59 | 1.32 | 758.02 | 8.89 | 8.47% |
| 64 | 1.09 | 1.37 | 727.85 | 8.57 | 4.49% |
| 96 | 1.60 | 1.43 | 700.00 | 8.42 | 2.63% |
| 128 | 2.11 | 1.48 | 674.19 | 8.34 | 1.76% |

Interpretation:

1. the pilot path already cuts effective reads by `10.4x` to `37.3x`;
2. the best quality-efficiency knee appears around `r=64` to `r=96`; and
3. this pilot is suitable for validating fused generation-consume-release logic before
   scaling to the three-projection patent-grade scenario.

---

## 5. 8B Full-Replacement Rank Sweep

This is the main patent-grade frontier for the three-projection gated FFN block.

| Rank | Effective Read (MiB/block) | Batch Latency (s) | Tokens/s | Tensor Utilization | Validation Loss | Loss Increase |
| --- | --- | --- | --- | --- | --- | --- |
| Dense | 336.0 | 4.20 | 290.00 | 68.00% | 2.14 | 0.00% |
| 32 | 3.41 | 2.15 | 567.29 | 83.81% | 2.42 | 13.10% |
| 64 | 5.97 | 2.19 | 556.55 | 83.09% | 2.30 | 7.62% |
| 96 | 8.52 | 2.23 | 546.20 | 82.64% | 2.24 | 4.73% |
| 128 | 11.08 | 2.27 | 536.23 | 82.34% | 2.21 | 3.20% |
| 160 | 13.64 | 2.31 | 526.62 | 82.13% | 2.19 | 2.40% |
| 256 | 21.31 | 2.44 | 499.75 | 81.74% | 2.17 | 1.63% |

Interpretation:

1. the dense `336 MiB` block is reduced to `11.08 MiB` effective read at `r=128`,
   corresponding to about `30.3x` less target-block traffic;
2. the latency curve stays relatively flat from `r=32` to `r=160`, because the dense
   baseline is memory-bound and the MWG-EW path remains compute-favorable across that range;
3. `r=96` to `r=128` is the best compromise for the disclosure: it keeps the loss increase
   below `5%` while preserving about `1.85x` end-to-end speedup; and
4. tensor-core utilization rises from `68%` to more than `82%`, which matches the patent
   thesis that the target path shifts from external-memory pressure toward on-chip compute.

---

## 6. Replacement Ratio, Memory, and Context Sweep

The previous table describes full replacement. The patent, however, should also cover
partial deployment, because that is how most engineering teams will stage the rollout.

| Replacement Ratio | Effective Read (MiB/block) | Batch Latency (s) | Peak Memory (GiB) | Max Context (tokens) | Validation Loss | All-Reduce (MiB/step) | Comm Time (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0% | 336.0 | 4.20 | 68.00 | 16384 | 2.14 | 1024.0 | 340.00 |
| 25% | 11.08 | 3.72 | 61.71 | 24965 | 2.16 | 816.0 | 270.94 |
| 50% | 11.08 | 3.24 | 55.43 | 33547 | 2.18 | 608.0 | 201.88 |
| 75% | 11.08 | 2.75 | 49.14 | 42129 | 2.19 | 400.0 | 132.81 |
| 100% | 11.08 | 2.27 | 42.86 | 50711 | 2.21 | 192.0 | 63.75 |

Interpretation:

1. even `50%` FFN replacement already reduces end-to-end batch latency from `4.20 s` to
   `3.24 s` while increasing the maximum context from `16.4k` to `33.5k` tokens;
2. full replacement lowers peak model memory from `68.0 GiB` to `42.86 GiB`, freeing
   enough space to expand the KV-cache budget to about `50.7k` tokens under the same card;
3. the communication benefit scales with the replaced share and reaches `1024 -> 192 MiB`
   per step at full replacement, which is about a `5.3x` reduction; and
4. this table is the cleanest source for the disclosure because it ties latency, memory,
   context, and communication to the same replacement-ratio parameter.

---

## 7. Token-Group Reuse Sweep

Grouped-token reuse is optional, but it is useful to show that the invention can trade a
small amount of approximation drift for further efficiency once descriptor generation is
already stable.

| Reuse Window | Effective Read (MiB/block) | Batch Latency (s) | Tokens/s | Extra Loss Drift |
| --- | --- | --- | --- | --- |
| 1 | 11.08 | 2.27 | 536.23 | 0.0% |
| 2 | 10.40 | 2.23 | 547.31 | 0.2% |
| 4 | 10.06 | 2.20 | 553.03 | 0.6% |
| 8 | 9.89 | 2.19 | 555.93 | 1.5% |

Interpretation:

1. a reuse window of `2` or `4` provides a clean engineering sweet spot;
2. the latency gain from reuse is incremental rather than dramatic, which means the
   primary patent effect still comes from eliminating dense weight movement; and
3. the disclosure can safely describe bounded-window reuse as an optional enhancement
   instead of a mandatory precondition.

---

## 8. Hardware Sensitivity

The script also sweeps memory bandwidth to show that the benefit persists across different
hardware tiers, with the largest speedup appearing on the most memory-constrained devices.

| HBM Bandwidth (TB/s) | Dense Latency (s) | MWG-EW Latency (s) | Dense Tokens/s | MWG-EW Tokens/s | Speedup |
| --- | --- | --- | --- | --- | --- |
| 1.6 | 5.36 | 2.81 | 227.45 | 433.06 | 1.90x |
| 2.4 | 4.20 | 2.27 | 290.00 | 536.23 | 1.85x |
| 3.2 | 3.62 | 2.02 | 336.23 | 604.29 | 1.80x |

Interpretation:

1. the benefit is robust across the tested bandwidth range;
2. lower-bandwidth accelerators see the strongest relative gain, which is consistent with
   the patent's memory-bound motivation; and
3. even when bandwidth improves to `3.2 TB/s`, the simulated speedup remains about `1.8x`
   because the target FFN block is still much smaller than its dense counterpart.

---

## 9. Patent Evidence Mapping

The simulation directly supports the patent narrative in five ways:

1. **No dense external-memory object is required**: the effective-read model is built from
   descriptor traffic plus generator amortization, not from persistent dense weights.
2. **The object lifecycle has measurable system impact**: the same change that removes
   dense block traffic also reduces peak memory and All-Reduce volume.
3. **The decode benefit is visible**: released memory translates into a larger KV-cache
   budget and longer supported contexts under a fixed card budget.
4. **The training benefit is visible**: target-layer synchronization volume falls as the
   replacement ratio increases.
5. **The benefit is not tied to one hardware tier**: the bandwidth sensitivity table shows
   that the effect survives across multiple HBM regimes.

---

## 10. Recommended Empirical Next Steps

The simulation is now strong enough to guide real measurement. The next steps should be:

1. implement the single-projection direct-factor kernel and validate it against the 1B
   pilot table;
2. build the three-projection basis-bank fused kernel for `r=96` and `r=128`;
3. capture Nsight traces that prove zero descriptor write-back for the target block;
4. measure dense versus MWG-EW HBM bytes to anchor the effective-read model in hardware;
5. run the `50%` and `100%` replacement cases first, because those are the cleanest rows
   for the disclosure and the strongest patent evidence; and
6. measure distributed-training communication to confirm the `1024 -> 192 MiB/step`
   synchronization collapse predicted by the simulation.

---

## 11. Acceptance Thresholds

Based on the simulation, the project should use the following thresholds:

### Minimum engineering threshold

1. target-block traffic reduction `>= 10x`;
2. zero descriptor write-back in the fused path;
3. end-to-end speedup `>= 1.3x` for `50%` replacement or better;
4. at least `2x` context-capacity gain for full replacement; and
5. synchronization reduction `>= 3x` for the full target path.

### Strong patent-support threshold

1. target-block traffic reduction `>= 25x`;
2. end-to-end speedup around `1.8x` or better on bandwidth-limited hardware;
3. peak-memory reduction `>= 20 GiB` under the patent-grade setup;
4. context-capacity gain `>= 3x` under the same device budget; and
5. synchronization reduction `>= 5x` for the target path.

Under the current script-backed assumptions, the `r=128`, `100%` replacement configuration
meets all five strong-threshold conditions.
