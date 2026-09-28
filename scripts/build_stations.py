"""Build fuelrouter/data/stations.json from the OPIS fuel-price CSV.

Each truck stop gets a latitude/longitude so the API can match stations to a
route with zero external calls at request time:

1. Deduplicate the CSV by "OPIS Truckstop ID", keeping the cheapest
   "Retail Price" seen for each stop.
2. Resolve each stop's (City, State) to coordinates using the US Census
   Bureau's 2024 place gazetteer (public domain, downloaded once):
   https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip
3. For cities missing from the gazetteer (small unincorporated places, plus
   the few Canadian stops in the file), fall back to one Nominatim geocode
   per city, cached in --cache so re-runs are free.

Usage:
    python scripts/build_stations.py \\
        --csv path/to/fuel-prices-for-be-assessment.csv \\
        --gazetteer /tmp/gaz/2024_Gaz_place_national.txt \\
        --out fuelrouter/data/stations.json
"""

import argparse
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

SUFFIXES = {"CITY", "TOWN", "VILLAGE", "BOROUGH", "CDP", "MUNICIPALITY",
            "TOWNSHIP", "CHARTER TOWNSHIP"}


def norm(name):
    name = re.sub(r"[.']", "", name.upper().strip())
    toks = name.split()
    while toks and toks[-1] in SUFFIXES:
        toks.pop()
    return " ".join(toks)


def load_gazetteer(path):
    gaz = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        for row in reader:
            key = (norm(row["NAME"]), row["USPS"].strip().upper())
            gaz.setdefault(key, (float(row["INTPTLAT"]),
                                 float(row["INTPTLONG"])))
    return gaz


def nominatim_city(city, state):
    q = f"{city}, {state}, USA"
    url = ("https://nominatim.openstreetmap.org/search?"
           + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1,
                                     "countrycodes": "us,ca"}))
    req = urllib.request.Request(
        url, headers={"User-Agent": "SpotterFuelRouteAssessment/1.0 (data build)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--gazetteer", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default=".geocode_cache.json")
    args = ap.parse_args()

    gaz = load_gazetteer(args.gazetteer)
    print(f"gazetteer places: {len(gaz)}")

    stations = {}
    with open(args.csv, newline="") as f:
        for row in csv.DictReader(f):
            sid = row["OPIS Truckstop ID"].strip()
            price = float(row["Retail Price"])
            if sid in stations:
                if price < stations[sid]["price"]:
                    stations[sid]["price"] = price
                    stations[sid]["name"] = row["Truckstop Name"].strip()
            else:
                stations[sid] = {
                    "id": sid,
                    "name": row["Truckstop Name"].strip(),
                    "address": row["Address"].strip(),
                    "city": row["City"].strip(),
                    "state": row["State"].strip().upper(),
                    "price": price,
                }
    print(f"unique stations: {len(stations)}")

    try:
        cache = json.load(open(args.cache))
    except FileNotFoundError:
        cache = {}

    matched = unmatcheable = 0
    for s in stations.values():
        key = (norm(s["city"]), s["state"])
        if key in gaz:
            s["lat"], s["lng"] = gaz[key]
            matched += 1
            continue
        ckey = f"{s['city']}, {s['state']}"
        if ckey not in cache:
            try:
                cache[ckey] = nominatim_city(s["city"], s["state"])
            except Exception as exc:  # noqa: BLE001 - keep building
                print(f"geocode failed for {ckey}: {exc}")
                cache[ckey] = None
            json.dump(cache, open(args.cache, "w"))
            time.sleep(1.1)  # Nominatim usage policy: max 1 req/sec
        res = cache[ckey]
        if res:
            s["lat"], s["lng"] = res
            matched += 1
        else:
            unmatcheable += 1

    final = [s for s in stations.values() if "lat" in s]
    print(f"stations with coordinates: {len(final)} "
          f"(unresolvable: {unmatcheable})")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(final, open(out, "w"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
