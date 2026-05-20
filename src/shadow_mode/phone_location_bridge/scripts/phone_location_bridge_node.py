#!/usr/bin/env python3
import json
import math
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, unquote, urlparse
from urllib.request import Request, urlopen

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import String


EARTH_M_PER_DEG = 111_320.0
GOOGLE_MAPS_USER_AGENT = "Mozilla/5.0 phone_location_bridge"
OSRM_SERVICE_URL = "https://routing.openstreetmap.de/routed-car/route/v1/driving"
URL_COORD_RE = r"(-?\d+(?:\.\d+)?)"


@dataclass
class GeoPoint:
    lat: float
    lon: float
    accuracy_m: Optional[float] = None
    heading_deg: Optional[float] = None
    name: str = ""
    updated_sec: float = 0.0


class BridgeState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.current: Optional[GeoPoint] = None
        self.goal: Optional[GeoPoint] = None
        self.route_options: list[dict[str, Any]] = []
        self.selected_route_index: int = -1
        self.route_warning: str = ""
        self.route_request_options: dict[str, Any] = {
            "alternatives": 3,
            "avoid_motorway": False,
            "avoid_toll": False,
            "avoid_ferry": False,
        }
        self.off_route_since_sec: Optional[float] = None
        self.last_reroute_sec: float = 0.0
        self.last_route_distance_m: Optional[float] = None
        self.auto_reroute_count: int = 0
        self.last_reroute_reason: str = ""
        self.last_client: str = ""
        self.last_error: str = ""

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "current": self._point_to_dict(self.current),
                "goal": self._point_to_dict(self.goal),
                "route_options": self._route_options_summary(),
                "selected_route_index": self.selected_route_index,
                "selected_route": self._selected_route_payload(),
                "route_warning": self.route_warning,
                "reroute": self._reroute_status(),
                "last_client": self.last_client,
                "last_error": self.last_error,
            }

    @staticmethod
    def _point_to_dict(point: Optional[GeoPoint]) -> Optional[dict[str, Any]]:
        if point is None:
            return None
        return {
            "lat": point.lat,
            "lon": point.lon,
            "accuracy_m": point.accuracy_m,
            "heading_deg": point.heading_deg,
            "name": point.name,
            "updated_sec": point.updated_sec,
            "age_sec": max(0.0, time.time() - point.updated_sec),
        }

    def selected_route(self) -> Optional[dict[str, Any]]:
        if 0 <= self.selected_route_index < len(self.route_options):
            return self.route_options[self.selected_route_index]
        return None

    def _route_options_summary(self) -> list[dict[str, Any]]:
        summaries = []
        for route in self.route_options:
            summaries.append(
                {
                    "index": route.get("index"),
                    "distance_m": route.get("distance_m"),
                    "duration_sec": route.get("duration_sec"),
                    "geometry_points": len(route.get("geometry", [])),
                    "constraints": route.get("constraints", {}),
                }
            )
        return summaries

    def _selected_route_payload(self) -> Optional[dict[str, Any]]:
        route = self.selected_route()
        if route is None:
            return None
        return {
            "index": route.get("index"),
            "distance_m": route.get("distance_m"),
            "duration_sec": route.get("duration_sec"),
            "geometry": route.get("geometry", []),
            "guidance_steps": route.get("guidance_steps", []),
            "constraints": route.get("constraints", {}),
        }

    def _reroute_status(self) -> dict[str, Any]:
        return {
            "off_route_since_sec": self.off_route_since_sec,
            "last_reroute_sec": self.last_reroute_sec,
            "last_route_distance_m": self.last_route_distance_m,
            "auto_reroute_count": self.auto_reroute_count,
            "last_reroute_reason": self.last_reroute_reason,
            "route_request_options": dict(self.route_request_options),
        }


