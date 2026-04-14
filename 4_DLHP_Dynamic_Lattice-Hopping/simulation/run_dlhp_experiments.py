from __future__ import annotations

import argparse
from pathlib import Path

from dlhp_simulation import CONFIG_PATH, RESULTS_DIR, load_config, run_all, write_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DLHP patent simulation.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Path to the simulation config file.")
    parser.add_argument("--seed", type=int, default=None, help="Override the random seed.")
    parser.add_argument("--schedule-samples", type=int, default=None, help="Override the number of schedule samples.")
    parser.add_argument("--transition-trials", type=int, default=None, help="Override the number of transition trials.")
    parser.add_argument("--session-trials", type=int, default=None, help="Override the number of interval trials.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    if args.seed is not None:
        config["seed"] = args.seed
    if args.schedule_samples is not None:
        config["schedule_samples"] = args.schedule_samples
    if args.transition_trials is not None:
        config["transition_trials"] = args.transition_trials
    if args.session_trials is not None:
        config["session_trials_per_interval"] = args.session_trials

    summary = run_all(config)
    write_results(summary, RESULTS_DIR)

    print("DLHP simulation completed.")
    print(f"Summary JSON: {RESULTS_DIR / 'summary.json'}")
    print(f"Summary report: {RESULTS_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
