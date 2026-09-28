# Fuel-Route API — cheapest fuel stops along a US road trip

Backend Django Engineer coding assessment (Spotter).

**What it does:** given a start and finish location (both within the USA), the API
returns the driving route, an interactive map of that route, and the **cheapest
places to fuel up along the way** based on the provided OPIS truck-stop fuel
prices — assuming a 500-mile max range and 10 MPG — plus the total money spent
on fuel.

## Tech stack

- **Python 3.10+**, **Django 6.1** (latest stable), Django REST Framework
- **Free, keyless map APIs:** OpenStreetMap Nominatim (geocoding), OSRM (routing)
- **Map UI:** Leaflet + OpenStreetMap tiles (no API key)
- **Data:** 6,625 US truck stops with retail fuel prices, bundled as JSON
  (resolved offline at build time — zero network calls at request time)

## Requirements coverage

| Assignment requirement | How it's met |
|---|---|
| Accept USA start and finish locations | `GET`/`POST /api/route/`; geocoding restricted to the USA (`countrycodes=us`); non-US or unknown places return `422` |
| Return the driving route on a map | Interactive Leaflet map at `GET /map/` (route polyline, numbered fuel-stop markers, summary panel); full route geometry also in the JSON |
| Find cost-effective fuel stops from the fuel-price dataset | Minimum-cost refuelling optimizer over the 6,625 OPIS truck stops near the route; proven optimal against an exact dynamic-programming oracle |
| Support multiple stops with a 500-mile maximum range | Multi-stop plans verified (e.g. 6 stops Dallas→Chicago, 21 stops Seattle→Miami); any gap over range returns `422` |
| Calculate fuel expenditure at 10 MPG | Gallons always equal miles ÷ MPG exactly (fuel-conservation tested); `mpg` is overridable |
| Use a free maps/routing API | Nominatim + public OSRM demo server — no API keys anywhere |
| Use the latest stable Django release | Django 6.1.1 (verified latest stable) |
| Respond quickly, ideally one routing request | Exactly **1** OSRM call per unique (start, finish) pair (cached 24 h); ~3 s cold, milliseconds warm; station matching is fully local |

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.10+
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

## Demo

A ≤5-minute walkthrough video (Loom) demonstrates the API end-to-end —
`LOOM_SCRIPT.md` in this repo is the script it follows. The video link is
submitted alongside this repository.

## API reference

### `GET /api/route/?start=<place>&finish=<place>` (also accepts POST with a JSON body)

Optional overrides: `mpg` (default 10), `max_range_miles` (default 500).
Both must be positive numbers within sane bounds or the API returns 400.

Response (200) — real output for `start=Dallas,TX&finish=Chicago,IL`:

