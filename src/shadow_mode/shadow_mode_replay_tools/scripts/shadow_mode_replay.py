#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


DEFAULT_BAG_RECORD_REGEX = "(/shadow/.*|/livox/lane_detection/.*|/Odometry|/path|/scan)"


def positive_float(value):
    number = float(value)
    if number <= 0.0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return number


def non_negative_float(value):
    number = float(value)
    if number < 0.0:
        raise argparse.ArgumentTypeError("value must be greater than or equal to 0")
    return number


def sanitize_name(value):
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return sanitized.strip("._-") or "shadow_replay"


def bool_arg(value):
    return "true" if value else "false"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run a repeatable AMaRanthus shadow-mode replay evaluation."
    )
    parser.add_argument("--bag", required=True, help="Input rosbag2 directory or bag URI.")
    parser.add_argument(
        "--scenario",
        help="Scenario name used in the output directory. Defaults to the bag directory name.",
    )
    parser.add_argument(
        "--results-root",
        default="Data/shadow_mode_runs",
        help="Directory where per-run outputs are created.",
    )
    parser.add_argument(
        "--virtual-input-mode",
        choices=("scan", "pointcloud"),
        default="scan",
        help="Input mode passed to shadow_mode_bringup.",
    )
    parser.add_argument(
        "--scan-topic",
        default="/livox/lane_detection/scan",
        help="LaserScan topic used by shadow_virtual_control in scan mode.",
    )
    parser.add_argument(
        "--pointcloud-topic",
        default="/livox/lidar",
        help="PointCloud2 topic used by shadow_virtual_control in pointcloud mode.",
    )
    parser.add_argument(
        "--odom-topic",
        default="/Odometry",
        help="Odometry topic used by shadow_ego_estimation.",
    )
    parser.add_argument(
        "--bag-record-regex",
        default=DEFAULT_BAG_RECORD_REGEX,
        help="Topic regex passed to shadow_mode_bringup when recording a shadow bag.",
    )
    parser.add_argument("--rate", type=positive_float, default=1.0, help="ros2 bag play rate.")
    parser.add_argument(
        "--startup-delay",
        type=non_negative_float,
        default=2.0,
        help="Seconds to wait after launching shadow-mode nodes before bag play.",
    )
    parser.add_argument(
        "--shutdown-delay",
        type=non_negative_float,
        default=1.0,
        help="Seconds to keep shadow-mode nodes alive after bag play exits.",
    )
    parser.add_argument(
        "--record-shadow-bag",
        dest="record_shadow_bag",
        action="store_true",
        default=True,
        help="Record shadow-mode evaluation topics during replay.",
    )
    parser.add_argument(
        "--no-record-shadow-bag",
        dest="record_shadow_bag",
        action="store_false",
        help="Do not record a shadow-mode output bag.",
    )
    parser.add_argument(
        "--metrics-csv",
        dest="metrics_csv",
        action="store_true",
        default=True,
        help="Enable metrics CSV logging.",
    )
    parser.add_argument(
        "--no-metrics-csv",
        dest="metrics_csv",
        action="store_false",
        help="Disable metrics CSV logging.",
    )
    parser.add_argument(
        "--clock",
        dest="clock",
        action="store_true",
        default=True,
        help="Pass --clock to ros2 bag play.",
    )
    parser.add_argument(
        "--no-clock",
        dest="clock",
        action="store_false",
        help="Do not pass --clock to ros2 bag play.",
    )
    parser.add_argument("--loop", action="store_true", help="Pass --loop to ros2 bag play.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create no processes; print the commands and metadata path only.",
    )
    parser.add_argument(
        "--extra-launch-arg",
        action="append",
        default=[],
        metavar="NAME:=VALUE",
        help="Additional launch argument appended to shadow_mode_bringup.",
    )
    parser.add_argument(
        "--bag-play-arg",
        action="append",
        default=[],
        help="Additional argument appended to ros2 bag play.",
    )
    return parser


def make_run_paths(args):
    bag_path = Path(args.bag).expanduser()
    scenario = sanitize_name(args.scenario or bag_path.name)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.results_root).expanduser() / f"{timestamp}_{scenario}"
    metrics_csv = run_dir / "metrics" / "shadow_mode_metrics.csv"
    shadow_bag = run_dir / "rosbag" / "shadow_mode_bag"
    metadata = run_dir / "run_metadata.json"
    return bag_path, run_dir, metrics_csv, shadow_bag, metadata


