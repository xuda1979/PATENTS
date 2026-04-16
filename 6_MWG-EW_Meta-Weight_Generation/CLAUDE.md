When the user asks to improve, revise, expand, or simulate the patent in this directory, do not stop after a plan or a clarification reply.

If the user says "current directory", "当前目录", or does not name a file, infer the targets from the files in this folder and start work in the same turn.

Default file inspection order for this project:
- `一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法-交底书.md`
- `一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法-交底书.tex`
- `technical_specification.md`
- `experimental_data.md`
- `benchmark_protocol_CN.md`
- `patent_draft.md`

Execution policy for this directory:
- Read the relevant files first in the same turn.
- If the request is actionable, edit the files directly instead of waiting for more confirmation.
- Use the current directory as the project scope unless the user explicitly redirects you.
- After editing, verify consistency with the disclosure terminology and summarize the changed files.
- If you have already proposed a concrete next step and the user replies with "go ahead", "continue", "当前目录", "继续", or equivalent confirmation, execute immediately in the same turn instead of replying with another intent statement.
- Do not stop with messages like "I'll inspect the files", "I'll tighten the simulation", or "I'll update the disclosure" unless a real blocker prevents further progress.

For simulation-strengthening requests, prioritize:
- experiment setup and assumptions
- parameter tables and workload definitions
- baseline comparisons
- evaluation metrics
- result interpretation text suitable for the disclosure
- short robustness, complexity, or ablation discussion when supported by the material

## Huanxin ai1 Real Experiments

This workspace now has Huanxin ai1 integration for running real GPU benchmarks:

- **Skill**: `skills/huanxin-s3-ops/` — customized for this patent project
- **Tools**: `TOOLS.md` — workspace-specific Huanxin and S3 configuration
- **Scripts**: `scripts/ai1_shell.sh`, `scripts/ai1_job.sh`, `scripts/push_to_s3.sh`, etc.
- **Browser automation**: `browser-automation/` — local copy for self-contained operation
- **Experiments**: `experiments/run_real_benchmark.py` — real PyTorch GPU benchmarks for patent evidence
- **Profiler**: `experiments/profile_descriptor_lifecycle.py` — Nsight-style evidence capture

When the user asks to "run experiments on ai1" or "improve numerical experiments":
1. Use `scripts/push_to_s3.sh` to sync code to S3
2. Use `scripts/ai1_sync_from_s3.sh` to pull code to ai1
3. Use `scripts/ai1_shell.sh` or `scripts/ai1_job.sh` to run experiments remotely
4. Use `scripts/ai1_push_results_to_s3.sh` to push results back
5. Use `scripts/pull_from_s3.sh` to fetch results locally
6. Update the 交底书 with real measured data from `results/`

The analytical simulation (`simulation/mwg_ew_simulation.py`) is for design exploration only. Real patent evidence must come from ai1 GPU measurements.
