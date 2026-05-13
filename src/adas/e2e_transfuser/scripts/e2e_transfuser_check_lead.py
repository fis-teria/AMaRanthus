#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "e2e_transfuser").exists():
    sys.path.insert(0, str(_SOURCE_ROOT))

from e2e_transfuser.environment import dumps_summary, inspect_lead_environment


def build_parser():
    parser = argparse.ArgumentParser(
        description="Inspect LEAD / TransFuser model files and optional runtime dependencies."
    )
    parser.add_argument("--lead-project-root", default="", help="Path to the LEAD checkout.")
    parser.add_argument(
        "--model-path",
        default="Data/models/tfv6/tfv6_resnet34",
        help="Path to a TFv6 checkpoint directory.",
    )
    parser.add_argument("--model-variant", default="tfv6_resnet34")
    parser.add_argument(
        "--runtime-mode",
        choices=("mock", "lead_python", "onnx", "tensorrt"),
        default="lead_python",
    )
    parser.add_argument(
        "--precision-mode",
        choices=("fp32", "fp16", "int8"),
        default="fp32",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Always exit with 0 after printing the summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status when the requested runtime is not ready.",
    )
    return parser


def main():
    args = build_parser().parse_args()
    summary = inspect_lead_environment(
        lead_project_root=args.lead_project_root,
        model_path=args.model_path,
        model_variant=args.model_variant,
        runtime_mode=args.runtime_mode,
        precision_mode=args.precision_mode,
    )
    print(dumps_summary(summary))

    if args.strict and not args.dry_run and not summary["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
