# phone_location_bridge

`phone_location_bridge` serves a small phone-friendly web page on the PC and
bridges submitted phone location / destination data into ROS 2.

## Usage

```bash
ros2 launch phone_location_bridge phone_location_bridge.launch.py
```

Open the displayed URL from a USB-tethered phone. If browser geolocation is
blocked over plain HTTP, enter the current latitude / longitude manually and tap
`Send current`.

For Android, the easiest way to make browser geolocation work without HTTPS is
to use ADB reverse:

```bash
ros2 run phone_location_bridge phone_location_adb_reverse.sh
```

Then open `http://localhost:8765/` on the phone.

To make that PC-side step run automatically when the phone is plugged in, install
the udev-triggered systemd user service:

```bash
ros2 run phone_location_bridge install_phone_adb_autoreverse.sh
```

USB debugging still has to be enabled and authorized once on the phone. The
installer defaults to Sony's Android USB vendor id `0fce`; override it with
`PHONE_LOCATION_ANDROID_VENDOR_ID=<vendor-id>` for another device. Installing the
udev rule requires root permission; use `--skip-udev` to install only the user
service first. Check logs with:

```bash
systemctl --user status phone-location-adb-reverse.service
journalctl --user -u phone-location-adb-reverse.service -n 50
```

HTTPS is also supported with trusted certificates:

```bash
ros2 run phone_location_bridge create_phone_https_cert.sh Data/certs/phone_location_bridge <pc-ip>
ros2 launch phone_location_bridge phone_location_bridge.launch.py \
  use_https:=true \
  tls_cert_file:=Data/certs/phone_location_bridge/phone_location_bridge.crt \
  tls_key_file:=Data/certs/phone_location_bridge/phone_location_bridge.key
```

The phone browser must trust the certificate, otherwise geolocation may still be
blocked.

The phone page can also import a destination from a Google Maps URL. Paste a
shared URL such as `https://maps.app.goo.gl/...` into `Google Maps URL` and tap
`Import goal from URL`. The bridge expands short URLs and prefers destination
coordinates from `!3d<lat>!4d<lon>` over map-center coordinates like
`@<lat>,<lon>,...`.

After current and goal are available, tap `Search road routes` to request OSRM
route alternatives. The selected route geometry is converted into local
`base_link` path points and published on `/shadow/route/gui_path`. The selected
route also carries guidance steps in `/phone/location/status`, so the PC GUI can
show the next maneuver and the step list on the Map view. Guidance text uses
OSRM step `name`, `ref`, and `destinations` when available, and otherwise falls
back to intersection-style prompts such as `次の交差点を右折`. The default
public OSRM endpoint supports alternatives, but may reject `exclude` options for
motorway/toll/ferry. When that happens, the bridge returns a warning and retries
without excludes. Use `osrm_service_url:=...` to point at a self-hosted OSRM
endpoint with the desired exclude support.

When a selected OSRM route exists, the bridge watches incoming phone locations
against that route. By default it reroutes if the phone stays more than 30 m
away from the route for 3 seconds, with a 10 second cooldown between reroutes.
Tune this with `auto_reroute_enabled`, `off_route_threshold_m`,
`off_route_hold_sec`, and `reroute_cooldown_sec`.

To protect downstream nodes from stale browser GPS, the bridge only publishes
`/phone/gps/fix` and `/shadow/route/gui_path` while the last phone update is
fresh. The default stale timeout is 3 seconds. Tune it with
`fix_stale_timeout_sec`; set it to `0.0` to disable the guard. While stale,
`/phone/location/status` sets `current` to null and keeps the stale coordinate in
`last_current` for diagnostics.

## Outputs

- `/phone/gps/fix` (`sensor_msgs/msg/NavSatFix`): current phone location.
- `/vehicle/gps_status` (`std_msgs/msg/String`): compact status for the GUI badge.
- `/phone/route/goal` (`std_msgs/msg/String`, JSON): destination latitude /
  longitude and route metadata.
- `/shadow/route/gui_path` (`nav_msgs/msg/Path`): straight local `base_link` path
  generated from current location to the goal.
- `/phone/location/status` (`std_msgs/msg/String`, JSON): bridge health/status.

The route path is intentionally local. It does not replace `/Odometry`; it only
feeds the existing `shadow_route_target` GUI-route input.
By default, the current-to-goal bearing is treated as local forward so the path
is useful even when the phone cannot provide a vehicle yaw estimate.
