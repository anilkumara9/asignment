# Fuel-Route API — cheapest fuel stops along a US road trip

Backend Django Engineer coding assessment (Spotter).

**What it does:** given a start and finish location (both within the USA), the API
returns the driving route, an interactive map of that route, and the **cheapest
places to fuel up along the way** based on the provided OPIS truck-stop fuel
prices — assuming a 500-mile max range and 10 MPG — plus the total money spent
on fuel.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Then open in your browser or Postman:

| What | URL |
|---|---|
| Plan a trip (JSON) | http://127.0.0.1:8000/api/route/?start=Dallas,TX&finish=Chicago,IL |
| Interactive map | http://127.0.0.1:8000/map/?start=Dallas,TX&finish=Chicago,IL |
| API index | http://127.0.0.1:8000/ |

A ready-made Postman collection is included: `postman_collection.json`
(import it into Postman; it targets `http://127.0.0.1:8000` by default).

Run the test suite:

```bash
python manage.py test fuelrouter
```

## API reference

### `GET /api/route/?start=<place>&finish=<place>` (also accepts POST with a JSON body)

Optional overrides: `mpg` (default 10), `max_range_miles` (default 500).

Response (200):

```json
{
  "start":   {"query": "Dallas,TX", "display_name": "Dallas, Dallas County, Texas, USA", "lat": 32.78, "lng": -96.80},
  "finish":  {"query": "Chicago,IL", "display_name": "Chicago, Cook County, Illinois, USA", "lat": 41.88, "lng": -87.63},
  "route":   {"distance_miles": 925.3, "duration_minutes": 830.5, "geometry": [[-96.8, 32.78], "..."]},
  "vehicle": {"mpg": 10, "max_range_miles": 500, "tank_gallons": 50.0},
  "fuel_stops": [
    {
      "station_id": "1243", "name": "PILOT TRAVEL CENTER #1243",
      "address": "I-8, EXIT 119 & SR-85", "city": "Gila Bend", "state": "AZ",
      "price_per_gallon_usd": 3.899, "lat": 32.95, "lng": -112.71,
      "route_mile": 412.6, "miles_off_route": 2.3,
      "gallons": 42.5, "cost_usd": 165.71
    }
  ],
  "summary": {"num_stops": 3, "total_gallons": 92.5, "total_cost_usd": 301.44,
              "avg_price_per_gallon_usd": 3.259},
  "map_url": "http://127.0.0.1:8000/map/?start=Dallas,TX&finish=Chicago,IL",
  "notes": ["...assumptions..."]
}
```

Errors: `400` for missing/invalid parameters, `422` when a place can't be
geocoded inside the USA or no route/fuel plan exists (message in `{"error": ...}`).

### `GET /map/?start=<place>&finish=<place>`

Server-rendered interactive map (Leaflet + OpenStreetMap tiles): the route
polyline, start/finish markers, numbered fuel-stop markers with price/gallon
popups, and a summary panel. Reuses the cached plan, so it triggers **zero**
additional external API calls.

## How it works

**Free external APIs (no keys needed):**
- **Nominatim (OpenStreetMap)** — geocodes `start`/`finish` to coordinates
  (restricted to the USA).
- **OSRM public demo server** — computes the driving route (distance + full
  geometry).

**Keeping external calls minimal (a requirement):**
- Geocoding results are cached 24 h → 1 call per unique place name, ever.
- Routing results are cached 24 h → exactly 1 OSRM call per unique
  (start, finish) pair; repeat requests (including the map page) hit the cache.
- Station coordinates are resolved **offline at build time** (see below), so
  fuel-stop matching never touches the network.

**Pipeline** (`fuelrouter/services/`):
1. `geocode.py` — place name → (lat, lng), USA-only, cached.
2. `routing.py` — coordinates → distance/duration/geometry via OSRM, cached.
3. `stations.py` — loads the 6,738 truck stops from the bundled
   `fuelrouter/data/stations.json`, indexes them on a lat/lng grid, and keeps
   those within 10 miles of the route, recording each stop's distance along
   the route (`route_mile`). Pure Python, ~0.5 s for a cross-country route.
4. `optimizer.py` — the classic minimum-cost refuelling greedy: at each stop,
   buy just enough to reach the next *cheaper* station within range, otherwise
   fill the tank (never buying more than needed to reach the destination, which
   is modelled as a $0 station). Optimal under the stated assumptions.
5. `planner.py` — orchestrates the above and shapes the JSON response.

**Station coordinates** were built once with `scripts/build_stations.py`:
each stop's city was resolved via the US Census Bureau's 2024 place gazetteer
(public domain), with a cached Nominatim fallback for the few hundred cities
missing from it. 6,738 of 6,738 stops resolved.

**Assumptions** (also returned in every response's `notes`):
- Prices are retail USD/gallon from the provided OPIS data (cheapest price kept
  per truck stop; duplicate rows collapsed).
- The vehicle starts with an empty tank; fuel burned before the first stop is
  billed at that stop's price.
- A station counts as "along the route" if within 10 miles of it
  (`STATION_CAPTURE_MILES` in settings).

## Project layout

```
config/                  Django project (settings, urls)
fuelrouter/              the app
  services/              geocode.py, routing.py, stations.py, optimizer.py,
                         planner.py, geo.py   (framework-free, unit-tested)
  data/stations.json     truck stops with coordinates + prices (built offline)
  tests/                 19 unit tests (optimizer, geometry, matching, API)
  views.py               DRF JSON API + map page
templates/fuelrouter/    map.html (Leaflet), map_error.html
scripts/build_stations.py  reproduces data/stations.json from the CSV
postman_collection.json   import into Postman for the demo
```

## Deployment notes

- Set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0` env vars for anything beyond
  local demo use; put a real cache (Redis) behind `CACHES` for multi-process
  serving.
- The OSRM demo server is rate-limited and meant for light use — fine for this
  assessment; a production version would self-host OSRM or use a keyed
  provider. The single-call-per-route caching design carries over unchanged.
