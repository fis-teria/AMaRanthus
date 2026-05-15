MAP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>OpenStreetMap with Search & Routing</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-control-geocoder@2.4.0/dist/Control.Geocoder.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script src="https://unpkg.com/leaflet-control-geocoder@2.4.0/dist/Control.Geocoder.js"></script>
    <style>
        #map {
            height: 100vh;
            width: 100%;
        }
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            background: #f4f6f8;
        }
        body.dark-mode {
            background: #101419;
        }
        body.dark-mode .leaflet-tile-pane {
            filter: brightness(0.62) contrast(1.16) saturate(0.82) hue-rotate(180deg);
        }
        body.dark-mode .leaflet-control-container,
        body.dark-mode .leaflet-popup-content-wrapper,
        body.dark-mode .leaflet-popup-tip,
        body.dark-mode .leaflet-routing-container {
            filter: none;
        }
        body.dark-mode .leaflet-control,
        body.dark-mode .leaflet-popup-content-wrapper,
        body.dark-mode .leaflet-routing-container,
        body.dark-mode .route-info {
            background: #161d24;
            border-color: #2c3845;
            color: #e6edf3;
        }
        body.dark-mode .leaflet-control a {
            background: #1d2730;
            color: #e6edf3;
        }
        body.dark-mode .leaflet-control-attribution,
        body.dark-mode .leaflet-control-attribution a {
            background: rgba(22, 29, 36, 0.88);
            color: #b6c5d2;
        }
        body.dark-mode .next-maneuver {
            background: #122d36;
            border-color: #255868;
        }
        body.dark-mode .steps-title {
            color: #e6edf3;
        }
        .search-container {
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 1000;
            display: none;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-family: 'Noto Sans CJK JP', Arial, sans-serif;
            min-width: 300px;
        }
        .search-container h4 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
        }
        .search-input {
            width: 100%;
            padding: 8px;
            margin-bottom: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            font-family: 'Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic', 'Yu Gothic', 'MS Gothic', Arial, sans-serif;
        }
        .search-button {
            width: 100%;
            padding: 8px;
            background: #4285f4;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .search-button:hover {
            background: #3367d6;
        }
        .search-button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .route-info {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            font-family: 'Noto Sans CJK JP', Arial, sans-serif;
            font-size: 12px;
            max-width: 320px;
            display: none;
        }
        .route-info.show {
            display: block;
        }
        .next-maneuver {
            margin: 8px 0;
            padding: 8px;
            border-radius: 6px;
            background: #f2f7ff;
            border: 1px solid #d6e5ff;
            line-height: 1.4;
        }
        .steps-title {
            margin: 8px 0 4px 0;
            font-size: 12px;
            font-weight: bold;
            color: #333;
        }
        .steps-list {
            margin: 0;
            padding-left: 18px;
            max-height: 170px;
            overflow-y: auto;
        }
        .steps-list li {
            margin-bottom: 4px;
            line-height: 1.35;
        }
        .leaflet-control-attribution {
            font-size: 10px;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="search-container">
        <h4>ルート検索</h4>
        <input type="text" id="start-search" class="search-input" placeholder="出発地を入力（例: 東京駅）" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" lang="ja" inputmode="text">
        <input type="text" id="end-search" class="search-input" placeholder="目的地を入力（例: 渋谷駅）" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" lang="ja" inputmode="text">
        <button id="search-route" class="search-button">ルート検索</button>
    </div>
    <div class="route-info" id="route-info">
        <h4>ルート情報</h4>
        <p id="route-distance">距離: -- km</p>
        <p id="route-time">時間: -- 分</p>
        <div class="next-maneuver" id="next-maneuver">次の案内: --</div>
        <div class="steps-title">案内ステップ</div>
        <ol class="steps-list" id="steps-list"></ol>
    </div>
    <script>
        const tokyoStation = [35.681236, 139.767125];
        const map = L.map('map').setView(tokyoStation, 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(map);

        let startMarker = null;
        let endMarker = null;
        let routingControl = null;
        let startCoords = null;
        let endCoords = null;
        let currentPositionMarker = null;
        let navigationTimer = null;
        let activeRouteCoordinates = [];
        let instructionMeta = [];
        let stepElements = [];
        let currentCoordIndex = 0;

        const geocoder = L.Control.Geocoder.nominatim();

        function clearNavigationState() {
            if (navigationTimer) {
                clearInterval(navigationTimer);
                navigationTimer = null;
            }
            activeRouteCoordinates = [];
            instructionMeta = [];
            currentCoordIndex = 0;
            stepElements.forEach(function(el) {
                el.style.background = '';
                el.style.fontWeight = '';
            });

            if (currentPositionMarker) {
                map.removeLayer(currentPositionMarker);
                currentPositionMarker = null;
            }
        }

        function setCurrentPositionMarker(latLng) {
            if (!currentPositionMarker) {
                currentPositionMarker = L.circleMarker(latLng, {
                    radius: 8,
                    color: '#1a73e8',
                    fillColor: '#4da3ff',
                    fillOpacity: 0.9,
                    weight: 2
                }).addTo(map);
            } else {
                currentPositionMarker.setLatLng(latLng);
            }
        }

        function extractRouteCoordinates(route) {
            const coords = route.coordinates || [];
            return coords
                .map(function(c) {
                    if (!c) {
                        return null;
                    }
                    if (typeof c.lat === 'number' && typeof c.lng === 'number') {
                        return L.latLng(c.lat, c.lng);
                    }
                    if (Array.isArray(c) && c.length >= 2) {
                        return L.latLng(c[0], c[1]);
                    }
                    return null;
                })
                .filter(function(c) { return c !== null; });
        }

        function normalizeInstructionMeta(instructions, coordCount) {
            if (!instructions || instructions.length === 0 || coordCount < 1) {
                return [];
            }
            return instructions.map(function(step, idx) {
                let startIndex = 0;
                if (typeof step.index === 'number' && !Number.isNaN(step.index)) {
                    startIndex = step.index;
                } else if (typeof step.waypointIndex === 'number' && !Number.isNaN(step.waypointIndex)) {
                    startIndex = step.waypointIndex;
                } else {
                    startIndex = idx === 0 ? 0 : Math.floor((idx / instructions.length) * (coordCount - 1));
                }
                startIndex = Math.max(0, Math.min(coordCount - 1, startIndex));
                return { step: step, startIndex: startIndex };
            }).sort(function(a, b) { return a.startIndex - b.startIndex; });
        }

        function distanceAlongRoute(fromIndex, toIndex) {
            if (activeRouteCoordinates.length < 2) {
                return 0;
            }
            const start = Math.max(0, Math.min(fromIndex, activeRouteCoordinates.length - 1));
            const end = Math.max(0, Math.min(toIndex, activeRouteCoordinates.length - 1));
            if (end <= start) {
                return 0;
            }
            let sum = 0;
            for (let i = start; i < end; i++) {
                sum += map.distance(activeRouteCoordinates[i], activeRouteCoordinates[i + 1]);
            }
            return sum;
        }

        function findNextInstructionIndex(coordIndex) {
            for (let i = 0; i < instructionMeta.length; i++) {
                if (instructionMeta[i].startIndex >= coordIndex) {
                    return i;
                }
            }
            return -1;
        }

        function highlightInstructionStep(activeIndex) {
            stepElements.forEach(function(el, idx) {
                if (idx === activeIndex) {
                    el.style.background = '#e8f0fe';
                    el.style.fontWeight = 'bold';
                } else {
                    el.style.background = '';
                    el.style.fontWeight = '';
                }
            });
        }

        function updateRealtimeGuidance(coordIndex) {
            const nextManeuverEl = document.getElementById('next-maneuver');
            if (instructionMeta.length === 0) {
                nextManeuverEl.textContent = '次の案内: 案内情報なし';
                return;
            }

            const nextInstructionIdx = findNextInstructionIndex(coordIndex);
            if (nextInstructionIdx < 0) {
                nextManeuverEl.textContent = '次の案内: 目的地付近です。到着します。';
                highlightInstructionStep(-1);
                return;
            }

            const meta = instructionMeta[nextInstructionIdx];
            const distToTurn = distanceAlongRoute(coordIndex, meta.startIndex);
            const stepText = (meta.step && meta.step.text) ? meta.step.text : '直進してください';
            nextManeuverEl.textContent =
                '次の案内: ' + stepText + '（約' + formatDistanceMeters(distToTurn) + '先）';
            highlightInstructionStep(nextInstructionIdx);
        }

        function startRouteNavigation(route, instructions) {
            clearNavigationState();
            activeRouteCoordinates = extractRouteCoordinates(route);
            if (activeRouteCoordinates.length === 0) {
                return;
            }
            instructionMeta = normalizeInstructionMeta(instructions, activeRouteCoordinates.length);
            currentCoordIndex = 0;

            setCurrentPositionMarker(activeRouteCoordinates[0]);
            map.setView(activeRouteCoordinates[0], 16);
            updateRealtimeGuidance(currentCoordIndex);

            navigationTimer = setInterval(function() {
                if (currentCoordIndex >= activeRouteCoordinates.length - 1) {
                    clearInterval(navigationTimer);
                    navigationTimer = null;
                    updateRealtimeGuidance(activeRouteCoordinates.length - 1);
                    return;
                }

                currentCoordIndex = Math.min(currentCoordIndex + 3, activeRouteCoordinates.length - 1);
                const currentLatLng = activeRouteCoordinates[currentCoordIndex];
                setCurrentPositionMarker(currentLatLng);
                map.panTo(currentLatLng, { animate: true, duration: 0.7 });
                updateRealtimeGuidance(currentCoordIndex);
            }, 1000);
        }

        function searchLocation(query, callback) {
            geocoder.geocode(query, function(results) {
                if (results && results.length > 0) {
                    const result = results[0];
                    callback({
                        lat: result.center.lat,
                        lng: result.center.lng,
                        name: result.name
                    });
                } else {
                    alert('場所が見つかりませんでした: ' + query);
                }
            });
        }

        function setMarker(coords, type) {
            if (type === 'start' && startMarker) {
                map.removeLayer(startMarker);
            }
            if (type === 'end' && endMarker) {
                map.removeLayer(endMarker);
            }

            const marker = L.marker([coords.lat, coords.lng])
                .addTo(map)
                .bindPopup('<b>' + (type === 'start' ? '出発地' : '目的地') + '</b><br/>' + coords.name)
                .openPopup();

            if (type === 'start') {
                startMarker = marker;
                startCoords = coords;
            } else {
                endMarker = marker;
                endCoords = coords;
            }

            if (startCoords && endCoords) {
                const bounds = L.latLngBounds([startCoords.lat, startCoords.lng], [endCoords.lat, endCoords.lng]);
                map.fitBounds(bounds, { padding: [20, 20] });
            } else {
                map.setView([coords.lat, coords.lng], 15);
            }
        }

        function calculateRoute(start, end) {
            if (!start || !end) {
                alert('出発地と目的地の両方を設定してください。');
                return;
            }

            clearNavigationState();

            if (routingControl) {
                map.removeControl(routingControl);
            }

            const routeLanguage =
                (L.Routing.Localization && L.Routing.Localization['ja']) ? 'ja' : 'en';

            routingControl = L.Routing.control({
                waypoints: [
                    L.latLng(start.lat, start.lng),
                    L.latLng(end.lat, end.lng)
                ],
                routeWhileDragging: false,
                createMarker: function() { return null; },
                router: L.Routing.osrmv1({
                    serviceUrl: 'https://routing.openstreetmap.de/routed-car/route/v1',
                    profile: 'driving'
                }),
                formatter: new L.Routing.Formatter({
                    language: routeLanguage
                }),
                summaryTemplate: '<h3>{name}</h3><p>{distance}, {time}</p>',
            }).addTo(map);

            routingControl.on('routesfound', function(e) {
                const routes = e.routes;
                const route = routes[0];
                const summary = route.summary;
                const instructions = route.instructions || [];

                const routeInfo = document.getElementById('route-info');
                const distanceKm = (summary.totalDistance / 1000).toFixed(1);
                const timeMin = Math.round(summary.totalTime / 60);

                document.getElementById('route-distance').textContent = '距離: ' + distanceKm + ' km';
                document.getElementById('route-time').textContent = '時間: ' + timeMin + ' 分';
                updateRouteGuidance(instructions);
                startRouteNavigation(route, instructions);
                routeInfo.classList.add('show');
            });

            routingControl.on('routingerror', function(e) {
                clearNavigationState();
                console.error('ルート検索エラー:', e.error);
                alert('ルート検索に失敗しました。ネットワーク接続を確認してください。');
            });
        }

        function formatDistanceMeters(distanceMeters) {
            if (!distanceMeters || distanceMeters < 1) {
                return '0 m';
            }
            if (distanceMeters >= 1000) {
                return (distanceMeters / 1000).toFixed(1) + ' km';
            }
            return Math.round(distanceMeters) + ' m';
        }

        function formatDurationSeconds(durationSeconds) {
            if (!durationSeconds || durationSeconds < 1) {
                return '0分';
            }
            const totalMin = Math.round(durationSeconds / 60);
            if (totalMin < 60) {
                return totalMin + '分';
            }
            const h = Math.floor(totalMin / 60);
            const m = totalMin % 60;
            return h + '時間' + m + '分';
        }

        function updateRouteGuidance(instructions) {
            const nextManeuverEl = document.getElementById('next-maneuver');
            const stepsListEl = document.getElementById('steps-list');
            stepsListEl.innerHTML = '';
            stepElements = [];

            if (!instructions || instructions.length === 0) {
                nextManeuverEl.textContent = '次の案内: 取得できませんでした';
                return;
            }

            const first = instructions[0];
            const firstText = first.text || '直進してください';
            nextManeuverEl.textContent = '次の案内: ' + firstText;

            instructions.forEach(function(step) {
                const li = document.createElement('li');
                const text = step.text || '案内情報なし';
                const dist = formatDistanceMeters(step.distance || 0);
                const time = formatDurationSeconds(step.time || 0);
                li.textContent = text + '（' + dist + ' / 約' + time + '）';
                stepsListEl.appendChild(li);
                stepElements.push(li);
            });
        }

        function executeRouteSearch(startQuery, endQuery) {
            if (!startQuery || !endQuery) {
                alert('出発地と目的地の両方を入力してください。');
                return;
            }

            const searchButton = document.getElementById('search-route');
            searchButton.disabled = true;
            searchButton.textContent = '検索中...';

            searchLocation(startQuery, function(startResult) {
                setMarker(startResult, 'start');

                searchLocation(endQuery, function(endResult) {
                    setMarker(endResult, 'end');
                    setTimeout(function() {
                        calculateRoute(startResult, endResult);
                    }, 500);

                    searchButton.disabled = false;
                    searchButton.textContent = 'ルート検索';
                });
            });
        }

        window.searchRouteFromNative = function(startQuery, endQuery) {
            executeRouteSearch((startQuery || '').trim(), (endQuery || '').trim());
        };

        window.setMapDarkMode = function(enabled) {
            document.body.classList.toggle('dark-mode', Boolean(enabled));
        };

        function setupIMEHandling(inputElement) {
            let isComposing = false;

            inputElement.addEventListener('compositionstart', function() {
                isComposing = true;
            });

            inputElement.addEventListener('compositionend', function() {
                isComposing = false;
            });

            inputElement.addEventListener('input', function(e) {
                if (!isComposing) {
                    console.log('Direct input:', e.target.value);
                }
            });

            inputElement.addEventListener('keydown', function(e) {
                if (e.key === 'Convert' || e.key === 'NonConvert' || e.key === 'KanaMode') {
                    console.log('IME toggle key pressed:', e.key);
                }
            });
        }

        setupIMEHandling(document.getElementById('start-search'));
        setupIMEHandling(document.getElementById('end-search'));

        document.getElementById('search-route').addEventListener('click', function() {
            const startQuery = document.getElementById('start-search').value.trim();
            const endQuery = document.getElementById('end-search').value.trim();
            executeRouteSearch(startQuery, endQuery);
        });

        document.getElementById('start-search').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('search-route').click();
            }
        });
        document.getElementById('end-search').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('search-route').click();
            }
        });

        L.control.scale().addTo(map);

        L.marker(tokyoStation)
            .addTo(map)
            .bindPopup('<b>東京駅</b><br/>検索ボックスでルート検索ができます')
            .openPopup();

        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('.search-input');
            inputs.forEach(function(input) {
                input.style.fontFamily = "'Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic', 'Yu Gothic', 'MS Gothic', Arial, sans-serif";
                input.setAttribute('lang', 'ja');
                input.setAttribute('inputmode', 'text');
                input.addEventListener('focus', function() {
                    this.style.imeMode = 'active';
                });
            });
        });
    </script>
</body>
</html>
"""
