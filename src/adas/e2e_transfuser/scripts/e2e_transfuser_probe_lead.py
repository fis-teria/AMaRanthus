#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "e2e_transfuser").exists():
    sys.path.insert(0, str(_SOURCE_ROOT))

from e2e_transfuser.lead_runtime import LeadTorchRuntime


def main():
    parser = argparse.ArgumentParser(
        description="Load LEAD / TFv6 with inference-only heads and optionally run one CUDA forward."
    )
    parser.add_argument("--lead-project-root", default="")
    parser.add_argument("--model-path", default="Data/models/tfv6/tfv6_resnet34")
    parser.add_argument("--python-site", default="")
    parser.add_argument("--torch-lib", default="")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--precision-mode", default="fp32", choices=("fp32", "fp16", "bf16"))
    parser.add_argument("--enable-aux-heads", action="store_true")
    parser.add_argument("--all-checkpoints", action="store_true")
    parser.add_argument("--strict-weight-load", action="store_true")
    parser.add_argument("--allow-timm-pretrained-download", action="store_true")
    parser.add_argument("--forward", action="store_true")
    args = parser.parse_args()

    runtime = LeadTorchRuntime(
        lead_project_root=args.lead_project_root,
        model_path=args.model_path,
        device=args.device,
        precision_mode=args.precision_mode,
        disable_aux_heads=not args.enable_aux_heads,
        single_checkpoint=not args.all_checkpoints,
        strict_weight_load=args.strict_weight_load,
        python_site=args.python_site,
        torch_lib=args.torch_lib,
        force_timm_pretrained_off=not args.allow_timm_pretrained_download,
    )
    extra_roots = [Path.cwd(), _SOURCE_ROOT.parents[2]]
    loaded = runtime.load(extra_roots=extra_roots)
    result = {
        "loaded": loaded,
        "error": runtime.error,
        "device": args.device,
        "precision_mode": args.precision_mode,
        "disable_aux_heads": not args.enable_aux_heads,
        "single_checkpoint": not args.all_checkpoints,
        "checkpoint_files": runtime.checkpoint_files,
        "forward": None,
    }
    if loaded and args.forward:
        forward = runtime.synthetic_forward()
        result["forward"] = {
            "device": forward.device,
            "latency_ms": forward.latency_ms,
            "path_points": len(forward.path_xy),
            "speed_target_mps": forward.speed_target_mps,
            "confidence": forward.confidence,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if loaded and (not args.forward or result["forward"] is not None) else 2


if __name__ == "__main__":
    raise SystemExit(main())
