# Loom demo script (≤ 5 minutes)

Record your screen with Postman + the running server + your code open.
Talk through this outline — it hits everything the assignment asks for.

## 0:00–0:30 — The ask (show the API index)
- Open `http://127.0.0.1:8000/` in the browser: "This is the API index —
  one endpoint plans the trip, one renders the map."

## 0:30–1:30 — Live demo in Postman
- Import `postman_collection.json`, run **"Plan a trip (GET) — Dallas, TX → Chicago, IL"**.
- Point at the response: `route.distance_miles`, then scroll to `fuel_stops` —
  "each stop shows the station name, price per gallon, how many gallons to buy
  there, and the cost."
- Point at `summary`: "6 stops, $274.95 total — that's 966.7 miles ÷ 10 MPG
  at the blended cheapest price."
- Run **"Plan a trip (POST, JSON body)"** (New York → Miami): "same endpoint
  accepts a JSON body too."
- Run **"Validation error"** once: "missing params give a clean 400."

## 1:30–2:30 — The map
- Open the `map_url` from the first response (or the "Open the interactive
  map" request).
- "The route polyline, green start / checkered finish, numbered fuel-stop
  markers with price and gallons in each popup, and a summary panel —
  Leaflet with free OpenStreetMap tiles, no API key."

## 2:30–4:00 — Code overview (have the repo open)
- `fuelrouter/services/` — "all framework-free, unit-tested":
  - `geocode.py` — free Nominatim geocoding, USA-only, cached.
  - `routing.py` — free OSRM routing; **exactly one call per unique route**,
    cached 24 h.
  - `stations.py` — the 6,625 US truck stops are geocoded **offline at build
    time** (`scripts/build_stations.py`), grid-indexed, matched within
    10 miles of the route in under a second — zero network at request time.
  - `optimizer.py` — classic min-cost refuelling greedy: at each stop buy
    just enough to reach the next cheaper station in range, else fill up.
- `views.py` — DRF `APIView` for JSON, Django `View` for the map page.

## 4:00–4:45 — Speed + tests
- Re-run the Dallas → Chicago request: "first call took ~2 s for geocoding +
  routing; this one is instant — everything's cached."
- Terminal: `python manage.py test fuelrouter` → "19 tests pass."

## 4:45–5:00 — Close
- "Repo's on GitHub at <link>; README covers setup, the algorithm, and the
  assumptions. Thanks!"

### Before you hit record
1. `source .venv/bin/activate && python manage.py runserver` (fresh terminal).
2. Clear Django's cache once so the first Postman call shows the real
   ~2 s timing: restart `runserver` (locmem cache lives in the process).
3. Have Postman, the browser, the repo, and a terminal tiled and ready.