class PhoneLocationBridge(Node):
    def __init__(self) -> None:
        super().__init__("phone_location_bridge")
        self.server_host = self.declare_parameter("server_host", "0.0.0.0").value
        self.server_port = int(self.declare_parameter("server_port", 8765).value)
        self.use_https = bool(self.declare_parameter("use_https", False).value)
        self.tls_cert_file = self.declare_parameter("tls_cert_file", "").value
        self.tls_key_file = self.declare_parameter("tls_key_file", "").value
        self.osrm_service_url = self.declare_parameter(
            "osrm_service_url", OSRM_SERVICE_URL
        ).value.rstrip("/")
        self.publish_rate_hz = float(self.declare_parameter("publish_rate_hz", 5.0).value)
        self.fix_topic = self.declare_parameter("fix_topic", "/phone/gps/fix").value
        self.goal_topic = self.declare_parameter("goal_topic", "/phone/route/goal").value
        self.route_path_topic = self.declare_parameter(
            "route_path_topic", "/shadow/route/gui_path"
        ).value
        self.gps_status_topic = self.declare_parameter(
            "gps_status_topic", "/vehicle/gps_status"
        ).value
        self.status_topic = self.declare_parameter(
            "status_topic", "/phone/location/status"
        ).value
        self.route_frame_id = self.declare_parameter("route_frame_id", "base_link").value
        self.path_step_m = max(0.5, float(self.declare_parameter("path_step_m", 2.0).value))
        self.max_path_length_m = max(
            1.0, float(self.declare_parameter("max_path_length_m", 200.0).value)
        )
        self.default_heading_deg = float(
            self.declare_parameter("default_heading_deg", 0.0).value
        )
        self.assume_heading_to_goal = bool(
            self.declare_parameter("assume_heading_to_goal", True).value
        )
        self.route_command_topic = self.declare_parameter(
            "route_command_topic", "/shadow/route/command"
        ).value
        self.route_command = self.declare_parameter("route_command", "lane_follow").value
        self.auto_reroute_enabled = bool(
            self.declare_parameter("auto_reroute_enabled", True).value
        )
        self.off_route_threshold_m = max(
            1.0, float(self.declare_parameter("off_route_threshold_m", 30.0).value)
        )
        self.off_route_hold_sec = max(
            0.0, float(self.declare_parameter("off_route_hold_sec", 3.0).value)
        )
        self.reroute_cooldown_sec = max(
            0.0, float(self.declare_parameter("reroute_cooldown_sec", 10.0).value)
        )

        self.state = BridgeState()
        self.fix_pub = self.create_publisher(NavSatFix, self.fix_topic, 10)
        self.goal_pub = self.create_publisher(String, self.goal_topic, 10)
        self.path_pub = self.create_publisher(Path, self.route_path_topic, 10)
        self.gps_status_pub = self.create_publisher(String, self.gps_status_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.command_pub = self.create_publisher(String, self.route_command_topic, 10)

        period = 1.0 / max(0.1, self.publish_rate_hz)
        self.timer = self.create_timer(period, self._publish_latest)
        self.httpd: Optional[ThreadingHTTPServer] = None
        self.http_thread: Optional[threading.Thread] = None
        self._start_http_server()

    def destroy_node(self) -> bool:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.http_thread is not None:
            self.http_thread.join(timeout=2.0)
            self.http_thread = None
        return super().destroy_node()

    def _start_http_server(self) -> None:
        handler = self._make_handler()
        self.httpd = ThreadingHTTPServer((self.server_host, self.server_port), handler)
        scheme = "http"
        if self.use_https:
            if not self.tls_cert_file or not self.tls_key_file:
                raise RuntimeError("use_https=true requires tls_cert_file and tls_key_file")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=self.tls_cert_file, keyfile=self.tls_key_file)
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
            scheme = "https"
        self.http_thread = threading.Thread(
            target=self.httpd.serve_forever,
            name=f"phone_location_{scheme}",
            daemon=True,
        )
        self.http_thread.start()
        urls = ", ".join(f"{scheme}://{addr}:{self.server_port}/" for addr in self._local_ips())
        self.get_logger().info(
            f"phone_location_bridge serving {scheme.upper()} on "
            f"{self.server_host}:{self.server_port}; "
            f"try {urls or f'{scheme}://<pc-ip>:{self.server_port}/'}"
        )

    def _local_ips(self) -> list[str]:
        ips = []
        try:
            host = socket.gethostname()
            for item in socket.getaddrinfo(host, None, family=socket.AF_INET):
                ip = item[4][0]
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except OSError:
            pass
        return ips

    def _make_handler(self):
        node = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if self.path in ("/", "/index.html"):
                    self._send_html(PHONE_HTML)
                    return
                if self.path == "/api/state":
                    self._send_json(node.state.snapshot())
                    return
                self.send_error(404)

            def do_POST(self) -> None:
                try:
                    payload = self._read_json()
                    if self.path == "/api/location":
                        point = node._parse_point(payload, default_name="phone")
                        with node.state.lock:
                            node.state.current = point
                            node.state.last_client = self.client_address[0]
                            node.state.last_error = ""
                        reroute = node._maybe_auto_reroute(point)
                        self._send_json(
                            {
                                "ok": True,
                                "current": node.state._point_to_dict(point),
                                "reroute": reroute,
                            }
                        )
                        return
                    if self.path == "/api/goal":
                        point = node._parse_point(payload, default_name="goal")
                        with node.state.lock:
                            node.state.goal = point
                            node.state.last_client = self.client_address[0]
                            node.state.last_error = ""
                        self._send_json({"ok": True, "goal": node.state._point_to_dict(point)})
                        return
                    if self.path == "/api/goal_url":
                        goal, meta = node._parse_goal_url(payload)
                        with node.state.lock:
                            node.state.goal = goal
                            node.state.last_client = self.client_address[0]
                            node.state.last_error = ""
                        self._send_json(
                            {
                                "ok": True,
                                "goal": node.state._point_to_dict(goal),
                                "url": meta,
                            }
                        )
                        return
                    if self.path == "/api/osrm_routes":
                        routes, warning, request_options = node._fetch_osrm_routes(payload)
                        with node.state.lock:
                            node.state.route_options = routes
                            node.state.selected_route_index = 0 if routes else -1
                            node.state.route_warning = warning
                            node.state.route_request_options = request_options
                            node.state.off_route_since_sec = None
                            node.state.last_route_distance_m = None
                            node.state.last_client = self.client_address[0]
                            node.state.last_error = ""
                        self._send_json(
                            {
                                "ok": True,
                                "routes": node.state._route_options_summary(),
                                "selected_route_index": node.state.selected_route_index,
                                "warning": warning,
                            }
                        )
                        return
                    if self.path == "/api/select_route":
                        selected_index = int(payload.get("index", 0))
                        with node.state.lock:
                            if not 0 <= selected_index < len(node.state.route_options):
                                raise ValueError("route index out of range")
                            node.state.selected_route_index = selected_index
                            node.state.last_client = self.client_address[0]
                            node.state.last_error = ""
                        self._send_json({"ok": True, "state": node.state.snapshot()})
                        return
                    if self.path == "/api/route":
                        current_payload = payload.get("current")
                        goal_payload = payload.get("goal")
                        current = (
                            node._parse_point(current_payload, default_name="phone")
                            if isinstance(current_payload, dict)
                            else None
                        )
                        goal = (
                            node._parse_point(goal_payload, default_name="goal")
                            if isinstance(goal_payload, dict)
                            else None
                        )
                        with node.state.lock:
                            if current is not None:
                                node.state.current = current
                            if goal is not None:
                                node.state.goal = goal
                            node.state.last_client = self.client_address[0]
                            node.state.last_error = ""
                        self._send_json({"ok": True, "state": node.state.snapshot()})
                        return
                    self.send_error(404)
                except Exception as exc:
                    with node.state.lock:
                        node.state.last_error = f"{type(exc).__name__}: {exc}"
                    self._send_json({"ok": False, "error": str(exc)}, status=400)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object")
                return payload

            def _send_html(self, body: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler

    def _parse_point(self, payload: dict[str, Any], *, default_name: str) -> GeoPoint:
        lat = float(payload["lat"])
        lon = float(payload["lon"])
        if not math.isfinite(lat) or not math.isfinite(lon):
            raise ValueError("lat/lon must be finite")
        if abs(lat) > 90.0 or abs(lon) > 180.0:
            raise ValueError("lat/lon out of range")

        accuracy = self._optional_float(payload.get("accuracy_m", payload.get("accuracy")))
        heading = self._optional_float(payload.get("heading_deg", payload.get("heading")))
        name = str(payload.get("name") or default_name)
        return GeoPoint(
            lat=lat,
            lon=lon,
            accuracy_m=accuracy,
            heading_deg=heading,
            name=name,
            updated_sec=time.time(),
        )

    def _parse_goal_url(self, payload: dict[str, Any]) -> tuple[GeoPoint, dict[str, Any]]:
        raw_url = str(payload.get("url", "")).strip()
        if not raw_url:
            raise ValueError("url is required")
        name_hint = str(payload.get("name", "")).strip()

        expanded_url = raw_url
        source = "input"
        coords = self._extract_coords_from_url(expanded_url)
        if coords is None:
            expanded_url = self._expand_url(raw_url)
            source = "expanded"
            coords = self._extract_coords_from_url(expanded_url)
        if coords is None:
            raise ValueError("Could not find lat/lon in the Google Maps URL")

        lat, lon, coord_source = coords
        name = name_hint or self._extract_name_from_url(expanded_url) or "goal"
        goal = self._parse_point(
            {
                "lat": lat,
                "lon": lon,
                "name": name,
            },
            default_name="goal",
        )
        return goal, {
            "input_url": raw_url,
            "expanded_url": expanded_url,
            "source": source,
            "coordinate_source": coord_source,
        }

    def _fetch_osrm_routes(
        self, payload: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        with self.state.lock:
            current = self.state.current
            goal = self.state.goal

        if isinstance(payload.get("current"), dict):
            current = self._parse_point(payload["current"], default_name="phone")
        if isinstance(payload.get("goal"), dict):
            goal = self._parse_point(payload["goal"], default_name="goal")
        if current is None or goal is None:
            raise ValueError("current and goal are required before route search")

        alternatives = int(payload.get("alternatives", 3))
        alternatives = max(1, min(3, alternatives))
        constraints = {
            "avoid_motorway": bool(payload.get("avoid_motorway", False)),
            "avoid_toll": bool(payload.get("avoid_toll", False)),
            "avoid_ferry": bool(payload.get("avoid_ferry", False)),
        }
        request_options = {"alternatives": alternatives, **constraints}
        excludes = []
        if constraints["avoid_motorway"]:
            excludes.append("motorway")
        if constraints["avoid_toll"]:
            excludes.append("toll")
        if constraints["avoid_ferry"]:
            excludes.append("ferry")

        warning = ""
        try:
            osrm_payload = self._request_osrm(current, goal, alternatives, excludes)
            constraints_applied = True
        except HTTPError as exc:
            if not excludes:
                raise
            warning = (
                f"OSRM endpoint rejected exclude={','.join(excludes)} "
                f"({exc.code}); retried without excludes."
            )
            osrm_payload = self._request_osrm(current, goal, alternatives, [])
            constraints_applied = False
        except URLError as exc:
            raise ValueError(f"OSRM request failed: {exc}") from exc

        routes = []
        for index, route in enumerate(osrm_payload.get("routes", [])):
            coordinates = (
                route.get("geometry", {}).get("coordinates", [])
                if isinstance(route.get("geometry"), dict)
                else []
            )
            geometry = []
            for coord in coordinates:
                if not isinstance(coord, list) or len(coord) < 2:
                    continue
                lon = float(coord[0])
                lat = float(coord[1])
                if self._coords_in_range(lat, lon):
                    geometry.append({"lat": lat, "lon": lon})
            if not geometry:
                continue
            guidance_steps = self._extract_guidance_steps(route, geometry)
            route_constraints = dict(constraints)
            route_constraints["exclude_requested"] = excludes
            route_constraints["exclude_applied"] = constraints_applied
            routes.append(
                {
                    "index": index,
                    "distance_m": float(route.get("distance", 0.0)),
                    "duration_sec": float(route.get("duration", 0.0)),
                    "geometry": geometry,
                    "guidance_steps": guidance_steps,
                    "constraints": route_constraints,
                }
            )

        if not routes:
            raise ValueError("OSRM returned no usable routes")
        with self.state.lock:
            self.state.current = current
            self.state.goal = goal
        return routes, warning, request_options

    def _maybe_auto_reroute(self, current: GeoPoint) -> dict[str, Any]:
        if not self.auto_reroute_enabled:
            return {"enabled": False, "action": "disabled"}

        now = time.time()
        with self.state.lock:
            goal = self.state.goal
            selected_route = self.state.selected_route()
            request_options = dict(self.state.route_request_options)

        if goal is None or selected_route is None:
            return {"enabled": True, "action": "no_route"}

        distance_m = self._distance_to_route_m(current, selected_route)
        with self.state.lock:
            self.state.last_route_distance_m = distance_m
            if distance_m <= self.off_route_threshold_m:
                self.state.off_route_since_sec = None
                self.state.last_reroute_reason = "on_route"
                return {
                    "enabled": True,
                    "action": "on_route",
                    "distance_m": distance_m,
                    "threshold_m": self.off_route_threshold_m,
                }
            if self.state.off_route_since_sec is None:
                self.state.off_route_since_sec = now
            off_route_age = now - self.state.off_route_since_sec
            cooldown_age = now - self.state.last_reroute_sec

        if off_route_age < self.off_route_hold_sec:
            return {
                "enabled": True,
                "action": "waiting",
                "distance_m": distance_m,
                "off_route_age_sec": off_route_age,
                "threshold_m": self.off_route_threshold_m,
            }
        if cooldown_age < self.reroute_cooldown_sec:
            return {
                "enabled": True,
                "action": "cooldown",
                "distance_m": distance_m,
                "cooldown_age_sec": cooldown_age,
                "threshold_m": self.off_route_threshold_m,
            }

        payload = {"current": self._point_payload(current), "goal": self._point_payload(goal)}
        payload.update(request_options)
        routes, warning, normalized_options = self._fetch_osrm_routes(payload)
        with self.state.lock:
            self.state.route_options = routes
            self.state.selected_route_index = 0 if routes else -1
            self.state.route_warning = warning
            self.state.route_request_options = normalized_options
            self.state.off_route_since_sec = None
            self.state.last_reroute_sec = now
            self.state.auto_reroute_count += 1
            self.state.last_reroute_reason = (
                f"off_route distance={distance_m:.1f}m threshold={self.off_route_threshold_m:.1f}m"
            )
        self.get_logger().info(
            "auto rerouted via OSRM: "
            f"distance={distance_m:.1f}m routes={len(routes)} warning={warning or 'none'}"
        )
        return {
            "enabled": True,
            "action": "rerouted",
            "distance_m": distance_m,
            "routes": len(routes),
            "warning": warning,
        }

    @staticmethod
    def _point_payload(point: GeoPoint) -> dict[str, Any]:
        return {
            "lat": point.lat,
            "lon": point.lon,
            "accuracy_m": point.accuracy_m,
            "heading_deg": point.heading_deg,
            "name": point.name,
        }

    def _distance_to_route_m(self, current: GeoPoint, route: dict[str, Any]) -> float:
        geometry = route.get("geometry", [])
        points: list[tuple[float, float]] = []
        for item in geometry:
            try:
                target = GeoPoint(lat=float(item["lat"]), lon=float(item["lon"]))
            except (KeyError, TypeError, ValueError):
                continue
            points.append(self._enu_delta_m(current, target))
        if not points:
            return float("inf")
        if len(points) == 1:
            return math.hypot(points[0][0], points[0][1])

        best = float("inf")
        for start, end in zip(points, points[1:]):
            best = min(best, self._point_segment_distance_m(0.0, 0.0, start, end))
        return best

    @staticmethod
    def _point_segment_distance_m(
        px: float,
        py: float,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> float:
        ax, ay = start
        bx, by = end
        dx = bx - ax
        dy = by - ay
        denom = dx * dx + dy * dy
        if denom <= 1e-9:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        closest_x = ax + t * dx
        closest_y = ay + t * dy
        return math.hypot(px - closest_x, py - closest_y)

    def _request_osrm(
        self,
        current: GeoPoint,
        goal: GeoPoint,
        alternatives: int,
        excludes: list[str],
    ) -> dict[str, Any]:
        coords = f"{current.lon:.8f},{current.lat:.8f};{goal.lon:.8f},{goal.lat:.8f}"
        query: dict[str, str] = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "alternatives": str(alternatives) if alternatives > 1 else "false",
        }
        if excludes:
            query["exclude"] = ",".join(excludes)
        url = f"{self.osrm_service_url}/{coords}?{urlencode(query)}"
        request = Request(url, headers={"User-Agent": GOOGLE_MAPS_USER_AGENT})
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != "Ok":
            raise ValueError(f"OSRM returned code={payload.get('code')}")
        return payload

    def _extract_guidance_steps(
        self, route: dict[str, Any], geometry: list[dict[str, float]]
    ) -> list[dict[str, Any]]:
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                location = maneuver.get("location", [])
                if not isinstance(location, list) or len(location) < 2:
                    continue
                try:
                    lon = float(location[0])
                    lat = float(location[1])
                except (TypeError, ValueError):
                    continue
                if not self._coords_in_range(lat, lon):
                    continue
                route_index = self._nearest_geometry_index(lat, lon, geometry)
                steps.append(
                    {
                        "lat": lat,
                        "lon": lon,
                        "route_index": route_index,
                        "type": str(maneuver.get("type", "")),
                        "modifier": str(maneuver.get("modifier", "")),
                        "name": str(step.get("name", "")),
                        "ref": str(step.get("ref", "")),
                        "destinations": str(step.get("destinations", "")),
                        "distance_m": float(step.get("distance", 0.0)),
                        "duration_sec": float(step.get("duration", 0.0)),
                        "text": self._instruction_text(step),
                    }
                )
        return steps

    def _nearest_geometry_index(
        self, lat: float, lon: float, geometry: list[dict[str, float]]
    ) -> int:
        best_index = 0
        best_distance = float("inf")
        probe = GeoPoint(lat=lat, lon=lon)
        for index, point in enumerate(geometry):
            east_m, north_m = self._enu_delta_m(
                probe,
                GeoPoint(lat=float(point["lat"]), lon=float(point["lon"])),
            )
            distance = east_m * east_m + north_m * north_m
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def _instruction_text(self, step: dict[str, Any]) -> str:
        maneuver = step.get("maneuver", {})
        maneuver_type = str(maneuver.get("type", ""))
        modifier = str(maneuver.get("modifier", ""))
        label = self._step_label(step)
        direction = self._modifier_text(modifier)
        turn_action = self._turn_action_text(modifier)

        if maneuver_type == "depart":
            return f"{label}から出発" if label else "出発"
        if maneuver_type == "arrive":
            return "目的地に到着"
        if maneuver_type in ("turn", "end of road"):
            if turn_action:
                return f"{label}へ{turn_action}" if label else f"次の交差点を{turn_action}"
            return f"{label}へ進む" if label else "次の交差点を曲がる"
        if maneuver_type in ("new name", "continue"):
            return f"{label}を直進" if label else "直進"
        if maneuver_type in ("merge", "on ramp", "off ramp", "fork"):
            if label and direction:
                return f"{label}方面へ{direction}に進む"
            if label:
                return f"{label}方面へ進む"
            return f"{direction}に進む" if direction else "分岐を進む"
        if maneuver_type == "roundabout":
            return f"ラウンドアバウトを{direction}方向へ進む" if direction else "ラウンドアバウトを進む"
        if turn_action:
            return f"{label}へ{turn_action}" if label else f"次の交差点を{turn_action}"
        if direction:
            return f"{label}方面へ{direction}に進む" if label else f"{direction}に進む"
        return label or "道なりに進む"

    def _step_label(self, step: dict[str, Any]) -> str:
        name = self._clean_osrm_text(step.get("name", ""))
        ref = self._clean_osrm_text(step.get("ref", ""))
        destinations = self._clean_osrm_text(step.get("destinations", ""))
        exits = self._clean_osrm_text(step.get("exits", ""))

        if destinations:
            return destinations
        if name and ref and ref not in name:
            return f"{ref} {name}"
        if name:
            return name
        if ref:
            return ref
        if exits:
            return exits
        return ""

    @staticmethod
    def _modifier_text(modifier: str) -> str:
        return {
            "left": "左",
            "slight left": "斜め左",
            "sharp left": "大きく左",
            "right": "右",
            "slight right": "斜め右",
            "sharp right": "大きく右",
            "straight": "直進",
            "uturn": "Uターン",
        }.get(modifier, "")

    @staticmethod
    def _turn_action_text(modifier: str) -> str:
        return {
            "left": "左折",
            "right": "右折",
            "sharp left": "大きく左折",
            "sharp right": "大きく右折",
            "slight left": "斜め左へ進む",
            "slight right": "斜め右へ進む",
            "uturn": "Uターン",
        }.get(modifier, "")

    @staticmethod
    def _clean_osrm_text(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = text.replace(";", " / ").replace(",", " / ")
        text = re.sub(r"\s+", " ", text)
        return text.strip(" /")

    def _expand_url(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": GOOGLE_MAPS_USER_AGENT})
        with urlopen(request, timeout=8.0) as response:
            return response.geturl()

    def _extract_coords_from_url(self, url: str) -> Optional[tuple[float, float, str]]:
        decoded_url = unquote(url)
        patterns = [
            (rf"!3d{URL_COORD_RE}!4d{URL_COORD_RE}", "place_3d4d"),
            (rf"/@{URL_COORD_RE},{URL_COORD_RE}", "map_center"),
        ]
        for pattern, source in patterns:
            match = re.search(pattern, decoded_url)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if self._coords_in_range(lat, lon):
                    return lat, lon, source

        parsed = urlparse(decoded_url)
        query_values = parse_qs(parsed.query)
        for key in ("destination", "query", "q", "daddr", "ll"):
            for value in query_values.get(key, []):
                coords = self._extract_coords_from_text(value)
                if coords is not None:
                    lat, lon = coords
                    return lat, lon, f"query_{key}"

        return None

    def _extract_coords_from_text(self, text: str) -> Optional[tuple[float, float]]:
        text = unquote(str(text)).strip()
        loc_match = re.search(rf"loc:{URL_COORD_RE},{URL_COORD_RE}", text)
        if loc_match:
            lat = float(loc_match.group(1))
            lon = float(loc_match.group(2))
            if self._coords_in_range(lat, lon):
                return lat, lon

        coord_match = re.search(rf"(?<!\d){URL_COORD_RE}\s*,\s*{URL_COORD_RE}(?!\d)", text)
        if coord_match:
            lat = float(coord_match.group(1))
            lon = float(coord_match.group(2))
            if self._coords_in_range(lat, lon):
                return lat, lon
        return None

    def _extract_name_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        try:
            place_index = parts.index("place")
        except ValueError:
            return ""
        if place_index + 1 >= len(parts):
            return ""
        return unquote(parts[place_index + 1]).replace("+", " ").strip()

    @staticmethod
    def _coords_in_range(lat: float, lon: float) -> bool:
        return math.isfinite(lat) and math.isfinite(lon) and abs(lat) <= 90.0 and abs(lon) <= 180.0

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        converted = float(value)
        return converted if math.isfinite(converted) else None

    def _publish_latest(self) -> None:
        with self.state.lock:
            current = self.state.current
            goal = self.state.goal
            selected_route = self.state.selected_route()
            snapshot = self.state.snapshot()

        now = self.get_clock().now().to_msg()
        if current is not None:
            self.fix_pub.publish(self._build_fix(current, now))
            age = max(0.0, time.time() - current.updated_sec)
            self.gps_status_pub.publish(String(data=f"FIX phone age={age:.1f}s"))
        else:
            self.gps_status_pub.publish(String(data="NO_FIX phone"))

        route_meta = self._route_meta(current, goal, selected_route)
        if goal is not None:
            self.goal_pub.publish(String(data=json.dumps(route_meta, sort_keys=True)))
        if current is not None and goal is not None:
            path = self._build_path(current, goal, now, route_meta, selected_route)
            if path.poses:
                self.path_pub.publish(path)
                self.command_pub.publish(String(data=str(self.route_command)))

        snapshot["route"] = route_meta
        self.status_pub.publish(String(data=json.dumps(snapshot, sort_keys=True)))

    def _build_fix(self, point: GeoPoint, stamp) -> NavSatFix:
        msg = NavSatFix()
        msg.header.stamp = stamp
        msg.header.frame_id = "phone_gps"
        msg.status.status = NavSatStatus.STATUS_FIX
        msg.status.service = NavSatStatus.SERVICE_GPS
        msg.latitude = point.lat
        msg.longitude = point.lon
        msg.altitude = float("nan")
        if point.accuracy_m is not None:
            variance = max(0.0, point.accuracy_m) ** 2
            msg.position_covariance = [variance, 0.0, 0.0, 0.0, variance, 0.0, 0.0, 0.0, variance]
            msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_APPROXIMATED
        else:
            msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_UNKNOWN
        return msg

    def _route_meta(
        self,
        current: Optional[GeoPoint],
        goal: Optional[GeoPoint],
        selected_route: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload = {
            "current": BridgeState._point_to_dict(current),
            "goal": BridgeState._point_to_dict(goal),
            "frame_id": self.route_frame_id,
            "available": current is not None and goal is not None,
        }
        if current is None or goal is None:
            return payload

        east_m, north_m = self._enu_delta_m(current, goal)
        distance_m = math.hypot(east_m, north_m)
        bearing_deg = self._bearing_deg(east_m, north_m)
        heading_deg, heading_source = self._route_heading(current, bearing_deg)
        x_m, y_m = self._base_link_xy(east_m, north_m, heading_deg)
        payload.update(
            {
                "distance_m": distance_m,
                "bearing_deg": bearing_deg,
                "heading_deg": heading_deg,
                "heading_source": heading_source,
                "target_x_m": x_m,
                "target_y_m": y_m,
                "path_source": "osrm" if selected_route else "straight",
            }
        )
        if selected_route:
            payload["selected_route_index"] = selected_route.get("index")
            payload["route_distance_m"] = selected_route.get("distance_m")
            payload["route_duration_sec"] = selected_route.get("duration_sec")
            payload["route_constraints"] = selected_route.get("constraints", {})
        return payload

    def _build_path(
        self,
        current: GeoPoint,
        goal: GeoPoint,
        stamp,
        meta: dict[str, Any],
        selected_route: Optional[dict[str, Any]] = None,
    ) -> Path:
        path = Path()
        path.header.stamp = stamp
        path.header.frame_id = self.route_frame_id
        if selected_route:
            route_path = self._build_route_geometry_path(current, stamp, meta, selected_route)
            if route_path.poses:
                return route_path

        x_m = float(meta.get("target_x_m", 0.0))
        y_m = float(meta.get("target_y_m", 0.0))
        distance_m = math.hypot(x_m, y_m)
        if distance_m < 0.5:
            return path
        clipped_distance = min(distance_m, self.max_path_length_m)
        scale = clipped_distance / max(distance_m, 1e-6)
        steps = max(1, int(math.ceil(clipped_distance / self.path_step_m)))
        for index in range(steps + 1):
            ratio = index / steps
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = x_m * scale * ratio
            pose.pose.position.y = y_m * scale * ratio
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        return path

    def _build_route_geometry_path(
        self,
        current: GeoPoint,
        stamp,
        meta: dict[str, Any],
        selected_route: dict[str, Any],
    ) -> Path:
        path = Path()
        path.header.stamp = stamp
        path.header.frame_id = self.route_frame_id
        heading_deg = float(meta.get("heading_deg", self.default_heading_deg))
        total_length = 0.0
        previous_xy: Optional[tuple[float, float]] = None
        path.poses.append(self._pose(0.0, 0.0, path.header))
        for point in selected_route.get("geometry", []):
            try:
                lat = float(point["lat"])
                lon = float(point["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            east_m, north_m = self._enu_delta_m(current, GeoPoint(lat=lat, lon=lon))
            x_m, y_m = self._base_link_xy(east_m, north_m, heading_deg)
            if x_m < -5.0:
                continue
            current_xy = (x_m, y_m)
            if previous_xy is not None:
                total_length += math.hypot(
                    current_xy[0] - previous_xy[0],
                    current_xy[1] - previous_xy[1],
                )
                if total_length > self.max_path_length_m:
                    break
            if not path.poses or math.hypot(
                x_m - path.poses[-1].pose.position.x,
                y_m - path.poses[-1].pose.position.y,
            ) >= self.path_step_m:
                path.poses.append(self._pose(x_m, y_m, path.header))
            previous_xy = current_xy
        return path

    def _pose(self, x_m: float, y_m: float, header) -> PoseStamped:
        pose = PoseStamped()
        pose.header = header
        pose.pose.position.x = x_m
        pose.pose.position.y = y_m
        pose.pose.position.z = 0.0
        pose.pose.orientation.w = 1.0
        return pose

    def _route_heading(self, current: GeoPoint, bearing_deg: float) -> tuple[float, str]:
        if self.assume_heading_to_goal:
            return bearing_deg, "goal_bearing"
        if current.heading_deg is not None:
            return current.heading_deg, "phone"
        return self.default_heading_deg, "default"

    @staticmethod
    def _enu_delta_m(origin: GeoPoint, target: GeoPoint) -> tuple[float, float]:
        mean_lat = math.radians((origin.lat + target.lat) * 0.5)
        north_m = (target.lat - origin.lat) * EARTH_M_PER_DEG
        east_m = (target.lon - origin.lon) * EARTH_M_PER_DEG * math.cos(mean_lat)
        return east_m, north_m

    @staticmethod
    def _bearing_deg(east_m: float, north_m: float) -> float:
        return (math.degrees(math.atan2(east_m, north_m)) + 360.0) % 360.0

    @staticmethod
    def _base_link_xy(east_m: float, north_m: float, heading_deg: float) -> tuple[float, float]:
        heading_rad = math.radians(heading_deg)
        forward_m = north_m * math.cos(heading_rad) + east_m * math.sin(heading_rad)
        left_m = north_m * math.sin(heading_rad) - east_m * math.cos(heading_rad)
        return forward_m, left_m


PHONE_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phone Location Bridge</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #020814;
      --panel: rgba(4, 17, 38, 0.92);
      --line: rgba(34, 156, 255, 0.64);
      --line-soft: rgba(64, 146, 255, 0.28);
      --cyan: #00d5ff;
      --blue: #1677ff;
      --violet: #7837ff;
      --green: #18f5a2;
      --text: #f3f7ff;
      --muted: #91a4c4;
      --shadow: 0 0 28px rgba(0, 153, 255, 0.25);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 14% 0%, rgba(16, 125, 255, 0.25), transparent 34%),
        radial-gradient(circle at 88% 18%, rgba(116, 53, 255, 0.18), transparent 30%),
        linear-gradient(135deg, #01040b 0%, #041225 48%, #020711 100%);
      color: var(--text);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(35, 132, 255, 0.08) 1px, transparent 1px),
        linear-gradient(90deg, rgba(35, 132, 255, 0.08) 1px, transparent 1px);
      background-size: 42px 42px;
      mask-image: radial-gradient(circle at center, black, transparent 76%);
    }
    main {
      width: min(1180px, 100%);
      margin: 0 auto;
      padding: 22px;
      position: relative;
    }
    .shell {
      border: 1px solid rgba(25, 125, 255, 0.62);
      border-radius: 20px;
      padding: 28px;
      background: rgba(1, 8, 20, 0.78);
      box-shadow: inset 0 0 80px rgba(0, 153, 255, 0.08), 0 0 50px rgba(0, 0, 0, 0.45);
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 24px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 18px;
      min-width: 0;
    }
    .brand > div:last-child {
      min-width: 0;
    }
    .brand-mark {
      width: 82px;
      height: 82px;
      display: grid;
      place-items: center;
      position: relative;
      color: var(--cyan);
      border-radius: 50%;
      background: radial-gradient(circle, rgba(0, 213, 255, 0.25), rgba(17, 82, 255, 0.08) 52%, transparent 70%);
      box-shadow: 0 0 26px rgba(0, 160, 255, 0.55);
    }
    .brand-mark::before, .brand-mark::after {
      content: "";
      position: absolute;
      inset: 8px;
      border-radius: 50%;
      border: 1px dashed rgba(0, 213, 255, 0.65);
    }
    .brand-mark::after {
      inset: 18px;
      border-style: solid;
      opacity: 0.55;
    }
    .pin {
      width: 28px;
      height: 28px;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      background: linear-gradient(135deg, #14e6ff, #1769ff);
      box-shadow: 0 0 18px rgba(0, 213, 255, 0.85);
      position: relative;
      z-index: 1;
    }
    .pin::after {
      content: "";
      position: absolute;
      inset: 8px;
      border-radius: 50%;
      background: #021124;
    }
    h1 {
      margin: 0;
      font-size: clamp(24px, 3vw, 34px);
      letter-spacing: 0;
      line-height: 1.05;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }
    .subtitle {
      color: #c2d4f2;
      margin-top: 8px;
      font-size: 15px;
    }
    .connection {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .status-pill, .gear {
      border: 1px solid rgba(30, 157, 255, 0.72);
      background: rgba(4, 20, 45, 0.86);
      border-radius: 8px;
      min-height: 52px;
      padding: 0 20px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: inset 0 0 26px rgba(10, 86, 180, 0.15);
    }
    .gear {
      width: 54px;
      justify-content: center;
      padding: 0;
      color: #80c6ff;
      font-size: 24px;
    }
    .dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 14px var(--green);
      flex: none;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(320px, 0.95fr) minmax(360px, 1.15fr);
      gap: 22px;
      align-items: start;
    }
    .stack {
      display: grid;
      gap: 20px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 22px;
      background:
        linear-gradient(135deg, rgba(4, 18, 42, 0.96), rgba(2, 10, 24, 0.88)),
        radial-gradient(circle at top right, rgba(0, 157, 255, 0.18), transparent 42%);
      box-shadow: var(--shadow), inset 0 0 32px rgba(15, 114, 255, 0.08);
    }
    .card-title {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 0 0 18px;
      font-size: 21px;
      line-height: 1.2;
    }
    .card-title small {
      color: #c8d5ec;
      font-weight: 500;
    }
    .title-icon {
      width: 32px;
      height: 32px;
      display: grid;
      place-items: center;
      color: #5fc7ff;
      font-size: 25px;
      text-shadow: 0 0 16px rgba(0, 195, 255, 0.8);
      flex: none;
    }
    .live-badge {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--green);
      font-size: 14px;
      white-space: nowrap;
    }
    .map-frame {
      border: 1px solid rgba(116, 169, 236, 0.62);
      border-radius: 8px;
      overflow: hidden;
      background: #071527;
      margin-bottom: 16px;
    }
    .last-update {
      color: #cbd8ee;
      padding: 10px 14px;
      border-bottom: 1px solid rgba(116, 169, 236, 0.28);
      font-size: 14px;
    }
    .map-preview {
      min-height: 350px;
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(28deg, rgba(0, 185, 135, 0.18), transparent 28%),
        linear-gradient(122deg, transparent 0 20%, rgba(35, 111, 206, 0.45) 20% 22%, transparent 22% 42%, rgba(35, 111, 206, 0.28) 42% 44%, transparent 44%),
        linear-gradient(38deg, transparent 0 34%, rgba(41, 125, 232, 0.55) 34% 36%, transparent 36%),
        linear-gradient(90deg, rgba(27, 93, 165, 0.2) 1px, transparent 1px),
        linear-gradient(rgba(27, 93, 165, 0.2) 1px, transparent 1px),
        #071327;
      background-size: auto, auto, auto, 34px 34px, 34px 34px, auto;
    }
    .map-preview::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 50% 50%, rgba(0, 182, 255, 0.22), transparent 20%),
        radial-gradient(circle at 20% 70%, rgba(0, 255, 178, 0.14), transparent 22%),
        linear-gradient(rgba(4, 13, 30, 0.05), rgba(1, 6, 15, 0.42));
    }
    .map-label {
      position: absolute;
      color: rgba(209, 228, 255, 0.75);
      font-size: 15px;
      text-shadow: 0 1px 2px #000;
    }
    .map-label.a { left: 18%; top: 18%; }
    .map-label.b { right: 16%; top: 28%; }
    .map-label.c { left: 28%; bottom: 18%; }
    .locator {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 56px;
      height: 56px;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      border: 4px solid #e8f6ff;
      background: radial-gradient(circle, #238cff 0 28%, rgba(35, 140, 255, 0.12) 32% 100%);
      box-shadow: 0 0 0 14px rgba(0, 136, 255, 0.18), 0 0 30px rgba(0, 180, 255, 0.86);
    }
    .locator::after {
      content: "";
      position: absolute;
      inset: -28px;
      border-radius: 50%;
      border: 1px solid rgba(0, 204, 255, 0.38);
    }
    .google {
      position: absolute;
      left: 12px;
      bottom: 10px;
      font-weight: 700;
      color: white;
      text-shadow: 0 1px 3px #000;
    }
    .metric-list {
      border: 1px solid rgba(116, 169, 236, 0.48);
      border-radius: 8px;
      overflow: hidden;
      margin: 18px 0;
      background: rgba(4, 15, 34, 0.68);
    }
    .metric {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: center;
      padding: 16px 18px;
      border-bottom: 1px solid rgba(116, 169, 236, 0.28);
    }
    .metric:last-child { border-bottom: 0; }
    .metric span:first-child { color: #c9d7ef; }
    .metric strong {
      font-size: clamp(18px, 3vw, 24px);
      font-weight: 500;
      letter-spacing: 0;
      text-align: right;
    }
    label {
      display: block;
      color: #cfdbf0;
      font-size: 14px;
      margin: 14px 0 8px;
    }
    .label-ja {
      display: block;
      color: #f4f8ff;
      font-size: 16px;
      margin-bottom: 3px;
    }
    input, select {
      width: 100%;
      min-height: 58px;
      border-radius: 8px;
      border: 1px solid rgba(116, 169, 236, 0.55);
      background: rgba(2, 8, 22, 0.85);
      color: #f8fbff;
      padding: 0 20px;
      font-size: 18px;
      outline: none;
      box-shadow: inset 0 0 20px rgba(14, 70, 150, 0.12);
    }
    input:focus, select:focus {
      border-color: var(--cyan);
      box-shadow: 0 0 0 3px rgba(0, 213, 255, 0.12), inset 0 0 20px rgba(14, 70, 150, 0.2);
    }
    input::placeholder { color: #7788a4; }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    .btn {
      width: 100%;
      min-height: 64px;
      border: 1px solid rgba(0, 213, 255, 0.95);
      border-radius: 8px;
      margin-top: 14px;
      color: white;
      font-weight: 750;
      font-size: 18px;
      background:
        linear-gradient(135deg, rgba(0, 185, 255, 0.9), rgba(32, 70, 229, 0.94) 62%, rgba(108, 39, 236, 0.92));
      box-shadow: 0 0 22px rgba(0, 148, 255, 0.45), inset 0 0 24px rgba(255, 255, 255, 0.08);
      cursor: pointer;
    }
    .btn:hover { filter: brightness(1.08); }
    .btn.secondary {
      background: rgba(2, 11, 27, 0.75);
      box-shadow: inset 0 0 22px rgba(0, 152, 255, 0.13);
    }
    .btn.violet {
      border-color: rgba(139, 80, 255, 0.95);
      background: linear-gradient(135deg, rgba(67, 48, 229, 0.92), rgba(86, 30, 174, 0.95));
      box-shadow: 0 0 22px rgba(102, 46, 255, 0.35), inset 0 0 24px rgba(255, 255, 255, 0.08);
    }
    .goal-visual {
      min-height: 190px;
      display: grid;
      place-items: center;
    }
    .radar {
      width: 168px;
      aspect-ratio: 1;
      border-radius: 50%;
      border: 1px dashed rgba(0, 213, 255, 0.52);
      position: relative;
      display: grid;
      place-items: center;
      color: #5fc7ff;
      font-size: 46px;
      text-shadow: 0 0 18px rgba(0, 195, 255, 0.8);
      background: radial-gradient(circle, rgba(18, 114, 255, 0.2), transparent 62%);
    }
    .radar::before, .radar::after {
      content: "";
      position: absolute;
      border-radius: 50%;
      border: 2px solid rgba(26, 139, 255, 0.8);
    }
    .radar::before { inset: 24px; }
    .radar::after { inset: 48px; opacity: 0.7; }
    .route-options {
      border: 1px solid rgba(116, 169, 236, 0.48);
      border-radius: 8px;
      overflow: hidden;
      margin-top: 12px;
    }
    .option-row {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 16px;
      min-height: 60px;
      padding: 0 16px;
      border-bottom: 1px solid rgba(116, 169, 236, 0.28);
      color: #f2f7ff;
      margin: 0;
    }
    .option-row:last-child { border-bottom: 0; }
    .option-row input {
      width: 26px;
      min-height: 26px;
      accent-color: #158cff;
    }
    .log-card { margin-top: 24px; }
    .log-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }
    .clear-btn {
      min-height: 44px;
      width: auto;
      padding: 0 18px;
      margin: 0;
      font-size: 14px;
    }
    #status {
      min-height: 130px;
      max-height: 250px;
      overflow: auto;
      border: 1px solid rgba(116, 169, 236, 0.48);
      border-radius: 8px;
      padding: 16px 20px;
      margin: 0;
      background: rgba(2, 8, 22, 0.82);
      color: #bcd8ff;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.6;
    }
    .footer {
      margin-top: 18px;
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      border: 1px solid rgba(116, 169, 236, 0.38);
      border-radius: 8px;
      background: rgba(4, 17, 38, 0.74);
      overflow: hidden;
    }
    .foot-item {
      min-height: 78px;
      padding: 14px 20px;
      border-right: 1px solid rgba(116, 169, 236, 0.28);
    }
    .foot-item:last-child { border-right: 0; }
    .foot-label {
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 7px;
    }
    .foot-value {
      font-size: 17px;
      color: #e9f2ff;
    }
    @media (max-width: 900px) {
      main { padding: 10px; }
      .shell { padding: 16px; border-radius: 14px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .connection { justify-content: stretch; width: 100%; }
      .status-pill { flex: 1; min-width: 0; }
      .grid { grid-template-columns: 1fr; }
      .brand-mark { width: 66px; height: 66px; }
      .form-grid { grid-template-columns: 1fr; gap: 0; }
      .map-preview { min-height: 260px; }
      .footer { grid-template-columns: 1fr 1fr; }
      .foot-item { border-bottom: 1px solid rgba(116, 169, 236, 0.28); }
      .foot-item:nth-child(2n) { border-right: 0; }
    }
    @media (max-width: 520px) {
      main { padding: 8px; }
      .shell { padding: 14px; overflow: hidden; }
      .brand { gap: 10px; }
      .brand-mark { width: 50px; height: 50px; }
      h1 { font-size: 18px; line-height: 1.15; }
      .subtitle { font-size: 13px; }
      .card { padding: 16px; }
      .card-title { font-size: 18px; flex-wrap: wrap; }
      .live-badge { margin-left: 0; }
      .status-pill { width: 100%; padding: 10px 12px; gap: 10px; flex-wrap: wrap; font-size: 15px; }
      input, select { font-size: 16px; min-height: 52px; padding: 0 14px; }
      .btn { font-size: 16px; min-height: 58px; }
      .metric { padding: 14px; grid-template-columns: 1fr; gap: 4px; }
      .metric strong { text-align: left; }
      .footer { grid-template-columns: 1fr; }
      .foot-item { border-right: 0; }
      .gear { display: none; }
    }
  </style>
</head>
<body>
<main>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark"><div class="pin"></div></div>
        <div>
          <h1>Phone Location Bridge</h1>
          <div class="subtitle">スマホの位置情報をPCへブリッジ</div>
        </div>
      </div>
      <div class="connection">
        <div class="status-pill"><span class="dot"></span><span id="connection-label">PC接続中</span><span id="port-label">USB / localhost</span></div>
        <div class="gear">⚙</div>
      </div>
    </header>

    <div class="grid">
      <section class="card">
        <h2 class="card-title"><span class="title-icon">◆</span>現在地 <small>（スマホ）</small><span class="live-badge"><span class="dot"></span><span id="watch-label">待機中</span></span></h2>
        <div class="map-frame">
          <div class="last-update">最終更新: <span id="last-update">--:--:--</span></div>
          <div class="map-preview">
            <span class="map-label a">現在地</span>
            <span class="map-label b">目的地方向</span>
            <span class="map-label c">Route</span>
            <div class="locator"></div>
            <div class="google">Phone GPS</div>
          </div>
        </div>
        <button class="btn secondary" onclick="toggleWatch()" id="watch-button">現在地の取得を開始</button>
        <div class="metric-list">
          <div class="metric"><span>緯度 <small>Latitude</small></span><strong id="lat-display">--</strong></div>
          <div class="metric"><span>経度 <small>Longitude</small></span><strong id="lon-display">--</strong></div>
          <div class="metric"><span>精度 <small>Accuracy</small></span><strong id="accuracy-display">--</strong></div>
          <div class="metric"><span>方位 <small>Heading</small></span><strong id="heading-display">--</strong></div>
        </div>
        <div class="form-grid">
          <label><span class="label-ja">緯度</span>Current latitude<input id="current-lat" inputmode="decimal" onchange="updateCurrentReadout()"></label>
          <label><span class="label-ja">経度</span>Current longitude<input id="current-lon" inputmode="decimal" onchange="updateCurrentReadout()"></label>
          <label><span class="label-ja">方位</span>Heading, north=0 east=90<input id="heading" inputmode="decimal" placeholder="optional" onchange="updateCurrentReadout()"></label>
          <label><span class="label-ja">精度</span>Accuracy m<input id="accuracy" inputmode="decimal" placeholder="optional" onchange="updateCurrentReadout()"></label>
        </div>
        <button class="btn" onclick="sendCurrent()">現在地を送信</button>
      </section>

      <div class="stack">
        <section class="card">
          <h2 class="card-title"><span class="title-icon">⌁</span>目的地 <small>（Google Maps URL）</small></h2>
          <label><span class="label-ja">Google Maps URL</span><input id="goal-url" placeholder="https://maps.app.goo.gl/..."></label>
          <button class="btn secondary" onclick="importGoalUrl()">URLからインポート</button>
          <div class="form-grid">
            <div>
              <label><span class="label-ja">目的地名</span>Goal name<input id="goal-name" value="goal"></label>
              <label><span class="label-ja">緯度</span>Goal latitude<input id="goal-lat" inputmode="decimal"></label>
              <label><span class="label-ja">経度</span>Goal longitude<input id="goal-lon" inputmode="decimal"></label>
            </div>
            <div class="goal-visual"><div class="radar">⚑</div></div>
          </div>
          <button class="btn" onclick="sendGoal()">目的地を送信</button>
          <button class="btn violet" onclick="sendRoute()">現在地 + 目的地のルートを送信</button>
        </section>

        <section class="card">
          <h2 class="card-title"><span class="title-icon">↟</span>ルート検索オプション</h2>
          <label><span class="label-ja">ルート候補</span>
            <select id="route-alternatives">
              <option value="1">1 route</option>
              <option value="2">Up to 2 routes</option>
              <option value="3" selected>Up to 3 routes</option>
            </select>
          </label>
          <label><span class="label-ja">選択中ルート</span>
            <select id="route-select" onchange="selectRoute()">
              <option value="">No route searched</option>
            </select>
          </label>
          <div class="route-options">
            <label class="option-row"><span>高速道路を避ける</span><input id="avoid-motorway" type="checkbox"></label>
            <label class="option-row"><span>有料道路を避ける</span><input id="avoid-toll" type="checkbox"></label>
            <label class="option-row"><span>フェリーを避ける</span><input id="avoid-ferry" type="checkbox"></label>
          </div>
          <button class="btn violet" onclick="searchRoutes()">ルート検索</button>
        </section>
      </div>
    </div>

    <section class="card log-card">
      <div class="log-head">
        <h2 class="card-title" style="margin:0;"><span class="title-icon">&gt;_</span>送信ログ / レスポンス</h2>
        <button class="btn secondary clear-btn" onclick="clearLog()">ログをクリア</button>
      </div>
      <pre id="status">Ready</pre>
    </section>

    <footer class="footer">
      <div class="foot-item"><span class="foot-label">接続状態</span><span class="foot-value" id="footer-connection">USB / localhost</span></div>
      <div class="foot-item"><span class="foot-label">最終送信</span><span class="foot-value" id="last-send">--</span></div>
      <div class="foot-item"><span class="foot-label">最終受信</span><span class="foot-value" id="last-receive">--</span></div>
      <div class="foot-item"><span class="foot-label">ステータス</span><span class="foot-value" id="footer-status">準備完了</span></div>
      <div class="foot-item"><span class="foot-label">バージョン</span><span class="foot-value">v1.0.0</span></div>
    </footer>
  </div>
</main>
<script>
let watchId = null;
const $ = (id) => document.getElementById(id);
function timeText() {
  return new Date().toLocaleTimeString('ja-JP', {hour12: false});
}
function num(id) {
  const value = $(id).value.trim();
  return value === '' ? null : Number(value);
}
function show(data) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  const line = '[' + timeText() + ']  ' + text;
  const current = $('status').textContent.trim();
  $('status').textContent = current && current !== 'Ready' ? current + '\\n' + line : line;
  $('status').scrollTop = $('status').scrollHeight;
  $('last-receive').textContent = timeText();
  $('footer-status').textContent = typeof data === 'string' && data.toLowerCase().includes('error') ? '要確認' : '準備完了';
}
function clearLog() {
  $('status').textContent = 'Ready';
}
async function post(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  $('last-send').textContent = timeText();
  show(data);
  return data;
}
function currentPayload() {
  return {
    lat: num('current-lat'),
    lon: num('current-lon'),
    heading_deg: num('heading'),
    accuracy_m: num('accuracy'),
    name: 'phone'
  };
}
function goalPayload() {
  return {
    lat: num('goal-lat'),
    lon: num('goal-lon'),
    name: $('goal-name').value.trim() || 'goal'
  };
}
function sendCurrent() {
  updateCurrentReadout();
  post('/api/location', currentPayload()).catch((e) => show(String(e)));
}
function sendGoal() {
  post('/api/goal', goalPayload()).catch((e) => show(String(e)));
}
function sendRoute() {
  post('/api/route', {current: currentPayload(), goal: goalPayload()}).catch((e) => show(String(e)));
}
function formatDistance(meters) {
  if (!Number.isFinite(meters)) return '--';
  return meters >= 1000 ? (meters / 1000).toFixed(1) + ' km' : Math.round(meters) + ' m';
}
function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return '--';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return minutes + ' min';
  return Math.floor(minutes / 60) + ' h ' + (minutes % 60) + ' min';
}
function updateRouteSelect(routes, selectedIndex) {
  const select = $('route-select');
  select.innerHTML = '';
  if (!routes || routes.length === 0) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No route';
    select.appendChild(option);
    return;
  }
  routes.forEach((route) => {
    const option = document.createElement('option');
    option.value = route.index;
    option.textContent = 'Route ' + (route.index + 1) + ' / ' +
      formatDistance(route.distance_m) + ' / ' + formatDuration(route.duration_sec);
    select.appendChild(option);
  });
  select.value = String(selectedIndex >= 0 ? selectedIndex : routes[0].index);
}
async function searchRoutes() {
  try {
    const data = await post('/api/osrm_routes', {
      current: currentPayload(),
      goal: goalPayload(),
      alternatives: Number($('route-alternatives').value || 3),
      avoid_motorway: $('avoid-motorway').checked,
      avoid_toll: $('avoid-toll').checked,
      avoid_ferry: $('avoid-ferry').checked
    });
    if (data && data.ok) {
      updateRouteSelect(data.routes, data.selected_route_index);
    }
  } catch (e) {
    show(String(e));
  }
}
function selectRoute() {
  const value = $('route-select').value;
  if (value === '') return;
  post('/api/select_route', {index: Number(value)}).catch((e) => show(String(e)));
}
function setValueIfPresent(id, value, digits) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return;
  $(id).value = Number(value).toFixed(digits);
}
function hydrateState(data) {
  if (!data) return;
  if (data.current) {
    setValueIfPresent('current-lat', data.current.lat, 8);
    setValueIfPresent('current-lon', data.current.lon, 8);
    setValueIfPresent('heading', data.current.heading_deg, 1);
    setValueIfPresent('accuracy', data.current.accuracy_m, 1);
    updateCurrentReadout();
  }
  if (data.goal) {
    setValueIfPresent('goal-lat', data.goal.lat, 8);
    setValueIfPresent('goal-lon', data.goal.lon, 8);
    $('goal-name').value = data.goal.name || 'goal';
  }
  if (data.route_options) {
    updateRouteSelect(data.route_options, data.selected_route_index);
  }
}
async function importGoalUrl() {
  const url = $('goal-url').value.trim();
  if (!url) {
    show('Google Maps URL is empty.');
    return;
  }
  try {
    const data = await post('/api/goal_url', {url: url, name: $('goal-name').value.trim()});
    if (data && data.ok && data.goal) {
      $('goal-lat').value = Number(data.goal.lat).toFixed(8);
      $('goal-lon').value = Number(data.goal.lon).toFixed(8);
      $('goal-name').value = data.goal.name || 'goal';
    }
  } catch (e) {
    show(String(e));
  }
}
function updateCurrentReadout() {
  const lat = num('current-lat');
  const lon = num('current-lon');
  const heading = num('heading');
  const accuracy = num('accuracy');
  $('lat-display').textContent = Number.isFinite(lat) ? lat.toFixed(8) : '--';
  $('lon-display').textContent = Number.isFinite(lon) ? lon.toFixed(8) : '--';
  $('heading-display').textContent = Number.isFinite(heading) ? heading.toFixed(1) + '°' : '--';
  $('accuracy-display').textContent = Number.isFinite(accuracy) ? accuracy.toFixed(1) + ' m' : '--';
  if (Number.isFinite(lat) && Number.isFinite(lon)) $('last-update').textContent = timeText();
}
function setWatchUi(active) {
  $('watch-label').textContent = active ? '取得中' : '待機中';
  $('watch-button').textContent = active ? '現在地の取得を停止' : '現在地の取得を開始';
}
function toggleWatch() {
  if (watchId === null) startWatch();
  else stopWatch();
}
function startWatch() {
  if (!navigator.geolocation) {
    show('Geolocation is not available in this browser.');
    return;
  }
  if (watchId !== null) {
    show('Location watch is already running.');
    return;
  }
  watchId = navigator.geolocation.watchPosition((pos) => {
    $('current-lat').value = pos.coords.latitude.toFixed(8);
    $('current-lon').value = pos.coords.longitude.toFixed(8);
    if (Number.isFinite(pos.coords.heading)) $('heading').value = pos.coords.heading.toFixed(1);
    if (Number.isFinite(pos.coords.accuracy)) $('accuracy').value = pos.coords.accuracy.toFixed(1);
    updateCurrentReadout();
    sendCurrent();
  }, (err) => show('Geolocation error: ' + err.message), {
    enableHighAccuracy: true,
    maximumAge: 1000,
    timeout: 10000
  });
  setWatchUi(true);
  show('Started location watch.');
}
function stopWatch() {
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
  watchId = null;
  setWatchUi(false);
  show('Stopped location watch.');
}
fetch('/api/state')
  .then((r) => r.json())
  .then((data) => { hydrateState(data); show(data); })
  .catch(() => {});
</script>
</body>
</html>
"""


def main() -> None:
    rclpy.init()
    node = PhoneLocationBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
