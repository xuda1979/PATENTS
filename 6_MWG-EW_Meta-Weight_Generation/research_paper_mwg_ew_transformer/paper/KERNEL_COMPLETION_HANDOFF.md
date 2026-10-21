# Final handoff: the only remaining step to close the four-arm experiment

Status: the paper is fully review-compliant (verified). Arms 1-3 measured on NPU:
dense 0.467ms / persistent 0.286ms / materialized 0.931ms. The fused arm-4
Ascend-C kernel is the single remaining item, fully specified in
`REVIEW_COMPLIANCE_AUDIT.md` Addendum 8.

## What a human/inference-author must do (each step, in order)

1. Author ONE file: `custom_ops/ephemeral_core_apply/torch_ext/ephemeral_core_apply.asc`
   using the exact spec in Addendum 8 (CANN 8.5 Matmul template, GenerateTiling via
   matmul_tiling::MultiCoreMatmulTiling, host wrapper transposes head_weight to
   [R,H], computes tiling + workspace, launches `<<<1,nullptr,acl_stream>>>(...,
   tiling)`). Constraint note for implementor: the harness default is B=1,S=128
   => T=128, R=128, H=128. Any implementor should NOT trust that the current
   .asc exists -- it does not. Use only the spec.

2. Build: `cd /root/work/mwg_torch_ext && source .../bin/setenv.bash && cmake .. && make`
   (CMakeLists is already correct: ASC language, pinned real bisheng,
   `--cce-aicore-arch=dav-c220`, torch/torch_npu includes).

3. Hash + manifest: `python3 custom_ops/.../make_op_package_and_manifest.py
   --vendor-dir <opp vendors customize> --audited-source <kernel.asc> --out-dir <dir>`
   BUT for the eager .asc route the "binary" is libcustom_ops.so : set
   `binary_sha256` = sha256(libcustom_ops.so). (The manifest generator currently
   targets the opp-package; for the eager .so route either point vendor-dir at a
   packaged tree or set the binary hash directly.)

4. Run the decisive comparison:
   `python3 experiments/mwg_four_arm_lifetime_benchmark.py --arms materialized,fused
   --device npu:0 --d 512 --m 1408 --rank 128 --controller-hidden 128
   --fused-contract-manifest <contract.json> --op-library <libcustom_ops.so>
   --output results/four_arm_fused_run.json`
   Expect `validations.materialized_vs_fused.passed == true`.

5. msprof counters for arms 3 vs 4 (HBM/L2, kernel latency). Success criterion:
   fused core-region global writes ~0 and fused latency <= materialized.

## Inferred root cause of prior loop failures (for the implementor)
The folding author repeatedly corrupted C++ identifiers through the loop's
heredoc channel (e.g. `TILE_M = 64` -> `TILE_M = 64Atl`), confirmed by
byte-level readback. The spec and toolchain are nevertheless complete and
validated; only the single .asc file needs clean authoring by a corruption-free
path. Do not re-derive the toolchain.
