from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class UiRenderConfig:
    max_range_m: float = 20.0
    dynamic_range_enabled: bool = False
    dynamic_range_min_m: float = 12.0
    dynamic_range_max_m: float = 35.0
    dynamic_range_speed_min_kmh: float = 0.0
    dynamic_range_speed_max_kmh: float = 80.0
    scan_point_size: int = 3
    lane_point_size: int = 4
    obstacle_marker_width_px: float = 24.0
    obstacle_marker_height_px: float = 14.0
    obstacle_label_dx_px: float = 14.0
    obstacle_label_dy_px: float = -8.0


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_ui_render_config(config_path: str | None = None) -> UiRenderConfig:
    root = Path(__file__).resolve().parent.parent
    path = Path(config_path) if config_path else root / "config" / "ui.yaml"

    config = UiRenderConfig()
    if not path.exists():
        return config

    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, dict):
        return config

    render = payload.get("render", {})
    if not isinstance(render, dict):
        return config

    config.max_range_m = _to_float(render.get("max_range_m"), config.max_range_m)
    config.dynamic_range_enabled = bool(
        render.get("dynamic_range_enabled", config.dynamic_range_enabled)
    )
    config.dynamic_range_min_m = _to_float(
        render.get("dynamic_range_min_m"), config.dynamic_range_min_m
    )
    config.dynamic_range_max_m = _to_float(
        render.get("dynamic_range_max_m"), config.dynamic_range_max_m
    )
    config.dynamic_range_speed_min_kmh = _to_float(
        render.get("dynamic_range_speed_min_kmh"), config.dynamic_range_speed_min_kmh
    )
    config.dynamic_range_speed_max_kmh = _to_float(
        render.get("dynamic_range_speed_max_kmh"), config.dynamic_range_speed_max_kmh
    )
    config.scan_point_size = _to_int(render.get("scan_point_size"), config.scan_point_size)
    config.lane_point_size = _to_int(render.get("lane_point_size"), config.lane_point_size)
    config.obstacle_marker_width_px = _to_float(
        render.get("obstacle_marker_width_px"), config.obstacle_marker_width_px
    )
    config.obstacle_marker_height_px = _to_float(
        render.get("obstacle_marker_height_px"), config.obstacle_marker_height_px
    )
    config.obstacle_label_dx_px = _to_float(
        render.get("obstacle_label_dx_px"), config.obstacle_label_dx_px
    )
    config.obstacle_label_dy_px = _to_float(
        render.get("obstacle_label_dy_px"), config.obstacle_label_dy_px
    )
    return config
