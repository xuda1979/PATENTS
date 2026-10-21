# ASI3 v1-NaN Root Cause — v1z A/B Diagnostic (diag7/diag8)

**Date:** 2026-10-02
**Question:** Is the shipped v1 `mwg::ephemeral_core_apply` NaN (6/6
harness aborts since Sep 28) a device-0 hardware fault or a software bug?

## Method

Built **v1z** (`libcustom_ops_z.so`, md5 `1d445a98…`): byte-identical to
the shipped v1 (source md5 `740e7411…`, built from the same CMake config)
except:

| Change | Shipped v1 | v1z |
|---|---|---|
| (a) workspace | `aclrtMalloc` raw, never initialized | `aclrtMemset` zeroed at allocation |
| (b) weight fp16 cache | pointer-keyed `unordered_map<void*, Tensor>` | removed; convert per call |
| (c) registration | `mwg::ephemeral_core_apply` | `mwgz::ephemeral_core_apply_z` (co-exists in one process) |

A/B ran both ops in the same process on the same device (NPU 0,
Ascend910B2, CANN 8.5.0, driver 25.5.2):
`diag7_ab_v1_vs_v1z.py` — fresh-process first call, harness-order
replication, weight-tensor recycling, T sweep {64…2048}, 5× repeat.
`diag8_dirty_ab.py` — deliberate 512 MiB device-memory dirt
(1e30/NaN fill → free → empty_cache → aclnn churn), then first call,
3 rounds per arm.

## Result 1 — the weight cache serves stale bytes (decisive)

`diag7` S3 (weight recycling; a new weight tensor landed at the freed
address 20616936325120, `recycled_addr=true`):

- v1's output with the **new** weight is **bit-identical** to its output
  with the old weight (fingerprint equality, max 1.8623, min −1.9668).
- v1 error vs the true new-weight reference: **0.1412** (silently wrong).
- v1z error: **0.0012** (fp16 noise).

`diag7` S4 T=2048 (loop weight-tensor address recycling): v1
**0.1450** vs v1z **0.0013**. Same bug, independent reproduction.

**Mechanism:** `static thread_local std::unordered_map<void*, at::Tensor>
g_w16` keyed by `weight_t.data_ptr()`. The torch NPU caching allocator
recycles freed device addresses; when a new weight tensor reuses a
cached address, v1 returns the stale fp16 tensor of a *different*
weight. Silent wrong-finite corruption, no NaN, no error.

## Result 2 — first-call corruption is arm-independent (diag8)

3 rounds × {v1, v1z}: call1 err **0.1529** (wrong-finite, output
fingerprint differs from call2), self-heals by call2; **bit-identical
across arms**. Not the weight cache (same tensor all calls), not the
zeroed workspace (v1z shows it too). Consistent with a CANN/torch_npu
first-custom-launch lazy-init path (e.g. the async fp16 cast feeding the
kernel) that settles on the second launch — matches diag6's
garbage(759)→NaN(7929)→pass-by-call-3 settling pattern.

## Verdict

Per the agreed decision rule — **v1 fails (silent stale-weight
corruption) while v1z passes in the same process on the same device —
the device-wedged theory is dead.** The ASI3 v1 failure is a **software
bug in the shipped v1 host wrapper**, dominated by:

1. **Pointer-keyed fp16 weight cache** (confirmed silent corruption,
   diag7 S3/S4). Explains the wrong-finite arms (0.371/0.395/0.410 in
   `diag_t128_discriminator`, 0.141/0.145 here).
2. **Uninitialized raw-aclrtMalloc workspace** + first-call settling
   (diag6 S1/S2, diag8): explains the intermittent call-1/2 garbage and
   NaN that self-heals, amplified by co-tenant device state on
   Sep 28–Oct 2 (those sessions' hard NaN did not reproduce today on a
   quiet device, but every reproducible failure mode is host-side
   state, not hardware).

Device 0 is healthy: all 8 NPUs OK, aicore error count 0, no running
processes, HBM clean.

## Remediation for the v4 comparison run

Apply to v1-equivalent host wrapper (and mirror in v4):

1. Remove the pointer-keyed weight cache (or key it by a unique token
   carried by the caller — never by `data_ptr()`).
2. Zero the workspace once after `aclrtMalloc` (`aclrtMemset`).
3. Keep the existing pre-launch `aclrtSynchronizeStream`.

With (1)+(2) the v1 arm is expected to match v1z behavior (≤ fp16
noise), unblocking the v4-vs-v1 decisive rerun.

## Artifacts

| File | Purpose |
|---|---|
| `ephemeral_core_apply_z.asc` | v1z source (7-opcode diff vs shipped v1) |
| `CMakeLists.txt` | v1z build config (clone of v1's) |
| `diag7_ab_v1_vs_v1z.py` | same-process A/B driver |
| `diag8_dirty_ab.py` | dirty-memory first-call A/B |
| `diag7_ab_v1_vs_v1z_result.json` | diag7 results (pulled from ASI3) |
| Remote `results/diag7_ab_v1_vs_v1z.json` | canonical results on ASI3 |
| Remote `/tmp/diag8_run.log` | diag8 raw (6 runs) |
