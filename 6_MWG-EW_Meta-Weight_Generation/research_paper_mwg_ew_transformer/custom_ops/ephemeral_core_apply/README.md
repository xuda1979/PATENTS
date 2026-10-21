# Ephemeral-core custom-op contract

The auditable Ascend-C kernel source for benchmark arm 4 now exists in this
directory (`ephemeral_core_apply_kernel.cpp`). **No compiled operator is
included yet** — the source must be audited and compiled on an NPU host with
the CANN/torch_npu toolchain, then hash-bound via the contract manifest.
Until a validated shared object exists, the benchmark harness fails closed
(`FUSED_BACKEND_UNAVAILABLE`) and arm 4 cannot run.

The operator registers:

```text
mwg::ephemeral_core_apply(
    rank_activation,      # [T, R] fp16
    controller_hidden,    # [T, H] fp32
    head_weight,          # [H, R] fp32 (host transposes to [R, H] for the kernel)
    head_bias,            # [R]    fp32
    amplitude             # scalar float
) -> scaled_rank_activation   # [T, R] fp16
```

For every token and rank channel it computes

```text
scaled_rank_activation = rank_activation
    * (1 + amplitude * tanh(controller_hidden @ head_weight + head_bias))
```

The generated diagonal core exists only as an Ascend-C `LocalTensor` in
UB/scratch: it is formed in place in the C tile buffer and multiplied into the
activation tile; it is never declared as a `GlobalTensor` and never copied to
global memory. The operator has one global output, zero global workspace, and
no core `GlobalTensor` or core-to-global `DataCopy` — see the source audit
fields in `contract.example.json`.

## v1 kernel constraints

- `hiddenDim` must equal 128 (fixed `TILE_K`); `16 <= rankDim <= 128` with
  `rankDim % 16 == 0` (no N tiling in v1); any `tokenCount >= 1` (M tiling
  handles tails).
- Controller tensors are fp32; activation/output are fp16; all GM tensors are
  contiguous with 32-byte-aligned base addresses (guaranteed by the harness).
- `head_weight` is transposed to `[R, H]` by the host wrapper before launch.
- UB budget at the maximum v1 shape is ~153 KiB < 192 KiB.

The harness defaults (`rank=128`, `controller-hidden=128`) satisfy these
constraints, which is sufficient for the decisive arm-3-vs-arm-4 comparison at
the paper's headline rank. N tiling for `rankDim > 128` is documented as v2
work.

## Build and registration (on an NPU host with CANN + torch_npu)

1. Compile the kernel with the Ascend C compiler (`ccec`) into a shared object,
   e.g. via the official custom-op sample `build.sh`:

   ```bash
   cd <custom_op_template_dir>   # sample: pytorch custom op template
   ./build.sh --kernel ephemeral_core_apply_kernel.cpp \
              --output libmwg_ephemeral_core_apply.so
   ```

2. Register the operator under `mwg::ephemeral_core_apply` so that
   `torch.ops.load_library(...)` exposes it. The registration stub (adapt to
   the installed torch_npu version and the template's `OpCommand`/`EXEC_NPU_CMD`
   infra) is:

   ```cpp
   // op_host stub (template-dependent; adapt macros to the installed version)
   #include <torch/torch.h>

   torch::Tensor ephemeral_core_apply(torch::Tensor rank_activation,
                                      torch::Tensor controller_hidden,
                                      torch::Tensor head_weight,
                                      torch::Tensor head_bias,
                                      double amplitude) {
     TORCH_CHECK(rank_activation.dim() == 2 && controller_hidden.dim() == 2,
                 "expected [T, R] and [T, H]");
     TORCH_CHECK(controller_hidden.size(1) == 128, "v1: H must equal 128");
     int64_t rank = rank_activation.size(1);
     TORCH_CHECK(rank >= 16 && rank <= 128 && rank % 16 == 0,
                 "v1: R in {16..128}, R % 16 == 0");
     auto output = at::empty_like(rank_activation);           // the one global output
     auto weight_t = head_weight.t().contiguous();            // [R, H] for the kernel
     uint32_t t = rank_activation.size(0), h = controller_hidden.size(1), r = rank;
     // ... dispatch kernel with (rank_activation, controller_hidden,
     //     weight_t, head_bias, output, amplitude, t, h, r) ...
     return output;
   }

   TORCH_LIBRARY(mwg, m) {
     m.def("ephemeral_core_apply(Tensor rank_activation, Tensor controller_hidden, "
           "Tensor head_weight, Tensor head_bias, float amplitude) -> Tensor");
   }
   TORCH_LIBRARY_IMPL(mwg, PrivateUse1, m) {
     m.impl("ephemeral_core_apply", &ephemeral_core_apply);
   }
   ```

3. Fill the contract manifest:

   ```bash
   cp contract.example.json ephemeral_core_apply.contract.json
   # set audited_source_path = ephemeral_core_apply_kernel.cpp
   # set audited_source_sha256 = sha256sum of the audited source
   # set binary_sha256        = sha256sum of the compiled shared object
   ```

4. Run the decisive comparison on the NPU (arm 4 fails closed until the
   manifest and library validate):

   ```bash
   python experiments/mwg_four_arm_lifetime_benchmark.py \
       --arms materialized,fused --device npu:0 \
       --d 4096 --m 14336 --rank 128 --controller-hidden 128 \
       --batch 2 --seq 512 --dtype fp16 \
       --fused-contract-manifest custom_ops/ephemeral_core_apply/ephemeral_core_apply.contract.json \
       --op-library custom_ops/ephemeral_core_apply/libmwg_ephemeral_core_apply.so \
       --output results/four_arm_fused_run.json
   ```

5. Collect physical counters for the same two arms (mandatory; static
   validation is not HBM evidence):

   ```bash
   msprof --output=mwg_prof --application="python experiments/... --arms materialized"
   msprof --output=mwg_prof --application="python experiments/... --arms fused"
   ```

   Required per arm: HBM read/write bytes, L2 traffic, core-region stores,
   kernel latency, achieved FLOP/s, occupancy, energy, peak temporary memory.
   The paper's success criterion: arm 4's core-region global writes are zero
   (or within instrumentation noise) and arm 4 latency is no worse than arm 3.

## Audit checklist before the run is evidence

- [ ] Kernel source reviewed for the four `source_audit` properties.
- [ ] Manifest hashes match the audited source and the compiled binary.
- [ ] `mwg::ephemeral_core_apply` resolves after `torch.ops.load_library`.
- [ ] Materialized-vs-fused algebraic equivalence passes in the harness output
      (`validations.materialized_vs_fused.passed == true`).
- [ ] Matched arm-3/arm-4 `msprof` counters recorded and reported.

Static validation alone is not HBM evidence; matched arm-3/arm-4 `msprof`
counters remain mandatory.
