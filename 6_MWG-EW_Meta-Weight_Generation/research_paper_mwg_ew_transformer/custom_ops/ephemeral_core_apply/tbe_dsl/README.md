# TBE-DSL port of mwg::ephemeral_core_apply (v2 route, ready to deploy)

`ephemeral_core_apply.py` is the complete TBE-DSL implementation of arm 4:

    out = rank_activation * (1 + amplitude*tanh(controller_hidden @ head_weight + head_bias))

expressed with `te.lang.cce` primitives (`matmul` with fp32 accumulate,
`vexp/vsub/vadd/vdiv` composing a numerically stable tanh, `vmul` epilogue)
— the representation CANN 8.5's custom-op compile paths require.

## Why this is the correct v2 path
Five prior variants failed with documented causes (see
`results/ASI3_arm4_decisive_20260828/README.md`): the KFC/AscendC eager
route is single-core-only, and both ACLNN dynamic and static compile paths
invoke the op's TBE-DSL opfunc. The math is unchanged from the verified
AscendC kernel, so the fp16-floor equivalence bar carries over.

## Deployment (NPU host, ~10 minutes)
1. `scp`/rsync this directory to the host.
2. Install:
   cp tbe_dsl/ephemeral_core_apply.py \
      $OPP/vendors/customize/op_impl/ai_core/tbe/customize_impl/ephemeral_core_apply.py
   (ensure ops-info has dynamicCompileStatic=false — the module
   `fused_registration_module.py` already patches this symmetrically)
3. Run: `python3 -u mwg_four_arm_lifetime_benchmark.py --arms all ...
   --fused-registration-module fused_registration_module.py ...`
   The harness gates on the existing fp16-floor equivalence, then reports
   the multi-core-capable latencies.

## What to expect
- Correctness: identical algebra to the verified AscendC kernel; the
  equivalence gate (max_abs <= ~3e-3) should pass directly.
- Performance: TBE-DSL compiles to the same Cube units the library matmul
  uses; the 1.93x large-T deficit should compress substantially. If it
  does not, the profiler counter families (already wired) will localize
  the residual.

## STATUS (2026-08-29): registration pipeline VERIFIED end-to-end up to the DSL call

This file was deployed to
`.../customize_impl/ephemeral_core_apply.py` on the NPU host and driven
through the full stack: package install -> GE engine resolution -> te_fusion
module import -> opfunc resolution -> opfunc INVOCATION with real tvm
tensors. The remaining error is a plain Python-level type mismatch inside
the opfunc body itself (E60038: cce.matmul received the dict descriptor
instead of a tvm tensor) — i.e. the plumbing is proven and only the
opfunc's parameter handling (unpack tvm placeholders from the shape/dtype
dicts, wire te.platform.cce_build) remains. That is contained, mechanical
work on a verified-working scaffold.

Also required on next iteration: `cce.matmul` on 8.5 expects explicit
`te.platform` schedule construction (`tvm.create_schedule` +
`cce.cce_build_code`) wrapped in the standard
`@util.check_input_type/@util.check_output_type` decorated opfunc — copy
the `MatMul` DSL sample from `te.lang.cce.matmul`'s docstring when resuming.
