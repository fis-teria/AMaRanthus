import json
import math
import os
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LeadForwardResult:
    path_xy: list[tuple[float, float]]
    speed_target_mps: float
    confidence: float
    latency_ms: float
    device: str


def _prepend_env_path(env_name: str, path: str) -> None:
    if not path:
        return
    current = os.environ.get(env_name, "")
    values = [value for value in current.split(os.pathsep) if value]
    if path not in values:
        os.environ[env_name] = os.pathsep.join([path, *values])


def _resolve_existing_path(path: str, extra_roots: list[Path] | None = None) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute() or candidate.exists():
        return candidate
    for root in extra_roots or []:
        rooted = root / candidate
        if rooted.exists():
            return rooted
    return candidate


class LeadTorchRuntime:
    """Small inference-only bridge into LEAD / TFv6.

    The bridge deliberately avoids LEAD's CARLA agent and training entrypoints.  It
    constructs only the PyTorch model, disables training-time auxiliary heads when
    requested, loads one or more checkpoints, and runs `net(data)` under
    `torch.inference_mode()`.
    """

    def __init__(
        self,
        *,
        lead_project_root: str,
        model_path: str,
        device: str = "cuda:0",
        precision_mode: str = "fp32",
        disable_aux_heads: bool = True,
        single_checkpoint: bool = True,
        strict_weight_load: bool = False,
        python_site: str = "",
        torch_lib: str = "",
        force_timm_pretrained_off: bool = True,
        input_preprocess_backend: str = "cpu",
        lidar_raster_enabled: bool = True,
        lidar_flip_y_axis: bool = True,
        lidar_history_size: int = 1,
        lidar_max_points: int = 250000,
    ):
        self.lead_project_root = lead_project_root
        self.model_path = model_path
        self.device_name = device
        self.precision_mode = precision_mode
        self.disable_aux_heads = disable_aux_heads
        self.single_checkpoint = single_checkpoint
        self.strict_weight_load = strict_weight_load
        self.python_site = python_site
        self.torch_lib = torch_lib
        self.force_timm_pretrained_off = force_timm_pretrained_off
        self.input_preprocess_backend = str(input_preprocess_backend).lower()
        self.lidar_raster_enabled = bool(lidar_raster_enabled)
        self.lidar_flip_y_axis = bool(lidar_flip_y_axis)
        self.lidar_history_size = max(1, int(lidar_history_size))
        self.lidar_max_points = max(0, int(lidar_max_points))
        self.loaded = False
        self.error = ""
        self.nets = []
        self.config = None
        self.torch = None
        self.np = None
        self.cv2 = None
        self.device = None
        self.checkpoint_files: list[str] = []
        self.forward_count = 0
        self.last_latency_ms = None
        self.last_preprocess_latency_ms = None
        self.last_error = ""
        self._lidar_history: list[tuple[tuple[int, int, str], Any]] = []
        self.last_lidar_raster_status: dict[str, Any] = {
            "enabled": self.lidar_raster_enabled,
            "source": "zero",
            "reason": "not_started",
            "input_points": 0,
            "finite_points": 0,
            "used_points": 0,
            "nonzero_pixels": 0,
            "max_value": 0.0,
            "frame_id": "",
            "history_size": 0,
        }

    def load(self, *, extra_roots: list[Path] | None = None) -> bool:
        try:
            if self.python_site:
                sys.path.insert(0, self.python_site)
                _prepend_env_path("PYTHONPATH", self.python_site)
            if self.torch_lib:
                _prepend_env_path("LD_LIBRARY_PATH", self.torch_lib)

            lead_root = _resolve_existing_path(self.lead_project_root, extra_roots)
            if lead_root:
                sys.path.insert(0, str(lead_root))
                os.environ.setdefault("LEAD_PROJECT_ROOT", str(lead_root))

            import cv2
            import numpy as np
            import torch

            self.torch = torch
            self.np = np
            self.cv2 = cv2

            if self.device_name.startswith("cuda") and not torch.cuda.is_available():
                raise RuntimeError("torch.cuda.is_available() is false")
            self.device = torch.device(self.device_name)

            if self.force_timm_pretrained_off:
                self._disable_timm_pretrained_download()

            self._install_carla_import_stubs()
            from lead.tfv6.tfv6 import TFv6
            from lead.training.config_training import TrainingConfig

            model_dir = _resolve_existing_path(self.model_path, extra_roots)
            config_path = model_dir / "config.json"
            if not config_path.exists():
                raise FileNotFoundError(f"LEAD config not found: {config_path}")
            with config_path.open(encoding="utf-8") as handle:
                loaded_config = json.load(handle)
            self.config = TrainingConfig(loaded_config, raise_error_on_missing_key=False)
            self._configure_inference_only(self.config)

            checkpoint_files = self._checkpoint_files(model_dir)
            if not checkpoint_files:
                raise FileNotFoundError(f"No model*.pth checkpoint found in {model_dir}")
            if self.single_checkpoint:
                checkpoint_files = checkpoint_files[:1]

            self.nets = []
            for checkpoint in checkpoint_files:
                net = TFv6(self.device, self.config)
                state_dict = torch.load(
                    checkpoint,
                    map_location=self.device,
                    weights_only=True,
                )
                if not (self.strict_weight_load and not self.disable_aux_heads):
                    state_dict = self._filter_compatible_state_dict(net, state_dict)
                load_info = net.load_state_dict(
                    state_dict,
                    strict=self.strict_weight_load and not self.disable_aux_heads,
                )
                if self.disable_aux_heads:
                    missing = len(getattr(load_info, "missing_keys", []))
                    unexpected = len(getattr(load_info, "unexpected_keys", []))
                    if missing or unexpected:
                        # Expected when auxiliary heads are not constructed at inference.
                        pass
                net.to(self.device).eval()
                self.nets.append(net)

            self.checkpoint_files = [str(path) for path in checkpoint_files]
            self.loaded = bool(self.nets)
            self.error = ""
            return self.loaded
        except Exception as exc:
            self.loaded = False
            self.error = f"{type(exc).__name__}: {exc}"
            return False

    def _disable_timm_pretrained_download(self) -> None:
        import timm

        if getattr(timm.create_model, "_e2e_transfuser_no_pretrained", False):
            return
        original_create_model = timm.create_model

        def create_model_no_pretrained(*args, **kwargs):
            kwargs["pretrained"] = False
            return original_create_model(*args, **kwargs)

        create_model_no_pretrained._e2e_transfuser_no_pretrained = True
        timm.create_model = create_model_no_pretrained

    def _install_carla_import_stubs(self) -> None:
        if "carla" not in sys.modules:
            carla = types.ModuleType("carla")

            class _Transform:
                pass

            class _Location:
                def __init__(self, x=0.0, y=0.0, z=0.0):
                    self.x = x
                    self.y = y
                    self.z = z

            class _Color:
                def __init__(self, r=0, g=0, b=0, a=255):
                    self.r = r
                    self.g = g
                    self.b = b
                    self.a = a

            def _missing_attr(name):
                placeholder = type(name, (), {})
                setattr(carla, name, placeholder)
                return placeholder

            carla.Transform = _Transform
            carla.Location = _Location
            carla.Color = _Color
            carla.__getattr__ = _missing_attr
            sys.modules["carla"] = carla

        if "agents.navigation.local_planner" not in sys.modules:
            agents = types.ModuleType("agents")
            navigation = types.ModuleType("agents.navigation")
            local_planner = types.ModuleType("agents.navigation.local_planner")

            class RoadOption:
                LEFT = "left"
                RIGHT = "right"
                STRAIGHT = "straight"
                LANEFOLLOW = "lane_follow"
                CHANGELANELEFT = "change_lane_left"
                CHANGELANERIGHT = "change_lane_right"

            local_planner.RoadOption = RoadOption
            sys.modules.setdefault("agents", agents)
            sys.modules.setdefault("agents.navigation", navigation)
            sys.modules["agents.navigation.local_planner"] = local_planner

    def _configure_inference_only(self, config: Any) -> None:
        overrides = getattr(config, "_loaded_config", {})
        self._set_config_values(
            config,
            overrides,
            {
                "compile": False,
                "sync_batchnorm": False,
                "log_wandb": False,
                "visualize_training": False,
                "visualize_dataset": False,
                "debug_boxes_visualization": False,
                "use_planning_decoder": True,
            },
        )

        if self.precision_mode == "fp16":
            self._set_config_values(
                config, overrides, {"use_mixed_precision_training": True}
            )
        elif self.precision_mode == "bf16":
            self._set_config_values(
                config, overrides, {"use_mixed_precision_training": True}
            )
        else:
            self._set_config_values(
                config, overrides, {"use_mixed_precision_training": False}
            )

        if self.disable_aux_heads:
            self._set_config_values(
                config,
                overrides,
                {
                    "use_semantic": False,
                    "use_depth": False,
                    "use_bev_semantic": False,
                    "detect_boxes": False,
                    "radar_detection": False,
                    "use_radar_detection": False,
                    "forecast_radar_detections": False,
                }
            )
        config._loaded_config = overrides

    def _set_config_values(self, config: Any, overrides: dict, values: dict) -> None:
        for key, value in values.items():
            overrides[key] = value
            try:
                setattr(config, key, value)
            except Exception:
                pass

    def _checkpoint_files(self, model_dir: Path) -> list[Path]:
        return sorted(
            path
            for path in model_dir.iterdir()
            if path.name.startswith("model") and path.suffix == ".pth"
        )

    def _filter_compatible_state_dict(self, net, state_dict):
        current = net.state_dict()
        return {
            key: value
            for key, value in state_dict.items()
            if key in current and tuple(current[key].shape) == tuple(value.shape)
        }

    def build_data_from_ros(
        self,
        *,
        image_msg,
        pointcloud_msg=None,
        speed_mps: float = 0.0,
        target_xy: tuple[float, float] = (15.0, 0.0),
        target_points_xy=None,
        command: str = "lane_follow",
    ) -> dict[str, Any]:
        start = time.perf_counter()
        if self.input_preprocess_backend == "torch_cuda" and self.device.type == "cuda":
            data = self._build_data_from_ros_torch_cuda(
                image_msg=image_msg,
                pointcloud_msg=pointcloud_msg,
                speed_mps=speed_mps,
                target_xy=target_xy,
                target_points_xy=target_points_xy,
                command=command,
            )
            self.torch.cuda.synchronize(self.device)
            self.last_preprocess_latency_ms = (time.perf_counter() - start) * 1000.0
            return data

        image = self._image_msg_to_rgb_array(image_msg)
        data = self.build_data_from_arrays(
            image_rgb=image,
            rasterized_lidar=self.rasterized_lidar_from_pointcloud(pointcloud_msg),
            speed_mps=speed_mps,
            target_xy=target_xy,
            target_points_xy=target_points_xy,
            command=command,
        )
        self.last_preprocess_latency_ms = (time.perf_counter() - start) * 1000.0
        return data

    def build_synthetic_data(self) -> dict[str, Any]:
        image = self.np.zeros(
            (int(self.config.final_image_height), int(self.config.final_image_width), 3),
            dtype=self.np.uint8,
        )
        return self.build_data_from_arrays(image_rgb=image)

    def build_data_from_arrays(
        self,
        *,
        image_rgb,
        rasterized_lidar=None,
        speed_mps: float = 0.0,
        target_xy: tuple[float, float] = (15.0, 0.0),
        target_points_xy=None,
        command: str = "lane_follow",
    ) -> dict[str, Any]:
        torch = self.torch
        np = self.np
        cv2 = self.cv2
        image_h = int(self.config.final_image_height)
        image_w = int(self.config.final_image_width)
        resized = cv2.resize(image_rgb, (image_w, image_h), interpolation=cv2.INTER_AREA)
        rgb = np.transpose(resized, (2, 0, 1))[None].copy()

        if rasterized_lidar is None:
            rasterized_lidar = self.zero_lidar_raster(reason="missing_pointcloud")
        command_one_hot = self._command_one_hot(command)
        previous_xy, current_xy, next_xy = self._target_triplet(target_xy, target_points_xy)
        target = np.array([current_xy], dtype=np.float32)
        target_previous = np.array([previous_xy], dtype=np.float32)
        target_next = np.array([next_xy], dtype=np.float32)

        return {
            "rgb": torch.from_numpy(rgb),
            "rasterized_lidar": torch.from_numpy(rasterized_lidar),
            "speed": torch.tensor([float(speed_mps)], dtype=torch.float32),
            "command": torch.from_numpy(command_one_hot),
            "target_point": torch.from_numpy(target),
            "target_point_previous": torch.from_numpy(target_previous),
            "target_point_next": torch.from_numpy(target_next),
            "iteration": torch.tensor([0], dtype=torch.long),
        }

    def _build_data_from_ros_torch_cuda(
        self,
        *,
        image_msg,
        pointcloud_msg=None,
        speed_mps: float = 0.0,
        target_xy: tuple[float, float] = (15.0, 0.0),
        target_points_xy=None,
        command: str = "lane_follow",
    ) -> dict[str, Any]:
        torch = self.torch
        image = self._image_msg_to_torch_rgb_tensor(image_msg)
        rasterized_lidar = self.rasterized_lidar_from_pointcloud(pointcloud_msg)

        command_one_hot = torch.zeros((1, 6), dtype=torch.float32, device=self.device)
        command_one_hot[0, self._command_index(command)] = 1.0
        previous_xy, current_xy, next_xy = self._target_triplet(target_xy, target_points_xy)
        target = torch.tensor([current_xy], dtype=torch.float32, device=self.device)
        target_previous = torch.tensor([previous_xy], dtype=torch.float32, device=self.device)
        target_next = torch.tensor([next_xy], dtype=torch.float32, device=self.device)

        return {
            "rgb": image,
            "rasterized_lidar": torch.from_numpy(rasterized_lidar).to(
                self.device, dtype=torch.float32, non_blocking=True
            ),
            "speed": torch.tensor([float(speed_mps)], dtype=torch.float32, device=self.device),
            "command": command_one_hot,
            "target_point": target,
            "target_point_previous": target_previous,
            "target_point_next": target_next,
            "iteration": torch.tensor([0], dtype=torch.long, device=self.device),
        }

    @staticmethod
    def _target_triplet(target_xy, target_points_xy) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        def clean(point, fallback):
            if point is None:
                return fallback
            try:
                x = float(point[0])
                y = float(point[1])
            except Exception:
                return fallback
            if not (math.isfinite(x) and math.isfinite(y)):
                return fallback
            return (x, y)

        current = clean(target_xy, (15.0, 0.0))
        previous = current
        next_point = current
        if isinstance(target_points_xy, dict):
            previous = clean(target_points_xy.get("previous"), previous)
            current = clean(target_points_xy.get("current"), current)
            next_point = clean(target_points_xy.get("next"), next_point)
        elif target_points_xy is not None:
            try:
                values = list(target_points_xy)
            except Exception:
                values = []
            if len(values) >= 3:
                previous = clean(values[0], previous)
                current = clean(values[1], current)
                next_point = clean(values[2], next_point)
        return previous, current, next_point

    def zero_lidar_raster(self, *, reason: str) -> Any:
        np = self.np
        lidar_h = int(self.config.lidar_height_pixel)
        lidar_w = int(self.config.lidar_width_pixel)
        self.last_lidar_raster_status = {
            "enabled": self.lidar_raster_enabled,
            "source": "zero",
            "reason": reason,
            "input_points": 0,
            "finite_points": 0,
            "used_points": 0,
            "nonzero_pixels": 0,
            "max_value": 0.0,
            "frame_id": "",
            "history_size": 0,
            "configured_history_size": self.lidar_history_size,
            "flip_y_axis": self.lidar_flip_y_axis,
        }
        return np.zeros((1, 1, lidar_h, lidar_w), dtype=np.float32)

    def rasterized_lidar_from_pointcloud(self, pointcloud_msg) -> Any:
        if not self.lidar_raster_enabled:
            return self.zero_lidar_raster(reason="disabled")
        if pointcloud_msg is None:
            return self.zero_lidar_raster(reason="missing_pointcloud")

        np = self.np
        cv2 = self.cv2
        try:
            points = self._pointcloud_xyz_array(pointcloud_msg)
            input_points = int(points.shape[0])
            points = points[np.isfinite(points).all(axis=1)]
            finite_points = int(points.shape[0])
            if finite_points == 0:
                return self.zero_lidar_raster(reason="empty_after_finite_filter")

            if self.lidar_flip_y_axis:
                points = points.copy()
                points[:, 1] = -points[:, 1]

            precision = 0.1
            points = np.round(points / precision) * precision
            if self.lidar_max_points > 0 and points.shape[0] > self.lidar_max_points:
                stride = int(np.ceil(points.shape[0] / float(self.lidar_max_points)))
                points = points[::stride]

            stamp_key = self._pointcloud_stamp_key(pointcloud_msg)
            if not self._lidar_history or self._lidar_history[-1][0] != stamp_key:
                self._lidar_history.append((stamp_key, points))
                self._lidar_history = self._lidar_history[-self.lidar_history_size :]
            history_points = (
                np.concatenate([entry[1] for entry in self._lidar_history], axis=0)
                if self._lidar_history
                else points
            )

            raster = self._rasterize_lidar_points(history_points)
            compressed_ok = False
            try:
                scaled = (np.clip(raster[..., None], 0.0, 1.0) * 65535.0).astype(np.uint16)
                success, compressed = cv2.imencode(
                    ".png",
                    scaled,
                    [int(cv2.IMWRITE_PNG_COMPRESSION), int(self.config.training_png_compression_level)],
                )
                if success:
                    decoded = cv2.imdecode(compressed, cv2.IMREAD_UNCHANGED).astype(np.float32)
                    raster = np.squeeze(decoded / 65535.0).astype(np.float32)
                    compressed_ok = True
            except Exception:
                compressed_ok = False

            raster = raster[None, None].astype(np.float32, copy=False)
            self.last_lidar_raster_status = {
                "enabled": self.lidar_raster_enabled,
                "source": "pointcloud",
                "reason": "",
                "input_points": input_points,
                "finite_points": finite_points,
                "used_points": int(history_points.shape[0]),
                "nonzero_pixels": int(np.count_nonzero(raster)),
                "max_value": float(raster.max()) if raster.size else 0.0,
                "frame_id": str(getattr(getattr(pointcloud_msg, "header", None), "frame_id", "")),
                "history_size": len(self._lidar_history),
                "configured_history_size": self.lidar_history_size,
                "flip_y_axis": self.lidar_flip_y_axis,
                "compression_roundtrip": compressed_ok,
            }
            return raster
        except Exception as exc:
            status = {
                "enabled": self.lidar_raster_enabled,
                "source": "zero",
                "reason": f"{type(exc).__name__}: {exc}",
                "input_points": 0,
                "finite_points": 0,
                "used_points": 0,
                "nonzero_pixels": 0,
                "max_value": 0.0,
                "frame_id": str(getattr(getattr(pointcloud_msg, "header", None), "frame_id", "")),
                "history_size": len(self._lidar_history),
                "configured_history_size": self.lidar_history_size,
                "flip_y_axis": self.lidar_flip_y_axis,
            }
            raster = self.zero_lidar_raster(reason=status["reason"])
            self.last_lidar_raster_status.update(status)
            return raster

    def _rasterize_lidar_points(self, points) -> Any:
        np = self.np
        config = self.config
        lidar_h = int(config.lidar_height_pixel)
        lidar_w = int(config.lidar_width_pixel)
        if points.size == 0:
            return np.zeros((lidar_h, lidar_w), dtype=np.float32)

        mask = (
            (points[:, 0] >= float(config.min_x_meter))
            & (points[:, 0] <= float(config.max_x_meter))
            & (points[:, 1] >= float(config.min_y_meter))
            & (points[:, 1] <= float(config.max_y_meter))
            & (points[:, 2] >= float(config.min_height_lidar))
            & (points[:, 2] <= float(config.max_height_lidar))
        )
        points = points[mask]
        if points.size == 0:
            return np.zeros((lidar_h, lidar_w), dtype=np.float32)

        xbins = np.linspace(float(config.min_x_meter), float(config.max_x_meter), lidar_w + 1)
        ybins = np.linspace(float(config.min_y_meter), float(config.max_y_meter), lidar_h + 1)
        hist = np.histogramdd(points[:, :2], bins=(xbins, ybins))[0]
        hist = np.minimum(hist, float(config.hist_max_per_pixel)) / float(config.hist_max_per_pixel)
        return hist.T.astype(np.float32)

    def _pointcloud_stamp_key(self, msg) -> tuple[int, int, str]:
        header = getattr(msg, "header", None)
        stamp = getattr(header, "stamp", None)
        return (
            int(getattr(stamp, "sec", 0)),
            int(getattr(stamp, "nanosec", 0)),
            str(getattr(header, "frame_id", "")),
        )

    def _pointcloud_xyz_array(self, msg):
        np = self.np
        width = int(getattr(msg, "width", 0))
        height = int(getattr(msg, "height", 1))
        point_step = int(getattr(msg, "point_step", 0))
        row_step = int(getattr(msg, "row_step", width * point_step))
        if width <= 0 or height <= 0 or point_step <= 0:
            return np.zeros((0, 3), dtype=np.float32)

        dtype = self._pointcloud_dtype(msg)
        count_per_row = width
        raw = memoryview(getattr(msg, "data", b""))
        if row_step == width * point_step:
            records = np.frombuffer(raw, dtype=dtype, count=width * height)
        else:
            rows = []
            for row in range(height):
                start = row * row_step
                stop = start + width * point_step
                rows.append(np.frombuffer(raw[start:stop], dtype=dtype, count=count_per_row))
            records = np.concatenate(rows) if rows else np.zeros((0,), dtype=dtype)

        xyz = np.empty((records.shape[0], 3), dtype=np.float32)
        xyz[:, 0] = records["x"].astype(np.float32, copy=False)
        xyz[:, 1] = records["y"].astype(np.float32, copy=False)
        xyz[:, 2] = records["z"].astype(np.float32, copy=False)
        return xyz

    def _pointcloud_dtype(self, msg):
        np = self.np
        endian = ">" if bool(getattr(msg, "is_bigendian", False)) else "<"
        type_map = {
            1: "i1",
            2: "u1",
            3: "i2",
            4: "u2",
            5: "i4",
            6: "u4",
            7: "f4",
            8: "f8",
        }
        names = []
        formats = []
        offsets = []
        for field in getattr(msg, "fields", []):
            datatype = int(getattr(field, "datatype", 0))
            if datatype not in type_map:
                continue
            name = str(getattr(field, "name", ""))
            count = max(1, int(getattr(field, "count", 1)))
            base = type_map[datatype]
            fmt = base if base.endswith("1") else endian + base
            if count > 1:
                fmt = (fmt, (count,))
            names.append(name)
            formats.append(fmt)
            offsets.append(int(getattr(field, "offset", 0)))
        for required in ("x", "y", "z"):
            if required not in names:
                raise ValueError(f"PointCloud2 field {required!r} is missing")
        return np.dtype(
            {
                "names": names,
                "formats": formats,
                "offsets": offsets,
                "itemsize": int(getattr(msg, "point_step", 0)),
            }
        )

    def forward(self, data: dict[str, Any]) -> LeadForwardResult:
        if not self.loaded:
            raise RuntimeError(self.error or "LEAD runtime is not loaded")
        torch = self.torch
        start = time.perf_counter()
        predictions = []
        with torch.inference_mode():
            autocast_enabled = self.precision_mode in {"fp16", "bf16"}
            autocast_dtype = {
                "fp16": torch.float16,
                "bf16": torch.bfloat16,
            }.get(self.precision_mode, torch.float32)
            with torch.amp.autocast(
                device_type="cuda" if self.device.type == "cuda" else "cpu",
                dtype=autocast_dtype,
                enabled=autocast_enabled,
            ):
                for net in self.nets:
                    predictions.append(net(data))
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        latency_ms = (time.perf_counter() - start) * 1000.0
        self.forward_count += 1
        self.last_latency_ms = latency_ms
        self.last_error = ""
        return self._result_from_predictions(predictions, latency_ms)

    def synthetic_forward(self) -> LeadForwardResult:
        return self.forward(self.build_synthetic_data())

    def _result_from_predictions(
        self,
        predictions: list[Any],
        latency_ms: float,
    ) -> LeadForwardResult:
        torch = self.torch
        routes = [
            prediction.pred_route
            for prediction in predictions
            if getattr(prediction, "pred_route", None) is not None
        ]
        waypoints = [
            prediction.pred_future_waypoints
            for prediction in predictions
            if getattr(prediction, "pred_future_waypoints", None) is not None
        ]
        path_tensor = None
        if routes:
            path_tensor = torch.stack([route[0] for route in routes]).mean(dim=0)
        elif waypoints:
            path_tensor = torch.stack([waypoint[0] for waypoint in waypoints]).mean(dim=0)
        path_xy = []
        if path_tensor is not None:
            for point in path_tensor.detach().cpu().float().numpy().reshape(-1, 2):
                path_xy.append((float(point[0]), float(point[1])))

        speed_tensors = [
            prediction.pred_target_speed_scalar
            for prediction in predictions
            if getattr(prediction, "pred_target_speed_scalar", None) is not None
        ]
        speed_target_mps = 0.0
        if speed_tensors:
            speed_target_mps = float(
                torch.stack([speed[0] for speed in speed_tensors]).mean().detach().cpu()
            )

        return LeadForwardResult(
            path_xy=path_xy,
            speed_target_mps=speed_target_mps,
            confidence=1.0 if path_xy else 0.2,
            latency_ms=latency_ms,
            device=str(self.device),
        )

    def _command_one_hot(self, command: str):
        one_hot = self.np.zeros((1, 6), dtype=self.np.float32)
        one_hot[0, self._command_index(command)] = 1.0
        return one_hot

    def _command_index(self, command: str) -> int:
        lookup = {
            "left": 0,
            "right": 1,
            "straight": 2,
            "lane_follow": 3,
            "lanefollow": 3,
            "change_lane_left": 4,
            "change_lane_right": 5,
        }
        return lookup.get(str(command), 3)

    def _image_msg_to_rgb_array(self, msg):
        np = self.np
        cv2 = self.cv2
        width = int(msg.width)
        height = int(msg.height)
        step = int(msg.step)
        encoding = str(msg.encoding).lower()
        raw = np.frombuffer(msg.data, dtype=np.uint8)

        if encoding == "rgb8":
            return raw.reshape(height, step)[:, : width * 3].reshape(height, width, 3)
        if encoding == "bgr8":
            bgr = raw.reshape(height, step)[:, : width * 3].reshape(height, width, 3)
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if encoding == "rgba8":
            rgba = raw.reshape(height, step)[:, : width * 4].reshape(height, width, 4)
            return cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB)
        if encoding == "bgra8":
            bgra = raw.reshape(height, step)[:, : width * 4].reshape(height, width, 4)
            return cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGB)
        if encoding in {"yuv422", "uyvy"}:
            uyvy = raw.reshape(height, step)[:, : width * 2].reshape(height, width, 2)
            return cv2.cvtColor(uyvy, cv2.COLOR_YUV2RGB_UYVY)
        if encoding in {"yuv422_yuy2", "yuyv", "yuy2"}:
            yuyv = raw.reshape(height, step)[:, : width * 2].reshape(height, width, 2)
            return cv2.cvtColor(yuyv, cv2.COLOR_YUV2RGB_YUY2)
        if encoding in {"mono8", "8uc1"}:
            gray = raw.reshape(height, step)[:, :width].reshape(height, width)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        raise ValueError(f"Unsupported image encoding for LEAD runtime: {msg.encoding}")

    def _image_msg_to_torch_rgb_tensor(self, msg):
        torch = self.torch
        width = int(msg.width)
        height = int(msg.height)
        step = int(msg.step)
        encoding = str(msg.encoding).lower()
        raw = torch.frombuffer(memoryview(msg.data), dtype=torch.uint8)

        if encoding in {"rgb8", "bgr8"}:
            packed = raw.reshape(height, step)[:, : width * 3]
            image = packed.reshape(height, width, 3).to(self.device, non_blocking=True)
            if encoding == "bgr8":
                image = image[..., [2, 1, 0]]
            return self._resize_torch_rgb_hwc(image)

        if encoding in {"rgba8", "bgra8"}:
            packed = raw.reshape(height, step)[:, : width * 4]
            image = packed.reshape(height, width, 4).to(self.device, non_blocking=True)
            if encoding == "rgba8":
                image = image[..., :3]
            else:
                image = image[..., [2, 1, 0]]
            return self._resize_torch_rgb_hwc(image)

        if encoding in {"yuv422", "uyvy", "yuv422_yuy2", "yuyv", "yuy2"}:
            packed = raw.reshape(height, step)[:, : width * 2].contiguous()
            image = packed.reshape(height, width, 2).to(self.device, non_blocking=True)
            if encoding in {"yuv422", "uyvy"}:
                return self._resize_torch_rgb_hwc(self._uyvy_to_rgb_torch(image))
            return self._resize_torch_rgb_hwc(self._yuyv_to_rgb_torch(image))

        if encoding in {"mono8", "8uc1"}:
            packed = raw.reshape(height, step)[:, :width]
            gray = packed.reshape(height, width).to(self.device, non_blocking=True)
            image = gray[..., None].expand(height, width, 3)
            return self._resize_torch_rgb_hwc(image)

        raise ValueError(f"Unsupported image encoding for LEAD runtime: {msg.encoding}")

    def _uyvy_to_rgb_torch(self, image):
        y = image[..., 1].float()
        u = image[:, 0::2, 0].repeat_interleave(2, dim=1)[:, : image.shape[1]].float()
        v = image[:, 1::2, 0].repeat_interleave(2, dim=1)[:, : image.shape[1]].float()
        return self._yuv_to_rgb_torch(y, u, v)

    def _yuyv_to_rgb_torch(self, image):
        y = image[..., 0].float()
        u = image[:, 0::2, 1].repeat_interleave(2, dim=1)[:, : image.shape[1]].float()
        v = image[:, 1::2, 1].repeat_interleave(2, dim=1)[:, : image.shape[1]].float()
        return self._yuv_to_rgb_torch(y, u, v)

    def _yuv_to_rgb_torch(self, y, u, v):
        y = (y - 16.0).clamp_(min=0.0)
        u = u - 128.0
        v = v - 128.0
        r = 1.164383 * y + 1.596027 * v
        g = 1.164383 * y - 0.391762 * u - 0.812968 * v
        b = 1.164383 * y + 2.017232 * u
        return self.torch.stack((r, g, b), dim=2).clamp_(0.0, 255.0)

    def _resize_torch_rgb_hwc(self, image):
        image_h = int(self.config.final_image_height)
        image_w = int(self.config.final_image_width)
        tensor = image.permute(2, 0, 1).unsqueeze(0).float()
        if image.shape[0] == image_h and image.shape[1] == image_w:
            return tensor.contiguous()
        return self.torch.nn.functional.interpolate(
            tensor,
            size=(image_h, image_w),
            mode="bilinear",
            align_corners=False,
            antialias=True,
        ).contiguous()