```json
{
  "start":  {"query": "Dallas,TX", "display_name": "Dallas, Dallas County, Texas, United States", "lat": 32.776, "lng": -96.797},
  "finish": {"query": "Chicago,IL", "display_name": "Chicago, South Chicago Township, Cook County, Illinois, United States", "lat": 41.876, "lng": -87.624},
  "route":   {"distance_miles": 966.7, "duration_minutes": 1026.4, "geometry": [[-96.797, 32.776], "..."]},
  "vehicle": {"mpg": 10, "max_range_miles": 500, "tank_gallons": 50.0},
  "fuel_stops": [
    {"station_id": "72773", "name": "RaceTrac #2626", "city": "Dallas", "state": "TX",
     "price_per_gallon_usd": 2.864, "route_mile": 2.86, "miles_off_route": 0.34,
     "gallons": 1.381, "cost_usd": 3.96},
    {"station_id": "3970", "name": "EXXON - Pilot #1293", "city": "Garland", "state": "TX",
     "price_per_gallon_usd": 2.842, "route_mile": 13.81, "miles_off_route": 5.23,
     "gallons": 2.83, "cost_usd": 8.04},
    {"station_id": "68213", "name": "CADOO MILLS", "city": "Caddo Mills", "state": "TX",
     "price_per_gallon_usd": 2.801, "route_mile": 42.11, "miles_off_route": 3.49,
     "gallons": 50.0, "cost_usd": 140.03},
    {"station_id": "68256", "name": "EXTRA MILE TRUCK STOP", "city": "Hooks", "state": "TX",
     "price_per_gallon_usd": 2.817, "route_mile": 163.1, "miles_off_route": 0.31,
     "gallons": 12.099, "cost_usd": 34.09},
    {"station_id": "72594", "name": "Quiktrip #7900", "city": "Texarkana", "state": "TX",
     "price_per_gallon_usd": 2.857, "route_mile": 175.04, "miles_off_route": 0.49,
     "gallons": 1.194, "cost_usd": 3.41},
    {"station_id": "69861", "name": "HUCKS FOOD & FUEL #379", "city": "Marion", "state": "IL",
     "price_per_gallon_usd": 2.929, "route_mile": 649.52, "miles_off_route": 0.96,
     "gallons": 29.165, "cost_usd": 85.42}
  ],
  "summary": {"num_stops": 6, "total_gallons": 96.669, "total_cost_usd": 274.95,
              "avg_price_per_gallon_usd": 2.844},
  "map_url": "http://127.0.0.1:8000/map/?start=Dallas,TX&finish=Chicago,IL",
  "notes": ["Fuel prices are retail USD/gallon from the provided OPIS truck-stop data.",
            "The vehicle starts with an empty tank; fuel burned before the first stop is billed at that stop's price.",
            "Stations are matched within 10 miles of the driving route."]
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
- Geocoding results are cached 24 h → 1 call per unique place name per cache
  lifetime (use a persistent cache like Redis in production for "ever").
- Routing results are cached 24 h → exactly 1 OSRM call per unique
  (start, finish) pair; repeat requests (including the map page) hit the cache.
- Station coordinates are resolved **offline at build time** (see below), so
  fuel-stop matching never touches the network.

**Pipeline** (`fuelrouter/services/`):
1. `geocode.py` — place name → (lat, lng), USA-only, cached.
2. `routing.py` — coordinates → distance/duration/geometry via OSRM, cached.
3. `stations.py` — loads the truck stops from the bundled
   `fuelrouter/data/stations.json`, indexes them on a lat/lng grid, and keeps
   those within 10 miles of the route, recording each stop's distance along
   the route (`route_mile`). Pure Python, ~0.5 s for a cross-country route.
4. `optimizer.py` — the classic minimum-cost refuelling greedy: at each stop,
   buy just enough to reach the next *cheaper* station within range, otherwise
   fill the tank (never buying more than needed to reach the destination, which
   is modelled as a $0 station). Optimal from the first stop onward; the first
   stop itself is the nearest station within range of the origin (see the
   optimizer docstring for the exact optimality claim).
5. `planner.py` — orchestrates the above and shapes the JSON response.

**Station coordinates** were built once with `scripts/build_stations.py`:
each stop's city was resolved via the US Census Bureau's 2024 place gazetteer
(public domain), with a cached Nominatim fallback for the few hundred cities
missing from it. Of the 6,738 unique stops in the CSV, **6,625 US stops** are
bundled (82 Canadian stops excluded — out of scope for USA trips; 31 US stops
could not be resolved to coordinates). Coordinates are **city centroids**
from the gazetteer, not exact truck-stop addresses, so `miles_off_route` is
approximate (typically within a few miles) — good enough for the 10-mile
capture radius, but not a precise detour measurement.

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
  tests/                 29 unit tests (optimizer, geometry, matching, API,
                         planner overrides, input validation, cache keys)
  views.py               DRF JSON API + map page
templates/fuelrouter/    map.html (Leaflet), map_error.html
scripts/build_stations.py  reproduces data/stations.json from the CSV
postman_collection.json   import into Postman for the demo
LOOM_SCRIPT.md            script for the ≤5-minute demo video
```

## Testing

```bash
python manage.py test fuelrouter   # 29 tests, all passing
```

Covers the optimizer (including fuel conservation and a fuel-never-vanishes
invariant), geometry helpers, station matching, the API views (200/400/422
paths, override forwarding), planner overrides, input validation, and cache-key
sanitization. The optimizer was additionally cross-checked against an exact
dynamic-programming oracle on 60 randomized cases.

## Deployment notes

- Set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0` env vars for anything beyond
  local demo use; put a real cache (Redis) behind `CACHES` for multi-process
  serving.
- The OSRM demo server is rate-limited and meant for light use — fine for this
  assessment; a production version would self-host OSRM or use a keyed
  provider. The single-call-per-route caching design carries over unchanged.
