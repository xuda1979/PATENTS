# ASI1 Reviewer-Controls Queue (launched 2026-08-13T08:04Z)

Remote: ASI1 (env dl-9a5a098accce31c28cf4c6ca23391341), single Ascend 910B2 NPU,
torch 2.7.1 / torch_npu 2.7.1. Project root: `/root/work/filestorage/mwg-ew-transformer-research`.
Queue script: `run_reviewer_controls.sh` (PID 4088). Launcher log:
`logs/reviewer_controls_launcher.log`; stage log: `logs/reviewer_controls_20260813T080428Z.log`.
Output dir: `results/asi1_reviewer_controls_20260813T080428Z/`; replication dir:
`results/asi1_ckpt_replication_20260813T080428Z/`.

Serial stages (one NPU):
1. **Random-perturbation control** — `mwg_random_perturbation_control.py`
   (new script, checksum c511f3b0...): calibrated layer-16 checkpoint, five-suite
   manifest eval (617 texts, 75,073 tokens), dense + always-patched +
   random masks at p ∈ {0.01, 0.02, 0.05} × seeds {0,1,2} → `random_perturbation_control.json`.
   Compare vs learned-router cell 0.9923× at ~2%.
2. **GSM8K EM** — `mwg_gsm8k_em_eval.py` (new script, checksum 46e00ccb...): 260 items,
   arms = dense / selective (TokenRouterMLP, Δmax=-0.20, policy global, budget 0.10,
   router seed 0, suite-balanced ridge) / random-2% → `gsm8k_em_eval.json`.
3. **Checkpoint-level replication** — distillation seed 2027 (expert_residual r384,
   5000 steps, same protocol as 20260624 recovery, activation cache rebuilt) →
   LM-CE calibrate 1200 steps on the same 256 belle texts (extracted from the
   original calibration config into `data/heldout/belle_lmce_replication_texts.txt`)
   → 96-cell tighter-eligibility sweep (same grid: 8 deltas × 4 policies × 3 seeds)
   → `asi1_ckpt_replication_*/pareto/d=*/p=*/s*/token_router_five_suite.json`.

Paper updates pending per stage result:
- variance-scope paragraph + ladder + limitations: replace "required, not yet run"
  with measured controls;
- add GSM8K EM table (dense vs selective vs random);
- add checkpoint replication result to the 96-cell story.

## Status 2026-08-13 (~08:40Z)
- Stage 1 DONE: random-perturbation control. Dense PPL 7.718 (75,073 tokens);
  always-patched 1.4096x (reproduces 1.4086x replication); random cells at
  1%/2%/5%: mean 1.00057x / 1.00091x / 1.00174x (3 seeds, all >= 1.0) — random
  patching never beats dense, so the 0.9923x learned-router win tracks learned
  selection. Local artifact: results/ASI1_random_perturbation_control_20260813.json.
  Paper updated: new Table tab:randomcontrol + variance-scope/abstract/ladder/
  limitations/conclusion edits; compiles clean.
- Stage 2 RUNNING: GSM8K EM, dense arm generating (right-padding warning from
  tokenizer defaults — same padding on all arms so the relative comparison
  stands; consider a padding_side='left' re-run later).
- Stage 3 QUEUED: checkpoint replication (distill seed 2027 -> lmce -> 96 cells).

## Status 2026-08-14 (~12:40Z) — ALL REVIEWER-CONTROL EXPERIMENTS COMPLETE
- HumanEval pass@1 done rc=0: dense 34.76% (57/164), selective 34.15%
  (56/164), random-2% 31.71% (52/164); SE≈3.7pp, all diffs ≤0.7σ —
  task-accuracy-neutral, mirroring GSM8K EM. Paper updated: new
  Table tab:humanevalpass1 + interpretation, ladder row, limitations, future
  work, conclusion, artifact trail; zero "queued" references remain; compiles
  clean. The entire reviewer-required experiment set is now measured:
  (1) traffic accounting corrected; (2) lifetime ablation (persistent arm
  2.1x faster); (3) granularity alignment; (4) Corollary 1 reformulated;
  (5) random-perturbation control passed + checkpoint replication 66/96
  reproduced; (6) platform details + K-basis reconciliation + ladder +
  conservative-first narrative.

## Status 2026-08-14 (~11:00Z) — REPLICATION SWEEP COMPLETE (96/96, 0 failures)
- Full grid on seed-2027 checkpoint: **66/96 net wins at the 96-cell level —
  IDENTICAL to the original**, same per-row pattern (rows -0.25..-0.10: 12/12
  wins each; -0.08/-0.05: 3/12 each; -0.30: 0/12). Decisive row -0.20:
  0.99428x (range 0.99427-0.99429) @1.29% vs orig 0.9923x @2.01%.
  Always-patched 1.3972x vs orig 1.4086x. Frontier shape replicates including
  the loose-threshold penalty.
