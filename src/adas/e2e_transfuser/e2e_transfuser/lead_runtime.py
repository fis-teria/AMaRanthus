import json
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
        self.last_error = ""

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
        command: str = "lane_follow",
    ) -> dict[str, Any]:
        image = self._image_msg_to_rgb_array(image_msg)
        return self.build_data_from_arrays(
            image_rgb=image,
            speed_mps=speed_mps,
            target_xy=target_xy,
            command=command,
        )

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
        speed_mps: float = 0.0,
        target_xy: tuple[float, float] = (15.0, 0.0),
        command: str = "lane_follow",
    ) -> dict[str, Any]:
        torch = self.torch
        np = self.np
        cv2 = self.cv2
        image_h = int(self.config.final_image_height)
        image_w = int(self.config.final_image_width)
        resized = cv2.resize(image_rgb, (image_w, image_h), interpolation=cv2.INTER_AREA)
        rgb = np.transpose(resized, (2, 0, 1))[None].copy()

        lidar_h = int(self.config.lidar_height_pixel)
        lidar_w = int(self.config.lidar_width_pixel)
        rasterized_lidar = np.zeros((1, 1, lidar_h, lidar_w), dtype=np.float32)
        command_one_hot = self._command_one_hot(command)
        target = np.array([target_xy], dtype=np.float32)

        return {
            "rgb": torch.from_numpy(rgb),
            "rasterized_lidar": torch.from_numpy(rasterized_lidar),
            "speed": torch.tensor([float(speed_mps)], dtype=torch.float32),
            "command": torch.from_numpy(command_one_hot),
            "target_point": torch.from_numpy(target),
            "target_point_previous": torch.from_numpy(target),
            "target_point_next": torch.from_numpy(target),
            "iteration": torch.tensor([0], dtype=torch.long),
        }

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
        lookup = {
            "left": 0,
            "right": 1,
            "straight": 2,
            "lane_follow": 3,
            "change_lane_left": 4,
            "change_lane_right": 5,
        }
        one_hot[0, lookup.get(str(command), 3)] = 1.0
        return one_hot

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
        if encoding in {"mono8", "8uc1"}:
            gray = raw.reshape(height, step)[:, :width].reshape(height, width)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        raise ValueError(f"Unsupported image encoding for LEAD runtime: {msg.encoding}")
