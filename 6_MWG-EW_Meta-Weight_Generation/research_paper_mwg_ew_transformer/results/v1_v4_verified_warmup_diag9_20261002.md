# v1+v4 Verified Warmup Fix — diag9 First-Call Postmortem — 2026-10-02

## Summary

diag9 (fixed-pair validation of the 2026-10-02 root-cause fixes) exposed
a residual first-call defect the blind settle launches could not cover:
v1's **first 3 settle launches ALL returned tanh-saturated garbage**
(err 0.15286 on the returned output), while v4 — invoked after v1 in
the same process — passed everywhere. The bad-launch streak is
**runtime-global and variable** (diag6: 2 consecutive bad launches;
diag8: 1; diag9: 3), so a fixed settle count is guesswork. Both host
wrappers now perform a **verified warmup**: on the first call per
thread, launch the real kernel on a fixed deterministic 128x128x128
probe, compare against the analytic expectation, retry up to 16x, and
raise `TORCH_CHECK` if the path never converges. The decisive rerun of
diag9 passes **OVERALL_PASS** with every section green.

## diag9 first run (before this fix)

| Section | v1 | v4 |
|---|---|---|
| S1 first call | **FAIL err 0.15286** | pass |
| S1 repeat | pass | pass |
| S2 weight-recycling (`recycled_addr: true`) | pass | pass |
| S3 T-sweep 64..2048 | pass | pass |
| S4 multicore T=1024 | — | pass |
| S5 5x repeat | pass | pass |

The err 0.15286 signature equals `2*amp*max|act|` (2 x 0.05 x ~1.53) —
the matmul accumulator serving uninitialized/zeros, i.e. the
KFC-lazy-init path, not the weight cache (S2 recycles addresses and
passes with the same build).

## Fix: verified warmup (both wrappers)

On the first call per thread (`g_settle_done == 0` / `g_v4_settle_done == 0`):

1. Build a deterministic probe: `act=1.0` (fp16), `ctrl=0.25` (fp16),
   `W=0.5` (fp16), `bias=0` (fp32), `amp=0.05`, geometry 128x128x128.
2. Generate a matching warmup tiling (`GenerateTiling(..., 128, 128,
   128, block_dim=1)`) — NOT the cached per-call tiling, whose (t,h,r)
   need not match the probe geometry.
3. Launch `<<<1u>>>`, `aclrtSynchronizeStream`, copy back, compare
   against `tanh(0.25*128*0.5)*0.05 + 1` with tolerance 5e-3.
4. Retry up to 16 attempts; `TORCH_CHECK(false)` if never converged
   (fail loudly rather than return wrong-finite output).
5. Then perform the real launch as before.

The v4 warmup mirrors v1 with `GenerateTilingV4` (per-core partition
arithmetic consistent with `block_dim=1`).

## diag9 decisive rerun (after the fix)

- v1 `libcustom_ops.so` md5 `e7c377c6f4f6f8202fc983e9d732c72d`
- v4 `libcustom_ops_v4.so` md5 `1659bbe61f85e10d88f240a89843f036`
- v1 source `ephemeral_core_apply.asc` md5 `59cf1751d920f5f90851b117f7483d6c`
- v4 source `ephemeral_core_apply_v4_multicore.asc` md5 `701e9be098b51b13ac89409384735e2d`

Result: **OVERALL_PASS** — S1 (first call + repeat, both ops), S2
(weight recycling, `recycled_addr: true`), S3 (T = 64, 128, 192, 256,
512, 2048), S4 (v4 multicore T=1024, 8 cores), S5 (5x repeat) all
green; max err 0.0016 (fp16 noise), zero NaN/Inf. Canonical result:
`results/diag9_fixed_pair_validation.json`; remote copy at
`/root/work/filestorage/mwg-ew-transformer-research/results/diag9_fixed_pair_validation.json`.

## Combined 2026-10-02 fix set (v1 + v4, cumulative)

1. **Pointer-keyed fp16 weight cache removed** (diag7 S3/S4 root cause):
   per-call `.to(kHalf)` cast of controller_hidden and head_weight.
2. **Workspace zeroed** via `aclrtMemset` after `aclrtMalloc` (dirty
   allocation poisoning the KFC handshake; diag6/diag8).
3. **Verified first-call warmup** (this session): deterministic probe +
   analytic check + bounded retry + loud failure; replaces the blind
   3-launch settle that diag9 proved insufficient.

## Deployment state (ASI3)

- `/root/work/mwg_torch_ext/ephemeral_core_apply.asc` — updated, md5
  `59cf1751d920f5f90851b117f7483d6c` (verified via chunked upload).
- `/root/work/mwg_v4_torch_ext/ephemeral_core_apply_v4_multicore.asc` —
  updated, md5 `701e9be098b51b13ac89409384735e2d` (verified).
- Both `.so` rebuilt at the fixed sources; diag9 rerun from a clean
  python process passed.

## Caveats

- The warmup probe occupies the first call's latency with up to 16
  launches + D2H checks; observed cost is 1-3 extra launches (the path
  converges quickly once CANN's KFC/aicore init completes).
- If the probe ever fails all 16 attempts, the op raises instead of
  returning corrupt output; callers see a Python `RuntimeError`.
- `g_settle_done` is thread-local; multi-threaded eager callers warm
  once per calling thread.
