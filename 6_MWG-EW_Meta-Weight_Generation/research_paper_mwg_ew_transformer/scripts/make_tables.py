#!/usr/bin/env python3
"""Compatibility entry point for the current audited journal tables.

Historical numbered ICLR tables are no longer active. Use
scripts/audit_journal_evidence.py for the machine-readable audit.
"""
import argparse
import json
from audit_journal_evidence import ROOT, collect, emit_tables

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    result = collect(ROOT)
    if not args.check:
        emit_tables(result, ROOT / "paper/generated_tables")
    if args.stdout:
        print(json.dumps(result["quality"], indent=2, allow_nan=False))
    else:
        print("Archive arithmetic verified; scientific readiness remains false.")
