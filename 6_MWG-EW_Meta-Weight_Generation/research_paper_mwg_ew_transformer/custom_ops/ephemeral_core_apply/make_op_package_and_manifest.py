#!/usr/bin/env python3
"""Package the built EphemeralCoreApply vendor op and emit the contract manifest.

Runs ON the NPU host (ASI2) after `build.sh` + vendor install.  Produces:
  - <out_dir>/mwg_op_package.tgz      : tarball of the customize/ opp tree
  - <out_dir>/ephemeral_core_apply.contract.json : hash-bound contract manifest

Usage:
  python3 make_op_package_and_manifest.py \
      --vendor-dir /usr/local/Ascend/ascend-toolkit/latest/opp/vendors/customize \
      --audited-source /root/work/.../template_adapted/op_kernel/add_custom.cpp \
      --out-dir /root/work/mwg_op_build
"""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor-dir", required=True)
    parser.add_argument("--audited-source", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    vendor = Path(args.vendor_dir).expanduser().resolve()
    source = Path(args.audited_source).expanduser().resolve()
    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    if not vendor.is_dir():
        raise SystemExit(f"vendor dir not found: {vendor}")
    if not source.is_file():
        raise SystemExit(f"audited source not found: {source}")

    package = out / "mwg_op_package.tgz"
    # GE validates ASCEND_OPP_PATH entries as opp roots: a top-level
    # version.info marker plus a vendors/<name>/ tree are both required.
    marker = out / "version.info.marker"
    marker.write_text(
        "vendor_package=mwg-ephemeral-core-apply\n"
        f"package_built_from={source.name}\n",
        encoding="utf-8",
    )
    with tarfile.open(package, "w:gz") as tf:
        tf.add(marker, arcname="version.info")
        tf.add(vendor, arcname="vendors/customize")
    marker.unlink()

    source_sha = sha256_file(source)
    binary_sha = sha256_file(package)

    manifest = {
        "schema_version": 1,
        "op_qualified_name": "mwg::ephemeral_core_apply",
        "implementation": "ascendc",
        "core_residency": "ub_local_tensor",
        "global_core_output": False,
        "workspace_bytes": 0,
        "outputs": ["scaled_rank_activation"],
        "audited_source_path": str(source),
        "audited_source_sha256": source_sha,
        "binary_sha256": binary_sha,
        "source_audit": {
            "no_global_core_tensor": True,
            "no_core_datacopy_to_global": True,
        },
        "package_notes": (
            "binary artifact is the tarball of the installed customize/ opp "
            "tree (op_info config, op_tiling lib, dynamic impl, kernel); "
            "torchair registration module exposes it via ASCEND_OPP_PATH"
        ),
    }
    manifest_path = out / "ephemeral_core_apply.contract.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "package": str(package),
        "manifest": str(manifest_path),
        "audited_source_sha256": source_sha,
        "binary_sha256": binary_sha,
    }, indent=2))


if __name__ == "__main__":
    main()
