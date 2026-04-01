from dataclasses import dataclass
from typing import List

from PyQt5.QtCore import QPointF


@dataclass
class DetectedObject:
    x_m: float
    y_m: float
    kind: str


@dataclass
class UiState:
    scan_points: List[QPointF]
    lane_points: List[QPointF]
    objects: List[DetectedObject]
    speed_kmh: float
    min_distance_m: float
    obstacle_count: int
    mode: str
    gps_status: str
