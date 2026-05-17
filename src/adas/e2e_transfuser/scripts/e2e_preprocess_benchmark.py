#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import statistics
import sys
import time

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "e2e_transfuser").exists():
    sys.path.insert(0, str(_SOURCE_ROOT))

from e2e_transfuser.lead_runtime import LeadTorchRuntime


def summarize(samples_ms):
    if not samples_ms:
        return {}
    ordered = sorted(samples_ms)
    p95_index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    mean_ms = statistics.fmean(ordered)
    return {
        "mean_ms": mean_ms,
        "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[p95_index],
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
        "hz_estimate": 1000.0 / mean_ms if mean_ms > 0.0 else None,
    }


def make_image_msg(*, width, height, encoding):
    if encoding.lower() in {"yuv422", "uyvy", "yuv422_yuy2", "yuyv", "yuy2"}:
        step = width * 2
    elif encoding.lower() in {"rgb8", "bgr8"}:
        step = width * 3
    elif encoding.lower() in {"rgba8", "bgra8"}:
        step = width * 4
    elif encoding.lower() in {"mono8", "8uc1"}:
        step = width
    else:
        raise ValueError(f"unsupported synthetic encoding: {encoding}")
    data = bytearray((index * 37 + 91) & 0xFF for index in range(height * step))
    return SimpleNamespace(
        width=width,
        height=height,
        step=step,
        encoding=encoding,
        data=data,
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Benchmark LEAD image preprocessing backends.")
    parser.add_argument("--backend", action="append", default=[])
    parser.add_argument("--encoding", default="yuv422")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1280)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--precision-mode", default="fp16", choices=("fp32", "fp16", "bf16"))
    parser.add_argument("--lead-project-root", default="")
    parser.add_argument("--model-path", default="Data/models/tfv6/tfv6_resnet34")
    parser.add_argument("--python-site", default="")
    parser.add_argument("--torch-lib", default="")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--forward", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    backends = args.backend or ["cpu", "torch_cuda"]

    runtime = LeadTorchRuntime(
        lead_project_root=args.lead_project_root,
        model_path=args.model_path,
        device=args.device,
        precision_mode=args.precision_mode,
        python_site=args.python_site,
        torch_lib=args.torch_lib,
        input_preprocess_backend=backends[0],
    )
    extra_roots = [Path.cwd(), _SOURCE_ROOT.parents[2]]
    if not runtime.load(extra_roots=extra_roots):
        print(
            json.dumps(
                {
                    "loaded": False,
                    "error": runtime.error,
                    "backends": backends,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    msg = make_image_msg(width=args.width, height=args.height, encoding=args.encoding)
    results = {}
    total = max(0, args.warmup) + max(1, args.iterations)
    for backend in backends:
        runtime.input_preprocess_backend = backend
        preprocess_samples = []
        forward_samples = []
        for index in range(total):
            start = time.perf_counter()
            data = runtime.build_data_from_ros(image_msg=msg)
            preprocess_ms = runtime.last_preprocess_latency_ms
            if args.forward:
                forward = runtime.forward(data)
                forward_ms = forward.latency_ms
            else:
                forward_ms = None
            if index >= args.warmup:
                preprocess_samples.append(preprocess_ms)
                if forward_ms is not None:
                    forward_samples.append(forward_ms)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if runtime.device.type == "cuda":
                runtime.torch.cuda.synchronize(runtime.device)
            if index < args.warmup and elapsed_ms < 0.0:
                raise RuntimeError("unreachable timing guard")
        results[backend] = {
            "preprocess": summarize(preprocess_samples),
            "forward": summarize(forward_samples),
        }

    print(
        json.dumps(
            {
                "loaded": True,
                "device": str(runtime.device),
                "precision_mode": args.precision_mode,
                "image": {
                    "width": args.width,
                    "height": args.height,
                    "encoding": args.encoding,
                },
                "model_input": {
                    "width": int(runtime.config.final_image_width),
                    "height": int(runtime.config.final_image_height),
                },
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