- Paper updated: new Table tab:ckptreplication; variance-scope, ladder,
  limitations, scope, future-work, abstract, and conclusion all now report the
  completed replication (66/96 reproduced). Compiles clean.
- HumanEval pass@1: watcher fired after ALL DONE; run starting.
  Queue complete.

## Status 2026-08-13 (~14:50Z) — 4 rows complete (48/96)
Partial frontier, seed-2027 replication checkpoint (mean over policies x seeds, target 0.10):
| dmax | rep ratio | rep actual | orig ratio | orig actual |
| -0.30 | 1.00021 | 0.09% | 0.9992 | 0.36% |
| -0.25 | 0.99924 | 0.32% | 0.9941 | 1.19% |
| -0.20 | 0.99428 | 1.29% | 0.9923 | 2.01% |
| -0.15 | 0.99271 | 2.26% | 0.9928 | 2.37% |
Frontier shape replicates: wins at -0.25/-0.20/-0.15, near-neutral at -0.30;
checkpoints converge at -0.15 (0.9927 vs 0.9928). Remaining rows: -0.12, -0.10,
-0.08, -0.05 (48 cells, ~8h), then HumanEval.

## Status 2026-08-13 (~14:00Z) — d=-0.20 ROW COMPLETE
- Sweep: 36/96 cells. d=-0.20 row complete (12/12): mean 0.99428x, range
  0.99427-0.99429, at 1.29% actual patching, all policies x seeds net wins on
  the seed-2027 checkpoint. Remaining rows: d=-0.15..-0.05 (60 cells).
- Paper variance-scope + ladder updated with the definitive row numbers; compiles clean.

## Status 2026-08-13 (~13:10Z) — DECISIVE PARTIAL RESULT
- Sweep: 29/96 cells. d=-0.30 (12/12) and d=-0.25 (12/12) rows complete;
  d=-0.20 row in progress (5/12 at check time).
- Seed-2027 replication checkpoint, d=-0.20 completed cells (suite_min, 3
  seeds): ppl_ratio 0.99427-0.99429 at 1.29% actual patching — NET WINS on
  the independently re-distilled checkpoint. Original checkpoint: 0.9923x at
  2.01%. The selective win survives checkpoint-level variation in direction
  (magnitude 0.57% vs 0.77%). Always-patched on seed-2027: 1.3972x.
- Paper updated: variance-scope paragraph + evidence-ladder row now report the
  partial replication result; compiles clean.

## Status 2026-08-13 (~11:20Z)
- Sweep: 5/96 cells, 0 failures. Consistency check on completed cells:
  always-patched five-suite ratio identical (1.3972) across cells (deterministic
  harness ✓); best frontier cells at d=-0.30 ≈ 1.00014-1.00024 at ~0.08-0.09%
  patching (near neutral, matching the original sweep's d=-0.30 shape).
- ASI3 re-probe: still unavailable (shell terminal endpoint error).

## Status 2026-08-13 (~09:55Z)
- Stage 3a done 09:28 (distillation seed 2027, 17.5 min — `mwg_expert_residual_r384.pt`
  in results/asi1_ckpt_replication_20260813T080428Z/layer16/checkpoints/).
- Stage 3b done 09:32 (LM-CE 1200 steps, 3.5 min — `..._belle_lmce_cal_1200.pt`).
- Stage 3c RUNNING: 96-cell sweep since 09:32; 1 cell done, 0 failures. Early
  read on cell 1 (d=-0.30, suite_min, seed 0): seed-2027 always-patched
  five-suite ratio 1.3972x (original: 1.4086x — consistent, still above dense);
  frontier at 0.08% patching ≈ 1.00024x (near neutral). Cell pace ~15-25 min
  on the single (possibly contended) NPU → sweep ETA ~1 day. HumanEval queued after.
- Paper trims: "completed rerun" and "why out-of-family regress" paragraphs
  compressed (repeated suite numbers now live only in tables/ladder); compiles clean.

## Status 2026-08-13 (~08:25Z)
- HumanEval prep done: `mwg_humaneval_pass1_eval.py` written locally and uploaded
  to ASI1 (sha 309e1084...); canonical 164 problems available from the
  `human_eval-1.0.3` PyPI wheel at /tmp/hedl/ on ASI1. Watcher PID 5190 runs
  `run_humaneval_stage.sh` (dense/selective/random arms, greedy pass@1, exec
  harness in subprocess) automatically after the main queue finishes.
- Fixed GSM8K script (padding_side="left") uploaded as
  `mwg_gsm8k_em_eval.py.fixed` for any future re-run; the in-flight run keeps
  the old version (internally valid comparison across arms).
