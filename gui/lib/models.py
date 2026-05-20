from dataclasses import dataclass, field
from typing import List, Optional

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QImage


@dataclass
class DetectedObject:
    x_m: float
    y_m: float
    kind: str


@dataclass
class PointCloudPoint:
    x_m: float
    y_m: float
    z_m: float


@dataclass
class GeoPoint:
    lat: float
    lon: float
    name: str = ""
    accuracy_m: Optional[float] = None


@dataclass
class RouteStep:
    lat: float
    lon: float
    route_index: int
    text: str
    distance_m: float = 0.0
    duration_sec: float = 0.0


@dataclass
class CameraFrame:
    image: QImage
    width: int
    height: int
    encoding: str
    frame_id: str
    stamp_sec: float
    topic: str


@dataclass
class ShadowMetrics:
    ego_speed_mps: Optional[float] = None
    ego_yaw_rate_radps: Optional[float] = None
    ego_curvature_inv_m: Optional[float] = None
    virtual_steering_rad: Optional[float] = None
    virtual_curvature_inv_m: Optional[float] = None
    virtual_warning_score: Optional[float] = None
    driver_steering_proxy_rad: Optional[float] = None
    steering_delta_rad: Optional[float] = None
    curvature_delta_inv_m: Optional[float] = None
    intervention_score: Optional[float] = None
    summary: str = "--"


@dataclass
class UiState:
    scan_points: List[QPointF]
    lane_points: List[QPointF]
    pointcloud_points: List[PointCloudPoint]
    objects: List[DetectedObject]
    speed_kmh: float
    min_distance_m: float
    obstacle_count: int
    mode: str
    gps_status: str
    shadow: ShadowMetrics = field(default_factory=ShadowMetrics)
    camera_frame: Optional[CameraFrame] = None
    phone_current: Optional[GeoPoint] = None
    phone_goal: Optional[GeoPoint] = None
    phone_route_points: List[GeoPoint] = field(default_factory=list)
    phone_route_steps: List[RouteStep] = field(default_factory=list)