def build_commands(args, bag_path, metrics_csv, shadow_bag):
    launch_cmd = [
        "ros2",
        "launch",
        "shadow_mode_bringup",
        "shadow_mode_bringup.launch.py",
        "use_adas_bringup:=false",
        f"virtual_input_mode:={args.virtual_input_mode}",
        f"lane_detection_scan_topic:={args.scan_topic}",
        f"virtual_pointcloud_topic:={args.pointcloud_topic}",
        f"pointcloud_topic:={args.pointcloud_topic}",
        f"odom_topic:={args.odom_topic}",
        f"record_shadow_bag:={bool_arg(args.record_shadow_bag)}",
        f"metrics_csv_logging:={bool_arg(args.metrics_csv)}",
        f"metrics_csv_path:={metrics_csv}",
        f"bag_output:={shadow_bag}",
        f"bag_record_regex:={args.bag_record_regex}",
    ]
    launch_cmd.extend(args.extra_launch_arg)

    bag_cmd = ["ros2", "bag", "play", str(bag_path), "--rate", str(args.rate)]
    if args.clock:
        bag_cmd.append("--clock")
    if args.loop:
        bag_cmd.append("--loop")
    bag_cmd.extend(args.bag_play_arg)
    return launch_cmd, bag_cmd


def write_metadata(path, args, launch_cmd, bag_cmd):
    metadata = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bag": args.bag,
        "scenario": args.scenario,
        "results_root": args.results_root,
        "virtual_input_mode": args.virtual_input_mode,
        "scan_topic": args.scan_topic,
        "pointcloud_topic": args.pointcloud_topic,
        "odom_topic": args.odom_topic,
        "record_shadow_bag": args.record_shadow_bag,
        "metrics_csv": args.metrics_csv,
        "clock": args.clock,
        "rate": args.rate,
        "loop": args.loop,
        "launch_command": launch_cmd,
        "bag_play_command": bag_cmd,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_command(label, command):
    print(f"{label}:")
    print("  " + " ".join(str(part) for part in command))


def start_process(command):
    return subprocess.Popen(command, preexec_fn=os.setsid)


def stop_process(process, label, grace_sec=5.0):
    if process is None or process.poll() is not None:
        return

    print(f"[INFO] Stopping {label}...")
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + grace_sec
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)

    if process.poll() is None:
        print(f"[WARN] {label} did not stop after SIGINT; terminating.")
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        process.wait(timeout=grace_sec)


def run(args):
    bag_path, run_dir, metrics_csv, shadow_bag, metadata = make_run_paths(args)
    if not bag_path.exists():
        print(f"[ERROR] Bag path does not exist: {bag_path}", file=sys.stderr)
        return 2

    launch_cmd, bag_cmd = build_commands(args, bag_path, metrics_csv, shadow_bag)
    write_metadata(metadata, args, launch_cmd, bag_cmd)

    print(f"[INFO] Run directory: {run_dir}")
    print(f"[INFO] Metadata: {metadata}")
    print_command("[INFO] Launch command", launch_cmd)
    print_command("[INFO] Bag play command", bag_cmd)

    if args.dry_run:
        return 0

    launch_process = None
    bag_process = None
    try:
        launch_process = start_process(launch_cmd)
        time.sleep(args.startup_delay)

        if launch_process.poll() is not None:
            print(
                f"[ERROR] shadow_mode_bringup exited early with code {launch_process.returncode}",
                file=sys.stderr,
            )
            return launch_process.returncode or 1

        bag_process = start_process(bag_cmd)
        bag_return = bag_process.wait()
        time.sleep(args.shutdown_delay)

        if launch_process.poll() not in (None, 0):
            print(
                f"[WARN] shadow_mode_bringup exited with code {launch_process.returncode}",
                file=sys.stderr,
            )
        return bag_return
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        return 130
    finally:
        stop_process(bag_process, "ros2 bag play")
        stop_process(launch_process, "shadow_mode_bringup")


def main():
    parser = build_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
