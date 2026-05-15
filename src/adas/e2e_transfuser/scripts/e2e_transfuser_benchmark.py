#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
import time

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "e2e_transfuser").exists():
    # symlink-install と source 実行の両方で共通 helper を import できるようにする。
    sys.path.insert(0, str(_SOURCE_ROOT))

from e2e_transfuser.environment import inspect_lead_environment


def build_parser():
    parser = argparse.ArgumentParser(
        description="Benchmark e2e_transfuser runtime readiness and lightweight forward paths."
    )
    parser.add_argument(
        "--runtime-mode",
        choices=("mock", "lead_python", "onnx", "tensorrt"),
        default="mock",
    )
    parser.add_argument(
        "--precision-mode",
        choices=("fp32", "fp16", "int8"),
        default="fp32",
    )
    parser.add_argument("--lead-project-root", default="")
    parser.add_argument("--model-path", default="Data/models/tfv6/tfv6_resnet34")
    parser.add_argument("--model-variant", default="tfv6_resnet34")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--allow-int8", action="store_true")
    parser.add_argument(
        "--enable-aux-heads",
        dest="disable_aux_heads",
        action="store_false",
        default=True,
    )
    parser.add_argument(
        "--ensemble",
        dest="single_checkpoint",
        action="store_false",
        default=True,
    )
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-csv", default="")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect readiness without running a timing loop.",
    )
    return parser


def run_mock_forward(iterations, warmup):
    # 実モデルではなく、ROS adapter 側の軽い path/proxy 計算コストだけを測る。
    samples_ms = []
    total = max(0, warmup) + max(1, iterations)
    for index in range(total):
        start = time.perf_counter()
        target_x = 15.0
        target_y = 0.5
        wheel_base = 2.7
        distance_sq = max(target_x * target_x + target_y * target_y, 0.1)
        curvature = 2.0 * target_y / distance_sq
        steering = wheel_base * curvature
        path = [
            (target_x * float(step + 1) / 10.0, target_y * float(step + 1) / 10.0)
            for step in range(10)
        ]
        if not path or steering > 999.0:
            raise RuntimeError("unexpected mock benchmark state")
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if index >= warmup:
            # warmup は Python import/cache 等の初回ゆらぎを測定から外す。
            samples_ms.append(elapsed_ms)
    return samples_ms


def summarize_samples(samples_ms):
    # 実車向けには平均だけでなく p95 を見る。10Hz維持には tail latency が効くため。
    if not samples_ms:
        return {
            "latency_ms_mean": None,
            "latency_ms_p50": None,
            "latency_ms_p95": None,
            "latency_ms_min": None,
            "latency_ms_max": None,
            "hz_estimate": None,
        }
    sorted_samples = sorted(samples_ms)
    p95_index = min(len(sorted_samples) - 1, int(round(0.95 * (len(sorted_samples) - 1))))
    mean_ms = statistics.fmean(sorted_samples)
    return {
        "latency_ms_mean": mean_ms,
        "latency_ms_p50": statistics.median(sorted_samples),
        "latency_ms_p95": sorted_samples[p95_index],
        "latency_ms_min": min(sorted_samples),
        "latency_ms_max": max(sorted_samples),
        "hz_estimate": 1000.0 / mean_ms if mean_ms > 0.0 else None,
    }


def write_json(path, payload):
    if not path:
        return
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path, payload):
    if not path:
        return
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(payload.keys()))
        writer.writeheader()
        writer.writerow(payload)


def main():
    args = build_parser().parse_args()
    # まず runtime の準備状態を確認し、未配置 checkpoint を forward 測定と誤認しないようにする。
    summary = inspect_lead_environment(
        lead_project_root=args.lead_project_root,
        model_path=args.model_path,
        model_variant=args.model_variant,
        runtime_mode=args.runtime_mode,
        precision_mode=args.precision_mode,
        allow_int8=args.allow_int8,
        disable_aux_heads=args.disable_aux_heads,
        single_checkpoint=args.single_checkpoint,
    )

    samples_ms = []
    measurement_type = "readiness_only"
    if not args.dry_run and args.runtime_mode == "mock":
        samples_ms = run_mock_forward(args.iterations, args.warmup)
        measurement_type = "mock_adapter_overhead"
    elif not args.dry_run and args.runtime_mode != "mock" and not summary["ready"]:
        # 依存や checkpoint が足りない場合は、測定せず readiness 結果として残す。
        measurement_type = "not_run_runtime_not_ready"
    elif not args.dry_run:
        # LEAD 本体の forward hook は今後差し込む。現段階で測ったことにはしない。
        measurement_type = "not_run_model_forward_not_implemented"
        summary["blocking_reasons"].append(
            "model forward benchmark hook is ready, but LEAD model invocation is not implemented"
        )
        summary["ready"] = False

    latency = summarize_samples(samples_ms)
    payload = {
        "runtime_mode": args.runtime_mode,
        "precision_mode": args.precision_mode,
        "model_variant": args.model_variant,
        "model_path": args.model_path,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "allow_int8": args.allow_int8,
        "disable_aux_heads": args.disable_aux_heads,
        "single_checkpoint": args.single_checkpoint,
        "measurement_type": measurement_type,
        "runtime_ready": summary["ready"],
        "blocking_reasons": "; ".join(summary["blocking_reasons"]),
    }
    payload.update(latency)

    print(json.dumps({"environment": summary, "benchmark": payload}, indent=2, sort_keys=True))
    write_json(args.output_json, {"environment": summary, "benchmark": payload})
    write_csv(args.output_csv, payload)
    return 0 if args.dry_run or args.runtime_mode == "mock" else 2


if __name__ == "__main__":
    sys.exit(main())
